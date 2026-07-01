import os
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

class TenderApp(tk.Tk, CalendarTabMixin, MatrixTabMixin, AnalyticsTabMixin, DialogsMixin):
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

    # ── styles ────────────────────────────────────────────────────────────────
    def _style(self):
        s = ttk.Style(self); s.theme_use("clam")
        s.configure(".", background=BG, foreground=TEXT, font=FB)
        s.configure("Treeview", background=PANEL, foreground=TEXT,
                    fieldbackground=PANEL, rowheight=26, borderwidth=0, font=FL)
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
        
        tk.Label(date_fr, text="To:", font=("Segoe UI", 8), bg=PANEL, fg=TEXTSUB).pack(side="left", padx=(4, 2))
        self.scrape_date_to_var = tk.StringVar()
        self.scrape_date_to_ent = tk.Entry(date_fr, textvariable=self.scrape_date_to_var, bg=CARD, fg=TEXT,
                                           insertbackground=TEXT, relief="flat", font=("Segoe UI", 8), width=8,
                                           highlightthickness=1, highlightbackground="#30363D")
        self.scrape_date_to_ent.pack(side="left", padx=(0, 4))

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

        # Table Tab Header (formerly right header)
        hdr = tk.Frame(self.tab_table, bg=BG)
        hdr.pack(fill="x", pady=(4,4))
        tk.Label(hdr, text="Parsed Tenders", font=("Segoe UI",9,"bold"),
                 bg=BG, fg=MUTED).pack(side="left")
        self.count_lbl = tk.Label(hdr, text="0 rows", font=FL, bg=BG, fg=TEXTSUB)
        self.count_lbl.pack(side="left", padx=8)

        self._btn(hdr,"Select All",   self._sel_all,    bg=CARD).pack(side="right",padx=2)
        self._btn(hdr,"Delete Selected", self._del_sel, bg=CARD, fg=ERR).pack(side="right",padx=2)
        self._btn(hdr,"  Fetch Selected (Selenium)  ",
                  self._do_fetch_sel, bg="#2D333B").pack(side="right",padx=2)
        self._btn(hdr,"  Save Selected to Excel  ",
                  self._save_selected, bg=ACCENT, pad=10).pack(side="right",padx=(6,2))

        # ── Filter & Refine Bar ──────────────────────────────────────────────
        filter_fr = tk.Frame(self.tab_table, bg=PANEL, padx=10, pady=6,
                             highlightthickness=1, highlightbackground="#30363D")
        filter_fr.pack(fill="x", pady=(0, 6))

        # Search box
        tk.Label(filter_fr, text="Search:", font=FL, bg=PANEL, fg=MUTED).pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *args: self._refresh_table_view())
        
        self.search_ent = tk.Entry(filter_fr, textvariable=self.search_var, bg=CARD, fg=TEXT,
                              insertbackground=TEXT, relief="flat", font=FL, width=22,
                              highlightthickness=1, highlightbackground="#30363D",
                              highlightcolor=ACCENT2)
        self.search_ent.pack(side="left", padx=(4, 15))

        # View dropdown
        tk.Label(filter_fr, text="Category View:", font=FL, bg=PANEL, fg=MUTED).pack(side="left")
        
        self.view_var = tk.StringVar(value="All Tenders")
        view_opt = ttk.Combobox(filter_fr, textvariable=self.view_var, 
                                values=["All Tenders", "Wants (Matches)", "Don't Wants (Filtered)"],
                                state="readonly", font=FL, width=20)
        view_opt.pack(side="left", padx=4)
        view_opt.bind("<<ComboboxSelected>>", lambda e: self._refresh_table_view())
        
        # Style Combobox listbox dropdown
        self.option_add("*TCombobox*Listbox.background", CARD)
        self.option_add("*TCombobox*Listbox.foreground", TEXT)
        self.option_add("*TCombobox*Listbox.selectBackground", SEL_BG)

        # Refine rules and copy table buttons
        self._btn(filter_fr, "⚙ Refine Rules...", self._show_filter_rules_dialog, bg=CARD).pack(side="right")
        self._btn(filter_fr, "📋 Copy Table", self._copy_table_output, bg=CARD).pack(side="right", padx=(0, 6))

        # Create a PanedWindow inside self.tab_table for resizable Treeview and Detail Side-Panel
        table_pane = tk.PanedWindow(self.tab_table, orient="horizontal", bg=BG,
                                    sashwidth=4, sashrelief="flat", handlesize=0)
        table_pane.pack(fill="both", expand=True)

        # treeview frame (placed in the left pane of table_pane)
        tv_fr = tk.Frame(table_pane, bg=BG)
        table_pane.add(tv_fr, minsize=400, stretch="always")

        cols = [c[0] for c in TV_COLS]
        self.tv = ttk.Treeview(tv_fr, columns=cols, show="headings",
                               selectmode="extended")
        for cid, lbl, w in TV_COLS:
            self.tv.heading(cid, text=lbl, command=lambda c=cid: self._sort(c))
            self.tv.column(cid, width=w, minwidth=40, stretch=False)

        vsb = ttk.Scrollbar(tv_fr, orient="vertical",   command=self.tv.yview)
        hsb = ttk.Scrollbar(tv_fr, orient="horizontal", command=self.tv.xview)
        self.tv.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tv.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        tv_fr.rowconfigure(0, weight=1); tv_fr.columnconfigure(0, weight=1)

        # Detail Side-Panel frame (placed in the right pane of table_pane)
        self.detail_panel = tk.Frame(table_pane, bg=PANEL, highlightthickness=1, highlightbackground="#30363D", padx=12, pady=10)
        table_pane.add(self.detail_panel, minsize=320, stretch="always")

        # Detail Title
        detail_title = tk.Label(self.detail_panel, text="TENDER DETAILS", font=FT, bg=PANEL, fg=TEXT)
        detail_title.pack(anchor="w", pady=(0, 6))

        # Detail Scrollable Text widget
        txt_fr = tk.Frame(self.detail_panel, bg=PANEL)
        txt_fr.pack(fill="both", expand=True)

        self.detail_txt = tk.Text(txt_fr, bg=CARD, fg=TEXT, insertbackground=TEXT,
                                  relief="flat", font=FL, wrap="word", highlightthickness=0)
        self.detail_txt.pack(side="left", fill="both", expand=True)

        detail_vsb = ttk.Scrollbar(txt_fr, orient="vertical", command=self.detail_txt.yview)
        detail_vsb.pack(side="right", fill="y")
        self.detail_txt.configure(yscrollcommand=detail_vsb.set)
        
        # Configure tags for detail_txt formatting & highlighting
        self.detail_txt.tag_configure("header", foreground=ACCENT2, font=("Segoe UI", 10, "bold"))
        self.detail_txt.tag_configure("label", foreground=MUTED, font=("Segoe UI", 9, "bold"))
        self.detail_txt.tag_configure("value", foreground=TEXT, font=("Segoe UI", 9))
        self.detail_txt.tag_configure("match_inc", background="#1A4A2A", foreground=SUCCESS, font=("Segoe UI", 9, "bold"))
        self.detail_txt.tag_configure("match_exc", background="#4A1A1A", foreground=ERR, font=("Segoe UI", 9, "bold"))

        # Initialize detail text state
        self._clear_detail_panel()

        # Bind MouseWheel events for self.detail_txt
        def on_detail_mousewheel(event):
            if event.num == 5 or event.delta < 0:
                self.detail_txt.yview_scroll(1, "units")
            elif event.num == 4 or event.delta > 0:
                self.detail_txt.yview_scroll(-1, "units")
        self.detail_txt.bind("<MouseWheel>", on_detail_mousewheel)
        self.detail_txt.bind("<Button-4>", on_detail_mousewheel)
        self.detail_txt.bind("<Button-5>", on_detail_mousewheel)

        self.tv.tag_configure("alt",     background="#1C2128")
        self.tv.tag_configure("fetched", background="#1A2E1A", foreground=SUCCESS)
        self.tv.tag_configure("saved",   background="#1A3A2A", foreground=SUCCESS)
        self.tv.tag_configure("fetching",background="#2A2A1A", foreground=WARN)
        self.tv.tag_configure("dont_want", foreground="#5D6570")
        self.tv.tag_configure("manual_want", background="#1A3324")

        self.tv.bind("<Double-1>", self._on_dbl)
        self.tv.bind("<Button-1>", self._cancel_edit)
        self.tv.bind("<<TreeviewSelect>>", self._on_treeview_select)

        # Context Menu
        self.ctx_menu = tk.Menu(self, tearoff=0, bg=PANEL, fg=TEXT, 
                                activebackground=SEL_BG, activeforeground=TEXT, font=FL)
        self.ctx_menu.add_command(label="Mark as Want (Keep)", command=self._mark_selected_want)
        self.ctx_menu.add_command(label="Mark as Don't Want (Ignore)", command=self._mark_selected_dont_want)
        self.ctx_menu.add_command(label="Reset Manual Tag", command=self._reset_selected_tag)
        self.ctx_menu.add_command(label="Manage Tags...", command=self._show_tags_dialog)
        self.ctx_menu.add_separator()
        self.ctx_menu.add_command(label="Delete Selected", command=self._del_sel)
        self.ctx_menu.add_command(label="Fetch Details (Selenium)", command=self._do_fetch_sel)
        self.ctx_menu.add_command(label="Save Selected to Excel", command=self._save_selected)
        
        self.tv.bind("<Button-3>", self._show_context_menu)
        self.tv.bind("<Button-2>", self._show_context_menu) # For macOS

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
        btn = tk.Button(parent, text=text, command=cmd,
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
            self._refresh_table_view()
            
            display_path = db.DB_FILE.replace(os.path.expanduser("~"), "~")
            self._set_status(f"Database: {display_path}", SUCCESS)
            self._log("info", f"Loaded {len(self._records)} historical tender(s) from database: {db.DB_FILE}")
        except Exception as e:
            self._log("err", f"Failed to load tenders from database: {e}")
            self._set_status("Database error", ERR)



    def _do_parse(self):
        raw = self.paste_txt.get("1.0","end").strip()
        if not raw: self._log("warn","Paste area is empty."); return
        self._log("info", f"--- Parse started {datetime.now().strftime('%H:%M:%S')} ---")
        self._set_prog(0,"Processing input…")

        def worker():
            import pypdf
            from concurrent.futures import ThreadPoolExecutor, as_completed
            
            # Step 1: Split raw text into initial blocks.
            initial_blocks = split_blocks(raw)
            
            # Process each block from split_blocks:
            # If it starts with a BID NO label, process it as a single block.
            # Otherwise, split it by lines (handling lists of PDF paths, URLs, or raw bid numbers).
            blocks_to_process = []
            for blk in initial_blocks:
                if re.match(r"^\s*BID\s*(?:NO|Number)(?:\.|\b)\s*:", blk, re.I):
                    blocks_to_process.append(blk)
                else:
                    for line in blk.splitlines():
                        ln = line.strip().strip('"\'')
                        if ln:
                            blocks_to_process.append(ln)
                
            total = len(blocks_to_process)
            self._log("info", f"Found {total} item(s) to process.")
            
            recs = []
            completed_count = 0
            
            def process_one(i, blk):
                # Check if block is a local PDF path on disk
                if blk.lower().endswith(".pdf"):
                    if os.path.exists(blk):
                        self.after(0, lambda f=blk: self._log("info", f"[{i}/{total}] Reading PDF: {os.path.basename(f)}"))
                        try:
                            reader = pypdf.PdfReader(blk)
                            pdf_text = ""
                            for page in reader.pages:
                                t = page.extract_text()
                                if t:
                                    pdf_text += t + "\n"
                            md_text = convert_pdf_text_to_markdown(pdf_text)
                            rec = parse_one(md_text)
                            if rec.get("bid_no"):
                                self.after(0, lambda b=rec['bid_no']: self._log("ok", f"Parsed PDF {b}"))
                                return rec
                            else:
                                self.after(0, lambda f=blk: self._log("warn", f"Failed to find Bid Number in PDF: {os.path.basename(f)}"))
                        except Exception as ex:
                            self.after(0, lambda f=blk, err=ex: self._log("err", f"Failed to read PDF {os.path.basename(f)}: {err}"))
                        return None
                    else:
                        self.after(0, lambda: self._log("warn", f"SKIP — PDF file does not exist on disk: {blk}"))
                        return None
                
                # Parse block as text first
                rec = parse_one(blk)
                bid_no = rec.get("bid_no")
                bid_url = rec.get("bid_url")
                
                if not bid_no and not bid_url:
                    # Try to reconstruct from raw line if it's a URL or Bid Number
                    cleaned_blk = blk.strip().strip('"\'')
                    line_val = re.sub(r"^(?:BID\s*(?:NO|Number)(?:\.|\b)\s*:\s*)", "", cleaned_blk, flags=re.I).strip()
                    line_val = re.sub(r"\s+View\s+Corrigendum.*$", "", line_val, flags=re.I).strip()
                    
                    if "showbidDocument" in cleaned_blk:
                        bid_url = cleaned_blk
                        doc_id = cleaned_blk.rstrip('/').split('/')[-1]
                        bid_no = f"GEM/2026/B/{doc_id}"
                    elif re.match(r"^GEM/\d{4}/[A-Z0-9]+/\d+$", line_val, re.I):
                        bid_no = line_val
                    else:
                        snippet = blk.strip().replace("\n", " ")
                        if len(snippet) > 40:
                            snippet = snippet[:40] + "..."
                        self.after(0, lambda: self._log("warn", f"SKIP — No valid Bid Number or URL found in block: \"{snippet}\""))
                        return None
                
                # Check if it is in Don't Wants
                id_to_check = bid_no if bid_no else bid_url
                if self._is_bid_in_dont_wants(id_to_check):
                    self.after(0, lambda: self._log("info", f"Skipping {id_to_check}: Already in database 'Don't Wants'"))
                    return None
                
                # Determine if we need to download the PDF:
                has_details = any(rec.get(k) for k in ("items", "dept", "start_date", "end_date", "ministry", "category"))
                
                if not has_details:
                    # Need details. Check if we already have it fully parsed in database records
                    existing_rec = None
                    for r in self._records:
                        if bid_no and r.get("bid_no") == bid_no:
                            existing_rec = r
                            break
                        if bid_url and r.get("bid_url") == bid_url:
                            existing_rec = r
                            break
                            
                    if existing_rec and any(existing_rec.get(k) for k in ("items", "dept", "start_date")):
                        self.after(0, lambda: self._log("info", f"Using existing database details for {bid_no}"))
                        return existing_rec
                    else:
                        self.after(0, lambda: self._log("info", f"Downloading PDF to fetch details for {bid_no or bid_url}..."))
                        try:
                            dl_dir = os.path.dirname(db.DB_FILE)
                            dest_path = None
                            
                            if bid_url and "showbidDocument" in bid_url:
                                doc_id = bid_url.rstrip('/').split('/')[-1]
                                filename = f"GeM-Bidding-{doc_id}.pdf"
                                dest_path = os.path.abspath(os.path.join(dl_dir, filename))
                                
                                import urllib.request
                                req = urllib.request.Request(
                                    bid_url,
                                    headers={
                                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                                    }
                                )
                                with urllib.request.urlopen(req) as response:
                                    with open(dest_path, 'wb') as out_file:
                                        out_file.write(response.read())
                            elif bid_no:
                                headless_opt = db.load_settings().get("selenium_headless", False)
                                dest_path = download_tender_pdf(bid_no, dl_dir, log_fn=self._log, headless=headless_opt)
                                
                            if dest_path and os.path.exists(dest_path):
                                self.after(0, lambda: self._log("ok", f"PDF downloaded successfully for {bid_no}. Parsing..."))
                                reader = pypdf.PdfReader(dest_path)
                                pdf_text = ""
                                for page in reader.pages:
                                    t = page.extract_text()
                                    if t:
                                        pdf_text += t + "\n"
                                md_text = convert_pdf_text_to_markdown(pdf_text)
                                pdf_rec = parse_one(md_text)
                                if bid_url and "bid_url" not in pdf_rec:
                                    pdf_rec["bid_url"] = bid_url
                                return pdf_rec
                            else:
                                self.after(0, lambda: self._log("err", f"Failed to download PDF for {bid_no or bid_url}"))
                                if not rec.get("bid_no") and bid_no:
                                    rec["bid_no"] = bid_no
                                if not rec.get("bid_url") and bid_url:
                                    rec["bid_url"] = bid_url
                                return rec
                        except Exception as dl_err:
                            self.after(0, lambda: self._log("err", f"Error downloading PDF for {bid_no}: {dl_err}"))
                            return rec
                else:
                    self.after(0, lambda: self._log("ok", f"Parsed details directly from text for {bid_no}"))
                    return rec
                    
            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = {executor.submit(process_one, idx, blk): (idx, blk) for idx, blk in enumerate(blocks_to_process, 1)}
                for fut in futures:
                    idx, blk = futures[fut]
                    try:
                        res_rec = fut.result(timeout=15.0)
                        if res_rec:
                            recs.append(res_rec)
                    except (TimeoutError, Exception) as e:
                        filename = os.path.basename(blk) if blk.lower().endswith(".pdf") else blk[:20]
                        self.after(0, lambda fn=filename, err=e: self._log("err", f"[{idx}/{total}] PDF read timed out or failed (skipped): {fn}: {err}"))
                    
                    completed_count += 1
                    prog_val = int(completed_count / total * 100)
                    self.after(0, lambda p=prog_val, c=completed_count: self._set_prog(p, f"Processed {c}/{total}…"))
                    
            self.after(0, lambda: self._set_prog(100, "Done."))
            self.after(0, lambda: self._add_rows(recs, total))
        threading.Thread(target=worker, daemon=True).start()

    def _add_rows(self, recs, total):
        added_count = 0
        updated_count = 0
        
        settings = db.load_settings()
        inc_raw = settings.get("include_keywords", "")
        exc_raw = settings.get("exclude_keywords", "")
        inc_kws = [k.strip().lower() for k in inc_raw.split(",") if k.strip()]
        exc_kws = [k.strip().lower() for k in exc_raw.split(",") if k.strip()]
        
        children = self.tv.get_children()
        records_by_bid = {}
        for iid in children:
            bid_no = self.tv.set(iid, "bid_no")
            if bid_no:
                matched_rec = None
                for r in self._records:
                    if r.get("bid_no") == bid_no:
                        matched_rec = r
                        break
                if matched_rec:
                    records_by_bid[bid_no] = (matched_rec, iid)

        new_wants = []
        for rec in recs:
            bid_no = rec.get("bid_no")
            if bid_no in records_by_bid:
                existing_rec, iid = records_by_bid[bid_no]
                merged_fields = []
                for k, v in rec.items():
                    if v and (k not in existing_rec or not str(existing_rec[k]).strip()):
                        existing_rec[k] = v
                        if k in TV_IDS:
                            self.tv.set(iid, k, v)
                        merged_fields.append(k)
                if merged_fields:
                    updated_count += 1
                    self.tv.item(iid, tags=("fetched",))
                    self._log("ok", f"Updated {bid_no} with {len(merged_fields)} new fields")
                else:
                    self._log("info", f"Skipped {bid_no}: Already exists with identical details")
            else:
                is_want = self._get_tender_status(rec, inc_kws, exc_kws)
                rec["is_want_derived"] = is_want
                self._records.append(rec)
                self._tv_insert(rec)
                added_count += 1
                
                if is_want:
                    new_wants.append(rec)
                    self._log("ok", f"Added {bid_no} to database (matches Wants)")
                else:
                    self._log("info", f"Added {bid_no} to database (Don't Want / Filtered)")

        db.save_all_tenders(self._records)
        self._refresh_table_view()
        
        if new_wants:
            w_count = len(new_wants)
            first_w = new_wants[0]
            first_bid = first_w.get('bid_no', '')
            first_item = first_w.get('items', '')
            desc = f"{first_bid}: {first_item[:30]}..." if w_count == 1 \
                   else f"{first_bid} and {w_count - 1} other(s)"
            self._show_toast("New Want Tender Match!", desc, "ok")
            
        skipped = total - (added_count + updated_count)
        msg = f"Parsed {total} block(s): {added_count} added"
        if updated_count:
            msg += f", {updated_count} updated"
        if skipped > 0:
            msg += f", {skipped} skipped"
        self._log("info", msg)
        self._set_status(msg, SUCCESS if (added_count or updated_count) else WARN)
        self._set_prog(100, "Done.")
        if recs: self.paste_txt.delete("1.0","end")
        try:
            if self.notebook.index(self.notebook.select()) == 1:
                self._update_calendar()
                self._update_details()
        except:
            pass

    def _do_portal_scrape_start(self):
        if self._scrape_running or self._fetch_running:
            self._log("warn", "An operation is already running (scrape or fetch). Please wait.")
            return

        query = self.scrape_query_var.get().strip()
        max_pages_str = self.scrape_max_pages_var.get().strip()
        
        try:
            max_pages = int(max_pages_str) if max_pages_str else 0
        except ValueError:
            messagebox.showerror("Invalid Input", "Max Pages must be an integer.", parent=self)
            return

        # Date filter validation
        date_filter_type = self.scrape_date_type_var.get()
        from_date_str = self.scrape_date_from_var.get().strip()
        to_date_str = self.scrape_date_to_var.get().strip()
        
        if date_filter_type in ("Start Date", "End Date"):
            if from_date_str:
                from_date_parsed = self._parse_date_str(from_date_str)
                if not from_date_parsed:
                    messagebox.showerror("Invalid Date", "From Date must be in DD-MM-YYYY format.", parent=self)
                    return
            if to_date_str:
                to_date_parsed = self._parse_date_str(to_date_str)
                if not to_date_parsed:
                    messagebox.showerror("Invalid Date", "To Date must be in DD-MM-YYYY format.", parent=self)
                    return

        if not _try_import_selenium():
            messagebox.showerror("Missing library",
                "Please install Selenium:\n\npip install selenium webdriver-manager", parent=self)
            return

        self._scrape_running = True
        self._stop_scrape_flag = False
        
        self.btn_start_scrape.configure(state="disabled")
        self.btn_stop_scrape.configure(state="normal")
        self.scrape_query_ent.configure(state="disabled")
        self.scrape_max_pages_ent.configure(state="disabled")
        self.scrape_filter_only_chk.configure(state="disabled")
        self.scrape_date_type_cb.configure(state="disabled")
        self.scrape_date_from_ent.configure(state="disabled")
        self.scrape_date_to_ent.configure(state="disabled")

        self._log("info", f"--- Portal Search & Scrape started: query='{query}', max_pages={max_pages} ---")
        if date_filter_type in ("Start Date", "End Date"):
            self._log("info", f"Date filter active: {date_filter_type} from {from_date_str or 'any'} to {to_date_str or 'any'}")
        self._set_status("Starting portal scraping...", ACCENT2)

        def worker():
            headless_opt = db.load_settings().get("selenium_headless", False)
            
            def stop_check():
                return self._stop_scrape_flag

            def record_callback(page_recs):
                recs = []
                date_filter_type = self.scrape_date_type_var.get()
                from_date_parsed = self._parse_date_str(self.scrape_date_from_var.get().strip())
                to_date_parsed = self._parse_date_str(self.scrape_date_to_var.get().strip())
                
                for blk in page_recs:
                    rec = parse_one(blk)
                    if rec.get("bid_no"):
                        # Date filter check
                        if date_filter_type in ("Start Date", "End Date"):
                            fld_key = "start_date" if date_filter_type == "Start Date" else "end_date"
                            bid_date_str = rec.get(fld_key)
                            bid_date = self._parse_date_str(bid_date_str)
                            if bid_date:
                                if from_date_parsed and bid_date < from_date_parsed:
                                    self._log("info", f"Skipping {rec['bid_no']}: {date_filter_type} {bid_date_str} < From Date")
                                    continue
                                if to_date_parsed and bid_date > to_date_parsed:
                                    self._log("info", f"Skipping {rec['bid_no']}: {date_filter_type} {bid_date_str} > To Date")
                                    continue
                            else:
                                if from_date_parsed or to_date_parsed:
                                    self._log("info", f"Skipping {rec['bid_no']}: {date_filter_type} missing/unparseable")
                                    continue

                        # Check if we should only save matches
                        if self.scrape_filter_only_var.get():
                            settings = db.load_settings()
                            inc_raw = settings.get("include_keywords", "")
                            exc_raw = settings.get("exclude_keywords", "")
                            inc_kws = [k.strip().lower() for k in inc_raw.split(",") if k.strip()]
                            exc_kws = [k.strip().lower() for k in exc_raw.split(",") if k.strip()]
                            
                            is_want = self._get_tender_status(rec, inc_kws, exc_kws)
                            if not is_want:
                                self._log("info", f"Skipping filtered bid: {rec['bid_no']}")
                                continue
                        recs.append(rec)
                if recs:
                    self.after(0, lambda r=recs: self._add_scraped_rows(r))

            scraped_total = scrape_portal_search(
                query=query,
                max_pages=max_pages,
                headless=headless_opt,
                log_fn=self._log,
                stop_check_fn=stop_check,
                record_callback=record_callback
            )

            def scrape_finished():
                self._scrape_running = False
                self.btn_start_scrape.configure(state="normal")
                self.btn_stop_scrape.configure(state="disabled")
                self.scrape_query_ent.configure(state="normal")
                self.scrape_max_pages_ent.configure(state="normal")
                self.scrape_filter_only_chk.configure(state="normal")
                self.scrape_date_type_cb.configure(state="readonly")
                self.scrape_date_from_ent.configure(state="normal")
                self.scrape_date_to_ent.configure(state="normal")
                
                msg = f"Portal scrape done: {scraped_total} bid(s) processed"
                self._set_status(msg, SUCCESS)
                try:
                    if self.notebook.index(self.notebook.select()) == 1:
                        self._update_calendar()
                        self._update_details()
                except:
                    pass

            self.after(0, scrape_finished)

        threading.Thread(target=worker, daemon=True).start()

    def _do_portal_scrape_stop(self):
        if self._scrape_running:
            self._log("info", "Stopping portal scraper... Please wait for Chrome to close.")
            self._stop_scrape_flag = True
            self.btn_stop_scrape.configure(state="disabled")

    def _add_scraped_rows(self, recs):
        added_count = 0
        updated_count = 0
        
        settings = db.load_settings()
        inc_raw = settings.get("include_keywords", "")
        exc_raw = settings.get("exclude_keywords", "")
        inc_kws = [k.strip().lower() for k in inc_raw.split(",") if k.strip()]
        exc_kws = [k.strip().lower() for k in exc_raw.split(",") if k.strip()]
        
        children = self.tv.get_children()
        records_by_bid = {}
        for iid in children:
            bid_no = self.tv.set(iid, "bid_no")
            if bid_no:
                matched_rec = None
                for r in self._records:
                    if r.get("bid_no") == bid_no:
                        matched_rec = r
                        break
                if matched_rec:
                    records_by_bid[bid_no] = (matched_rec, iid)

        for rec in recs:
            bid_no = rec.get("bid_no")
            is_want = self._get_tender_status(rec, inc_kws, exc_kws)
            rec["is_want_derived"] = is_want
            
            if bid_no in records_by_bid:
                existing_rec, iid = records_by_bid[bid_no]
                merged_fields = []
                for k, v in rec.items():
                    if v and (k not in existing_rec or not str(existing_rec[k]).strip()):
                        existing_rec[k] = v
                        if k in TV_IDS:
                            self.tv.set(iid, k, v)
                        merged_fields.append(k)
                if merged_fields:
                    updated_count += 1
                    self.tv.item(iid, tags=("fetched",))
            else:
                self._records.append(rec)
                self._tv_insert(rec)
                added_count += 1

        db.save_all_tenders(self._records)
        self._refresh_table_view()
        
        msg = f"Portal Scraper: {added_count} added, {updated_count} updated"
        self._log("ok", msg)

    # ── Step 2 — Selenium fetch ───────────────────────────────────────────────
    def _do_fetch_all(self):
        """Fetch details for ALL records that have a bid_url."""
        targets = [(i, r) for i,r in enumerate(self._records) if r.get("bid_url")]
        self._run_fetch(targets, "all")

    def _do_fetch_sel(self):
        """Fetch details for SELECTED rows only."""
        sel = self.tv.selection()
        if not sel:
            self._log("warn","No rows selected."); return
        targets = []
        for iid in sel:
            bid_no = self.tv.set(iid, "bid_no")
            if bid_no:
                for idx, r in enumerate(self._records):
                    if r.get("bid_no") == bid_no and r.get("bid_url"):
                        targets.append((idx, r))
                        break
        if not targets:
            self._log("warn","Selected rows have no Bid URL."); return
        self._run_fetch(targets, "selected")

    def _run_fetch(self, targets, label):
        if self._fetch_running:
            self._log("warn","A fetch is already running. Please wait."); return
        if not targets:
            self._log("warn","No rows with Bid URL to fetch."); return

        if not _try_import_selenium():
            messagebox.showerror("Missing library",
                "Please install Selenium:\n\npip install selenium webdriver-manager")
            return

        self._fetch_running = True
        self._log("info", f"--- Selenium fetch started: {len(targets)} {label} row(s) ---")
        self._set_prog(0, f"Fetching 0/{len(targets)}…")

        iid_map = {self.tv.set(iid, "bid_no"): iid for iid in self.tv.get_children() if self.tv.set(iid, "bid_no")}

        def worker():
            total = len(targets)
            from concurrent.futures import ThreadPoolExecutor, as_completed
            
            completed_count = 0
            
            def fetch_one(idx, rec):
                bid = rec.get("bid_no","?")
                iid = iid_map.get(bid)
                url = rec["bid_url"]
                
                self.after(0, lambda: self._log("info", f"Fetching details for {bid}"))
                if iid: self.after(0, lambda i=iid: self.tv.item(i, tags=("fetching",)))
                
                try:
                    headless_opt = db.load_settings().get("selenium_headless", False)
                    extra = scrape_bid_page(url, log_fn=self._log, headless=headless_opt)
                    if extra:
                        rec.update(extra)
                        rec["is_fetched"] = True
                        
                        def update_tv(i=iid, r=rec, e=extra):
                            if i:
                                for cid in TV_IDS:
                                    if cid in r:
                                        self.tv.set(i, cid, r[cid])
                                self.tv.item(i, tags=("fetched",))
                            db.upsert_tender(r)
                            
                        self.after(0, update_tv)
                        self.after(0, lambda e_len=len(extra): self._log("ok", f"{bid} — merged {e_len} extra fields"))
                    else:
                        if iid: self.after(0, lambda i=iid: self.tv.item(i, tags=()))
                        self.after(0, lambda: self._log("warn", f"{bid} — no extra data scraped"))
                except Exception as ex:
                    if iid: self.after(0, lambda i=iid: self.tv.item(i, tags=()))
                    self.after(0, lambda b=bid, err=ex: self._log("err", f"Failed to fetch details for {b}: {err}"))

            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = {executor.submit(fetch_one, idx, rec): rec for idx, rec in targets}
                for fut in as_completed(futures):
                    completed_count += 1
                    prog_val = int(completed_count / total * 100)
                    self.after(0, lambda p=prog_val, c=completed_count: self._set_prog(p, f"Fetched {c}/{total}…"))
                    
            self._fetch_running = False
            self.after(0, lambda: self._set_prog(100, "Fetch complete."))
            msg = f"Selenium fetch done: {total} URL(s) processed"
            self.after(0, lambda: self._log("info", f"--- {msg} ---"))
            
            # Show toast when fetch is done
            self._show_toast("Detail Fetching Complete", f"Successfully processed {total} URL(s).", "info")
            
            def fetch_finished():
                self._set_status(msg, SUCCESS)
                try:
                    if self.notebook.index(self.notebook.select()) == 1:
                        self._update_calendar()
                        self._update_details()
                except:
                    pass
            self.after(0, fetch_finished)

        threading.Thread(target=worker, daemon=True).start()

    # ── table helpers ─────────────────────────────────────────────────────────
    def _tv_insert(self, rec):
        raw_vals = []
        for c in TV_IDS:
            val = rec.get(c, "")
            if c == "tags" and isinstance(val, list):
                val = ", ".join(val)
            raw_vals.append(val)
        vals = tuple(raw_vals)
        tags = []
        
        # Wants / Don't Wants tags
        manual_want = rec.get("is_want")
        derived_want = rec.get("is_want_derived", True)
        
        if manual_want is False:
            tags.append("dont_want")
        elif manual_want is True:
            tags.append("manual_want")
        elif derived_want is False:
            tags.append("dont_want")
            
        if rec.get("is_saved"):
            tags.append("saved")
        elif rec.get("is_fetched"):
            tags.append("fetched")
            
        return self.tv.insert("","end", values=vals, tags=tuple(tags))

    def _refresh_alt(self):
        for i, iid in enumerate(self.tv.get_children()):
            cur_tags = self.tv.item(iid,"tags")
            special = [t for t in cur_tags if t in ("fetched","saved","fetching","dont_want","manual_want")]
            if not special:
                self.tv.item(iid, tags=("alt",) if i%2 else ())

    _sort_state = {}
    def _sort(self, col):
        rev = self._sort_state.get(col, False)
        items = [(self.tv.set(k,col),k) for k in self.tv.get_children()]
        items.sort(reverse=rev)
        for i,(_,k) in enumerate(items): self.tv.move(k,"",i)
        self._sort_state[col] = not rev
        self._refresh_alt()

    def _on_dbl(self, event):
        region = self.tv.identify_region(event.x, event.y)
        if region != "cell": return
        col = self.tv.identify_column(event.x)
        iid = self.tv.identify_row(event.y)
        if not iid: return
        col_idx = int(col[1:])-1
        if col_idx >= len(TV_IDS): return
        col_id = TV_IDS[col_idx]
        bbox = self.tv.bbox(iid, col)
        if not bbox: return
        x,y,w,h = bbox
        var = tk.StringVar(value=self.tv.set(iid, col_id))
        e = tk.Entry(self.tv, textvariable=var, bg=SEL_BG, fg=TEXT,
                     insertbackground=TEXT, relief="flat", font=FL,
                     highlightthickness=0)
        e.place(x=x,y=y,width=w,height=h); e.focus_set(); e.select_range(0,"end")
        self._editing = (iid, col_id, e)
        def commit(ev=None):
            nv = var.get(); self.tv.set(iid,col_id,nv)
            bid_no = self.tv.set(iid, "bid_no")
            if bid_no:
                for r in self._records:
                    if r.get("bid_no") == bid_no:
                        r[col_id] = nv
                        if col_id == "category":
                            import parser
                            parser.learn_category_mapping(r.get("items"), nv)
                        break
                if col_id == "category":
                    import parser
                    for r in self._records:
                        raw_text = r.get("items") or r.get("category") or ""
                        r["category"] = parser.map_category(raw_text)
                    self._refresh_table_view()
            e.destroy(); self._editing=None
            db.save_all_tenders(self._records)
            try:
                selected_tab = self.notebook.index(self.notebook.select())
                if selected_tab == 1:
                    self._update_calendar()
                    self._update_details()
                elif selected_tab == 2:
                    self._update_matrix()
                elif selected_tab == 3:
                    self._update_analytics()
            except:
                pass
        e.bind("<Return>",commit); e.bind("<Tab>",commit)
        e.bind("<Escape>",lambda ev: e.destroy())

    def _cancel_edit(self, event):
        if self._editing:
            try: self._editing[2].destroy()
            except: pass
            self._editing=None

    def _sel_all(self):
        self.tv.selection_set(self.tv.get_children())

    def _del_sel(self):
        sel = self.tv.selection()
        if not sel: return
        
        bids_to_del = []
        for iid in sel:
            bid_no = self.tv.set(iid, "bid_no")
            if bid_no:
                bids_to_del.append(bid_no)
                
        self._records = [r for r in self._records if r.get("bid_no") not in bids_to_del]
        
        self._refresh_table_view()
        self._log("info", f"Deleted {len(sel)} row(s).")
        db.save_all_tenders(self._records)
        try:
            if self.notebook.index(self.notebook.select()) == 1:
                self._update_calendar()
                self._update_details()
        except:
            pass

    def _save_selected(self):
        sel = self.tv.selection()
        if not sel:
            self._log("warn","No rows selected."); return
        folder = self.save_folder.get().strip()
        if not folder:
            self._set_status("Set output folder first.", ERR); return
        os.makedirs(folder, exist_ok=True)
        fy   = financial_year(datetime.now())
        pat  = db.load_settings().get("excel_filename_pattern", "GEM_Tenders_FY_{fy}")
        path = xl_path(folder, fy, pattern=pat)
        ensure_workbook(path)
        
        # Resolve selected records by bid_no
        recs = []
        bids_saved = []
        for iid in sel:
            bid_no = self.tv.set(iid, "bid_no")
            if bid_no:
                for r in self._records:
                    if r.get("bid_no") == bid_no:
                        recs.append(r)
                        bids_saved.append(bid_no)
                        break
        try:
            snos = xl_append(path, recs)
            msg = f"Saved {len(snos)} row(s) → {os.path.basename(path)}  (S.No {snos[0]}–{snos[-1]})"
            self._log("ok", msg); self._set_status(msg, SUCCESS); self._fy_tick()
            
            # Tag the rows in Treeview
            for iid in sel: 
                self.tv.item(iid, tags=("saved",))
                
            # Update records structure
            for r in self._records:
                if r.get("bid_no") in bids_saved:
                    r["is_saved"] = True
                    
            db.save_all_tenders(self._records)
        except Exception as ex:
            self._log("err", f"Save error: {ex}")
            messagebox.showerror("Save Error", str(ex))



    def _on_tab_changed(self, event):
        try:
            selected_tab = self.notebook.index(self.notebook.select())
            if selected_tab == 1:
                self._update_calendar()
                self._update_details()
            elif selected_tab == 2:
                self._update_matrix()
            elif selected_tab == 3:
                self._update_analytics()
        except Exception as e:
            self._log("err", f"Tab changed error: {e}")

    # ── Filtering & Refinement ────────────────────────────────────────────────
    def _get_tender_status(self, rec, inc_kws, exc_kws):
        is_want = rec.get("is_want")
        if is_want is not None:
            return is_want
            
        search_fields = [
            rec.get("items", ""),
            rec.get("category", ""),
            rec.get("ministry", ""),
            rec.get("dept", ""),
            rec.get("organisation", ""),
            rec.get("location", ""),
            rec.get("bid_no", "")
        ]
        combined_text = " ".join(search_fields).lower()
        
        def check_single_rule(rule):
            rule_clean = rule.strip()
            if not rule_clean:
                return False
            
            # Regex Rule Support
            if rule_clean.lower().startswith("rx:"):
                pattern = rule_clean[3:].strip()
                try:
                    import re
                    return bool(re.search(pattern, combined_text, re.I))
                except Exception:
                    return False
                    
            # Boolean Expression Support
            if " and " in rule_clean.lower() or " or " in rule_clean.lower() or "not " in rule_clean.lower() or "(" in rule_clean or ")" in rule_clean:
                return eval_expr(rule_clean.lower())
                
            # Standard Plain Substring Matching
            return rule_clean.lower() in combined_text

        def eval_expr(expr):
            import re
            parts = re.split(r"(\(|\)|\bnot\b|\band\b|\bor\b)", expr, flags=re.I)
            processed_tokens = []
            for p in parts:
                if p is None:
                    continue
                p_clean = p.strip()
                if not p_clean:
                    continue
                if p_clean.lower() in ("(", ")", "and", "or", "not"):
                    processed_tokens.append(p_clean.lower())
                else:
                    exists = p_clean.lower() in combined_text
                    processed_tokens.append("True" if exists else "False")
            
            expr_str = " ".join(processed_tokens)
            expr_str = re.sub(r"[^a-zA-Z0-9\s()&|!]", "", expr_str)
            try:
                if re.match(r"^[TrueFalse()andornot\s]+$", expr_str):
                    return bool(eval(expr_str))
            except Exception:
                pass
            return False

        matches_exc = False
        for rule in exc_kws:
            if check_single_rule(rule):
                matches_exc = True
                break
                
        if matches_exc:
            if inc_kws:
                for rule in inc_kws:
                    if check_single_rule(rule):
                        return True
            return False
            
        return True

    def _is_bid_in_dont_wants(self, bid_no_or_id):
        if not bid_no_or_id:
            return False
        target = bid_no_or_id.strip().lower()
        
        settings = db.load_settings()
        inc_raw = settings.get("include_keywords", "")
        exc_raw = settings.get("exclude_keywords", "")
        inc_kws = [k.strip().lower() for k in inc_raw.split(",") if k.strip()]
        exc_kws = [k.strip().lower() for k in exc_raw.split(",") if k.strip()]

        for r in self._records:
            r_bid_no = r.get("bid_no", "").strip().lower()
            r_bid_url = r.get("bid_url", "").strip().lower()
            
            match = False
            if target == r_bid_no:
                match = True
            elif target in r_bid_url:
                match = True
            elif "/" in r_bid_no and target == r_bid_no.split("/")[-1]:
                match = True
                
            if match:
                is_want = self._get_tender_status(r, inc_kws, exc_kws)
                if not is_want:
                    return True
        return False

    def _refresh_table_view(self):
        for child in self.tv.get_children():
            self.tv.delete(child)
            
        settings = db.load_settings()
        inc_raw = settings.get("include_keywords", "")
        exc_raw = settings.get("exclude_keywords", "")
        
        inc_kws = [k.strip().lower() for k in inc_raw.split(",") if k.strip()]
        exc_kws = [k.strip().lower() for k in exc_raw.split(",") if k.strip()]
        
        view_filter = self.view_var.get()
        search_text = self.search_var.get().strip().lower()
        
        visible_count = 0
        for rec in self._records:
            is_want = self._get_tender_status(rec, inc_kws, exc_kws)
            rec["is_want_derived"] = is_want
            
            if view_filter == "Wants (Matches)" and not is_want:
                continue
            if view_filter == "Don't Wants (Filtered)" and is_want:
                continue
                
            if search_text:
                combined_text = " ".join(str(v) for v in rec.values()).lower()
                if search_text not in combined_text:
                    continue
                    
            self._tv_insert(rec)
            visible_count += 1
            
        self._refresh_alt()
        self.count_lbl.configure(text=f"{visible_count} visible / {len(self._records)} total")

    def _show_context_menu(self, event):
        iid = self.tv.identify_row(event.y)
        if iid:
            if iid not in self.tv.selection():
                self.tv.selection_set(iid)
            self.ctx_menu.post(event.x_root, event.y_root)

    def _mark_selected_want(self):
        sel = self.tv.selection()
        if not sel: return
        for iid in sel:
            bid_no = self.tv.set(iid, "bid_no")
            if bid_no:
                for r in self._records:
                    if r.get("bid_no") == bid_no:
                        r["is_want"] = True
                        break
        db.save_all_tenders(self._records)
        self._refresh_table_view()
        self._log("ok", f"Marked {len(sel)} tender(s) as Want.")

    def _mark_selected_dont_want(self):
        sel = self.tv.selection()
        if not sel: return
        for iid in sel:
            bid_no = self.tv.set(iid, "bid_no")
            if bid_no:
                for r in self._records:
                    if r.get("bid_no") == bid_no:
                        r["is_want"] = False
                        break
        db.save_all_tenders(self._records)
        self._refresh_table_view()
        self._log("ok", f"Marked {len(sel)} tender(s) as Don't Want.")

    def _reset_selected_tag(self):
        sel = self.tv.selection()
        if not sel: return
        for iid in sel:
            bid_no = self.tv.set(iid, "bid_no")
            if bid_no:
                for r in self._records:
                    if r.get("bid_no") == bid_no:
                        r.pop("is_want", None)
                        break
        db.save_all_tenders(self._records)
        self._refresh_table_view()
        self._log("info", f"Reset manual tag for {len(sel)} tender(s).")

    def _copy_table_output(self):
        headers = [c[1] for c in TV_COLS]
        lines = ["\t".join(headers)]
        
        selected = self.tv.selection()
        rows_to_copy = selected if selected else self.tv.get_children()
        
        if not rows_to_copy:
            self._log("warn", "No data to copy.")
            return
            
        for iid in rows_to_copy:
            vals = [str(self.tv.set(iid, c[0])) for c in TV_COLS]
            lines.append("\t".join(vals))
            
        text_to_copy = "\n".join(lines)
        self.clipboard_clear()
        self.clipboard_append(text_to_copy)
        self.update()
        
        count = len(rows_to_copy)
        scope = "selected" if selected else "all visible"
        self._log("ok", f"Copied {count} {scope} row(s) to clipboard.")



    def _clear_detail_panel(self):
        self.detail_txt.configure(state="normal")
        self.detail_txt.delete("1.0", "end")
        self.detail_txt.insert("end", "\n\nSelect a tender from the table to view its full details here.", "value")
        self.detail_txt.configure(state="disabled")

    def _on_treeview_select(self, event):
        sel = self.tv.selection()
        if not sel:
            self._clear_detail_panel()
            return
            
        # Get selected record
        bid_no = self.tv.set(sel[0], "bid_no")
        rec = None
        for r in self._records:
            if r.get("bid_no") == bid_no:
                rec = r
                break
        if not rec:
            self._clear_detail_panel()
            return
            
        self.detail_txt.configure(state="normal")
        self.detail_txt.delete("1.0", "end")
        
        # Display fields in group categories
        categories = {
            "Basic Info": ["bid_no", "bid_url", "category", "items", "quantity", "location"],
            "Department Info": ["ministry", "dept", "organisation", "office"],
            "Dates & Schedule": ["start_date", "end_date", "bid_opening"],
            "Financial Details": ["est_value", "emd", "epbg", "min_turnover"],
            "Qualifications": ["exp_years", "contract_dur", "mii", "mse_pref", "mse_relax", "startup_relax"],
            "Status & Metadata": ["filing_status", "tags", "remarks"]
        }
        
        # Mapping DB field keys to human readable labels
        labels = {
            "bid_no": "Bid Number", "bid_url": "Bid URL", "category": "Category", "items": "Items", 
            "quantity": "Quantity", "location": "Location/Consignee", "ministry": "Ministry", 
            "dept": "Department", "organisation": "Organisation", "office": "Office", 
            "start_date": "Start Date", "end_date": "End Date", "bid_opening": "Bid Opening Date", 
            "est_value": "Estimated Value", "emd": "EMD Required", "epbg": "ePBG Required", 
            "min_turnover": "Min Turnover", "exp_years": "Exp Years Required", "contract_dur": "Contract Duration", 
            "mii": "MII Compliant", "mse_pref": "MSE Pref", "mse_relax": "MSE Relaxation", 
            "startup_relax": "Startup Relaxation", "filing_status": "Filing Status", "tags": "Tags", 
            "remarks": "Remarks"
        }
        
        first = True
        for cat_name, fields in categories.items():
            if not first:
                self.detail_txt.insert("end", "\n\n")
            first = False
            
            # Print Category Header
            self.detail_txt.insert("end", f"■ {cat_name}\n", "header")
            self.detail_txt.insert("end", "─" * 32 + "\n", "label")
            
            for field in fields:
                val = rec.get(field, "")
                if field == "tags":
                    if isinstance(val, list):
                        val = ", ".join(val)
                    elif not val:
                        val = "None"
                elif isinstance(val, bool):
                    val = "Yes" if val else "No"
                else:
                    val = str(val).strip()
                    
                if not val:
                    val = "N/A"
                    
                lbl = labels.get(field, field.capitalize())
                self.detail_txt.insert("end", f"{lbl}: ", "label")
                self.detail_txt.insert("end", f"{val}\n", "value")
                
        # Highlight match words (include / exclude keywords)
        settings = db.load_settings()
        inc_raw = settings.get("include_keywords", "")
        exc_raw = settings.get("exclude_keywords", "")
        
        inc_kws = [k.strip() for k in inc_raw.split(",") if k.strip()]
        exc_kws = [k.strip() for k in exc_raw.split(",") if k.strip()]
        
        # Apply include tags (case-insensitive)
        for kw in inc_kws:
            start = "1.0"
            while True:
                pos = self.detail_txt.search(kw, start, stopindex="end", nocase=True)
                if not pos:
                    break
                end = f"{pos} + {len(kw)}c"
                self.detail_txt.tag_add("match_inc", pos, end)
                start = end
                
        # Apply exclude tags (case-insensitive)
        for kw in exc_kws:
            start = "1.0"
            while True:
                pos = self.detail_txt.search(kw, start, stopindex="end", nocase=True)
                if not pos:
                    break
                end = f"{pos} + {len(kw)}c"
                self.detail_txt.tag_add("match_exc", pos, end)
                start = end
                
        self.detail_txt.configure(state="disabled")

    def _bind_shortcuts(self):
        self.bind("<Control-f>", lambda e: self._shortcut_focus_search())
        self.bind("<Control-s>", lambda e: self._shortcut_focus_search())
        self.bind("<Control-v>", lambda e: self._shortcut_clipboard_parse())
        self.bind("<Control-r>", lambda e: self._reload())
        self.bind("<Control-Alt-s>", lambda e: self._show_settings())
        self.bind("<Delete>", lambda e: self._shortcut_delete_selected())
        self.bind("<Escape>", lambda e: self._cancel_edit())

    def _shortcut_focus_search(self):
        try:
            self.notebook.select(0)
            self.search_ent.focus_set()
            self.search_ent.selection_range(0, "end")
        except Exception:
            pass
        return "break"

    def _shortcut_clipboard_parse(self):
        try:
            clipboard = self.clipboard_get()
            if clipboard:
                self.notebook.select(2)
                self.paste_txt.delete("1.0", "end")
                self.paste_txt.insert("1.0", clipboard)
                self._do_parse()
        except Exception:
            pass
        return "break"

    def _shortcut_delete_selected(self):
        try:
            if self.notebook.index(self.notebook.select()) == 0:
                self._delete_selected()
        except Exception:
            pass
        return "break"
