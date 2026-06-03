"""
gui/dashboard.py - Statistics Dashboard Panel
OJT Checker System

Displays real-time and post-processing statistics as
animated counter cards in the main window sidebar.
"""

import tkinter as tk
import customtkinter as ctk


class StatCard(ctk.CTkFrame):
    """A single statistics tile with a label, value, and accent bar."""

    def __init__(self, parent, label: str, color: str, **kwargs):
        super().__init__(
            parent,
            fg_color="#0F3460",
            corner_radius=12,
            **kwargs,
        )

        # Accent top bar
        accent = tk.Frame(self, bg=color, height=4)
        accent.pack(fill="x", pady=(0, 6))

        self._label = ctk.CTkLabel(
            self,
            text=label.upper(),
            font=ctk.CTkFont(size=9, weight="bold"),
            text_color=color,
        )
        self._label.pack(pady=(0, 2))

        self._value_var = tk.StringVar(value="0")
        self._value_label = ctk.CTkLabel(
            self,
            textvariable=self._value_var,
            font=ctk.CTkFont(family="Courier", size=28, weight="bold"),
            text_color="#EAEAEA",
        )
        self._value_label.pack(pady=(0, 8))

    def set_value(self, value) -> None:
        self._value_var.set(str(value))


class Dashboard(ctk.CTkFrame):
    """
    Dashboard panel displaying processing statistics.

    Sits on the right side (or bottom) of the main window.
    Updated via update_stats().
    """

    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color="#16213E", corner_radius=0, **kwargs)
        self._build_ui()

    # ─────────────────────────────────────────
    # UI Construction
    # ─────────────────────────────────────────

    def _build_ui(self) -> None:
        # Section header
        ctk.CTkLabel(
            self,
            text="📊  STATISTICS",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#4FC3F7",
        ).pack(pady=(16, 8), padx=16, anchor="w")

        # Stat cards grid
        cards_frame = ctk.CTkFrame(self, fg_color="transparent")
        cards_frame.pack(fill="x", padx=12, pady=4)
        cards_frame.columnconfigure(0, weight=1)
        cards_frame.columnconfigure(1, weight=1)

        card_defs = [
            ("Total",       "#90CAF9", "_card_total"),
            ("Pass",        "#4CAF50", "_card_pass"),
            ("Fail",        "#EF5350", "_card_fail"),
            ("Errors",      "#FFA726", "_card_errors"),
            ("Corrections", "#29B6F6", "_card_corr"),
            ("Pass Rate",   "#CE93D8", "_card_rate"),
        ]

        for i, (label, color, attr) in enumerate(card_defs):
            row, col = divmod(i, 2)
            card = StatCard(cards_frame, label=label, color=color)
            card.grid(row=row, column=col, padx=6, pady=6, sticky="nsew")
            setattr(self, attr, card)

        # Separator
        sep = ctk.CTkFrame(self, fg_color="#1F6AA5", height=1)
        sep.pack(fill="x", padx=16, pady=(12, 8))

        # Progress section
        ctk.CTkLabel(
            self,
            text="⚡  CURRENT RUN",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#4FC3F7",
        ).pack(pady=(0, 6), padx=16, anchor="w")

        # Mini progress bar
        self._mini_progress_var = tk.DoubleVar(value=0)
        self._mini_bar = ctk.CTkProgressBar(
            self,
            variable=self._mini_progress_var,
            height=14,
            corner_radius=7,
            progress_color="#1F6AA5",
            fg_color="#0F3460",
        )
        self._mini_bar.pack(fill="x", padx=16, pady=(0, 4))

        self._progress_text_var = tk.StringVar(value="Idle")
        ctk.CTkLabel(
            self,
            textvariable=self._progress_text_var,
            font=ctk.CTkFont(size=10),
            text_color="#8899AA",
        ).pack(padx=16, anchor="w")

        # Separator
        sep2 = ctk.CTkFrame(self, fg_color="#1F4E79", height=1)
        sep2.pack(fill="x", padx=16, pady=(12, 8))

        # Last report section
        ctk.CTkLabel(
            self,
            text="📄  LAST REPORT",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#4FC3F7",
        ).pack(pady=(0, 4), padx=16, anchor="w")

        self._report_path_var = tk.StringVar(value="No report yet")
        ctk.CTkLabel(
            self,
            textvariable=self._report_path_var,
            font=ctk.CTkFont(size=9),
            text_color="#8899AA",
            wraplength=180,
            justify="left",
        ).pack(padx=16, anchor="w")

        # Status indicator dot
        status_frame = ctk.CTkFrame(self, fg_color="transparent")
        status_frame.pack(fill="x", padx=16, pady=(12, 0))

        self._status_dot = tk.Canvas(
            status_frame, width=12, height=12,
            bg="#16213E", highlightthickness=0,
        )
        self._status_dot.pack(side="left")
        self._status_oval = self._status_dot.create_oval(
            2, 2, 10, 10, fill="#5A6472", outline=""
        )

        self._status_text_var = tk.StringVar(value="Idle")
        ctk.CTkLabel(
            status_frame,
            textvariable=self._status_text_var,
            font=ctk.CTkFont(size=10),
            text_color="#8899AA",
        ).pack(side="left", padx=6)

    # ─────────────────────────────────────────
    # Public update API
    # ─────────────────────────────────────────

    def update_stats(self, progress=None, stats: dict = None) -> None:
        """
        Update all dashboard cards.

        Args:
            progress: ProcessingProgress object (live run)
            stats:    Final stats dict from ReportGenerator
        """
        if progress:
            self._card_total.set_value(progress.total)
            self._card_pass.set_value(progress.passed)
            self._card_fail.set_value(progress.failed)
            self._card_errors.set_value(progress.errors)

            rate = (
                f"{(progress.passed / progress.total * 100):.1f}%"
                if progress.total > 0 else "—"
            )
            self._card_rate.set_value(rate)

            pct = progress.percent / 100.0
            self._mini_progress_var.set(min(pct, 1.0))
            self._progress_text_var.set(
                f"{progress.completed} of {progress.total} processed"
                if progress.total > 0 else "Starting…"
            )

            if progress.report_path:
                self._report_path_var.set(progress.report_path.name)

            if progress.is_running:
                self._set_status("running", "#4FC3F7")
            elif progress.is_done:
                self._set_status("done", "#4CAF50")

        if stats:
            self._card_total.set_value(stats.get("total", 0))
            self._card_pass.set_value(stats.get("pass", 0))
            self._card_fail.set_value(stats.get("fail", 0))
            self._card_errors.set_value(stats.get("error", 0))
            self._card_corr.set_value(stats.get("corrections", 0))

    def set_corrections(self, value: int) -> None:
        self._card_corr.set_value(value)

    def set_idle(self) -> None:
        self._set_status("idle", "#5A6472")
        self._mini_progress_var.set(0)
        self._progress_text_var.set("Idle")

    def _set_status(self, label: str, color: str) -> None:
        self._status_dot.itemconfig(self._status_oval, fill=color)
        self._status_text_var.set(label.capitalize())
