"""
gui/progress_dialog.py - Processing Progress Dialog
OJT Checker System

A non-blocking modal window showing real-time processing progress
with a log console and statistics counters.
"""

import tkinter as tk
from tkinter import scrolledtext
import customtkinter as ctk
from datetime import datetime


class ProgressDialog(ctk.CTkToplevel):
    """
    Modal-like window that appears during PDF processing.

    Features:
    - Animated progress bar
    - Live log console with auto-scroll
    - Stats counters (pass/fail/errors/corrections)
    - Cancel button
    """

    def __init__(self, parent, title: str = "Processing PDFs…", on_cancel=None):
        super().__init__(parent)

        self.title(title)
        self.geometry("700x520")
        self.resizable(False, False)
        self.grab_set()                 # Make modal
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._on_cancel = on_cancel
        self._cancelled = False

        self._build_ui()

    # ─────────────────────────────────────────
    # UI Construction
    # ─────────────────────────────────────────

    def _build_ui(self) -> None:
        self.configure(fg_color="#1A1A2E")

        # ── Title ─────────────────────────────
        ctk.CTkLabel(
            self,
            text="OJT Processing Engine",
            font=ctk.CTkFont(family="Courier", size=16, weight="bold"),
            text_color="#4FC3F7",
        ).pack(pady=(20, 4))

        # ── Current file ──────────────────────
        self._current_file_var = tk.StringVar(value="Preparing…")
        ctk.CTkLabel(
            self,
            textvariable=self._current_file_var,
            font=ctk.CTkFont(size=11),
            text_color="#90CAF9",
        ).pack()

        # ── Progress bar ──────────────────────
        progress_frame = ctk.CTkFrame(self, fg_color="transparent")
        progress_frame.pack(fill="x", padx=30, pady=(12, 4))

        self._progress_var = tk.DoubleVar(value=0)
        self._progress_bar = ctk.CTkProgressBar(
            progress_frame,
            variable=self._progress_var,
            height=22,
            corner_radius=11,
            progress_color="#1F6AA5",
            fg_color="#0F3460",
        )
        self._progress_bar.pack(fill="x")

        self._progress_label_var = tk.StringVar(value="0 / 0  (0.00%)")
        ctk.CTkLabel(
            progress_frame,
            textvariable=self._progress_label_var,
            font=ctk.CTkFont(size=10),
            text_color="#90CAF9",
        ).pack(anchor="e", pady=(2, 0))

        # ── Stats row ─────────────────────────
        stats_frame = ctk.CTkFrame(self, fg_color="#0F3460", corner_radius=10)
        stats_frame.pack(fill="x", padx=30, pady=6)

        for col, (label, color, attr) in enumerate([
            ("PASS",        "#4CAF50", "_pass_var"),
            ("FAIL",        "#EF5350", "_fail_var"),
            ("ERRORS",      "#FFA726", "_error_var"),
            ("CORRECTIONS", "#29B6F6", "_corr_var"),
        ]):
            cell = ctk.CTkFrame(stats_frame, fg_color="transparent")
            cell.grid(row=0, column=col, padx=10, pady=8, sticky="nsew")
            stats_frame.columnconfigure(col, weight=1)

            var = tk.StringVar(value="0")
            setattr(self, attr, var)

            ctk.CTkLabel(
                cell, text=label,
                font=ctk.CTkFont(size=9, weight="bold"),
                text_color=color,
            ).pack()
            ctk.CTkLabel(
                cell, textvariable=var,
                font=ctk.CTkFont(size=20, weight="bold"),
                text_color=color,
            ).pack()

        # ── Log console ───────────────────────
        log_frame = ctk.CTkFrame(self, fg_color="#0D1117", corner_radius=8)
        log_frame.pack(fill="both", expand=True, padx=30, pady=(4, 6))

        self._log_text = tk.Text(
            log_frame,
            bg="#0D1117",
            fg="#C9D1D9",
            font=("Courier New", 9),
            state="disabled",
            wrap="word",
            bd=0,
            highlightthickness=0,
        )
        scrollbar = tk.Scrollbar(log_frame, command=self._log_text.yview)
        self._log_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self._log_text.pack(fill="both", expand=True, padx=4, pady=4)

        # Tag colours for log levels
        self._log_text.tag_config("INFO",    foreground="#C9D1D9")
        self._log_text.tag_config("PASS",    foreground="#4CAF50")
        self._log_text.tag_config("FAIL",    foreground="#EF5350")
        self._log_text.tag_config("WARN",    foreground="#FFA726")
        self._log_text.tag_config("ERROR",   foreground="#FF6B6B")
        self._log_text.tag_config("SYSTEM",  foreground="#4FC3F7")

        # ── Buttons ───────────────────────────
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=(0, 16))

        self._cancel_btn = ctk.CTkButton(
            btn_frame,
            text="Cancel Processing",
            fg_color="#C0392B",
            hover_color="#922B21",
            command=self._request_cancel,
            width=180,
        )
        self._cancel_btn.pack(side="left", padx=8)

        self._close_btn = ctk.CTkButton(
            btn_frame,
            text="Close",
            fg_color="#2E4057",
            hover_color="#1A2A3A",
            command=self.destroy,
            width=120,
            state="disabled",
        )
        self._close_btn.pack(side="left", padx=8)

    # ─────────────────────────────────────────
    # Public update API
    # ─────────────────────────────────────────

    def update_progress(self, progress) -> None:
        """
        Called from the main thread via after() with a ProcessingProgress object.
        """
        try:
            pct = progress.percent / 100.0
            self._progress_var.set(min(pct, 1.0))
            self._progress_label_var.set(
                f"{progress.completed} / {progress.total}  "
                f"({progress.percent:.1f}%)"
            )
            self._current_file_var.set(
                f"Processing: {progress.current_file}" if progress.current_file else "Working…"
            )
            self._pass_var.set(str(progress.passed))
            self._fail_var.set(str(progress.failed))
            self._error_var.set(str(progress.errors))

            if progress.is_done:
                self._on_done(progress)
        except tk.TclError:
            pass  # Dialog was closed

    def append_log(self, message: str) -> None:
        """Add a line to the log console (call from main thread via after())."""
        try:
            ts = datetime.now().strftime("%H:%M:%S")
            tag = self._detect_tag(message)
            line = f"[{ts}] {message}\n"

            self._log_text.configure(state="normal")
            self._log_text.insert("end", line, tag)
            self._log_text.see("end")
            self._log_text.configure(state="disabled")
        except tk.TclError:
            pass

    # ─────────────────────────────────────────
    # Private helpers
    # ─────────────────────────────────────────

    def _detect_tag(self, msg: str) -> str:
        msg_up = msg.upper()
        if "→ PASS" in msg_up or "PASSED" in msg_up:
            return "PASS"
        if "→ FAIL" in msg_up or "FAILED" in msg_up:
            return "FAIL"
        if "ERROR" in msg_up:
            return "ERROR"
        if "WARN" in msg_up:
            return "WARN"
        if "DONE" in msg_up or "REPORT" in msg_up or "FOUND" in msg_up:
            return "SYSTEM"
        return "INFO"

    def _request_cancel(self) -> None:
        self._cancelled = True
        self.append_log("Cancellation requested — finishing current batch…")
        self._cancel_btn.configure(state="disabled", text="Cancelling…")
        if self._on_cancel:
            self._on_cancel()

    def _on_done(self, progress) -> None:
        self._cancel_btn.configure(state="disabled")
        self._close_btn.configure(state="normal")
        self._current_file_var.set(
            "✔ Processing complete!" if not progress.cancelled else "⚠ Processing cancelled."
        )
        self._progress_var.set(1.0)
        self.append_log("─" * 50)
        self.append_log(
            f"Processing finished: {progress.passed} PASS | "
            f"{progress.failed} FAIL | {progress.errors} Errors"
        )
        if progress.report_path:
            self.append_log(f"Report: {progress.report_path}")

    def _on_close(self) -> None:
        """Prevent accidental close during processing."""
        if self._cancel_btn.cget("state") == "normal":
            self._request_cancel()
        else:
            self.destroy()
