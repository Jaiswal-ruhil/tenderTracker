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

# Workers mixin
from workers import WorkersMixin

class TenderApp(tk.Tk, WorkersMixin):
    def __init__(self):
        super().__init__()
        self.title("GEM Tender Logger  v4")
        self.configure(bg=BG)
        self.geometry("1600x900")
        self.minsize(900, 600)
        self.state('zoomed')

        # UI Path & Breadcrumbs Setup
        self.ui_path_stack = ["UI/MAIN/TAB/TABLE"]
        
        # Monkey patch tk.Toplevel to track UI Paths
        orig_toplevel_init = tk.Toplevel.__init__
        app_self = self
        
        def new_toplevel_init(toplevel_self, parent=None, *args, **kwargs):
            p = parent if parent is not None else app_self
            orig_toplevel_init(toplevel_self, p, *args, **kwargs)
            
            try:
                if not app_self or not app_self.winfo_exists():
                    return
                if p != app_self and not str(p).startswith(str(app_self)):
                    return
            except Exception:
                return

            class_name = toplevel_self.__class__.__name__
            path_map = {
                "SettingsDialog": "UI/DIALOG/SETTINGS",
                "FirmsDialog": "UI/DIALOG/FIRMS",
                "TagsDialog": "UI/DIALOG/TAGS",
                "CommentsDialog": "UI/DIALOG/COMMENTS",
                "FilterRulesDialog": "UI/DIALOG/FILTER_RULES",
                "AlertViewer": "UI/DIALOG/ALERT_VIEWER",
                "InterventionDialog": "UI/DIALOG/INTERVENTION",
            }
            
            path = path_map.get(class_name)
            if not path:
                path = f"UI/DIALOG/{class_name.replace('Dialog', '').upper()}"
                
            try:
                app_self.push_ui_path(path)
            except Exception:
                pass
            
            orig_title = toplevel_self.title
            def new_title(new_title_str=None, *args, **kwargs):
                res = orig_title(new_title_str, *args, **kwargs) if new_title_str is not None else orig_title()
                if new_title_str:
                    try:
                        if not app_self or not app_self.winfo_exists():
                            return res
                    except Exception:
                        return res
                    cleaned_title = re.sub(r'[^a-zA-Z0-9]', '_', str(new_title_str)).strip('_').upper()
                    cleaned_title = re.sub(r'_+', '_', cleaned_title)
                    new_elem = f"UI/DIALOG/{cleaned_title}"
                    
                    try:
                        if len(app_self.ui_path_stack) > 0:
                            last = app_self.ui_path_stack[-1]
                            if last.startswith("UI/DIALOG/TOPLEVEL") or last == f"UI/DIALOG/{class_name.upper()}":
                                app_self.ui_path_stack[-1] = new_elem
                                app_self._draw_ui_path()
                    except Exception:
                        pass
                return res
            toplevel_self.title = new_title
            
            def on_destroy(event):
                if event.widget == toplevel_self:
                    try:
                        if app_self and app_self.winfo_exists():
                            app_self.pop_ui_path()
                    except Exception:
                        pass
            toplevel_self.bind("<Destroy>", on_destroy)
            
        tk.Toplevel.__init__ = new_toplevel_init


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
        self.ui_path_lbl = tk.Label(
            top, text="[UI/MAIN/TAB/TABLE]", font=("Segoe UI", 9, "bold"),
            bg=BG, fg=ACCENT, padx=8, pady=3, relief="solid", borderwidth=1
        )
        self.ui_path_lbl.pack(side="left", padx=15)
        self.fy_lbl = tk.Label(top, text="", font=FL, bg=ACCENT2, fg=TEXT, padx=10, pady=3)
        self.fy_lbl.pack(side="right", padx=(6,0))
        self._btn(top, "⚙ Settings", self._show_settings, bg=CARD).pack(side="right")
        self._btn(top, "🏢 Manage Firms", self._show_firms_dialog, bg=CARD).pack(side="right", padx=(0, 6))

        # Notebook for all views (Tenders Table, Ingest, Calendar, Analytics)
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=(4,0))

        self.tab_table = tk.Frame(self.notebook, bg=BG)
        self.tab_dashboard = tk.Frame(self.notebook, bg=BG)
        self.tab_ingest = tk.Frame(self.notebook, bg=BG)
        self.tab_calendar = tk.Frame(self.notebook, bg=BG)
        self.tab_analytics = tk.Frame(self.notebook, bg=BG)
        self.tab_chat = tk.Frame(self.notebook, bg=BG)
        
        self.notebook.add(self.tab_table, text="  Tenders Table  ")
        self.notebook.add(self.tab_dashboard, text="  Dashboard  ")
        self.notebook.add(self.tab_ingest, text="  Import / Ingest  ")
        self.notebook.add(self.tab_calendar, text="  Calendar View  ")
        self.notebook.add(self.tab_analytics, text="  Analytics  ")
        self.notebook.add(self.tab_chat, text="  Chat with Ruhil  ")

        # ── Import & Ingest Tab Layout ────────────────────────────────────────
        # Split ingest into left (paste/import options) and right (logs)
        ingest_pane = tk.PanedWindow(self.tab_ingest, orient="horizontal", bg=BG,
                                     sashwidth=6, sashrelief="flat", handlesize=0)
        ingest_pane.pack(fill="both", expand=True, padx=10, pady=10)

        ingest_left = tk.Frame(ingest_pane, bg=BG)
        ingest_pane.add(ingest_left, minsize=400, stretch="always")

        ingest_right = tk.Frame(ingest_pane, bg=BG)
        ingest_pane.add(ingest_right, minsize=450, stretch="always")

        tk.Label(ingest_left, text="Paste GEM Tender Block(s)", font=("Segoe UI", 9, "bold"),
                 bg=BG, fg=MUTED).pack(anchor="w", pady=(4, 2))
        
        self.paste_txt = tk.Text(ingest_left, bg=CARD, fg=TEXT, insertbackground=TEXT,
                                 relief="flat", font=FH, height=15,
                                 highlightthickness=1, highlightbackground="#30363D",
                                 highlightcolor=ACCENT2, wrap="word", undo=True,
                                 padx=8, pady=8)
        self.paste_txt.pack(fill="both", expand=True, pady=(0, 4))
        
        tk.Label(ingest_left, text="Paste tender text, bid numbers, URLs, or local PDF paths. One item per line also works.",
                 font=("Segoe UI", 8), bg=BG, fg=TEXTSUB).pack(anchor="w", pady=(2, 4))

        # progress
        self.progress = ttk.Progressbar(ingest_left, orient="horizontal",
                                        mode="determinate", length=200)
        self.progress.pack(fill="x", pady=(0, 4))
        self.prog_lbl = tk.Label(ingest_left, text="", font=("Segoe UI", 8),
                                 bg=BG, fg=TEXTSUB)
        self.prog_lbl.pack(anchor="w")

        # buttons
        btn_row = tk.Frame(ingest_left, bg=BG)
        btn_row.pack(fill="x", pady=(4, 8))
        self._btn(btn_row, "Parse", lambda: self._do_parse(force_llm=False),
                  bg=ACCENT2, pad=6).pack(side="left")
        self._btn(btn_row, "Parse with AI", lambda: self._do_parse(force_llm=True),
                  bg=ACCENT, pad=6).pack(side="left", padx=6)
        self._btn(btn_row, "Fetch Details",
                  self._do_fetch_all, bg=CARD, pad=6).pack(side="left")
        self._btn(btn_row, "Clear Input", lambda: self.paste_txt.delete("1.0", "end"),
                  bg=CARD).pack(side="left", padx=6)

        # log header
        log_hdr = tk.Frame(ingest_right, bg=BG)
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
        
        # Alert button
        alert_btn = tk.Button(log_hdr, text="🔔 Alerts", command=self._show_alert_viewer,
                             bg=CARD, fg=TEXTSUB, relief="flat", font=("Segoe UI", 8),
                             padx=6, pady=0, activebackground=ACCENT2, activeforeground=TEXT,
                             cursor="hand2")
        alert_btn.pack(side="right", padx=(0, 6))
                
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

        log_fr = tk.Frame(ingest_right, bg=CARD,
                          highlightthickness=1, highlightbackground="#30363D")
        log_fr.pack(fill="both", expand=True)
        self.log_txt = tk.Text(log_fr, bg=CARD, fg=TEXTSUB, relief="flat",
                               font=("Consolas", 8), state="disabled", wrap="word",
                               highlightthickness=0, padx=8, pady=8)
        lsb = ttk.Scrollbar(log_fr, orient="vertical", command=self.log_txt.yview)
        self.log_txt.configure(yscrollcommand=lsb.set)
        lsb.pack(side="right", fill="y")
        self.log_txt.pack(fill="both", expand=True, padx=4, pady=4)
        for tag, col in [("ok", SUCCESS), ("warn", WARN), ("err", ERR), ("info", ACCENT2)]:
            self.log_txt.tag_configure(tag, foreground=col)

        # Build Table tab layouts
        self._build_table_tab()

        # Build Dashboard tab layout
        self._build_dashboard_tab()

        # Build Calendar tab layouts
        self._build_calendar_tab()

        # Build Analytics tab layouts
        self._build_analytics_tab()
        
        # Build Chat tab layouts
        self._build_chat_tab()

        # Bind notebook tab change event to refresh calendar if switched to it
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        # Bind global focus and click listeners to update UI path breadcrumbs
        self.bind_all("<FocusIn>", self._on_focus_in)
        self.bind_all("<Button-1>", self._on_button_click)

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

    def _copy_to_clipboard(self, text):
        try:
            self.clipboard_clear()
            self.clipboard_append(text)
            self.update()
        except Exception as e:
            self._log("err", f"Failed to copy to clipboard: {e}")

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
            if self.winfo_exists():
                self._poll_log_after_id = self.after(50, self._poll_log_queue)
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
        if hasattr(self, '_poll_log_after_id') and self._poll_log_after_id:
            try:
                self.after_cancel(self._poll_log_after_id)
            except Exception:
                pass
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
        TAB_NAMES = ["Tenders Table", "Dashboard", "Import / Ingest", "Calendar View", "Analytics", "Chat with Ruhil"]
        try:
            selected_tab = self.notebook.index(self.notebook.select())
            _logger_mod.log_tab_change(TAB_NAMES[selected_tab] if selected_tab < len(TAB_NAMES) else str(selected_tab))
            
            TAB_PATHS = [
                "UI/MAIN/TAB/TABLE",
                "UI/MAIN/TAB/DASHBOARD",
                "UI/MAIN/TAB/INGEST",
                "UI/MAIN/TAB/CALENDAR",
                "UI/MAIN/TAB/ANALYTICS",
                "UI/MAIN/TAB/CHAT"
            ]
            if selected_tab < len(TAB_PATHS):
                self.ui_path_stack[0] = TAB_PATHS[selected_tab]
                self._draw_ui_path()

            if selected_tab == self.notebook.index(self.tab_dashboard):
                self.dashboard_tab.load_data()
            elif selected_tab == self.notebook.index(self.tab_calendar):
                self._update_calendar()
                self._update_details()
            elif selected_tab == self.notebook.index(self.tab_analytics):
                self._update_analytics()
            elif selected_tab == self.notebook.index(self.tab_chat):
                self.chat_tab._update_status()
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
            
            is_initial = not getattr(self, "_initial_load_done", False)
            if is_initial:
                self._initial_load_done = True
                if hasattr(self, "table_tab"):
                    self.table_tab.set_dynamic_default_date_filter()
                else:
                    self._refresh_table_view()
            else:
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
            
            # Run active learning from comments on startup
            try:
                db.apply_active_learning_from_comments()
            except Exception as al_err:
                self._log("warn", f"Could not run active learning from comments on startup: {al_err}")
            
            display_path = db.DB_FILE.replace(os.path.expanduser("~"), "~")
            self._set_status(f"Database: {display_path}", SUCCESS)
            self._log("info", f"Loaded {len(self._records)} historical tender(s) from database: {db.DB_FILE}")
        except Exception as e:
            self._log("err", f"Failed to load tenders from database: {e}")
            self._set_status("Database error", ERR)
    
    def _show_alert_viewer(self):
        """Show the alert viewer dialog."""
        from components.alert_viewer import AlertViewer
        if not hasattr(self, 'alert_viewer'):
            self.alert_viewer = AlertViewer(self, self)
        self.alert_viewer.show()

    # ── Dialog Spawning Methods ───────────────────────────────────────────
    def _show_settings(self):
        from dialogs import SettingsDialog
        SettingsDialog(self)
        
    def _show_firms_dialog(self):
        from dialogs import FirmsDialog
        FirmsDialog(self)
        
    def _show_tags_dialog(self):
        from dialogs import TagsDialog
        TagsDialog(self)
        
    def _show_comments_dialog(self):
        from dialogs import CommentsDialog
        CommentsDialog(self)
        
    def _show_filter_rules_dialog(self):
        from dialogs import FilterRulesDialog
        FilterRulesDialog(self)

    # ── Table Tab Adapters ────────────────────────────────────────────────
    def _build_table_tab(self):
        from components.table_tab import TableTab
        # Instantiate the TableTab component and pack it
        self.table_tab = TableTab(self.tab_table, self)
        self.table_tab.pack(fill="both", expand=True)

        # Expose child widgets/variables on TenderApp namespace for backward compatibility
        self.search_var = self.table_tab.search_var
        self.search_ent = self.table_tab.search_ent
        self.view_var = self.table_tab.view_var
        self.status_view_var = self.table_tab.status_view_var
        self.date_filter_preset_var = self.table_tab.date_filter_preset_var
        self.date_filter_type_var = self.table_tab.date_filter_type_var
        self.date_from_var = self.table_tab.date_from_var
        self.date_to_var = self.table_tab.date_to_var
        self.tv = self.table_tab.tv
        self.custom_date_frame = self.table_tab.custom_date_frame
        
    def _refresh_table_view(self):
        self.table_tab.refresh_table_view()
        
    def _get_tender_status(self, rec, inc_kws, exc_kws, settings=None):
        return self.table_tab.get_tender_status(rec, inc_kws, exc_kws, settings=settings)
        
    def _is_bid_in_dont_wants(self, bid_no_or_id):
        return self.table_tab.is_bid_in_dont_wants(bid_no_or_id)

    def _show_datepicker(self, button, var):
        self.table_tab._show_datepicker(button, var)

    def _cancel_edit(self, event=None):
        self.table_tab.table_view.cancel_edit(event)

    def _open_associated_pdf(self):
        self.table_tab.open_associated_pdf()

    def _link_associated_pdf(self):
        self.table_tab.link_associated_pdf()

    def _unlink_associated_pdf(self):
        self.table_tab.unlink_associated_pdf()

    def _start_filing_process(self):
        self.table_tab.start_filing_process()

    def _open_tender_url(self):
        self.table_tab.open_tender_url()

    def _copy_bid_number(self):
        self.table_tab.copy_bid_number()

    def _save_selected(self):
        self.table_tab.save_selected()

    def _mark_selected_want(self):
        self.table_tab.mark_selected_want()

    def _mark_want_and_learn(self):
        self.table_tab.mark_want_and_learn()

    def _mark_selected_dont_want(self):
        self.table_tab.mark_selected_dont_want()

    def _reset_selected_tag(self):
        self.table_tab.reset_selected_tag()

    def _set_selected_filing_status(self, status):
        self.table_tab.set_selected_filing_status(status)

    def _apply_column_visibility(self):
        self.table_tab.apply_column_visibility()

    def _show_column_selector(self):
        self.table_tab.show_column_selector()

    def _copy_table_output(self):
        self.table_tab.copy_table_output()

    def _tv_insert(self, rec):
        return self.table_tab.table_view.tv_insert(rec)

    def _refresh_alt(self):
        self.table_tab.table_view.refresh_alt()

    # ── Keyboard Shortcuts and Helpers ─────────────────────────────────────
    def _bind_shortcuts(self):
        self.bind("<Control-f>", lambda e: self._shortcut_focus_search())
        self.bind("<Control-s>", lambda e: self._shortcut_focus_search())
        self.bind("<Control-v>", lambda e: self._shortcut_clipboard_parse())
        self.bind("<Control-r>", lambda e: self._reload())
        self.bind("<Control-Alt-s>", lambda e: self._show_settings())
        self.bind("<Delete>", lambda e: self._shortcut_delete_selected())
        self.bind("<Escape>", lambda e: self._cancel_edit())
        # Additional shortcuts for common actions
        self.bind("<Control-e>", lambda e: self._shortcut_export_excel())
        self.bind("<Control-a>", lambda e: self._shortcut_select_all())
        self.bind("<Control-c>", lambda e: self._shortcut_copy_selected())
        self.bind("<Control-d>", lambda e: self._shortcut_start_filing())
        self.bind("<F5>", lambda e: self._reload())
        self.bind("<Control-1>", lambda e: self._shortcut_switch_tab(0))
        self.bind("<Control-2>", lambda e: self._shortcut_switch_tab(1))
        self.bind("<Control-3>", lambda e: self._shortcut_switch_tab(2))
        self.bind("<Control-4>", lambda e: self._shortcut_switch_tab(3))
        self.bind("<Control-5>", lambda e: self._shortcut_switch_tab(4))

    def _shortcut_focus_search(self):
        try:
            self.notebook.select(0)
            self.search_ent.focus_set()
            self.search_ent.selection_range(0, "end")
        except Exception:
            pass
        return "break"

    def _shortcut_clipboard_parse(self):
        focused = self.focus_get()
        if isinstance(focused, (tk.Text, tk.Entry, ttk.Entry, ttk.Combobox)):
            return None
        try:
            clipboard = self.clipboard_get()
            if clipboard:
                self.notebook.select(self.tab_ingest)
                self.paste_txt.delete("1.0", "end")
                self.paste_txt.insert("1.0", clipboard)
                self._do_parse()
        except Exception:
            pass
        return "break"

    def _shortcut_delete_selected(self):
        focused = self.focus_get()
        if isinstance(focused, (tk.Text, tk.Entry, ttk.Entry, ttk.Combobox)):
            return None
        try:
            if self.notebook.index(self.notebook.select()) == 0:
                self._del_sel()
        except Exception:
            pass
        return "break"

    def _shortcut_export_excel(self):
        focused = self.focus_get()
        if isinstance(focused, (tk.Text, tk.Entry, ttk.Entry, ttk.Combobox)):
            return None
        try:
            if self.notebook.index(self.notebook.select()) == 0:
                self.table_tab.export_selected()
        except Exception:
            pass
        return "break"

    def _shortcut_select_all(self):
        focused = self.focus_get()
        if isinstance(focused, (tk.Text, tk.Entry, ttk.Entry, ttk.Combobox)):
            return None
        try:
            if self.notebook.index(self.notebook.select()) == 0:
                self.table_tab.table_view.select_all()
        except Exception:
            pass
        return "break"

    def _shortcut_copy_selected(self):
        focused = self.focus_get()
        if isinstance(focused, (tk.Text, tk.Entry, ttk.Entry, ttk.Combobox)):
            return None
        try:
            if self.notebook.index(self.notebook.select()) == 0:
                self.table_tab.copy_table_output()
        except Exception:
            pass
        return "break"

    def _shortcut_start_filing(self):
        focused = self.focus_get()
        if isinstance(focused, (tk.Text, tk.Entry, ttk.Entry, ttk.Combobox)):
            return None
        try:
            if self.notebook.index(self.notebook.select()) == 0:
                self.table_tab.start_filing_process()
        except Exception:
            pass
        return "break"

    def _shortcut_switch_tab(self, tab_index):
        try:
            self.notebook.select(tab_index)
        except Exception:
            pass
        return "break"

    def _del_sel(self):
        self.table_tab.del_sel()

    def _build_dashboard_tab(self):
        from components.dashboard_tab import DashboardTab
        self.dashboard_tab = DashboardTab(self.tab_dashboard, self)
        self.dashboard_tab.pack(fill="both", expand=True)

    # ── Calendar Tab Adapters ─────────────────────────────────────────────
    def _build_calendar_tab(self):
        from components.calendar_tab import CalendarTab
        # Instantiate the CalendarTab component
        self.calendar_tab = CalendarTab(self.tab_calendar, self)
        self.calendar_tab.pack(fill="both", expand=True)

        # Expose widgets/variables on TenderApp namespace for backward compatibility
        self.cal_month_lbl = self.calendar_tab.cal_month_lbl
        self.cal_sel_date_lbl = self.calendar_tab.cal_sel_date_lbl
        self.cal_details_fr = self.calendar_tab.cal_details_fr

    def _cal_prev_month(self):
        self.calendar_tab.cal_prev_month()

    def _cal_next_month(self):
        self.calendar_tab.cal_next_month()

    def _parse_date_str(self, date_str):
        return self.calendar_tab._parse_date_str(date_str)

    def _get_events_for_date(self, target_date, inc_kws=None, exc_kws=None):
        return self.calendar_tab.get_events_for_date(target_date, inc_kws, exc_kws)

    def _update_calendar(self):
        self.calendar_tab.update_calendar()

    def _select_date(self, target_date):
        self.calendar_tab.select_date(target_date)

    def _update_details(self):
        self.calendar_tab.update_details()

    def _locate_in_table(self, bid):
        self.calendar_tab.locate_in_table(bid)

    # ── Analytics Tab Adapters ────────────────────────────────────────────
    def _build_analytics_tab(self):
        from components.analytics_tab import AnalyticsTab
        # Instantiate the AnalyticsTab component
        self.analytics_tab = AnalyticsTab(self.tab_analytics, self)
        self.analytics_tab.pack(fill="both", expand=True)

        # Expose widgets on TenderApp namespace for backward compatibility
        self.lbl_total_tenders = self.analytics_tab.lbl_total_tenders
        self.lbl_matching_wants = self.analytics_tab.lbl_matching_wants
        self.lbl_filtered_dont_wants = self.analytics_tab.lbl_filtered_dont_wants
        self.lbl_not_filed = self.analytics_tab.lbl_not_filed
        self.lbl_firm_matched = self.analytics_tab.lbl_firm_matched

    def _update_analytics(self):
        self.analytics_tab.update_analytics()

    def _redraw_chart(self):
        self.analytics_tab.redraw_chart()

    def _redraw_firm_chart(self):
        self.analytics_tab.redraw_firm_chart()

    def _show_all_tenders(self):
        self.analytics_tab.show_all_tenders()

    def _show_matching_wants(self):
        self.analytics_tab.show_matching_wants()

    def _show_filtered_dont_wants(self):
        self.analytics_tab.show_filtered_dont_wants()

    def _show_not_filed_wants(self):
        self.analytics_tab.show_not_filed_wants()

    def _show_firm_matched(self):
        self.analytics_tab.show_firm_matched()

    def _filter_by_ministry(self, name):
        self.analytics_tab._filter_by_ministry(name)

    def _filter_by_firm(self, name):
        self.analytics_tab._filter_by_firm(name)

    def _build_chat_tab(self):
        from components.chat_tab import ChatTab
        self.chat_tab = ChatTab(self.tab_chat, self)
        self.chat_tab.pack(fill="both", expand=True)

    def push_ui_path(self, path: str):
        """Push a new path segment to the UI breadcrumbs stack."""
        if not hasattr(self, 'ui_path_stack'):
            self.ui_path_stack = ["UI/MAIN/TAB/TABLE"]
        self.ui_path_stack.append(path)
        self.current_focus_path = ""
        self._draw_ui_path()
        
    def pop_ui_path(self):
        """Pop the last path segment from the UI breadcrumbs stack."""
        if hasattr(self, 'ui_path_stack') and len(self.ui_path_stack) > 1:
            self.ui_path_stack.pop()
        self.current_focus_path = ""
        self._draw_ui_path()
        
    def _draw_ui_path(self):
        """Redraw the UI path label in the top bar."""
        if hasattr(self, 'ui_path_lbl') and hasattr(self, 'ui_path_stack'):
            base_stack = " ➔ ".join(self.ui_path_stack)
            focused_suffix = getattr(self, "current_focus_path", "")
            if focused_suffix:
                full_display = f"[{base_stack} ➔ {focused_suffix}]"
            else:
                full_display = f"[{base_stack}]"
            self.ui_path_lbl.configure(text=full_display)
            self.update_idletasks()

    def _track_dialog_path(self, dialog, path: str):
        """Manually track a dialog window lifecycle for path tracking."""
        self.push_ui_path(path)
        def on_destroy(event):
            widget = event.widget
            if isinstance(widget, str):
                try:
                    widget = self.nametowidget(widget)
                except KeyError:
                    pass
            if widget == dialog:
                self.pop_ui_path()
        dialog.bind("<Destroy>", on_destroy)

    def _on_focus_in(self, event):
        path = self._resolve_widget_path(event.widget)
        if path:
            self.current_focus_path = path
            self._draw_ui_path()

    def _on_button_click(self, event):
        path = self._resolve_widget_path(event.widget)
        if path:
            self.current_focus_path = path
            self._draw_ui_path()

    def _resolve_widget_path(self, widget):
        if not widget:
            return ""
        if isinstance(widget, str):
            try:
                widget = self.nametowidget(widget)
            except KeyError:
                return ""
                
        if hasattr(widget, "ui_path"):
            return widget.ui_path
            
        parts = []
        curr = widget
        while curr:
            if curr == self:
                break
                
            if isinstance(curr, str):
                try:
                    curr = self.nametowidget(curr)
                except KeyError:
                    break
                    
            name = curr.winfo_name()
            if isinstance(curr, tk.Toplevel):
                title_str = ""
                try:
                    title_str = curr.title()
                except:
                    pass
                if title_str:
                    cleaned_title = re.sub(r'[^a-zA-Z0-9]', '_', str(title_str)).strip('_').upper()
                    cleaned_title = re.sub(r'_+', '_', cleaned_title)
                    parts.append(f"DIALOG/{cleaned_title}")
                else:
                    parts.append(f"DIALOG/{curr.__class__.__name__.upper()}")
                break
                
            part_name = ""
            if hasattr(curr, "ui_path_name"):
                part_name = curr.ui_path_name
            elif isinstance(curr, (tk.Button, ttk.Button)):
                btn_text = ""
                try:
                    btn_text = curr.cget("text")
                except:
                    pass
                if btn_text:
                    cleaned = re.sub(r'[^a-zA-Z0-9]', '_', str(btn_text)).strip('_').upper()
                    cleaned = re.sub(r'_+', '_', cleaned)
                    part_name = f"BTN/{cleaned}"
                else:
                    part_name = f"BTN/{name.strip('!').upper()}"
            elif isinstance(curr, (tk.Entry, ttk.Entry, tk.Text)):
                part_name = f"INPUT/{name.strip('!').upper()}"
            elif isinstance(curr, tk.Label):
                lbl_text = ""
                try:
                    lbl_text = curr.cget("text")
                except:
                    pass
                if lbl_text:
                    cleaned = re.sub(r'[^a-zA-Z0-9]', '_', str(lbl_text)).strip('_').upper()
                    cleaned = re.sub(r'_+', '_', cleaned)
                    part_name = f"LBL/{cleaned}"
                else:
                    part_name = f"LBL/{name.strip('!').upper()}"
            elif isinstance(curr, ttk.Notebook):
                part_name = "NOTEBOOK"
                
            if not part_name:
                part_name = name.strip('!').upper()
                
            parts.append(part_name)
            curr = curr.master
            
        parts.reverse()
        return "/".join(p for p in parts if p)



