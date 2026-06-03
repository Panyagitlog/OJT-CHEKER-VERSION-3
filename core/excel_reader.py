"""
core/excel_reader.py - Excel Master Data Reader
OJT Checker System

Loads the Excel master list, validates columns, and provides
fast lookup structures for student records.
"""

import logging
import pandas as pd
from pathlib import Path
from typing import Optional

import config

logger = logging.getLogger(__name__)


class ExcelReader:
    """
    Reads and indexes the OJT master Excel file.

    After loading, exposes:
        - self.df             : raw DataFrame
        - self.records        : list of dicts (one per student)
        - self.enrollment_map : dict keyed by enrollment number
    """

    REQUIRED_COLUMNS = [
        config.EXCEL_COL_ENROLLMENT,
        config.EXCEL_COL_NAME,
        config.EXCEL_COL_COURSE,
        config.EXCEL_COL_OJT_PERIOD,
        config.EXCEL_COL_YEAR,
    ]

    def __init__(self):
        self.df: Optional[pd.DataFrame] = None
        self.records: list[dict] = []
        self.enrollment_map: dict[str, dict] = {}
        self._all_names: list[str] = []
        self._all_courses: list[str] = []
        self._all_enrollments: list[str] = []

    # ─────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────

    def load(self, filepath: str | Path) -> None:
        """
        Load Excel file and build lookup indices.
        Raises ValueError if required columns are missing.
        """
        filepath = Path(filepath)
        logger.info(f"Loading Excel master file: {filepath.name}")

        try:
            # Support both .xlsx and .xls
            self.df = pd.read_excel(filepath, dtype=str)
        except Exception as exc:
            logger.error(f"Failed to read Excel file: {exc}")
            raise RuntimeError(f"Cannot read Excel file: {exc}") from exc

        self._validate_columns()
        self._clean_dataframe()
        self._build_indices()

        logger.info(
            f"Excel loaded: {len(self.records)} student records across "
            f"{self.df[config.EXCEL_COL_COURSE].nunique()} courses"
        )

    def get_by_enrollment(self, enrollment_no: str) -> Optional[dict]:
        """Return student record by exact enrollment number, or None."""
        return self.enrollment_map.get(self._normalize(enrollment_no))

    @property
    def all_names(self) -> list[str]:
        return self._all_names

    @property
    def all_courses(self) -> list[str]:
        return self._all_courses

    @property
    def all_enrollments(self) -> list[str]:
        return self._all_enrollments

    @property
    def is_loaded(self) -> bool:
        return self.df is not None and len(self.records) > 0

    def summary(self) -> dict:
        if not self.is_loaded:
            return {"loaded": False}
        return {
            "loaded": True,
            "total_records": len(self.records),
            "unique_courses": self.df[config.EXCEL_COL_COURSE].nunique(),
            "unique_years": self.df[config.EXCEL_COL_YEAR].nunique(),
        }

    # ─────────────────────────────────────────
    # Private helpers
    # ─────────────────────────────────────────

    def _validate_columns(self) -> None:
        """Check that all required columns exist (case-insensitive)."""
        actual_cols = {c.strip().lower(): c for c in self.df.columns}
        missing = []
        rename_map = {}

        for required in self.REQUIRED_COLUMNS:
            key = required.strip().lower()
            if key in actual_cols:
                rename_map[actual_cols[key]] = required
            else:
                missing.append(required)

        if missing:
            raise ValueError(
                f"Excel file is missing required columns: {missing}\n"
                f"Found columns: {list(self.df.columns)}"
            )

        self.df.rename(columns=rename_map, inplace=True)

    def _clean_dataframe(self) -> None:
        """Strip whitespace, drop fully-empty rows, normalise strings."""
        self.df = self.df.dropna(how="all")
        for col in self.REQUIRED_COLUMNS:
            self.df[col] = self.df[col].fillna("").astype(str).str.strip()
        # Drop rows where enrollment number is empty
        self.df = self.df[self.df[config.EXCEL_COL_ENROLLMENT] != ""]
        self.df.reset_index(drop=True, inplace=True)

    def _build_indices(self) -> None:
        """Build fast-access lookup structures from the cleaned DataFrame."""
        self.records = self.df.to_dict(orient="records")

        self.enrollment_map = {
            self._normalize(r[config.EXCEL_COL_ENROLLMENT]): r
            for r in self.records
        }

        self._all_names = list(self.df[config.EXCEL_COL_NAME].unique())
        self._all_courses = list(self.df[config.EXCEL_COL_COURSE].unique())
        self._all_enrollments = list(self.df[config.EXCEL_COL_ENROLLMENT].unique())

    @staticmethod
    def _normalize(value: str) -> str:
        """Lowercase, strip whitespace for dict key normalisation."""
        return value.strip().lower()
