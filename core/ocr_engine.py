"""
core/ocr_engine.py - OCR Engine (EasyOCR)
OJT Checker System

Wraps EasyOCR with lazy initialization, image preprocessing,
and structured field extraction from OJT document page 1.
"""

import logging
import re
from typing import Optional

import cv2
import numpy as np

import config

logger = logging.getLogger(__name__)

# Global singleton reader — initializing EasyOCR is expensive (~5 sec)
_ocr_reader = None


def get_ocr_reader():
    """Lazy-load EasyOCR reader (singleton per process)."""
    global _ocr_reader
    if _ocr_reader is None:
        logger.info("Initialising EasyOCR reader (first-time, may take ~5–10 seconds)…")
        try:
            import easyocr
            _ocr_reader = easyocr.Reader(
                config.OCR_LANGUAGES,
                gpu=config.OCR_GPU,
                verbose=False,
            )
            logger.info("EasyOCR reader ready.")
        except ImportError:
            logger.error("easyocr not installed. Run: pip install easyocr")
            raise
    return _ocr_reader


class OCRResult:
    """Structured container for a single OCR detection."""

    def __init__(self, bbox, text: str, confidence: float):
        self.bbox = bbox            # [[x0,y0],[x1,y0],[x1,y1],[x0,y1]]
        self.text = text.strip()
        self.confidence = confidence

    def __repr__(self):
        return f"OCRResult(conf={self.confidence:.2f}, text={self.text!r})"


