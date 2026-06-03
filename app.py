"""
app.py - OJT Checker System Entry Point
OJT Checker System

Initialises logging, applies CustomTkinter theme, and
launches the main application window.

Run with:
    python app.py
"""

import logging
import logging.handlers
import sys
from pathlib import Path

# ── Ensure project root on path ──────────────────────────────
ROOT = Path(__file__).parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import customtkinter as ctk

import config


# ─────────────────────────────────────────────
# Logging Setup
# ─────────────────────────────────────────────

def setup_logging() -> None:
    """
    Configure root logger with:
    - Rotating file handler (logs/app.log)
    - Coloured console handler (stdout)
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        fmt=config.LOG_FORMAT,
        datefmt=config.LOG_DATE_FORMAT,
    )

    # Rotating file handler
    file_handler = logging.handlers.RotatingFileHandler(
        filename=config.LOG_FILE,
        maxBytes=config.LOG_MAX_BYTES,
        backupCount=config.LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    try:
        import colorlog
        col_formatter = colorlog.ColoredFormatter(
            "%(log_color)s%(asctime)s | %(levelname)-8s%(reset)s | %(name)s | %(message)s",
            datefmt=config.LOG_DATE_FORMAT,
            log_colors={
                "DEBUG":    "cyan",
                "INFO":     "white",
                "WARNING":  "yellow",
                "ERROR":    "red",
                "CRITICAL": "bold_red",
            },
        )
        console_handler.setFormatter(col_formatter)
    except ImportError:
        console_handler.setFormatter(formatter)

    root_logger.addHandler(console_handler)

    # Silence overly verbose third-party loggers
    for noisy in ["PIL", "easyocr", "torch", "fitz", "urllib3"]:
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logging.info(f"{config.APP_NAME} v{config.APP_VERSION} — logging initialised.")


# ─────────────────────────────────────────────
# CustomTkinter Theme
# ─────────────────────────────────────────────

def configure_theme() -> None:
    ctk.set_appearance_mode(config.CTK_THEME)
    ctk.set_default_color_theme(config.CTK_COLOR_THEME)


# ─────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────

def main() -> None:
    setup_logging()
    configure_theme()

    logger = logging.getLogger(__name__)
    logger.info("Starting OJT Checker System…")

    from gui.main_window import MainWindow

    app = MainWindow()
    app.mainloop()

    logger.info("OJT Checker System exited.")


if __name__ == "__main__":
    main()
