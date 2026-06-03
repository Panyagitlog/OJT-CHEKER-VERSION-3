"""
core/pdf_reader.py - PDF Reader & Page Validator
OJT Checker System

Opens PDFs with PyMuPDF (fitz), checks page count,
and provides page images for OCR and stamp detection.
"""

import logging
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF
import numpy as np

import config

logger = logging.getLogger(__name__)


class PDFReader:
    """
    Lightweight wrapper around a single PDF document.

    Usage:
        reader = PDFReader(path)
        ok, reason = reader.validate_page_count()
        img = reader.get_page_image(0)
        reader.close()
    """

    def __init__(self, filepath: str | Path):
        self.filepath = Path(filepath)
        self._doc: Optional[fitz.Document] = None
        self._open()

    # ─────────────────────────────────────────
    # Lifecycle
    # ─────────────────────────────────────────

    def _open(self) -> None:
        try:
            self._doc = fitz.open(str(self.filepath))
            logger.debug(f"Opened PDF: {self.filepath.name} ({self.page_count} pages)")
        except Exception as exc:
            logger.error(f"Cannot open PDF {self.filepath.name}: {exc}")
            raise RuntimeError(f"Cannot open PDF: {exc}") from exc

    def close(self) -> None:
        if self._doc:
            self._doc.close()
            self._doc = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    # ─────────────────────────────────────────
    # Properties
    # ─────────────────────────────────────────

    @property
    def page_count(self) -> int:
        return len(self._doc) if self._doc else 0

    @property
    def name(self) -> str:
        return self.filepath.name

    # ─────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────

    def validate_page_count(self, expected: int = config.EXPECTED_PAGE_COUNT) -> tuple[bool, str]:
        """
        Returns (True, "OK") if page count matches expected,
        otherwise (False, reason_string).
        """
        if self.page_count == expected:
            return True, "OK"
        elif self.page_count < expected:
            return False, f"Too few pages: {self.page_count} (expected {expected})"
        else:
            return False, f"Extra pages: {self.page_count} (expected {expected})"

    def get_page_image(
        self,
        page_index: int,
        dpi: int = config.OCR_DPI,
        scale: float = config.OCR_IMAGE_SCALE,
    ) -> np.ndarray:
        """
        Render a PDF page to a numpy uint8 RGB array for OCR/image processing.

        Args:
            page_index: 0-based page index
            dpi:        Render resolution
            scale:      Additional upscale multiplier

        Returns:
            numpy array (H, W, 3) dtype uint8
        """
        if not self._doc:
            raise RuntimeError("PDF document is not open")
        if page_index >= self.page_count:
            raise IndexError(f"Page {page_index} out of range ({self.page_count} pages)")

        page = self._doc[page_index]
        zoom = (dpi / 72.0) * scale
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB, alpha=False)

        # Convert to numpy array without extra copy if possible
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
        return img.copy()  # Return writable copy

    def get_page_text(self, page_index: int) -> str:
        """
        Extract embedded text from a PDF page (fast, no OCR).
        Returns empty string if page has no selectable text.
        """
        if not self._doc:
            return ""
        try:
            page = self._doc[page_index]
            return page.get_text("text").strip()
        except Exception:
            return ""

    def get_page(self, page_index: int) -> fitz.Page:
        """Return the raw fitz Page object for direct manipulation."""
        if not self._doc:
            raise RuntimeError("PDF not open")
        return self._doc[page_index]

    def get_document(self) -> fitz.Document:
        """Return the underlying fitz Document for direct manipulation."""
        if not self._doc:
            raise RuntimeError("PDF not open")
        return self._doc

    def page_dimensions(self, page_index: int) -> tuple[float, float]:
        """Return (width, height) of page in PDF points."""
        page = self._doc[page_index]
        rect = page.rect
        return rect.width, rect.height


class PDFFolderScanner:
    """
    Scans a directory tree for all PDF files.
    Provides an iterator suitable for large folders (10k+ files).
    """

    def __init__(self, folder: str | Path):
        self.folder = Path(folder)

    def scan(self) -> list[Path]:
        """Return sorted list of all PDF paths found recursively."""
        if not self.folder.exists():
            raise FileNotFoundError(f"Folder not found: {self.folder}")
        pdfs = sorted(self.folder.rglob("*.pdf"))
        logger.info(f"Found {len(pdfs)} PDF files in {self.folder}")
        return pdfs

    def count(self) -> int:
        return sum(1 for _ in self.folder.rglob("*.pdf"))