class OCREngine:
    """
    High-level OCR interface for OJT document processing.

    Responsibilities:
    - Preprocess page images for better OCR accuracy
    - Run EasyOCR and filter low-confidence results
    - Extract structured fields (name, course, enrollment, period)
    """

    def __init__(self):
        self._reader = None   # loaded on first use

    def _ensure_reader(self):
        if self._reader is None:
            self._reader = get_ocr_reader()

    # ─────────────────────────────────────────
    # Image Preprocessing
    # ─────────────────────────────────────────

    def preprocess(self, image: np.ndarray) -> np.ndarray:
        """
        Apply image processing to improve OCR accuracy:
        - Convert to grayscale
        - Denoise
        - Adaptive threshold (binarise)
        - Slight sharpening
        """
        # Grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)

        # Denoise
        denoised = cv2.fastNlMeansDenoising(gray, h=15)

        # Adaptive threshold — handles uneven lighting on scanned docs
        binary = cv2.adaptiveThreshold(
            denoised, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            blockSize=15,
            C=8,
        )

        # Sharpen kernel
        kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
        sharpened = cv2.filter2D(binary, -1, kernel)

        # Convert back to 3-channel RGB for EasyOCR
        return cv2.cvtColor(sharpened, cv2.COLOR_GRAY2RGB)

    # ─────────────────────────────────────────
    # Core OCR
    # ─────────────────────────────────────────

    def read_image(
        self,
        image: np.ndarray,
        preprocess: bool = True,
        min_confidence: float = config.OCR_MIN_CONFIDENCE,
    ) -> list[OCRResult]:
        """
        Run EasyOCR on a numpy image.

        Returns list of OCRResult sorted by vertical position (top→bottom).
        """
        self._ensure_reader()

        if preprocess:
            processed = self.preprocess(image)
        else:
            processed = image

        try:
            raw = self._reader.readtext(processed, detail=1, paragraph=False)
        except Exception as exc:
            logger.error(f"OCR failed: {exc}")
            return []

        results = []
        for bbox, text, conf in raw:
            if conf >= min_confidence and text.strip():
                results.append(OCRResult(bbox, text, conf))

        # Sort top-to-bottom by the Y coordinate of the bounding box top-left
        results.sort(key=lambda r: r.bbox[0][1])
        return results

    def full_text(self, results: list[OCRResult]) -> str:
        """Join all OCR results into a single multi-line string."""
        return "\n".join(r.text for r in results)

    # ─────────────────────────────────────────
    # Field Extraction
    # ─────────────────────────────────────────

    def extract_fields(self, image: np.ndarray, filename_enrollment: str = None) -> dict[str, str]:
        """
        Extract structured OJT fields from a page-1 image.

        Strategy:
        1. Run OCR to get all text lines with positions
        2. Look for keyword-anchor lines
        3. The value usually follows the keyword on the same line
           or the next non-empty line
        4. Apply pattern cleanup (enrollment numbers, dates)

        Args:
            image: numpy array of page image
            filename_enrollment: Pre-extracted enrollment from filename (optional)

        Returns dict with keys matching config.FIELD_KEYWORDS keys.
        """
        results = self.read_image(image)
        lines = [r.text for r in results]
        full = self.full_text(results)

        fields = {
            "student_name":  self._extract_near_keyword(lines, config.FIELD_KEYWORDS["student_name"]),
            "course_name":   self._extract_near_keyword(lines, config.FIELD_KEYWORDS["course_name"]),
            "enrollment_no": self._extract_enrollment(lines, full, filename_enrollment=filename_enrollment),
            "ojt_period":    self._extract_period(lines, full),
            "department":    self._extract_near_keyword(lines, config.FIELD_KEYWORDS["department"]),
        }

        logger.debug(f"Extracted fields: {fields}")
        return fields

    # ─────────────────────────────────────────
    # Private extraction helpers
    # ─────────────────────────────────────────

    def _extract_near_keyword(self, lines: list[str], keywords: list[str]) -> str:
        """
        Search for a keyword in the line list.
        Return the text found after the colon on the same line,
        or the content of the next non-empty line.
        """
        kw_lower = [k.lower() for k in keywords]

        for i, line in enumerate(lines):
            line_lower = line.lower()
            if any(kw in line_lower for kw in kw_lower):
                # Try to get value after colon on same line
                if ":" in line:
                    parts = line.split(":", 1)
                    value = parts[1].strip()
                    if value and len(value) > 1:
                        return value

                # Try next non-empty line
                for j in range(i + 1, min(i + 4, len(lines))):
                    candidate = lines[j].strip()
                    if candidate and len(candidate) > 2:
                        # Reject if candidate is itself a keyword
                        if not any(kw in candidate.lower() for kw in kw_lower):
                            return candidate
        return ""

    def _extract_enrollment(self, lines: list[str], full_text: str, filename_enrollment: str = None) -> str:
        """
        Extract enrollment number from OCR.
        
        Validation:
        - Must match pattern DMCFSJU\\d+
        - Reject keywords: Name, Student, StudentName, Course, Skill, Year, 
          Period, Department, DepartmentandJob, JobRole
        
        Falls back to regex only if filename_enrollment not provided.
        """
        # Keywords to reject (common OCR errors)
        REJECTION_KEYWORDS = {
            "name", "student", "studentname", "course", "skill", 
            "year", "period", "department", "departmentandjob", "jobrole"
        }

        # Try keyword anchor first
        by_keyword = self._extract_near_keyword(
            lines, config.FIELD_KEYWORDS["enrollment_no"]
        )
        
        if by_keyword:
            # Check if it matches a rejection keyword
            if by_keyword.lower() in REJECTION_KEYWORDS:
                logger.debug(f"Rejected OCR enrollment '{by_keyword}' (matches keyword)")
            else:
                # Validate against DMCFSJU\\d+ pattern
                match = re.search(r"DMCFSJU\d+", by_keyword, re.IGNORECASE)
                if match:
                    return match.group(0).upper()

        # Regex fallback: DMCFSJU\\d+ pattern only
        match = re.search(r"DMCFSJU\d+", full_text, re.IGNORECASE)
        if match:
            return match.group(0).upper()

        # If filename_enrollment provided, it's already validated
        if filename_enrollment:
            return filename_enrollment

        return ""

    def _extract_period(self, lines: list[str], full_text: str) -> str:
        """
        Extract OJT period.
        Looks for date-range patterns like "Jan 2024 – Jun 2024".
        """
        by_keyword = self._extract_near_keyword(
            lines, config.FIELD_KEYWORDS["ojt_period"]
        )
        if by_keyword and len(by_keyword) > 4:
            return by_keyword

        # Regex: Month Year – Month Year or DD/MM/YYYY - DD/MM/YYYY
        date_patterns = [
            r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\.?\s+\d{4}"
            r"\s*[-–—to]+\s*"
            r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\.?\s+\d{4}\b",

            r"\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}\s*[-–—to]+\s*\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}",
        ]
        for pattern in date_patterns:
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                return match.group(0)

        return ""
