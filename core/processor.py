"""
core/processor.py - Main Processing Orchestrator
OJT Checker System

Coordinates the full pipeline:
  PDF → OCR → Validation → Correction → Report

Supports multithreaded batch processing for 10k+ PDFs via
concurrent.futures.ThreadPoolExecutor with memory monitoring.
"""

import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import psutil

import config
from core.excel_reader import ExcelReader
from core.ocr_engine import OCREngine
from core.pdf_corrector import PDFCorrector
from core.pdf_reader import PDFReader, PDFFolderScanner
from core.report_generator import ReportGenerator
from core.stamp_detector import StampDetector
from core.validator import ValidationReport, Validator

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Progress tracking
# ─────────────────────────────────────────────

@dataclass
class ProcessingProgress:
    total: int = 0
    completed: int = 0
    passed: int = 0
    failed: int = 0
    errors: int = 0
    current_file: str = ""
    is_running: bool = False
    is_done: bool = False
    cancelled: bool = False
    messages: list[str] = field(default_factory=list)
    report_path: Optional[Path] = None

    @property
    def percent(self) -> float:
        if self.total == 0:
            return 0.0
        return (self.completed / self.total) * 100.0

    def log(self, msg: str) -> None:
        self.messages.append(msg)
        logger.info(msg)


# ─────────────────────────────────────────────
# Main Processor
# ─────────────────────────────────────────────

