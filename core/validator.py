"""
core/validator.py - Field Validator with Fuzzy Matching
OJT Checker System

Compares OCR-extracted fields against Excel master data using
RapidFuzz for intelligent fuzzy matching that tolerates OCR errors
and handwriting variations.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

from rapidfuzz import fuzz, process

import config

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────

@dataclass
class FieldResult:
    """Validation result for a single field."""
    field_name: str
    ocr_value: str
    excel_value: str
    matched_value: str          # Best match from Excel master data
    score: float                # Fuzzy match score 0-100
    status: str                 # "PASS" | "FAIL" | "MISSING"
    corrected: bool = False     # True if auto-correction was applied
    correction_text: str = ""   # The corrected value written to PDF

    @property
    def needs_correction(self) -> bool:
        return self.status == "FAIL" and self.matched_value

    @property
    def is_pass(self) -> bool:
        return self.status == "PASS"


@dataclass
class ValidationReport:
    """Complete validation result for one PDF."""
    pdf_name: str
    enrollment_no: str = ""
    student_record: Optional[dict] = None
    field_results: dict[str, FieldResult] = field(default_factory=dict)
    stamp_status: str = "UNCHECKED"    # "PASS" | "FAIL" | "MISSING STAMP"
    page_count_ok: bool = True
    page_count_note: str = ""
    error: str = ""
    corrections_made: int = 0

    @property
    def final_status(self) -> str:
        if self.error:
            return "ERROR"
        all_pass = all(r.is_pass for r in self.field_results.values())
        stamp_ok = self.stamp_status in ("PASS", "UNCHECKED")
        if all_pass and stamp_ok and self.page_count_ok:
            return "PASS"
        return "FAIL"

    @property
    def failed_fields(self) -> list[str]:
        return [k for k, v in self.field_results.items() if not v.is_pass]


# ─────────────────────────────────────────────
# Validator
# ─────────────────────────────────────────────

class Validator:
    """
    Validates OCR-extracted fields against Excel master data.

    Uses RapidFuzz for:
    - Finding the best matching student record
    - Fuzzy-comparing individual fields
    - Deciding PASS / FAIL per field and overall
    """

    def __init__(self, excel_reader):
        """
        Args:
            excel_reader: Loaded ExcelReader instance
        """
        self.excel = excel_reader

    # ─────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────

    def validate(
        self,
        pdf_name: str,
        ocr_fields: dict[str, str],
        excel_enrollment: str = None,
        excel_record: dict = None,
    ) -> ValidationReport:
        """
        Full validation pipeline for one PDF.

        New flow (processor finds enrollment + record first):
        1. Use pre-found enrollment & Excel record (if provided)
        2. Validate each field against Excel values
        3. Apply fuzzy matching rules:
           - >= 80 similarity: PASS
           - < 80 similarity: FAIL
           - < 50 similarity: AUTO CORRECT using Excel
        4. Return ValidationReport

        Args:
            pdf_name:          PDF filename (for report)
            ocr_fields:        Dict from OCREngine.extract_fields()
            excel_enrollment:  Pre-extracted enrollment from filename
            excel_record:      Pre-found Excel record
        """
        report = ValidationReport(pdf_name=pdf_name)

        if not self.excel.is_loaded:
            report.error = "Excel master data not loaded"
            return report

        # Use pre-found enrollment and record if provided
        if excel_enrollment:
            report.enrollment_no = excel_enrollment

        if excel_record:
            report.student_record = excel_record
        else:
            # Fallback to old method if no pre-found record
            student_record = self._find_student_record(ocr_fields)
            report.student_record = student_record
            if not excel_enrollment:
                report.enrollment_no = ocr_fields.get("enrollment_no", "")

            if not student_record:
                report.error = "No matching student record found in Excel"
                self._validate_fields_without_record(report, ocr_fields)
                return report
            excel_record = student_record

        # Validate each key field against Excel values
        report.field_results["student_name"] = self._validate_field(
            field_name="student_name",
            ocr_value=ocr_fields.get("student_name", ""),
            excel_value=excel_record.get(config.EXCEL_COL_NAME, ""),
            choices=self.excel.all_names,
            threshold=config.FIELD_PASS_THRESHOLD["student_name"],
        )

        report.field_results["course_name"] = self._validate_field(
            field_name="course_name",
            ocr_value=ocr_fields.get("course_name", ""),
            excel_value=excel_record.get(config.EXCEL_COL_COURSE, ""),
            choices=self.excel.all_courses,
            threshold=config.FIELD_PASS_THRESHOLD["course_name"],
        )

        report.field_results["ojt_period"] = self._validate_field(
            field_name="ojt_period",
            ocr_value=ocr_fields.get("ojt_period", ""),
            excel_value=excel_record.get(config.EXCEL_COL_OJT_PERIOD, ""),
            choices=None,
            threshold=config.FIELD_PASS_THRESHOLD["ojt_period"],
        )

        report.field_results["enrollment_no"] = self._validate_field(
            field_name="enrollment_no",
            ocr_value=ocr_fields.get("enrollment_no", ""),
            excel_value=excel_record.get(config.EXCEL_COL_ENROLLMENT, ""),
            choices=self.excel.all_enrollments,
            threshold=config.FIELD_PASS_THRESHOLD["enrollment_no"],
        )

        # Count corrections needed
        report.corrections_made = sum(
            1 for r in report.field_results.values() if r.needs_correction
        )

        logger.debug(
            f"{pdf_name}: {report.final_status} "
            f"(failed: {report.failed_fields})"
        )
        return report

    # ─────────────────────────────────────────
    # Student record matching
    # ─────────────────────────────────────────

    def _find_student_record(self, ocr_fields: dict) -> Optional[dict]:
        """
        Identify which Excel student this PDF belongs to.

        Strategy:
        1. Try exact enrollment number lookup (fastest)
        2. Try fuzzy enrollment number match
        3. Try fuzzy name match
        4. Return best match or None
        """
        enrollment = ocr_fields.get("enrollment_no", "").strip()
        name = ocr_fields.get("student_name", "").strip()

        # Exact enrollment lookup
        if enrollment:
            record = self.excel.get_by_enrollment(enrollment)
            if record:
                logger.debug(f"Exact enrollment match: {enrollment}")
                return record

        # Fuzzy enrollment match
        if enrollment and self.excel.all_enrollments:
            best = self._best_match(enrollment, self.excel.all_enrollments, threshold=90)
            if best:
                matched_enroll, score = best
                record = self.excel.get_by_enrollment(matched_enroll)
                if record:
                    logger.debug(f"Fuzzy enrollment match '{enrollment}' → '{matched_enroll}' (score={score})")
                    return record

        # Fuzzy name match
        if name and self.excel.all_names:
            best = self._best_match(name, self.excel.all_names, threshold=80)
            if best:
                matched_name, score = best
                # Find first record with this name
                for rec in self.excel.records:
                    if rec[config.EXCEL_COL_NAME].strip().lower() == matched_name.lower():
                        logger.debug(f"Fuzzy name match '{name}' → '{matched_name}' (score={score})")
                        return rec

        logger.warning(f"No student record found for enrollment='{enrollment}', name='{name}'")
        return None

    # ─────────────────────────────────────────
    # Field validation
    # ─────────────────────────────────────────

    def _validate_field(
        self,
        field_name: str,
        ocr_value: str,
        excel_value: str,
        choices: Optional[list[str]],
        threshold: int,
    ) -> FieldResult:
        """
        Validate a single field.

        Fuzzy matching rules:
        - >= 80 similarity: PASS
        - 50-79 similarity: FAIL (needs manual review)
        - < 50 similarity: FAIL + AUTO CORRECT using Excel value

        If choices list provided → find best match from choices (for
        course names, names etc.) then compare to excel_value.
        Otherwise → directly compare ocr_value to excel_value.
        """
        if not ocr_value:
            return FieldResult(
                field_name=field_name,
                ocr_value="",
                excel_value=excel_value,
                matched_value=excel_value,
                score=0.0,
                status="MISSING",
                correction_text=excel_value,
            )

        # Find best match from all valid choices
        if choices:
            best = self._best_match(ocr_value, choices, threshold=0)
            if best:
                matched_value, score = best
            else:
                matched_value, score = excel_value, 0.0
        else:
            # Direct comparison
            matched_value = excel_value
            score = fuzz.WRatio(ocr_value, excel_value)

        # Compare matched_value against the expected excel_value
        if matched_value and excel_value:
            final_score = fuzz.WRatio(matched_value, excel_value)
        else:
            final_score = score

        # Apply fuzzy matching rules
        if final_score >= 80:
            status = "PASS"
            correction_text = ""
        elif final_score < 50:
            status = "FAIL"
            correction_text = excel_value  # Auto-correct
        else:
            status = "FAIL"
            correction_text = excel_value  # Also set correction for manual fields

        return FieldResult(
            field_name=field_name,
            ocr_value=ocr_value,
            excel_value=excel_value,
            matched_value=matched_value,
            score=final_score,
            status=status,
            correction_text=correction_text,
        )

    def _validate_fields_without_record(
        self, report: ValidationReport, ocr_fields: dict
    ) -> None:
        """Populate field results when no matching record was found."""
        for fname in ["student_name", "course_name", "enrollment_no", "ojt_period"]:
            report.field_results[fname] = FieldResult(
                field_name=fname,
                ocr_value=ocr_fields.get(fname, ""),
                excel_value="",
                matched_value="",
                score=0.0,
                status="FAIL",
            )

    # ─────────────────────────────────────────
    # Fuzzy matching helpers
    # ─────────────────────────────────────────

    @staticmethod
    def _best_match(
        query: str,
        choices: list[str],
        threshold: int = config.FUZZY_MATCH_THRESHOLD,
    ) -> Optional[tuple[str, float]]:
        """
        Return (best_match_string, score) or None if below threshold.
        Uses RapidFuzz process.extractOne for speed.
        """
        if not choices or not query:
            return None

        result = process.extractOne(
            query,
            choices,
            scorer=fuzz.WRatio,
            score_cutoff=threshold,
        )
        if result:
            match_str, score, _ = result
            return match_str, score
        return None
