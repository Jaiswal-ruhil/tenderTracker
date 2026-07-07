import os
import sys

# Ensure core and gui folders are in python path for direct execution
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "core"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "gui"))

import time
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
import calendar
import re
import webbrowser

# Local imports
from config import (
    BG, PANEL, CARD, ACCENT, ACCENT2, MUTED, TEXT, TEXTSUB, SUCCESS, ERR, WARN, SEL_BG,
    FH, FB, FL, FT, TV_COLS, TV_IDS
)
from excel import financial_year, xl_path, ensure_workbook, xl_append
from parser import split_blocks, parse_one, convert_pdf_text_to_markdown
from scraper import scrape_bid_page, _try_import_selenium, download_tender_pdf, scrape_portal_search
import db

# Mixins for tab structures and dialogs
from gui_calendar import CalendarTabMixin
from gui_analytics import AnalyticsTabMixin
from gui_dialogs import DialogsMixin
from gui_table_tab import TableTabMixin, DatePickerPopup
from gui_workers import WorkersMixin

class TenderApp(tk.Tk, CalendarTabMixin, AnalyticsTabMixin, DialogsMixin, TableTabMixin, WorkersMixin):
    def __init__(self):
        super().__init__()
        self.title("GEM Tender Logger  v4")
        self.configure(bg=BG)
        self.geometry("1400x860")
        self.minsize(900, 600)

        self.save_folder = tk.StringVar(
            value=os.path.expanduser("~\\Documents" if os.name=="nt" else "~/Documents"))
        self._records  = []
        self._editing  = None
        self._fetch_running = False
        self._scrape_running = False
        self._stop_scrape_flag = False
        self._log_detail_seq = 0
        self._log_detail_buttons = []

        # Calendar State
        self.cal_year = datetime.now().year
        self.cal_month = datetime.now().month
        self.cal_selected_date = datetime.now().date()
        self.cal_day_frames = []

        self._style()
        self._build()
        self._load_from_db()
        self._fy_tick()
        self._poll_log_queue()
        self._bind_shortcuts()
        # Start UI freeze watchdog after the app is fully up
        import logger as _logger_mod
        _logger_mod.start_watchdog()
        # Stop watchdog cleanly when the window is closed
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── styles ────────────────────────────────────────────────────────────────
    def _style(self):
        s = ttk.Style(self); s.theme_use("clam")
        s.configure(".", background=BG, foreground=TEXT, font=FB)
        s.configure("Treeview", background=PANEL, foreground=TEXT,
                    fieldbackground=PANEL, rowheight=28, borderwidth=0, font=FL)
        s.configure("Treeview.Heading", background=CARD, foreground=TEXT,
                    font=("Segoe UI",9,"bold"), relief="flat")
        s.map("Treeview",
              background=[("selected",SEL_BG)], foreground=[("selected",TEXT)])
        s.map("Treeview.Heading", background=[("active",CARD)])
        for o in ("Vertical","Horizontal"):
            s.configure(f"{o}.TScrollbar", background=CARD, troughcolor=BG,
                        bordercolor=BG, arrowcolor=MUTED, gripcount=0)
            s.map(f"{o}.TScrollbar",
                  background=[("pressed", ACCENT2), ("active", "#30363D")],
                  arrowcolor=[("pressed", TEXT), ("active", TEXT)])
        s.configure("TProgressbar", troughcolor=CARD, background=ACCENT2,
                    bordercolor=BG, lightcolor=ACCENT2, darkcolor=ACCENT2)
        s.configure("TNotebook", background=BG, borderwidth=0)
        s.configure("TNotebook.Tab", background=CARD, foreground=MUTED,
                    padding=[14, 6], font=("Segoe UI", 9, "bold"), relief="flat")
        s.map("TNotebook.Tab",
              background=[("selected", PANEL)],
              foreground=[("selected", TEXT)])

        # Style all TCombobox widgets (Filter dropdowns, etc.) to match the dark theme
        s.configure("TCombobox", 
                    fieldbackground=CARD, 
                    background=PANEL, 
                    foreground=TEXT, 
                    bordercolor="#30363D", 
                    arrowcolor=MUTED)
        s.map("TCombobox", 
              fieldbackground=[("readonly", CARD)], 
              foreground=[("readonly", TEXT)],
              selectbackground=[("readonly", SEL_BG)])
              
        # Centralize drop-down listboxes configuration for dark theme
        self.option_add("*TCombobox*Listbox.background", CARD)
        self.option_add("*TCombobox*Listbox.foreground", TEXT)
        self.option_add("*TCombobox*Listbox.selectBackground", SEL_BG)
        self.option_add("*TCombobox*Listbox.selectForeground", TEXT)

    # ── layout ────────────────────────────────────────────────────────────────
    def _build(self):
        # top bar
        top = tk.Frame(self, bg=PANEL, pady=8, padx=14,
                       highlightthickness=1, highlightbackground="#30363D")
        top.pack(fill="x")
        tk.Label(top, text="GEM Tender Logger", font=FT, bg=PANEL, fg=TEXT).pack(side="left")
        self.fy_lbl = tk.Label(top, text="", font=FL, bg=ACCENT2, fg=TEXT, padx=10, pady=3)
        self.fy_lbl.pack(side="right", padx=(6,0))
        self._btn(top, "⚙ Settings", self._show_settings, bg=CARD).pack(side="right")
        self._btn(top, "🏢 Manage Firms", self._show_firms_dialog, bg=CARD).pack(side="right", padx=(0, 6))

        # paned: left = paste+log, right = table
        pane = tk.PanedWindow(self, orient="horizontal", bg=BG,
                              sashwidth=5, sashrelief="flat", handlesize=0)
        pane.pack(fill="both", expand=True, padx=10, pady=(4,0))

        # ── LEFT ─────────────────────────────────────────────────────────────
        left = tk.Frame(pane, bg=BG)
        pane.add(left, minsize=320, width=400)

        tk.Label(left, text="Paste GEM Tender Block(s)", font=("Segoe UI",9,"bold"),
                 bg=BG, fg=MUTED).pack(anchor="w", pady=(4,2))
        self.paste_txt = tk.Text(left, bg=CARD, fg=TEXT, insertbackground=TEXT,
                                 relief="flat", font=FH, height=12,
                                 highlightthickness=1, highlightbackground="#30363D",
                                 highlightcolor=ACCENT2, wrap="word", undo=True,
                                 padx=8, pady=8)
        self.paste_txt.pack(fill="x")
        tk.Label(left, text="Paste tender text, bid numbers, URLs, or local PDF paths. One item per line also works.",
                 font=("Segoe UI",8), bg=BG, fg=TEXTSUB).pack(anchor="w", pady=(2,4))

        # progress
        self.progress = ttk.Progressbar(left, orient="horizontal",
                                        mode="determinate", length=200)
        self.progress.pack(fill="x", pady=(0,4))
        self.prog_lbl = tk.Label(left, text="", font=("Segoe UI",8),
                                 bg=BG, fg=TEXTSUB)
        self.prog_lbl.pack(anchor="w")

        # buttons
        btn_row = tk.Frame(left, bg=BG)
        btn_row.pack(fill="x", pady=(4,8))
        self._btn(btn_row, "Parse", lambda: self._do_parse(force_llm=False),
                  bg=ACCENT2, pad=6).pack(side="left")
        self._btn(btn_row, "Parse with AI", lambda: self._do_parse(force_llm=True),
                  bg=ACCENT, pad=6).pack(side="left", padx=6)
        self._btn(btn_row, "Fetch Details",
                  self._do_fetch_all, bg=CARD, pad=6).pack(side="left")
        self._btn(btn_row, "Clear Input", lambda: self.paste_txt.delete("1.0","end"),
                  bg=CARD).pack(side="left", padx=6)



        # log
        log_hdr = tk.Frame(left, bg=BG)
        log_hdr.pack(fill="x", pady=(0, 2))
        tk.Label(log_hdr, text="Log", font=("Segoe UI", 9, "bold"),
                 bg=BG, fg=MUTED).pack(side="left")
        
        def copy_log():
            try:
                self.clipboard_clear()
                self.clipboard_append(self.log_txt.get("1.0", "end-1c"))
                self._log("info", "Log copied to clipboard.")
            except Exception as e:
                self._log("err", f"Failed to copy log: {e}")

        def clear_log():
            self.log_txt.configure(state="normal")
            self.log_txt.delete("1.0", "end")
            self.log_txt.configure(state="disabled")
                
        copy_btn = tk.Button(log_hdr, text="📋 Copy", command=copy_log,
                             bg=CARD, fg=TEXTSUB, relief="flat", font=("Segoe UI", 8),
                             padx=4, pady=0, activebackground=ACCENT2, activeforeground=TEXT,
                             cursor="hand2")
        copy_btn.pack(side="right")
        clear_btn = tk.Button(log_hdr, text="Clear", command=clear_log,
                              bg=CARD, fg=TEXTSUB, relief="flat", font=("Segoe UI", 8),
                              padx=6, pady=0, activebackground=ACCENT2, activeforeground=TEXT,
                              cursor="hand2")
        clear_btn.pack(side="right", padx=(0, 6))

        log_fr = tk.Frame(left, bg=CARD,
                          highlightthickness=1, highlightbackground="#30363D")
        log_fr.pack(fill="both", expand=True)
        self.log_txt = tk.Text(log_fr, bg=CARD, fg=TEXTSUB, relief="flat",
                               font=("Consolas",8), state="disabled", wrap="word",
                               highlightthickness=0, padx=8, pady=8)
        lsb = ttk.Scrollbar(log_fr, orient="vertical", command=self.log_txt.yview)
        self.log_txt.configure(yscrollcommand=lsb.set)
        lsb.pack(side="right", fill="y")
        self.log_txt.pack(fill="both", expand=True, padx=4, pady=4)
        for tag,col in [("ok",SUCCESS),("warn",WARN),("err",ERR),("info",ACCENT2)]:
            self.log_txt.tag_configure(tag, foreground=col)

        # ── RIGHT ────────────────────────────────────────────────────────────
        right = tk.Frame(pane, bg=BG)
        pane.add(right, minsize=500)

        # Notebook for Table and Calendar View
        self.notebook = ttk.Notebook(right)
        self.notebook.pack(fill="both", expand=True)

        self.tab_table = tk.Frame(self.notebook, bg=BG)
        self.tab_calendar = tk.Frame(self.notebook, bg=BG)
        self.tab_analytics = tk.Frame(self.notebook, bg=BG)
        
        self.notebook.add(self.tab_table, text="  Table View  ")
        self.notebook.add(self.tab_calendar, text="  Calendar View  ")
        self.notebook.add(self.tab_analytics, text="  Analytics View  ")
        # Build Table tab layouts
        self._build_table_tab()

        # Build Calendar tab layouts
        self._build_calendar_tab()

        # Build Analytics tab layouts
        self._build_analytics_tab()

        # Bind notebook tab change event to refresh calendar if switched to it
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        # status bar
        self.status = tk.Label(self, text="Ready", font=FL,
                               bg=PANEL, fg=MUTED, anchor="w", padx=10, pady=4)
        self.status.pack(fill="x", side="bottom")

    # ── widget helpers ────────────────────────────────────────────────────────
    def _btn(self, parent, text, cmd, bg=CARD, fg=TEXT, pad=6):
        import logger as _logger_mod
        label = text.strip()
        def _traced_cmd(lbl=label, c=cmd):
            _logger_mod.log_button_click(lbl)
            c()
        btn = tk.Button(parent, text=text, command=_traced_cmd,
                        bg=bg, fg=fg, relief="flat", font=FL,
                        padx=pad, pady=4,
                        activebackground=ACCENT2, activeforeground=TEXT,
                        cursor="hand2")
                        
        hover_colors = {
            CARD: "#30363D",
            ACCENT2: "#388BFD",
            ACCENT: "#2EA44F",  # Modern lighter green hover for the Excel button
            BG: "#161B22",
            "#2D333B": "#444C56"  # Modern lighter dark hover for Fetch button
        }
        hover_bg = hover_colors.get(bg, "#30363D")
        
        btn.bind("<Enter>", lambda e: btn.configure(bg=hover_bg))
        btn.bind("<Leave>", lambda e: btn.configure(bg=bg))
        return btn

    def _log(self, level, msg, details=None):
        import logger
        logger.log(level, msg, details)

    def _write_to_log_widget(self, level, msg, details=None):
        self.log_txt.configure(state="normal")
        ts = datetime.now().strftime("%H:%M:%S")
        icons = {
            "ok": "✓ ",
            "warn": "⚠ ",
            "err": "✗ ",
            "info": "ℹ "
        }
        icon = icons.get(level, "")
        self.log_txt.insert("end", f"[{ts}] {icon}{msg}", level)
        if details and any(str(section.get("content", "")).strip() for section in details.get("sections", [])):
            btn = tk.Button(
                self.log_txt,
                text="Expand",
                command=lambda message=msg, payload=details: self._show_log_details(message, payload),
                bg=CARD,
                fg=TEXT,
                relief="flat",
                font=("Segoe UI", 8, "bold"),
                padx=6,
                pady=0,
                activebackground=ACCENT2,
                activeforeground=TEXT,
                cursor="hand2",
            )
            self._log_detail_buttons.append(btn)
            self.log_txt.insert("end", "  ")
            self.log_txt.window_create("end", window=btn)
        self.log_txt.insert("end", "\n")
        self.log_txt.see("end")
        self.log_txt.configure(state="disabled")
        self.update_idletasks()

    def _show_log_details(self, msg, details):
        win = tk.Toplevel(self)
        win.title("Log Details")
        win.configure(bg=BG)
        win.geometry("980x720")
        win.minsize(720, 480)

        hdr = tk.Frame(win, bg=PANEL, padx=12, pady=10, highlightthickness=1, highlightbackground="#30363D")
        hdr.pack(fill="x")
        tk.Label(hdr, text=details.get("title", "Log Details"), font=("Segoe UI", 11, "bold"), bg=PANEL, fg=TEXT).pack(anchor="w")
        tk.Label(hdr, text=msg, font=FL, bg=PANEL, fg=MUTED, wraplength=920, justify="left").pack(anchor="w", pady=(4, 0))

        body = tk.Frame(win, bg=BG, padx=10, pady=10)
        body.pack(fill="both", expand=True)

        txt = tk.Text(
            body,
            bg=CARD,
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            font=("Consolas", 9),
            wrap="word",
            padx=12,
            pady=12,
            highlightthickness=1,
            highlightbackground="#30363D",
        )
        sb = ttk.Scrollbar(body, orient="vertical", command=txt.yview)
        txt.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        txt.pack(side="left", fill="both", expand=True)

        txt.tag_configure("section", foreground=ACCENT2, font=("Segoe UI", 10, "bold"))
        txt.tag_configure("body", foreground=TEXT)

        first = True
        for section in details.get("sections", []):
            content = str(section.get("content", "")).strip()
            if not content:
                continue
            if not first:
                txt.insert("end", "\n\n", "body")
            first = False
            txt.insert("end", f"{section.get('label', 'Details')}\n", "section")
            txt.insert("end", f"{content}\n", "body")
        txt.configure(state="disabled")

    def _poll_log_queue(self):
        import logger
        try:
            logger.update_heartbeat()  # keep watchdog informed the main thread is alive
            while not logger.log_queue.empty():
                try:
                    payload = logger.log_queue.get_nowait()
                    if isinstance(payload, tuple) and len(payload) == 3:
                        level, msg, details = payload
                    else:
                        level, msg = payload
                        details = None
                    self._write_to_log_widget(level, msg, details)
                except Exception:
                    break
            self.after(50, self._poll_log_queue)
        except Exception:
            # Widget has been destroyed — stop rescheduling silently
            pass

    def _on_close(self):
        """Graceful shutdown: stop watchdog then destroy the window."""
        try:
            self.destroy()
        except Exception:
            pass

    def destroy(self):
        """Stop watchdog thread and destroy the window."""
        import logger as _logger_mod
        _logger_mod.stop_watchdog()
        super().destroy()

    def _show_toast(self, title, message, level="info"):
        if threading.current_thread() is not threading.main_thread():
            self.after(0, lambda: self._show_toast(title, message, level))
            return
            
        toast = tk.Toplevel(self)
        toast.overrideredirect(True)
        toast.attributes("-topmost", True)
        
        color_map = {
            "ok": SUCCESS,
            "err": ERR,
            "warn": WARN,
            "info": TEXT
        }
        accent_color = color_map.get(level, TEXT)
        toast.configure(bg=PANEL, highlightthickness=1, highlightbackground="#30363D")
        
        # Position bottom right of screen
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        w, h = 320, 80
        x = screen_w - w - 20
        y = screen_h - h - 65
        toast.geometry(f"{w}x{h}+{x}+{y}")
        
        stripe = tk.Frame(toast, bg=accent_color, width=6)
        stripe.pack(side="left", fill="y")
        
        content = tk.Frame(toast, bg=PANEL, padx=12, pady=10)
        content.pack(side="left", fill="both", expand=True)
        
        lbl_title = tk.Label(content, text=title, font=("Segoe UI", 10, "bold"), bg=PANEL, fg=TEXT)
        lbl_title.pack(anchor="w")
        
        lbl_msg = tk.Label(content, text=message, font=FL, bg=PANEL, fg=MUTED, wraplength=285, justify="left")
        lbl_msg.pack(anchor="w", pady=(2, 0))
        
        def fade_out(alpha=1.0):
            if alpha > 0.0:
                alpha -= 0.1
                try:
                    toast.attributes("-alpha", alpha)
                    self.after(50, lambda: fade_out(alpha))
                except Exception:
                    pass
            else:
                try:
                    toast.destroy()
                except Exception:
                    pass
                    
        self.after(3000, fade_out)

    def _on_tab_changed(self, event):
        import logger as _logger_mod
        TAB_NAMES = ["Table View", "Calendar View", "Analytics View"]
        try:
            selected_tab = self.notebook.index(self.notebook.select())
            _logger_mod.log_tab_change(TAB_NAMES[selected_tab] if selected_tab < len(TAB_NAMES) else str(selected_tab))
            if selected_tab == 1:
                self._update_calendar()
                self._update_details()
            elif selected_tab == 2:
                self._update_analytics()
        except Exception as e:
            self._log("err", f"Tab changed error: {e}")

    def _set_status(self, msg, color=MUTED):
        if threading.current_thread() is not threading.main_thread():
            self.after(0, lambda: self._set_status(msg, color))
            return
        self.status.configure(text=msg, fg=color)
        self.update_idletasks()

    def _set_prog(self, val, label=""):
        if threading.current_thread() is not threading.main_thread():
            self.after(0, lambda: self._set_prog(val, label))
            return
        self.progress["value"] = val
        self.prog_lbl.configure(text=label)
        self.update_idletasks()

    def _fy_tick(self):
        self.fy_lbl.configure(text=f"FY {financial_year(datetime.now())}")
        self.after(60000, self._fy_tick)

    def _reload(self):
        self._set_status("Reloading tenders from database...", MUTED)
        try:
            self._records = db.load_all_tenders()
            self._refresh_table_view()
            try:
                self._update_calendar()
                self._update_details()
            except Exception:
                pass
            self._log("ok", f"Reloaded {len(self._records)} tender(s) from database.")
            display_path = db.DB_FILE.replace(os.path.expanduser("~"), "~")
            self._set_status(f"Database: {display_path}", SUCCESS)
        except Exception as e:
            self._log("err", f"Failed to reload database: {e}")
            self._set_status("Reload failed", ERR)
        return "break"

    def _load_from_db(self):
        # Resolve DB path on first run
        cfg_path = db.get_configured_db_path()
        if not cfg_path:
            self._log("info", "First run detected: Prompting for database storage location.")
            selected_dir = filedialog.askdirectory(
                title="First Run: Select folder to store database (tenders_db.db)",
                parent=self
            )
            if selected_dir:
                db_path = os.path.join(os.path.abspath(selected_dir), "tenders_db.db")
                db.save_configured_db_path(db_path)
                db.init_db_path(db_path)
                import logger
                logger.setup_file_logger(db_path)
                self._log("ok", f"Database configured at: {db_path}")
            else:
                db_path = db.DEFAULT_DB_FILE
                messagebox.showwarning(
                    "No Folder Selected",
                    f"No folder was selected. The database will be stored in the default location:\n\n{db_path}",
                    parent=self
                )
                db.save_configured_db_path(db_path)
                db.init_db_path(db_path)
                import logger
                logger.setup_file_logger(db_path)
                self._log("warn", f"Prompt cancelled. Defaulting database to: {db_path}")
        else:
            db.init_db_path()
            import logger
            logger.setup_file_logger(db.DB_FILE)

        # Load Excel save folder setting if configured
        settings = db.load_settings()
        saved_excel_folder = settings.get("excel_save_folder")
        if saved_excel_folder and os.path.exists(saved_excel_folder):
            self.save_folder.set(saved_excel_folder)
        else:
            db.save_setting("excel_save_folder", self.save_folder.get())

        self._set_status("Loading tenders from database...", MUTED)
        try:
            self._records = db.load_all_tenders()

            # Migrate existing tenders that have no filing_status (or a legacy value)
            VALID_STATUSES = {"To Be Filed", "Evaluating", "Filed"}
            needs_migration = [
                r for r in self._records
                if r.get("filing_status", "") not in VALID_STATUSES
            ]
            if needs_migration:
                from parser import assign_tender_status
                for r in needs_migration:
                    assign_tender_status(r)
                db.save_all_tenders(self._records)
                self._log("info", f"Migrated filing_status for {len(needs_migration)} existing tender(s).")

            self._refresh_table_view()
            
            # Start background embedding worker on startup
            from vector_search import start_background_embedding_worker
            start_background_embedding_worker(callback_fn=self._refresh_table_view)
            
            display_path = db.DB_FILE.replace(os.path.expanduser("~"), "~")
            self._set_status(f"Database: {display_path}", SUCCESS)
            self._log("info", f"Loaded {len(self._records)} historical tender(s) from database: {db.DB_FILE}")
        except Exception as e:
            self._log("err", f"Failed to load tenders from database: {e}")
            self._set_status("Database error", ERR)