class OJTProcessor:
    """
    Orchestrates the complete OJT document processing pipeline.

    Thread-safe: progress updates go through self.progress,
    which the GUI reads on its polling timer.
    """

    def __init__(
        self,
        excel_reader: ExcelReader,
        ocr_engine: OCREngine,
        output_dir: Path,
        on_progress: Optional[Callable] = None,
        on_log: Optional[Callable[[str], None]] = None,
    ):
        self.excel = excel_reader
        self.ocr = ocr_engine
        self.output_dir = Path(output_dir)
        self.on_progress = on_progress      # Callback: (progress_obj) → None
        self.on_log = on_log                # Callback: (msg: str) → None

        self.validator = Validator(excel_reader)
        self.corrector = PDFCorrector()
        self.stamp_detector = StampDetector()

        self.progress = ProcessingProgress()
        self._lock = threading.Lock()
        self._cancel_event = threading.Event()

        # Output sub-directories
        self.corrected_dir = self.output_dir / "corrected"
        self.ocr_text_dir  = self.output_dir / "ocr_texts"
        self.reports_dir   = self.output_dir / "reports"

        for d in [self.corrected_dir, self.ocr_text_dir, self.reports_dir]:
            d.mkdir(parents=True, exist_ok=True)

    # ─────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────

    def start(self, pdf_folder: Path) -> None:
        """
        Start processing all PDFs in pdf_folder.
        Runs in the calling thread — call from a background thread!
        """
        self._cancel_event.clear()
        self.progress = ProcessingProgress()
        self.progress.is_running = True
        # Log key output folders for traceability
        self._log(f"Output folders → corrected: {self.corrected_dir}, ocr_texts: {self.ocr_text_dir}, reports: {self.reports_dir}")
        try:
            # Discover PDFs
            scanner = PDFFolderScanner(pdf_folder)
            pdf_paths = scanner.scan()

            if not pdf_paths:
                self._log("No PDF files found in the selected folder.")
                return

            self.progress.total = len(pdf_paths)
            self._log(f"Found {len(pdf_paths)} PDFs. Starting processing…")

            report_gen = ReportGenerator()

            # Process in batches to limit memory usage
            for batch_start in range(0, len(pdf_paths), config.BATCH_SIZE):
                if self._cancel_event.is_set():
                    self._log("Processing cancelled by user.")
                    break

                batch = pdf_paths[batch_start : batch_start + config.BATCH_SIZE]
                self._log(
                    f"Batch {batch_start // config.BATCH_SIZE + 1}: "
                    f"processing {len(batch)} PDFs…"
                )

                self._process_batch(batch, report_gen)
                self._check_memory()

            # Save report
            if not self._cancel_event.is_set():
                self._log("Generating Excel report…")
                report_path = report_gen.save(self.reports_dir)
                self.progress.report_path = report_path
                self._log(f"Report Saved: {report_path}")

                stats = report_gen.stats
                self._log(
                    f"Done! Total: {stats['total']} | "
                    f"Pass: {stats['pass']} | "
                    f"Fail: {stats['fail']} | "
                    f"Errors: {stats['error']}"
                )

        except Exception as exc:
            logger.exception("Fatal error during processing")
            self._log(f"FATAL ERROR: {exc}")
        finally:
            self.progress.is_running = False
            self.progress.is_done = True
            self._notify_progress()

    def cancel(self) -> None:
        """Request cancellation of the running job."""
        self._cancel_event.set()
        self.progress.cancelled = True
        self._log("Cancellation requested…")

    # ─────────────────────────────────────────
    # Batch processing
    # ─────────────────────────────────────────

    def _process_batch(self, pdf_paths: list[Path], report_gen: ReportGenerator) -> None:
        """Process a batch of PDFs using a thread pool."""
        max_workers = min(config.MAX_WORKER_THREADS, len(pdf_paths))

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {
                executor.submit(self._process_single_pdf, p): p
                for p in pdf_paths
            }

            for future in as_completed(future_map):
                if self._cancel_event.is_set():
                    break

                pdf_path = future_map[future]
                try:
                    validation_report = future.result()
                    report_gen.add(validation_report)

                    with self._lock:
                        self.progress.completed += 1
                        if validation_report.final_status == "PASS":
                            self.progress.passed += 1
                        elif validation_report.final_status == "ERROR":
                            self.progress.errors += 1
                        else:
                            self.progress.failed += 1
                        self.progress.current_file = pdf_path.name

                    self._log(
                        f"[{self.progress.completed}/{self.progress.total}] "
                        f"{pdf_path.name} → {validation_report.final_status}"
                    )
                    self._notify_progress()

                except Exception as exc:
                    logger.error(f"Worker error for {pdf_path.name}: {exc}")
                    with self._lock:
                        self.progress.completed += 1
                        self.progress.errors += 1
                    self._log(f"ERROR processing {pdf_path.name}: {exc}")

    # ─────────────────────────────────────────
    # Enrollment extraction from filename
    # ─────────────────────────────────────────

    def _extract_enrollment_from_filename(self, pdf_path: Path) -> Optional[str]:
        """
        Extract enrollment number from PDF filename.
        Example: AMULYA_DMCFSJU17090 (1).pdf → DMCFSJU17090
        Pattern: DMCFSJU\\d+
        Returns None if not found.
        """
        try:
            match = re.search(r"DMCFSJU\d+", pdf_path.stem, re.IGNORECASE)
            if match:
                enrollment = match.group(0).upper()
                return enrollment
        except Exception as exc:
            logger.debug(f"Error extracting enrollment from filename {pdf_path.name}: {exc}")
        return None

    # ─────────────────────────────────────────
    # Single PDF pipeline
    # ─────────────────────────────────────────

    def _process_single_pdf(self, pdf_path: Path) -> ValidationReport:
        """
        Reordered pipeline for one PDF:
        1. Extract enrollment from filename
        2. Find Excel record by enrollment
        3. Open PDF & validate page count
        4. OCR page 1 → extract fields
        5. Validate fields against Excel
        6. Check stamps on pages 2-7
        7. Auto-correct failed fields
        8. Save corrected PDF
        9. Save OCR text file
        """
        report = ValidationReport(pdf_name=pdf_path.name)

        try:
            # ── Step 1: Extract enrollment from filename ─────────
            enrollment_from_filename = self._extract_enrollment_from_filename(pdf_path)
            if enrollment_from_filename:
                self._log(f"[ENROLLMENT] Filename: {enrollment_from_filename}")
            else:
                self._log(f"[ENROLLMENT] Filename: NOT FOUND in {pdf_path.name}")

            # ── Step 2: Find Excel record ────────────────────────
            excel_record = None
            if enrollment_from_filename:
                excel_record = self.excel.get_by_enrollment(enrollment_from_filename)
                if excel_record:
                    self._log(f"[EXCEL] Match: FOUND for enrollment {enrollment_from_filename}")
                    report.enrollment_no = enrollment_from_filename
                    report.student_record = excel_record
                else:
                    self._log(f"[EXCEL] Match: NOT FOUND for enrollment {enrollment_from_filename}")

            # ── Step 3: Open PDF & validate page count ──────────
            with PDFReader(pdf_path) as reader:
                self._log(f"[PDF] Loaded: {pdf_path.name}")

                page_ok, page_note = reader.validate_page_count()
                report.page_count_ok = page_ok
                report.page_count_note = page_note
                if not page_ok:
                    logger.warning(f"{pdf_path.name}: {page_note}")

                # ── Step 4: OCR page 1 ──────────────────────────
                page_image = reader.get_page_image(config.OCR_PAGE_INDEX)
                ocr_fields = self.ocr.extract_fields(page_image, filename_enrollment=enrollment_from_filename)

                self._log(f"[OCR] Extraction completed for {pdf_path.name}")
                ocr_enroll = ocr_fields.get("enrollment_no", "")
                self._log(f"[OCR] Enrollment extracted: {ocr_enroll if ocr_enroll else 'NOT FOUND'}")
                
                # Debug: Compare filename vs OCR enrollment
                if enrollment_from_filename and ocr_enroll and enrollment_from_filename != ocr_enroll:
                    self._log(f"[ENROLLMENT] Mismatch: Filename={enrollment_from_filename} vs OCR={ocr_enroll}")
                    self._log(f"[ENROLLMENT] USING FILENAME (Priority 1)")

                # Save OCR text file
                self._save_ocr_text(pdf_path.stem, ocr_fields)

                # ── Step 5: Validation (Excel-driven) ───────────
                self._log(f"[VALIDATION] Starting validation...")
                val_report = self.validator.validate(
                    pdf_path.name,
                    ocr_fields,
                    excel_enrollment=enrollment_from_filename,
                    excel_record=excel_record
                )
                report = val_report
                report.page_count_ok = page_ok
                report.page_count_note = page_note

                # Log detailed field validation results
                for field_name, field_result in val_report.field_results.items():
                    status_str = field_result.status
                    if field_result.correction_text and field_result.status == "FAIL":
                        self._log(f"[FIELD] {field_name}: {status_str} (score={field_result.score:.0f}) → Corrected to '{field_result.correction_text}'")
                    else:
                        self._log(f"[FIELD] {field_name}: {status_str} (score={field_result.score:.0f})")

                self._log(f"[VALIDATION] Completed: {pdf_path.name} → {val_report.final_status}")

                # ── Step 6: Stamp detection ──────────────────
                stamp_result = self.stamp_detector.check_all_pages(reader)
                report.stamp_status = stamp_result["status"]
                if stamp_result["failed_pages"]:
                    logger.debug(
                        f"{pdf_path.name}: Stamp FAIL on pages {stamp_result['failed_pages']}"
                    )
                else:
                    self._log(f"[STAMP] Detection: {stamp_result['status']}")

                # ── Step 7: PDF Correction (using Excel values) ──
                corrections = self.corrector.build_corrections_dict(val_report)
                if corrections:
                    self._log(f"[CORRECTION] {len(corrections)} fields need correction")
                    out_path = self.corrected_dir / pdf_path.name
                    success, n_applied, msg = self.corrector.correct_pdf(
                        source_path=pdf_path,
                        output_path=out_path,
                        corrections=corrections,
                        ocr_fields=ocr_fields,
                    )
                    report.corrections_made = n_applied
                    if success:
                        self._log(f"[CORRECTION] Corrected PDF saved: {out_path.name} ({n_applied} corrections applied)")
                    else:
                        logger.error(f"Correction failed for {pdf_path.name}: {msg}")
                        self._log(f"[CORRECTION] FAILED: {msg}")
                else:
                    # No corrections needed — still copy to output for completeness
                    import shutil
                    out_path = self.corrected_dir / pdf_path.name
                    try:
                        shutil.copy2(str(pdf_path), str(out_path))
                        self._log(f"[CORRECTION] No corrections needed - PDF copied to output")
                    except Exception as exc:
                        logger.debug(f"Failed to copy original PDF to corrected folder: {exc}")
                        self._log(f"[CORRECTION] Failed to save PDF for {pdf_path.name}: {exc}")

        except Exception as exc:
            logger.exception(f"Pipeline error for {pdf_path.name}")
            report.error = str(exc)
            self._log(f"[ERROR] Pipeline error: {exc}")

        return report

    # ─────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────

    def _save_ocr_text(self, stem: str, fields: dict) -> None:
        """Save extracted OCR fields to a .txt file."""
        try:
            txt_path = self.ocr_text_dir / f"{stem}_ocr.txt"
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(f"OCR Extraction: {stem}\n")
                f.write("=" * 40 + "\n")
                for key, val in fields.items():
                    f.write(f"{key:20s}: {val}\n")
            # Log successful OCR text save
            self._log(f"OCR text saved: {txt_path.name}")
        except Exception as exc:
            logger.debug(f"Could not save OCR text for {stem}: {exc}")
            self._log(f"Failed to save OCR text for {stem}: {exc}")

    def _check_memory(self) -> None:
        """Pause processing if RAM usage exceeds configured limit."""
        mem = psutil.virtual_memory()
        used_mb = mem.used / (1024 ** 2)
        if used_mb > config.MEMORY_LIMIT_MB:
            self._log(
                f"Memory usage high ({used_mb:.0f} MB). "
                f"Pausing 5 seconds to let GC run…"
            )
            time.sleep(5)

    def _log(self, msg: str) -> None:
        self.progress.log(msg)
        if self.on_log:
            self.on_log(msg)

    def _notify_progress(self) -> None:
        if self.on_progress:
            try:
                self.on_progress(self.progress)
            except Exception:
                pass
