"""
core/stamp_detector.py - Stamp & Signature Detector
OJT Checker System

Analyses pages 2-7 of OJT PDFs to check whether required
stamps and signatures are present in predefined regions.

Detection approach:
- Render each page to image
- Crop the predefined stamp regions
- Check if dark pixel density exceeds threshold
  (stamps/signatures = dark ink on white paper)
"""

import logging
from typing import Optional

import cv2
import numpy as np

import config
from core.pdf_reader import PDFReader

logger = logging.getLogger(__name__)


class StampRegion:
    """Defines one region on a page where a stamp/signature is expected."""

    def __init__(self, x0_frac: float, y0_frac: float, x1_frac: float, y1_frac: float):
        """
        Fractions of page width/height (0.0 – 1.0).
        e.g. (0.6, 0.8, 1.0, 1.0) = bottom-right 40% x 20%
        """
        self.x0f = x0_frac
        self.y0f = y0_frac
        self.x1f = x1_frac
        self.y1f = y1_frac

    def crop(self, image: np.ndarray) -> np.ndarray:
        """Crop the region from a numpy image (H, W, C)."""
        h, w = image.shape[:2]
        x0 = int(self.x0f * w)
        y0 = int(self.y0f * h)
        x1 = int(self.x1f * w)
        y1 = int(self.y1f * h)
        return image[y0:y1, x0:x1]


class StampDetector:
    """
    Checks pages 2-7 for stamps and signatures.

    For each page, each defined region is checked for ink density.
    A page "passes" when at least one region contains a stamp.
    The overall result is PASS if all checked pages pass.
    """

    def __init__(self):
        self.regions = [
            StampRegion(*r) for r in config.STAMP_REGIONS
        ]
        self.stamp_pages = config.STAMP_PAGES          # [1,2,3,4,5,6] (0-indexed)
        self.dark_threshold = config.STAMP_DARK_THRESHOLD
        self.min_ratio = config.STAMP_MIN_DARK_PIXEL_RATIO

    # ─────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────

    def check_all_pages(self, pdf_reader: PDFReader) -> dict:
        """
        Check all stamp pages in a PDF.

        Returns dict:
        {
            "status": "PASS" | "FAIL" | "MISSING STAMP",
            "pages": {
                1: {"status": "PASS", "regions": [True, False]},
                ...
            },
            "failed_pages": [2, 5],
        }
        """
        results = {}
        failed_pages = []

        for page_idx in self.stamp_pages:
            if page_idx >= pdf_reader.page_count:
                # Page doesn't exist — count as missing
                results[page_idx + 1] = {
                    "status": "MISSING STAMP",
                    "regions": [],
                    "note": "Page does not exist",
                }
                failed_pages.append(page_idx + 1)
                continue

            try:
                image = pdf_reader.get_page_image(page_idx, dpi=150, scale=1.0)
                page_result = self._check_page(image)
                results[page_idx + 1] = page_result

                if page_result["status"] != "PASS":
                    failed_pages.append(page_idx + 1)

            except Exception as exc:
                logger.error(f"Stamp check failed on page {page_idx+1}: {exc}")
                results[page_idx + 1] = {
                    "status": "ERROR",
                    "regions": [],
                    "note": str(exc),
                }
                failed_pages.append(page_idx + 1)

        # Overall status
        if not failed_pages:
            overall = "PASS"
        elif len(failed_pages) == len(self.stamp_pages):
            overall = "MISSING STAMP"
        else:
            overall = "FAIL"

        return {
            "status": overall,
            "pages": results,
            "failed_pages": failed_pages,
        }

    # ─────────────────────────────────────────
    # Private helpers
    # ─────────────────────────────────────────

    def _check_page(self, image: np.ndarray) -> dict:
        """
        Check a single page image for stamps in all defined regions.
        The page passes if ANY region contains a detectable stamp.
        """
        region_results = []
        any_stamp = False

        for region in self.regions:
            crop = region.crop(image)
            has_stamp = self._has_ink(crop)
            region_results.append(has_stamp)
            if has_stamp:
                any_stamp = True

        status = "PASS" if any_stamp else "MISSING STAMP"
        return {"status": status, "regions": region_results}

    def _has_ink(self, crop: np.ndarray) -> bool:
        """
        Returns True if the cropped region has enough dark pixels
        to suggest a stamp or signature is present.
        """
        if crop.size == 0:
            return False

        # Convert to grayscale
        if len(crop.shape) == 3:
            gray = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY)
        else:
            gray = crop

        # Count dark pixels (ink = dark on white background)
        dark_pixels = np.sum(gray < self.dark_threshold)
        total_pixels = gray.size
        ratio = dark_pixels / total_pixels

        logger.debug(f"Ink ratio: {ratio:.4f} (threshold: {self.min_ratio})")
        return ratio >= self.min_ratio

    def quick_check(self, image: np.ndarray) -> bool:
        """Single-image stamp check (for quick preview)."""
        result = self._check_page(image)
        return result["status"] == "PASS"
