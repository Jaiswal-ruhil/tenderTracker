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
from gui_matrix import MatrixTabMixin
from gui_analytics import AnalyticsTabMixin
from gui_dialogs import DialogsMixin
from gui_table_tab import TableTabMixin, DatePickerPopup
from gui_workers import WorkersMixin

class TenderApp(tk.Tk, CalendarTabMixin, MatrixTabMixin, AnalyticsTabMixin, DialogsMixin, TableTabMixin, WorkersMixin):
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
        s.configure("TProgressbar", troughcolor=CARD, background=ACCENT2,
                    bordercolor=BG, lightcolor=ACCENT2, darkcolor=ACCENT2)
        s.configure("TNotebook", background=BG, borderwidth=0)
        s.configure("TNotebook.Tab", background=CARD, foreground=MUTED,
                    padding=[14, 6], font=("Segoe UI", 9, "bold"), relief="flat")
        s.map("TNotebook.Tab",
              background=[("selected", PANEL)],
              foreground=[("selected", TEXT)])

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
                                 highlightcolor=ACCENT2, wrap="word", undo=True)
        self.paste_txt.pack(fill="x")
        tk.Label(left, text="Paste one or many blocks — each starting with BID NO:",
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
        self._btn(btn_row, "  1. Parse Blocks  ", self._do_parse,
                  bg=ACCENT2, pad=10).pack(side="left")
        self._btn(btn_row, "  2. Fetch Details (Selenium)  ",
                  self._do_fetch_all, bg=ACCENT, pad=10).pack(side="left", padx=6)
        self._btn(btn_row, "Clear", lambda: self.paste_txt.delete("1.0","end"),
                  bg=CARD).pack(side="left")

        # ── Portal Scraper Frame ─────────────────────────────────────────────
        scrape_fr = tk.Frame(left, bg=PANEL, padx=12, pady=10, highlightthickness=1, highlightbackground="#30363D")
        scrape_fr.pack(fill="x", pady=(4, 8))
        
        tk.Label(scrape_fr, text="Automated Portal Scraper", font=("Segoe UI",9,"bold"),
                 bg=PANEL, fg=MUTED).pack(anchor="w")
        
        # Search query entry
        query_fr = tk.Frame(scrape_fr, bg=PANEL)
        query_fr.pack(fill="x", pady=(4, 4))
        tk.Label(query_fr, text="Query:", font=FL, bg=PANEL, fg=TEXTSUB).pack(side="left")
        self.scrape_query_var = tk.StringVar()
        self.scrape_query_ent = tk.Entry(query_fr, textvariable=self.scrape_query_var, bg=CARD, fg=TEXT,
                                         insertbackground=TEXT, relief="flat", font=FL,
                                         highlightthickness=1, highlightbackground="#30363D",
                                         highlightcolor=ACCENT2)
        self.scrape_query_ent.pack(side="right", fill="x", expand=True, padx=(6, 0))
        
        # Date Filter Row
        date_fr = tk.Frame(scrape_fr, bg=PANEL)
        date_fr.pack(fill="x", pady=(4, 4))
        
        tk.Label(date_fr, text="Date Filter:", font=FL, bg=PANEL, fg=TEXTSUB).pack(side="left")
        self.scrape_date_type_var = tk.StringVar(value="None")
        self.scrape_date_type_cb = ttk.Combobox(date_fr, textvariable=self.scrape_date_type_var,
                                                values=["None", "Start Date", "End Date"],
                                                state="readonly", font=("Segoe UI", 8), width=10)
        self.scrape_date_type_cb.pack(side="left", padx=4)
        
        tk.Label(date_fr, text="From:", font=("Segoe UI", 8), bg=PANEL, fg=TEXTSUB).pack(side="left", padx=(4, 2))
        self.scrape_date_from_var = tk.StringVar()
        self.scrape_date_from_ent = tk.Entry(date_fr, textvariable=self.scrape_date_from_var, bg=CARD, fg=TEXT,
                                             insertbackground=TEXT, relief="flat", font=("Segoe UI", 8), width=8,
                                             highlightthickness=1, highlightbackground="#30363D")
        self.scrape_date_from_ent.pack(side="left")
        self.btn_scrape_from_cal = tk.Button(date_fr, text="📅", bg=CARD, fg=TEXT, relief="flat",
                                             font=("Segoe UI", 8), padx=3, pady=0, cursor="hand2",
                                             activebackground=ACCENT)
        self.btn_scrape_from_cal.pack(side="left", padx=(2, 4))
        self.btn_scrape_from_cal.configure(
            command=lambda: self._show_datepicker(self.btn_scrape_from_cal, self.scrape_date_from_var))

        # To Label
        tk.Label(date_fr, text="To:", font=("Segoe UI", 8), bg=PANEL, fg=TEXTSUB).pack(side="left", padx=(4, 2))
        self.scrape_date_to_var = tk.StringVar()
        self.scrape_date_to_ent = tk.Entry(date_fr, textvariable=self.scrape_date_to_var, bg=CARD, fg=TEXT,
                                           insertbackground=TEXT, relief="flat", font=("Segoe UI", 8), width=8,
                                           highlightthickness=1, highlightbackground="#30363D")
        self.scrape_date_to_ent.pack(side="left")
        self.btn_scrape_to_cal = tk.Button(date_fr, text="📅", bg=CARD, fg=TEXT, relief="flat",
                                           font=("Segoe UI", 8), padx=3, pady=0, cursor="hand2",
                                           activebackground=ACCENT)
        self.btn_scrape_to_cal.pack(side="left", padx=(2, 4))
        self.btn_scrape_to_cal.configure(
            command=lambda: self._show_datepicker(self.btn_scrape_to_cal, self.scrape_date_to_var))

        # Options row (e.g. limit pages or only keep matching filter)
        opt_row = tk.Frame(scrape_fr, bg=PANEL)
        opt_row.pack(fill="x", pady=(2, 4))
        
        self.scrape_filter_only_var = tk.BooleanVar(value=True)
        self.scrape_filter_only_chk = tk.Checkbutton(opt_row, text="Only matches",
                                                     variable=self.scrape_filter_only_var, bg=PANEL, fg=TEXT,
                                                     selectcolor=BG, activebackground=PANEL, activeforeground=TEXT,
                                                     font=("Segoe UI", 8), relief="flat", highlightthickness=0)
        self.scrape_filter_only_chk.pack(side="left")
        
        # Limit pages
        tk.Label(opt_row, text="Max Pgs:", font=("Segoe UI", 8), bg=PANEL, fg=TEXTSUB).pack(side="left", padx=(8, 2))
        self.scrape_max_pages_var = tk.StringVar(value="0")
        self.scrape_max_pages_ent = tk.Entry(opt_row, textvariable=self.scrape_max_pages_var, bg=CARD, fg=TEXT,
                                             insertbackground=TEXT, relief="flat", font=("Segoe UI", 8), width=4,
                                             highlightthickness=1, highlightbackground="#30363D")
        self.scrape_max_pages_ent.pack(side="left")

        tk.Label(opt_row, text="(DD-MM-YYYY)", font=("Segoe UI", 7, "italic"), bg=PANEL, fg=MUTED).pack(side="right", padx=(4, 0))
        
        # Action Buttons
        act_row = tk.Frame(scrape_fr, bg=PANEL)
        act_row.pack(fill="x", pady=(4, 0))
        
        self.btn_start_scrape = self._btn(act_row, "  Start Portal Scrape  ", self._do_portal_scrape_start, bg=ACCENT2)
        self.btn_start_scrape.pack(side="left")
        
        self.btn_stop_scrape = self._btn(act_row, "  Stop  ", self._do_portal_scrape_stop, bg=CARD, fg=ERR)
        self.btn_stop_scrape.pack(side="right")
        self.btn_stop_scrape.configure(state="disabled")

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
                
        copy_btn = tk.Button(log_hdr, text="📋 Copy", command=copy_log,
                             bg=CARD, fg=TEXTSUB, relief="flat", font=("Segoe UI", 8),
                             padx=4, pady=0, activebackground=ACCENT2, activeforeground=TEXT,
                             cursor="hand2")
        copy_btn.pack(side="right")

        log_fr = tk.Frame(left, bg=CARD,
                          highlightthickness=1, highlightbackground="#30363D")
        log_fr.pack(fill="both", expand=True)
        self.log_txt = tk.Text(log_fr, bg=CARD, fg=TEXTSUB, relief="flat",
                               font=("Consolas",8), state="disabled", wrap="word",
                               highlightthickness=0)
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
        self.tab_matrix = tk.Frame(self.notebook, bg=BG)
        self.tab_analytics = tk.Frame(self.notebook, bg=BG)
        
        self.notebook.add(self.tab_table, text="  Table View  ")
        self.notebook.add(self.tab_calendar, text="  Calendar View  ")
        self.notebook.add(self.tab_matrix, text="  Matrix View  ")
        self.notebook.add(self.tab_analytics, text="  Analytics View  ")

        # Build Table tab layouts
        self._build_table_tab()

        # Build Calendar tab layouts
        self._build_calendar_tab()

        # Build Matrix tab layouts
        self._build_matrix_tab()

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
            BG: "#161B22"
        }
        hover_bg = hover_colors.get(bg, "#30363D")
        
        btn.bind("<Enter>", lambda e: btn.configure(bg=hover_bg))
        btn.bind("<Leave>", lambda e: btn.configure(bg=bg))
        return btn

    def _log(self, level, msg):
        import logger
        logger.log(level, msg)

    def _write_to_log_widget(self, level, msg):
        self.log_txt.configure(state="normal")
        ts = datetime.now().strftime("%H:%M:%S")
        icons = {
            "ok": "✓ ",
            "warn": "⚠ ",
            "err": "✗ ",
            "info": "ℹ "
        }
        icon = icons.get(level, "")
        self.log_txt.insert("end", f"[{ts}] {icon}{msg}\n", level)
        self.log_txt.see("end")
        self.log_txt.configure(state="disabled")
        self.update_idletasks()

    def _poll_log_queue(self):
        import logger
        logger.update_heartbeat()  # keep watchdog informed the main thread is alive
        while not logger.log_queue.empty():
            try:
                level, msg = logger.log_queue.get_nowait()
                self._write_to_log_widget(level, msg)
            except Exception:
                break
        self.after(50, self._poll_log_queue)

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
        TAB_NAMES = ["Table View", "Calendar View", "Matrix View", "Analytics View"]
        try:
            selected_tab = self.notebook.index(self.notebook.select())
            _logger_mod.log_tab_change(TAB_NAMES[selected_tab] if selected_tab < len(TAB_NAMES) else str(selected_tab))
            if selected_tab == 1:
                self._update_calendar()
                self._update_details()
            elif selected_tab == 2:
                self._update_matrix()
            elif selected_tab == 3:
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
