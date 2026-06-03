"""
config.py - Central Configuration Module
OJT Checker System

All tunable parameters, thresholds, and constants live here.
Change values here without touching business logic.
"""

import os
from pathlib import Path

# ─────────────────────────────────────────────
# PATHS
# ─────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
CORRECTED_DIR = DATA_DIR / "corrected"
REPORTS_DIR = DATA_DIR / "reports"
LOGS_DIR = BASE_DIR / "logs"
LOG_FILE = LOGS_DIR / "app.log"

# Ensure directories exist at import time
for _dir in [UPLOADS_DIR, CORRECTED_DIR, REPORTS_DIR, LOGS_DIR]:
    _dir.mkdir(parents=True, exist_ok=True)

# ─────────────────────────────────────────────
# APPLICATION METADATA
# ─────────────────────────────────────────────
APP_NAME = "OJT Checker System"
APP_VERSION = "1.0.0"
APP_AUTHOR = "OJT System"
WINDOW_SIZE = "1280x800"
WINDOW_MIN_SIZE = (1100, 700)

# ─────────────────────────────────────────────
# COLOR THEME (CustomTkinter)
# ─────────────────────────────────────────────
CTK_THEME = "dark"          # "dark" | "light" | "system"
CTK_COLOR_THEME = "blue"    # "blue" | "green" | "dark-blue"

# Brand colors
COLOR_PRIMARY    = "#1F6AA5"
COLOR_SUCCESS    = "#2FA827"
COLOR_WARNING    = "#E6A817"
COLOR_DANGER     = "#C0392B"
COLOR_NEUTRAL    = "#5A6472"
COLOR_BG_DARK    = "#1A1A2E"
COLOR_BG_PANEL   = "#16213E"
COLOR_BG_CARD    = "#0F3460"
COLOR_TEXT_MAIN  = "#EAEAEA"
COLOR_TEXT_DIM   = "#8899AA"

# ─────────────────────────────────────────────
# PDF PROCESSING
# ─────────────────────────────────────────────
EXPECTED_PAGE_COUNT = 7         # OJT documents are 7 pages
OCR_PAGE_INDEX = 0              # Page 1 = index 0 for field extraction
STAMP_PAGES = list(range(1, 7)) # Pages 2-7 (indices 1-6) checked for stamps

# Batch sizes for large-scale processing
BATCH_SIZE = 50                 # PDFs per worker batch
MAX_WORKER_THREADS = 4          # Parallel processing threads
MEMORY_LIMIT_MB = 2048          # Pause processing if RAM > this

# ─────────────────────────────────────────────
# OCR SETTINGS
# ─────────────────────────────────────────────
OCR_LANGUAGES = ["en"]          # EasyOCR language list
OCR_GPU = False                 # Set True if CUDA GPU available
OCR_MIN_CONFIDENCE = 0.3        # Discard detections below this
OCR_DPI = 200                   # DPI for PDF→image rasterization
OCR_IMAGE_SCALE = 2.0           # Upscale factor before OCR

# ─────────────────────────────────────────────
# FUZZY MATCHING
# ─────────────────────────────────────────────
FUZZY_MATCH_THRESHOLD = 75      # Minimum score (0-100) to consider a match
FUZZY_HIGH_CONFIDENCE = 90      # Score above this = high confidence match
FUZZY_SCORER = "WRatio"         # RapidFuzz scorer: WRatio | ratio | partial_ratio

# ─────────────────────────────────────────────
# VALIDATION THRESHOLDS
# ─────────────────────────────────────────────
# Per-field minimum fuzzy score to call a field PASS
FIELD_PASS_THRESHOLD = {
    "student_name":   80,
    "course_name":    75,
    "enrollment_no":  95,   # Numbers must be very accurate
    "ojt_period":     80,
}

# ─────────────────────────────────────────────
# EXCEL COLUMN MAPPING
# (Column headers as they appear in the Excel file)
# ─────────────────────────────────────────────
EXCEL_COL_ENROLLMENT = "Enrollment Number"
EXCEL_COL_NAME       = "Student Name"
EXCEL_COL_COURSE     = "Course Name"
EXCEL_COL_OJT_PERIOD = "OJT Period"
EXCEL_COL_YEAR       = "Year"

# ─────────────────────────────────────────────
# OCR FIELD EXTRACTION KEYWORDS
# Keywords used to locate fields in raw OCR text
# ─────────────────────────────────────────────
FIELD_KEYWORDS = {
    "student_name":   ["name", "student name", "trainee name", "student"],
    "course_name":    ["course", "skill course", "diploma", "program"],
    "enrollment_no":  ["enrollment", "enrolment", "id", "student id", "roll"],
    "ojt_period":     ["period", "ojt period", "training period", "duration"],
    "department":     ["department", "dept", "job role", "designation"],
}

# ─────────────────────────────────────────────
# STAMP DETECTION SETTINGS
# ─────────────────────────────────────────────
# Regions (x0, y0, x1, y1) as FRACTIONS of page dimensions
# where stamps/signatures are expected (pages 2-7)
STAMP_REGIONS = [
    (0.60, 0.80, 1.00, 1.00),   # Bottom-right: supervisor signature
    (0.00, 0.80, 0.40, 1.00),   # Bottom-left: company stamp
]
STAMP_MIN_DARK_PIXEL_RATIO = 0.01  # 1% dark pixels = stamp present
STAMP_DARK_THRESHOLD = 80           # Pixel value below this = "dark"

# ─────────────────────────────────────────────
# PDF CORRECTION SETTINGS
# ─────────────────────────────────────────────
CORRECTION_FONT_SIZE = 10       # Points
CORRECTION_FONT_NAME = "helv"   # Helvetica (built-in PDF font)
CORRECTION_TEXT_COLOR = (0, 0, 0)       # Black RGB
CORRECTION_RECT_COLOR = (1, 1, 1)       # White fill for cover rectangle
CORRECTION_RECT_PADDING = 2     # Extra pixels around detected text bbox

# ─────────────────────────────────────────────
# REPORT SETTINGS
# ─────────────────────────────────────────────
REPORT_COLUMNS = [
    "PDF Name",
    "Enrollment Number",
    "Student Name",
    "Course Match",
    "Name Match",
    "OJT Period Match",
    "Stamp Status",
    "Corrections Made",
    "Final Status",
    "Error Notes",
]

REPORT_FILENAME_TEMPLATE = "ojt_validation_report_{timestamp}.xlsx"

# ─────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────
LOG_LEVEL = "DEBUG"
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
LOG_MAX_BYTES = 10 * 1024 * 1024   # 10 MB
LOG_BACKUP_COUNT = 5
