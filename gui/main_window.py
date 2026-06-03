"""
gui/main_window.py - Main Application Window
OJT Checker System

Orchestrates the GUI: file selectors, log console, dashboard,
and coordinates with the processing engine backend.
"""

import logging
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

import config
from core.excel_reader import ExcelReader
from core.ocr_engine import OCREngine
from core.processor import OJTProcessor
from gui.dashboard import Dashboard
from gui.progress_dialog import ProgressDialog

logger = logging.getLogger(__name__)


class MainWindow(ctk.CTk):
    """
    Root application window.

    Layout:
    ┌─────────────────────────────────────┬──────────────┐
    │  Header                             │              │
    ├─────────────────────────────────────│  Dashboard   │
    │  Control Panel (file selectors,     │  Sidebar     │
    │  action buttons)                    │              │
    ├─────────────────────────────────────│              │
    │  Log Console                        │              │
    └─────────────────────────────────────┴──────────────┘
    """

    def __init__(self):
        super().__init__()

        self.title(f"{config.APP_NAME} v{config.APP_VERSION}")
        self.geometry(config.WINDOW_SIZE)
        self.minsize(*config.WINDOW_MIN_SIZE)
        self.configure(fg_color=config.COLOR_BG_DARK)

        # State
        self._excel_path: Path | None = None
        self._pdf_folder: Path | None = None
        self._output_dir: Path | None = None
        self._processor: OJTProcessor | None = None
        self._progress_dialog: ProgressDialog | None = None
        self._excel_reader = ExcelReader()
        self._ocr_engine: OCREngine | None = None   # Lazy-loaded

        self._build_ui()
        self._setup_logging_handler()
        self._log_system("OJT Checker System ready. Please load Excel master file.")

    # ─────────────────────────────────────────
    # UI Construction
    # ─────────────────────────────────────────

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=0)
        self.rowconfigure(0, weight=0)   # Header
        self.rowconfigure(1, weight=0)   # Controls
        self.rowconfigure(2, weight=1)   # Log

        # ── Header ────────────────────────────
        self._build_header()

        # ── Control Panel (left) ──────────────
        control_frame = ctk.CTkFrame(
            self, fg_color=config.COLOR_BG_PANEL, corner_radius=0
        )
        control_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 0))
        self._build_controls(control_frame)

        # ── Log Console (left, row 2) ─────────
        log_frame = ctk.CTkFrame(
            self, fg_color="#0D1117", corner_radius=0
        )
        log_frame.grid(row=2, column=0, sticky="nsew", padx=(0, 0))
        self._build_log_console(log_frame)

        # ── Dashboard Sidebar (right, spans rows 1-2) ──
        self._dashboard = Dashboard(self, width=220)
        self._dashboard.grid(
            row=1, column=1, rowspan=2, sticky="nsew",
            padx=(1, 0)
        )
        self.columnconfigure(1, minsize=220)

    def _build_header(self) -> None:
        header = ctk.CTkFrame(
            self, fg_color=config.COLOR_BG_CARD,
            corner_radius=0, height=64
        )
        header.grid(row=0, column=0, columnspan=2, sticky="nsew")
        header.grid_propagate(False)

        # Logo / title
        ctk.CTkLabel(
            header,
            text="⬡ OJT CHECKER SYSTEM",
            font=ctk.CTkFont(family="Courier", size=20, weight="bold"),
            text_color="#4FC3F7",
        ).pack(side="left", padx=24, pady=18)

        # Version badge
        ctk.CTkLabel(
            header,
            text=f"v{config.APP_VERSION}",
            font=ctk.CTkFont(size=10),
            text_color="#5A7A9A",
        ).pack(side="left")

        # Right: Excel status
        self._excel_status_var = tk.StringVar(value="No Excel loaded")
        ctk.CTkLabel(
            header,
            textvariable=self._excel_status_var,
            font=ctk.CTkFont(size=10),
            text_color="#FFA726",
        ).pack(side="right", padx=24)

    def _build_controls(self, parent) -> None:
        pad = {"padx": 20, "pady": 6}

        # ── File selector rows ─────────────────
        selectors = [
            ("📋  Excel Master File",  "Excel (*.xlsx *.xls)",
             "excel_entry", "_select_excel"),
            ("📁  PDF Input Folder",   "Select PDF folder",
             "pdf_entry",   "_select_pdf_folder"),
            ("💾  Output Folder",      "Select output folder",
             "output_entry","_select_output"),
        ]

        for row_idx, (label, hint, entry_attr, cmd) in enumerate(selectors):
            row = ctk.CTkFrame(parent, fg_color="transparent")
            row.pack(fill="x", **pad)

            ctk.CTkLabel(
                row, text=label,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color="#90CAF9",
                width=200, anchor="w",
            ).pack(side="left")

            entry = ctk.CTkEntry(
                row, placeholder_text=hint,
                width=440, height=32,
                fg_color="#0F3460",
                border_color="#1F6AA5",
                text_color="#EAEAEA",
            )
            entry.pack(side="left", padx=(0, 8))
            setattr(self, entry_attr, entry)

            ctk.CTkButton(
                row, text="Browse…",
                command=getattr(self, cmd),
                width=90, height=32,
                fg_color="#1F6AA5",
                hover_color="#154E87",
            ).pack(side="left")

        # ── Options row ───────────────────────
        opts = ctk.CTkFrame(parent, fg_color="transparent")
        opts.pack(fill="x", padx=20, pady=(4, 0))

        self._auto_correct_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            opts,
            text="Auto-correct PDFs",
            variable=self._auto_correct_var,
            text_color="#EAEAEA",
            checkmark_color="#4FC3F7",
            border_color="#1F6AA5",
            hover_color="#1F6AA5",
        ).pack(side="left", padx=(0, 20))

        self._stamp_check_var = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            opts,
            text="Check stamps (pages 2-7)",
            variable=self._stamp_check_var,
            text_color="#EAEAEA",
            checkmark_color="#4FC3F7",
            border_color="#1F6AA5",
            hover_color="#1F6AA5",
        ).pack(side="left", padx=(0, 20))

        # Worker count
        ctk.CTkLabel(
            opts, text="Workers:",
            font=ctk.CTkFont(size=10), text_color="#8899AA",
        ).pack(side="left", padx=(20, 4))

        self._workers_var = tk.StringVar(value=str(config.MAX_WORKER_THREADS))
        ctk.CTkOptionMenu(
            opts,
            values=["1", "2", "4", "8"],
            variable=self._workers_var,
            width=70, height=28,
            fg_color="#0F3460",
            button_color="#1F6AA5",
        ).pack(side="left")

        # ── Action buttons ────────────────────
        actions = ctk.CTkFrame(parent, fg_color="transparent")
        actions.pack(fill="x", padx=20, pady=10)

        self._start_btn = ctk.CTkButton(
            actions,
            text="▶  Start Processing",
            command=self._start_processing,
            height=40, width=200,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=config.COLOR_SUCCESS,
            hover_color="#1e8c1a",
        )
        self._start_btn.pack(side="left", padx=(0, 12))

        ctk.CTkButton(
            actions,
            text="📂  Open Output Folder",
            command=self._open_output_folder,
            height=40, width=180,
            fg_color="#2E4057",
            hover_color="#1A2A3A",
        ).pack(side="left", padx=(0, 12))

        ctk.CTkButton(
            actions,
            text="🗑  Clear Log",
            command=self._clear_log,
            height=40, width=120,
            fg_color="#2E4057",
            hover_color="#1A2A3A",
        ).pack(side="left")

    def _build_log_console(self, parent) -> None:
        # Header bar
        log_header = ctk.CTkFrame(parent, fg_color="#161B22", height=28)
        log_header.pack(fill="x")
        log_header.pack_propagate(False)

        ctk.CTkLabel(
            log_header,
            text="  ◉  LIVE LOG CONSOLE",
            font=ctk.CTkFont(family="Courier", size=10, weight="bold"),
            text_color="#4FC3F7",
        ).pack(side="left", padx=8, pady=4)

        # Text widget + scrollbar
        text_frame = tk.Frame(parent, bg="#0D1117")
        text_frame.pack(fill="both", expand=True)

        self._log_text = tk.Text(
            text_frame,
            bg="#0D1117",
            fg="#C9D1D9",
            font=("Courier New", 9),
            state="disabled",
            wrap="word",
            bd=0,
            highlightthickness=0,
            insertbackground="#C9D1D9",
        )
        sb = tk.Scrollbar(text_frame, command=self._log_text.yview, bg="#161B22")
        self._log_text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self._log_text.pack(fill="both", expand=True, padx=6, pady=4)

        # Log level colour tags
        self._log_text.tag_config("INFO",   foreground="#C9D1D9")
        self._log_text.tag_config("PASS",   foreground="#4CAF50")
        self._log_text.tag_config("FAIL",   foreground="#EF5350")
        self._log_text.tag_config("WARN",   foreground="#FFA726")
        self._log_text.tag_config("ERROR",  foreground="#FF6B6B")
        self._log_text.tag_config("SYSTEM", foreground="#4FC3F7")
        self._log_text.tag_config("DEBUG",  foreground="#546E7A")

    # ─────────────────────────────────────────
    # File selection callbacks
    # ─────────────────────────────────────────

    def _select_excel(self) -> None:
        path = filedialog.askopenfilename(
            title="Select Excel Master File",
            filetypes=[("Excel files", "*.xlsx *.xls"), ("All files", "*.*")],
        )
        if not path:
            return
        self._excel_path = Path(path)
        self.excel_entry.delete(0, "end")
        self.excel_entry.insert(0, str(self._excel_path))
        self._load_excel()

    def _select_pdf_folder(self) -> None:
        folder = filedialog.askdirectory(title="Select PDF Input Folder")
        if not folder:
            return
        self._pdf_folder = Path(folder)
        self.pdf_entry.delete(0, "end")
        self.pdf_entry.insert(0, str(self._pdf_folder))
        self._log_system(f"PDF folder: {self._pdf_folder}")

        # Quick count
        try:
            count = sum(1 for _ in self._pdf_folder.rglob("*.pdf"))
            self._log_info(f"Found {count} PDF files in selected folder.")
        except Exception:
            pass

    def _select_output(self) -> None:
        folder = filedialog.askdirectory(title="Select Output Folder")
        if not folder:
            return
        self._output_dir = Path(folder)
        self.output_entry.delete(0, "end")
        self.output_entry.insert(0, str(self._output_dir))
        self._log_system(f"Output folder: {self._output_dir}")

    # ─────────────────────────────────────────
    # Excel loading
    # ─────────────────────────────────────────

    def _load_excel(self) -> None:
        """Load Excel in background thread to keep UI responsive."""
        def _load():
            try:
                self._excel_reader.load(self._excel_path)
                summary = self._excel_reader.summary()
                self.after(0, lambda: self._on_excel_loaded(summary))
            except Exception as exc:
                self.after(0, lambda: self._on_excel_error(str(exc)))

        self._log_system(f"Loading Excel: {self._excel_path.name}…")
        threading.Thread(target=_load, daemon=True).start()

    def _on_excel_loaded(self, summary: dict) -> None:
        msg = (
            f"✔ Excel loaded: {summary['total_records']} students, "
            f"{summary['unique_courses']} courses"
        )
        self._excel_status_var.set(msg)
        self._log_pass(msg)

    def _on_excel_error(self, error: str) -> None:
        self._excel_status_var.set("⚠ Excel load failed")
        self._log_error(f"Excel error: {error}")
        messagebox.showerror("Excel Error", error)

    # ─────────────────────────────────────────
    # Processing
    # ─────────────────────────────────────────

    def _start_processing(self) -> None:
        # Validation
        if not self._excel_reader.is_loaded:
            messagebox.showwarning("Missing Data", "Please select and load the Excel master file first.")
            return
        if not self._pdf_folder or not self._pdf_folder.exists():
            messagebox.showwarning("Missing Folder", "Please select a valid PDF input folder.")
            return
        if not self._output_dir:
            messagebox.showwarning("Missing Folder", "Please select an output folder.")
            return

        # Lazy-load OCR engine
        if self._ocr_engine is None:
            self._ocr_engine = OCREngine()

        # Update worker count from UI
        try:
            config.MAX_WORKER_THREADS = int(self._workers_var.get())
        except ValueError:
            pass

        # Create processor
        self._processor = OJTProcessor(
            excel_reader=self._excel_reader,
            ocr_engine=self._ocr_engine,
            output_dir=self._output_dir,
            on_progress=self._on_progress_update,
            on_log=self._on_processor_log,
        )

        # Show progress dialog
        self._progress_dialog = ProgressDialog(
            self,
            title="Processing OJT PDFs…",
            on_cancel=self._processor.cancel,
        )

        # Disable start button
        self._start_btn.configure(state="disabled", text="Processing…")
        self._dashboard.set_idle()

        # Run in background thread
        def _run():
            self._processor.start(self._pdf_folder)

        threading.Thread(target=_run, daemon=True, name="OJT-Processor").start()
        self._log_system(f"Processing started → {self._pdf_folder}")

    def _on_progress_update(self, progress) -> None:
        """Called from processor thread — marshal to main thread."""
        def _update():
            if self._progress_dialog and self._progress_dialog.winfo_exists():
                self._progress_dialog.update_progress(progress)
            self._dashboard.update_stats(progress=progress)

            if progress.is_done:
                self._start_btn.configure(
                    state="normal", text="▶  Start Processing"
                )

        self.after(0, _update)

    def _on_processor_log(self, msg: str) -> None:
        """Called from processor thread — marshal to main thread."""
        def _append():
            self._append_log(msg)
            if self._progress_dialog and self._progress_dialog.winfo_exists():
                self._progress_dialog.append_log(msg)
        self.after(0, _append)

    # ─────────────────────────────────────────
    # Log console methods
    # ─────────────────────────────────────────

    def _setup_logging_handler(self) -> None:
        """Add a handler to root logger that writes to our log console."""
        class TkHandler(logging.Handler):
            def __init__(self_, win):
                super().__init__()
                self_._win = win

            def emit(self_, record):
                msg = self_.format(record)
                tag = {
                    "DEBUG":    "DEBUG",
                    "INFO":     "INFO",
                    "WARNING":  "WARN",
                    "ERROR":    "ERROR",
                    "CRITICAL": "ERROR",
                }.get(record.levelname, "INFO")
                self_._win.after(0, lambda: self_._win._append_log(msg, tag))

        handler = TkHandler(self)
        handler.setLevel(logging.INFO)
        handler.setFormatter(logging.Formatter("%(name)s: %(message)s"))
        logging.getLogger().addHandler(handler)

    def _append_log(self, message: str, tag: str = None) -> None:
        from datetime import datetime
        ts = datetime.now().strftime("%H:%M:%S")
        if tag is None:
            tag = self._detect_tag(message)
        line = f"[{ts}] {message}\n"
        try:
            self._log_text.configure(state="normal")
            self._log_text.insert("end", line, tag)
            self._log_text.see("end")
            self._log_text.configure(state="disabled")
        except Exception:
            pass

    def _detect_tag(self, msg: str) -> str:
        mu = msg.upper()
        if "→ PASS" in mu or "✔" in mu:
            return "PASS"
        if "→ FAIL" in mu or "FAIL" in mu:
            return "FAIL"
        if "ERROR" in mu:
            return "ERROR"
        if "WARN" in mu:
            return "WARN"
        if "SYSTEM" in mu or "READY" in mu or "LOADED" in mu:
            return "SYSTEM"
        return "INFO"

    def _log_system(self, msg):  self._append_log(msg, "SYSTEM")
    def _log_info(self, msg):    self._append_log(msg, "INFO")
    def _log_pass(self, msg):    self._append_log(msg, "PASS")
    def _log_warn(self, msg):    self._append_log(msg, "WARN")
    def _log_error(self, msg):   self._append_log(msg, "ERROR")

    def _clear_log(self) -> None:
        self._log_text.configure(state="normal")
        self._log_text.delete("1.0", "end")
        self._log_text.configure(state="disabled")

    # ─────────────────────────────────────────
    # Utility
    # ─────────────────────────────────────────

    def _open_output_folder(self) -> None:
        import subprocess, sys, os
        folder = self._output_dir or config.BASE_DIR / "data"
        if not folder.exists():
            folder.mkdir(parents=True, exist_ok=True)
        try:
            if sys.platform == "win32":
                os.startfile(str(folder))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(folder)])
            else:
                subprocess.Popen(["xdg-open", str(folder)])
        except Exception as exc:
            messagebox.showinfo("Output Folder", str(folder))
