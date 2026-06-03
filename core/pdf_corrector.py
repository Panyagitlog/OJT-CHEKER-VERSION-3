"""
core/pdf_corrector.py - PDF Auto-Corrector
OJT Checker System

Modifies PDFs to cover incorrect handwritten text with a white
rectangle and write the corrected system-generated text in its place.
Uses PyMuPDF (fitz) for in-place annotation-based corrections.
"""

import logging
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF

import config

logger = logging.getLogger(__name__)


class TextRegion:
    """Represents a region of text to be corrected on a PDF page."""

    def __init__(self, rect: fitz.Rect, original_text: str, corrected_text: str):
        self.rect = rect
        self.original_text = original_text
        self.corrected_text = corrected_text


class PDFCorrector:
    """
    Applies text corrections to a PDF document.

    Workflow:
    1. Receive PDF path + list of corrections (field → value)
    2. Locate the text on page 1 using PyMuPDF text search
    3. Draw white rectangle over found text
    4. Write corrected text in black using Helvetica
    5. Save corrected PDF to output path

    If text cannot be located (e.g. handwritten/image-only), place the
    correction in a predefined fallback region for that field.
    """

    # Predefined fallback regions on page 1 for each field
    # (x0, y0, x1, y1) in PDF points — assumes A4 ~595x842 pt
    FIELD_FALLBACK_REGIONS = {
        "student_name":  fitz.Rect(100, 180, 450, 210),
        "course_name":   fitz.Rect(100, 230, 500, 260),
        "enrollment_no": fitz.Rect(100, 280, 400, 310),
        "ojt_period":    fitz.Rect(100, 330, 450, 360),
        "department":    fitz.Rect(100, 380, 450, 410),
    }

    def __init__(self):
        self.font_size = config.CORRECTION_FONT_SIZE
        self.font_name = config.CORRECTION_FONT_NAME
        self.text_color = config.CORRECTION_TEXT_COLOR
        self.rect_color = config.CORRECTION_RECT_COLOR
        self.padding = config.CORRECTION_RECT_PADDING

    # ─────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────

    def correct_pdf(
        self,
        source_path: Path,
        output_path: Path,
        corrections: dict[str, str],
        ocr_fields: Optional[dict] = None,
    ) -> tuple[bool, int, str]:
        """
        Apply corrections to a PDF and save the result.

        Args:
            source_path:  Path to original PDF
            output_path:  Path where corrected PDF will be saved
            corrections:  Dict of {field_name: corrected_text}
                          Only fields that FAILed validation should be here
            ocr_fields:   Optional OCR results to help locate text on page

        Returns:
            (success: bool, corrections_applied: int, message: str)
        """
        try:
            doc = fitz.open(str(source_path))
        except Exception as exc:
            return False, 0, f"Cannot open PDF: {exc}"

        corrections_applied = 0
        page = doc[config.OCR_PAGE_INDEX]  # Corrections on page 1

        for field_name, corrected_text in corrections.items():
            if not corrected_text:
                continue

            # Try to find and replace existing text
            applied = self._apply_correction(
                page=page,
                field_name=field_name,
                ocr_value=ocr_fields.get(field_name, "") if ocr_fields else "",
                corrected_text=corrected_text,
            )
            if applied:
                corrections_applied += 1

        # Save to output path
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            doc.save(str(output_path), garbage=4, deflate=True)
            doc.close()
            logger.info(
                f"[PDF_CORRECTOR] Corrected PDF saved: {output_path.name} "
                f"({corrections_applied} corrections applied)"
            )
            return True, corrections_applied, "OK"
        except Exception as exc:
            doc.close()
            logger.error(f"[PDF_CORRECTOR] Failed to save corrected PDF: {exc}")
            return False, corrections_applied, f"Save failed: {exc}"

    # ─────────────────────────────────────────
    # Private helpers
    # ─────────────────────────────────────────

    def _apply_correction(
        self,
        page: fitz.Page,
        field_name: str,
        ocr_value: str,
        corrected_text: str,
    ) -> bool:
        """
        Apply a single field correction to a page.

        1. Try to find the OCR text on the page via text search
        2. If found, cover with white rect and write corrected text
        3. If not found (scanned/handwritten), use fallback region

        Returns True if correction was applied.
        """
        target_rect = None

        # Try to locate the erroneous text using PyMuPDF search
        if ocr_value and len(ocr_value) > 3:
            found_rects = page.search_for(ocr_value, quads=False)
            if found_rects:
                # Use the first matching rect
                target_rect = found_rects[0]
                # Expand slightly to ensure full coverage
                target_rect = target_rect + fitz.Rect(
                    -self.padding, -self.padding,
                    self.padding, self.padding
                )
                logger.debug(f"Text '{ocr_value}' found on page at {target_rect}")

        # Fall back to predefined region if text not locatable
        if target_rect is None:
            target_rect = self.FIELD_FALLBACK_REGIONS.get(field_name)
            if target_rect is None:
                logger.warning(f"No region for field '{field_name}', skipping correction")
                return False
            logger.debug(f"Using fallback region for '{field_name}'")

        # 1. Draw white filled rectangle to cover existing text
        self._draw_white_cover(page, target_rect)

        # 2. Write corrected text in black
        self._write_corrected_text(page, target_rect, corrected_text)

        return True

    def _draw_white_cover(self, page: fitz.Page, rect: fitz.Rect) -> None:
        """Draw a filled white rectangle over the specified region."""
        shape = page.new_shape()
        shape.draw_rect(rect)
        shape.finish(
            fill=self.rect_color,       # White fill
            color=self.rect_color,      # White border (invisible)
            width=0,
        )
        shape.commit()

    def _write_corrected_text(
        self, page: fitz.Page, rect: fitz.Rect, text: str
    ) -> None:
        """
        Insert corrected text into the specified rectangle.
        Text is left-aligned, vertically centred within the rect.
        """
        # Calculate text insertion point (bottom-left of text baseline)
        # PyMuPDF text origin is bottom-left of first character
        x = rect.x0 + 2
        y = rect.y0 + self.font_size + (rect.height - self.font_size) / 2

        page.insert_text(
            point=fitz.Point(x, y),
            text=text,
            fontname=self.font_name,
            fontsize=self.font_size,
            color=self.text_color,
        )

    # ─────────────────────────────────────────
    # Batch helper
    # ─────────────────────────────────────────

    def build_corrections_dict(self, validation_report) -> dict[str, str]:
        """
        Build corrections dict from a ValidationReport.
        Only includes FAIL/MISSING fields that have a correction value.
        """
        corrections = {}
        for field_name, field_result in validation_report.field_results.items():
            if field_result.needs_correction and field_result.correction_text:
                corrections[field_name] = field_result.correction_text
                logger.debug(f"[CORRECTOR] Will correct {field_name}: '{field_result.ocr_value}' → '{field_result.correction_text}'")
        return corrections
