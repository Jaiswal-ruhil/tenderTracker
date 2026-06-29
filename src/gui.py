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
from scraper import scrape_bid_page, _try_import_selenium, download_tender_pdf
import db

class TenderApp(tk.Tk):
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

        # Calendar State
        self.cal_year = datetime.now().year
        self.cal_month = datetime.now().month
        self.cal_selected_date = datetime.now().date()
        self.cal_day_frames = []

        self._style()
        self._build()
        self._load_from_db()
        self._fy_tick()

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
        
        self.notebook.add(self.tab_table, text="  Table View  ")
        self.notebook.add(self.tab_calendar, text="  Calendar View  ")

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

        # treeview (now inside self.tab_table)
        tv_fr = tk.Frame(self.tab_table, bg=BG)
        tv_fr.pack(fill="both", expand=True)
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

        self.tv.tag_configure("alt",     background="#1C2128")
        self.tv.tag_configure("fetched", background="#1A2E1A", foreground=SUCCESS)
        self.tv.tag_configure("saved",   background="#1A3A2A", foreground=SUCCESS)
        self.tv.tag_configure("fetching",background="#2A2A1A", foreground=WARN)

        self.tv.bind("<Double-1>", self._on_dbl)
        self.tv.bind("<Button-1>", self._cancel_edit)

        # Build Calendar tab layouts
        self._build_calendar_tab()

        # Bind notebook tab change event to refresh calendar if switched to it
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        # status bar
        self.status = tk.Label(self, text="Ready", font=FL,
                               bg=PANEL, fg=MUTED, anchor="w", padx=10, pady=4)
        self.status.pack(fill="x", side="bottom")

    # ── widget helpers ────────────────────────────────────────────────────────
    def _btn(self, parent, text, cmd, bg=CARD, fg=TEXT, pad=6):
        return tk.Button(parent, text=text, command=cmd,
                         bg=bg, fg=fg, relief="flat", font=FL,
                         padx=pad, pady=4,
                         activebackground=ACCENT2, activeforeground=TEXT,
                         cursor="hand2")

    def _log(self, level, msg):
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

    def _set_status(self, msg, color=MUTED):
        self.status.configure(text=msg, fg=color)
        self.update_idletasks()

    def _set_prog(self, val, label=""):
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
                title="First Run: Select folder to store database (tenders_db.json)",
                parent=self
            )
            if selected_dir:
                db_path = os.path.join(os.path.abspath(selected_dir), "tenders_db.json")
                db.save_configured_db_path(db_path)
                db.init_db_path(db_path)
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
                self._log("warn", f"Prompt cancelled. Defaulting database to: {db_path}")
        else:
            db.init_db_path()

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
            for rec in self._records:
                self._tv_insert(rec)
            self._refresh_alt()
            self.count_lbl.configure(text=f"{len(self._records)} rows")
            
            display_path = db.DB_FILE.replace(os.path.expanduser("~"), "~")
            self._set_status(f"Database: {display_path}", SUCCESS)
            self._log("info", f"Loaded {len(self._records)} historical tender(s) from database: {db.DB_FILE}")
        except Exception as e:
            self._log("err", f"Failed to load tenders from database: {e}")
            self._set_status("Database error", ERR)

    def _change_db_location(self, parent_win=None):
        parent = parent_win or self
        old_path = db.DB_FILE
        new_dir = filedialog.askdirectory(
            title="Select new folder to store tenders_db.json",
            parent=parent
        )
        if not new_dir:
            return
            
        new_path = os.path.join(os.path.abspath(new_dir), "tenders_db.json")
        if os.path.abspath(new_path) == os.path.abspath(old_path):
            return
            
        move_data = messagebox.askyesnocancel(
            "Move Database",
            "Do you want to move your existing tenders data to the new location?\n\n"
            f"From: {old_path}\n"
            f"To: {new_path}",
            parent=parent
        )
        
        if move_data is None:
            return
            
        if move_data:
            if os.path.exists(old_path):
                try:
                    import shutil
                    shutil.move(old_path, new_path)
                    self._log("ok", f"Moved database file to: {new_path}")
                except Exception as e:
                    self._log("err", f"Failed to move database file: {e}")
                    messagebox.showerror("Error Moving File", f"Failed to move database file:\n\n{e}", parent=parent)
                    return
            else:
                self._log("info", "No existing database file found to move.")
        
        db.save_configured_db_path(new_path)
        db.init_db_path(new_path)
        
        try:
            self._records = db.load_all_tenders()
            for child in self.tv.get_children():
                self.tv.delete(child)
            for rec in self._records:
                self._tv_insert(rec)
            self._refresh_alt()
            self.count_lbl.configure(text=f"{len(self._records)} rows")
            
            display_path = db.DB_FILE.replace(os.path.expanduser("~"), "~")
            self._set_status(f"Database: {display_path}", SUCCESS)
            self._log("ok", f"Database successfully relocated to: {db.DB_FILE}")
            
            try:
                if self.notebook.index(self.notebook.select()) == 1:
                    self._update_calendar()
                    self._update_details()
            except:
                pass
        except Exception as e:
            self._log("err", f"Failed to load tenders from new database location: {e}")
            self._set_status("Database error", ERR)

    def _show_settings(self):
        win = tk.Toplevel(self)
        win.grab_set()
        win.transient(self)
        win.title("Settings")
        win.configure(bg=BG)
        win.resizable(False, False)

        x = self.winfo_x() + (self.winfo_width() - 600) // 2
        y = self.winfo_y() + (self.winfo_height() - 480) // 2
        win.geometry(f"600x480+{max(0, x)}+{max(0, y)}")

        # Title Label
        tk.Label(win, text="Application Settings", font=FT, bg=BG, fg=TEXT).pack(pady=(12, 10))

        # DB Frame
        db_frame = tk.Frame(win, bg=PANEL, padx=12, pady=10, highlightthickness=1, highlightbackground="#30363D")
        db_frame.pack(fill="x", padx=15, pady=6)
        
        tk.Label(db_frame, text="Local Database Storage Location:", font=("Segoe UI", 9, "bold"), bg=PANEL, fg=MUTED).pack(anchor="w")
        
        db_path_var = tk.StringVar(value=db.DB_FILE.replace(os.path.expanduser("~"), "~"))
        db_lbl = tk.Label(db_frame, textvariable=db_path_var, font=FL, bg=PANEL, fg=TEXTSUB, anchor="w")
        db_lbl.pack(fill="x", pady=(4, 4))
        
        def run_db_change():
            self._change_db_location(parent_win=win)
            db_path_var.set(db.DB_FILE.replace(os.path.expanduser("~"), "~"))
            
        btn_db_row = tk.Frame(db_frame, bg=PANEL)
        btn_db_row.pack(fill="x", pady=(4, 0))
        self._btn(btn_db_row, "Relocate Database...", run_db_change, bg=CARD).pack(side="left", padx=(0, 6))
        self._btn(btn_db_row, "Backup Database...", lambda: self._backup_db(win), bg=CARD).pack(side="left", padx=6)
        self._btn(btn_db_row, "Clear Database", lambda: self._clear_db(win), bg=CARD, fg=ERR).pack(side="right")

        # Excel Frame
        ex_frame = tk.Frame(win, bg=PANEL, padx=12, pady=10, highlightthickness=1, highlightbackground="#30363D")
        ex_frame.pack(fill="x", padx=15, pady=6)
        
        tk.Label(ex_frame, text="Excel Export Folder:", font=("Segoe UI", 9, "bold"), bg=PANEL, fg=MUTED).pack(anchor="w")
        
        ex_path_var = tk.StringVar(value=self.save_folder.get().replace(os.path.expanduser("~"), "~"))
        ex_lbl = tk.Label(ex_frame, textvariable=ex_path_var, font=FL, bg=PANEL, fg=TEXTSUB, anchor="w")
        ex_lbl.pack(side="left", fill="x", expand=True, pady=(4, 0))
        
        def run_ex_change():
            d = filedialog.askdirectory(title="Select folder for Excel Tenders Sheets", initialdir=self.save_folder.get(), parent=win)
            if d:
                resolved_dir = os.path.abspath(d)
                self.save_folder.set(resolved_dir)
                db.save_setting("excel_save_folder", resolved_dir)
                ex_path_var.set(resolved_dir.replace(os.path.expanduser("~"), "~"))
                self._log("ok", f"Excel export folder changed to: {resolved_dir}")
                
        self._btn(ex_frame, "Change Folder...", run_ex_change, bg=CARD).pack(side="right")

        # Excel Pattern Frame
        pat_frame = tk.Frame(win, bg=PANEL, padx=12, pady=10, highlightthickness=1, highlightbackground="#30363D")
        pat_frame.pack(fill="x", padx=15, pady=6)
        
        tk.Label(pat_frame, text="Excel Filename Pattern:", font=("Segoe UI", 9, "bold"), bg=PANEL, fg=MUTED).pack(anchor="w")
        
        current_pattern = db.load_settings().get("excel_filename_pattern", "GEM_Tenders_FY_{fy}")
        pattern_var = tk.StringVar(value=current_pattern)
        
        pat_entry = tk.Entry(pat_frame, textvariable=pattern_var, bg=CARD, fg=TEXT,
                             insertbackground=TEXT, relief="flat", font=FL,
                             highlightthickness=1, highlightbackground="#30363D",
                             highlightcolor=ACCENT2)
        pat_entry.pack(fill="x", pady=(4, 2))
        
        tk.Label(pat_frame, text="Variables: {fy} (Financial Year), {date} (Date DD-MM-YYYY)",
                 font=("Segoe UI", 8), bg=PANEL, fg=TEXTSUB).pack(anchor="w")

        # Options Frame
        opt_frame = tk.Frame(win, bg=PANEL, padx=12, pady=8, highlightthickness=1, highlightbackground="#30363D")
        opt_frame.pack(fill="x", padx=15, pady=6)
        
        headless_var = tk.BooleanVar(value=db.load_settings().get("selenium_headless", False))
        chk = tk.Checkbutton(opt_frame, text="Run Chrome in Headless (Silent) Mode for Selenium fetching",
                             variable=headless_var, bg=PANEL, fg=TEXT, selectcolor=BG,
                             activebackground=PANEL, activeforeground=TEXT,
                             font=FL, relief="flat", highlightthickness=0)
        chk.pack(anchor="w")

        # Bottom Close Button
        def save_and_close():
            db.save_setting("excel_filename_pattern", pattern_var.get().strip())
            db.save_setting("selenium_headless", headless_var.get())
            self._log("info", "Settings saved successfully.")
            win.destroy()
            
        btn_fr = tk.Frame(win, bg=BG)
        btn_fr.pack(fill="x", side="bottom", pady=12)
        self._btn(btn_fr, "  Close  ", save_and_close, bg=ACCENT2).pack(anchor="center")
        
        win.protocol("WM_DELETE_WINDOW", save_and_close)

    def _backup_db(self, parent_win=None):
        parent = parent_win or self
        if not os.path.exists(db.DB_FILE):
            messagebox.showwarning("Backup Failed", "No database file exists yet to back up.", parent=parent)
            return
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"tenders_db_backup_{timestamp}.json"
        
        dest_path = filedialog.asksaveasfilename(
            title="Backup Database",
            initialfile=default_name,
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
            parent=parent
        )
        if not dest_path:
            return
            
        try:
            import shutil
            shutil.copy2(db.DB_FILE, dest_path)
            self._log("ok", f"Database backup saved to: {dest_path}")
            messagebox.showinfo("Backup Successful", f"Database successfully backed up to:\n\n{dest_path}", parent=parent)
        except Exception as e:
            self._log("err", f"Backup failed: {e}")
            messagebox.showerror("Backup Error", f"Failed to backup database:\n\n{e}", parent=parent)

    def _clear_db(self, parent_win=None):
        parent = parent_win or self
        confirm = messagebox.askyesno(
            "Clear Database",
            "Are you sure you want to permanently clear the local database?\n\n"
            "This will delete ALL tenders from the treeview and database file.",
            parent=parent
        )
        if not confirm:
            return
            
        try:
            # Clear GUI
            for child in self.tv.get_children():
                self.tv.delete(child)
            self._records.clear()
            self._refresh_alt()
            self.count_lbl.configure(text="0 rows")
            
            # Write empty list to DB
            db.save_all_tenders([])
            self._log("ok", "Database cleared successfully.")
            messagebox.showinfo("Database Cleared", "The database has been successfully cleared.", parent=parent)
            
            try:
                if self.notebook.index(self.notebook.select()) == 1:
                    self._update_calendar()
                    self._update_details()
            except:
                pass
        except Exception as e:
            self._log("err", f"Clear database failed: {e}")
            messagebox.showerror("Error Clearing Database", f"Failed to clear database:\n\n{e}", parent=parent)

    # ── Step 1 — parse paste blocks ───────────────────────────────────────────
    def _do_parse(self):
        raw = self.paste_txt.get("1.0","end").strip()
        if not raw: self._log("warn","Paste area is empty."); return
        self._log("info", f"--- Parse started {datetime.now().strftime('%H:%M:%S')} ---")
        self._set_prog(0,"Processing input…")

        def worker():
            import pypdf
            
            lines = raw.splitlines()
            processed_text = ""
            for line in lines:
                line_clean = line.strip().strip('"\'')
                if not line_clean:
                    continue
                    
                # Clean prefix/suffix from bid number if copied from web page header
                line_val = re.sub(r"^(?:BID\s*(?:NO|Number)(?:\.|\b)\s*:\s*)", "", line_clean, flags=re.I).strip()
                line_val = re.sub(r"\s+View\s+Corrigendum.*$", "", line_val, flags=re.I).strip()
                
                # Case A: PDF file path on disk
                if line_clean.lower().endswith(".pdf") and os.path.exists(line_clean):
                    self.after(0, lambda f=line_clean: self._log("info", f"Reading PDF: {os.path.basename(f)}"))
                    try:
                        reader = pypdf.PdfReader(line_clean)
                        pdf_text = ""
                        for page in reader.pages:
                            t = page.extract_text()
                            if t:
                                pdf_text += t + "\n"
                        md_text = convert_pdf_text_to_markdown(pdf_text)
                        processed_text += md_text + "\n"
                    except Exception as ex:
                        import traceback
                        tb = traceback.format_exc()
                        self.after(0, lambda f=line_clean, err=ex, trace=tb: self._log("err", f"Failed to read PDF {os.path.basename(f)}: {err}\n{trace}"))
                
                # Case B: GeM showbidDocument URL
                elif "showbidDocument" in line_clean:
                    self.after(0, lambda url=line_clean: self._log("info", f"URL detected: {url}. Downloading PDF..."))
                    try:
                        import urllib.request
                        doc_id = line_clean.rstrip('/').split('/')[-1]
                        dl_dir = self.save_folder.get() or "."
                        filename = f"GeM-Bidding-{doc_id}.pdf"
                        dest_path = os.path.join(dl_dir, filename)
                        
                        req = urllib.request.Request(
                            line_clean,
                            headers={
                                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                            }
                        )
                        with urllib.request.urlopen(req) as response:
                            with open(dest_path, 'wb') as out_file:
                                out_file.write(response.read())
                                
                        self.after(0, lambda fn=filename: self._log("ok", f"PDF downloaded to: {fn}"))
                        
                        reader = pypdf.PdfReader(dest_path)
                        pdf_text = ""
                        for page in reader.pages:
                            t = page.extract_text()
                            if t:
                                pdf_text += t + "\n"
                        md_text = convert_pdf_text_to_markdown(pdf_text)
                        processed_text += md_text + "\n"
                    except Exception as ex:
                        self.after(0, lambda url=line_clean, err=ex: self._log("err", f"Failed to download/parse URL {url}: {err}"))
                        
                # Case C: GeM Bid Number (e.g. GEM/2026/B/7647078)
                elif re.match(r"^GEM/\d{4}/[A-Z0-9]+/\d+$", line_val, re.I):
                    self.after(0, lambda bn=line_val: self._log("info", f"Bid Number detected: {bn}. Running portal search to download PDF..."))
                    try:
                        dl_dir = self.save_folder.get() or "."
                        headless_opt = db.load_settings().get("selenium_headless", False)
                        dest_path = download_tender_pdf(line_val, dl_dir, log_fn=self._log, headless=headless_opt)
                        
                        if dest_path and os.path.exists(dest_path):
                            reader = pypdf.PdfReader(dest_path)
                            pdf_text = ""
                            for page in reader.pages:
                                t = page.extract_text()
                                if t:
                                    pdf_text += t + "\n"
                            md_text = convert_pdf_text_to_markdown(pdf_text)
                            processed_text += md_text + "\n"
                        else:
                            self.after(0, lambda bn=line_val: self._log("err", f"Failed to download PDF for {bn}"))
                    except Exception as ex:
                        self.after(0, lambda bn=line_val, err=ex: self._log("err", f"Failed to process {bn}: {err}"))
                
                # Case D: Raw pasted text block
                else:
                    processed_text += line + "\n"

            blocks = split_blocks(processed_text)
            total  = len(blocks)
            self._log("info", f"Found {total} block(s).")
            recs = []
            for i, blk in enumerate(blocks,1):
                rec = parse_one(blk)
                self._set_prog(int(i/total*100), f"Parsing {i}/{total}…")
                time.sleep(0.04)
                if rec.get("bid_no"):
                    recs.append(rec)
                    flds = [k for k,v in rec.items() if v]
                    self._log("ok", f"[{i}/{total}] {rec['bid_no']} — {len(flds)} fields")
                else:
                    self._log("warn", f"[{i}/{total}] SKIP — BID NO not found")
            self.after(0, lambda: self._add_rows(recs, total))
        threading.Thread(target=worker, daemon=True).start()

    def _add_rows(self, recs, total):
        added_count = 0
        updated_count = 0
        
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
            if bid_no in records_by_bid:
                existing_rec, iid = records_by_bid[bid_no]
                merged_fields = []
                for k, v in rec.items():
                    if v and (k not in existing_rec or not str(existing_rec[k]).strip()):
                        existing_rec[k] = v
                        self.tv.set(iid, k, v)
                        merged_fields.append(k)
                if merged_fields:
                    updated_count += 1
                    self.tv.item(iid, tags=("fetched",))
            else:
                self._records.append(rec)
                self._tv_insert(rec)
                added_count += 1

        self._refresh_alt()
        db.save_all_tenders(self._records)
        self.count_lbl.configure(text=f"{len(self._records)} rows")
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
            idx = self.tv.index(iid)
            if idx < len(self._records) and self._records[idx].get("bid_url"):
                targets.append((idx, self._records[idx]))
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

        iid_map = {i: iid for i,iid in enumerate(self.tv.get_children())}

        def worker():
            total = len(targets)
            for n, (idx, rec) in enumerate(targets, 1):
                iid = iid_map.get(idx)
                bid = rec.get("bid_no","?")
                url = rec["bid_url"]

                self._set_prog(int((n-1)/total*100), f"Fetching {n}/{total}: {bid}")
                self._log("info", f"[{n}/{total}] Fetching {bid}")

                # mark row as "fetching"
                if iid: self.after(0, lambda i=iid: self.tv.item(i, tags=("fetching",)))

                extra = scrape_bid_page(url, log_fn=self._log)

                if extra:
                    rec.update(extra)
                    rec["is_fetched"] = True
                    # update treeview cells
                    def update_tv(i=iid, r=rec):
                        if i:
                            for cid in TV_IDS:
                                if cid in r:
                                    self.tv.set(i, cid, r[cid])
                            self.tv.item(i, tags=("fetched",))
                        db.save_all_tenders(self._records)
                    self.after(0, update_tv)
                    self._log("ok", f"[{n}/{total}] {bid} — merged {len(extra)} extra fields")
                else:
                    if iid: self.after(0, lambda i=iid: self.tv.item(i, tags=()))
                    self._log("warn", f"[{n}/{total}] {bid} — no extra data scraped")

                self._set_prog(int(n/total*100), f"Fetched {n}/{total}")

            self._fetch_running = False
            self._set_prog(100, "Fetch complete.")
            msg = f"Selenium fetch done: {total} URL(s) processed"
            self._log("info", f"--- {msg} ---")
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
        vals = tuple(rec.get(c,"") for c in TV_IDS)
        tags = []
        if rec.get("is_saved"):
            tags.append("saved")
        elif rec.get("is_fetched"):
            tags.append("fetched")
        return self.tv.insert("","end", values=vals, tags=tuple(tags))

    def _refresh_alt(self):
        for i, iid in enumerate(self.tv.get_children()):
            cur_tags = self.tv.item(iid,"tags")
            special = [t for t in cur_tags if t in ("fetched","saved","fetching")]
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
            idx = self.tv.index(iid)
            if idx < len(self._records): self._records[idx][col_id]=nv
            e.destroy(); self._editing=None
            db.save_all_tenders(self._records)
            try:
                if self.notebook.index(self.notebook.select()) == 1:
                    self._update_calendar()
                    self._update_details()
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
        for iid in sorted(sel, key=self.tv.index, reverse=True):
            idx = self.tv.index(iid)
            self.tv.delete(iid)
            if idx < len(self._records): self._records.pop(idx)
        self._refresh_alt()
        self.count_lbl.configure(text=f"{len(self._records)} rows")
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
        path = xl_path(folder, fy)
        ensure_workbook(path)
        recs = []
        for iid in sel:
            idx = self.tv.index(iid)
            if idx < len(self._records): recs.append(self._records[idx])
        try:
            snos = xl_append(path, recs)
            msg = f"Saved {len(snos)} row(s) → {os.path.basename(path)}  (S.No {snos[0]}–{snos[-1]})"
            self._log("ok", msg); self._set_status(msg, SUCCESS); self._fy_tick()
            for iid in sel: self.tv.item(iid, tags=("saved",))
            for idx in [self.tv.index(iid) for iid in sel]:
                if idx < len(self._records):
                    self._records[idx]["is_saved"] = True
            db.save_all_tenders(self._records)
        except Exception as ex:
            self._log("err", f"Save error: {ex}")
            messagebox.showerror("Save Error", str(ex))

    # ── Calendar View implementation ──────────────────────────────────────────
    def _build_calendar_tab(self):
        # We split the calendar tab into left (grid) and right (details sidebar)
        self.cal_pane = tk.PanedWindow(self.tab_calendar, orient="horizontal", bg=BG,
                                       sashwidth=4, sashrelief="flat", handlesize=0)
        self.cal_pane.pack(fill="both", expand=True, padx=4, pady=4)

        # LEFT PANEL: Calendar Grid Container
        left_fr = tk.Frame(self.cal_pane, bg=BG)
        self.cal_pane.add(left_fr, minsize=500, stretch="always")

        # Month Navigation Bar
        nav_fr = tk.Frame(left_fr, bg=PANEL, pady=6, padx=10,
                          highlightthickness=1, highlightbackground="#30363D")
        nav_fr.pack(fill="x", pady=(0, 6))

        self.cal_prev_btn = self._btn(nav_fr, " ◀ ", self._cal_prev_month, bg=CARD)
        self.cal_prev_btn.pack(side="left")

        self.cal_month_lbl = tk.Label(nav_fr, text="", font=FT, bg=PANEL, fg=TEXT)
        self.cal_month_lbl.pack(side="left", expand=True)

        self.cal_next_btn = self._btn(nav_fr, " ▶ ", self._cal_next_month, bg=CARD)
        self.cal_next_btn.pack(side="right")

        # Grid of Days (Mon to Sun headers + 6 weeks of cards)
        self.cal_grid_fr = tk.Frame(left_fr, bg=BG)
        self.cal_grid_fr.pack(fill="both", expand=True)

        # Weekdays headers
        weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        for idx, day in enumerate(weekdays):
            self.cal_grid_fr.columnconfigure(idx, weight=1, uniform="daycol")
            lbl = tk.Label(self.cal_grid_fr, text=day[:3], font=("Segoe UI", 9, "bold"),
                           bg=BG, fg=MUTED, pady=4)
            lbl.grid(row=0, column=idx, sticky="ew")

        # 6 rows for weeks
        for r in range(1, 7):
            self.cal_grid_fr.rowconfigure(r, weight=1, uniform="weekrow")

        # RIGHT PANEL: Details Sidebar
        right_fr = tk.Frame(self.cal_pane, bg=PANEL, highlightthickness=1, highlightbackground="#30363D")
        self.cal_pane.add(right_fr, minsize=280, width=320, stretch="never")

        # Selected Date Label Header
        self.cal_sel_date_lbl = tk.Label(right_fr, text="", font=("Segoe UI", 10, "bold"),
                                         bg=PANEL, fg=ACCENT2, pady=8, wraplength=300)
        self.cal_sel_date_lbl.pack(fill="x", padx=10)

        # Divider line
        div = tk.Frame(right_fr, height=1, bg="#30363D")
        div.pack(fill="x", padx=10, pady=(0, 10))

        # Scrollable container for detail cards
        self.cal_scroll_canvas = tk.Canvas(right_fr, bg=PANEL, highlightthickness=0)
        self.cal_scroll_canvas.pack(side="left", fill="both", expand=True)

        self.cal_scrollbar = ttk.Scrollbar(right_fr, orient="vertical", command=self.cal_scroll_canvas.yview)
        self.cal_scrollbar.pack(side="right", fill="y")
        self.cal_scroll_canvas.configure(yscrollcommand=self.cal_scrollbar.set)

        self.cal_details_fr = tk.Frame(self.cal_scroll_canvas, bg=PANEL)
        self.cal_scroll_canvas.create_window((0, 0), window=self.cal_details_fr, anchor="nw", tags="self.cal_details_fr")
        
        # Bind Canvas resizing
        self.cal_details_fr.bind("<Configure>", lambda e: self.cal_scroll_canvas.configure(
            scrollregion=self.cal_scroll_canvas.bbox("all")
        ))
        self.cal_scroll_canvas.bind("<Configure>", lambda e: self.cal_scroll_canvas.itemconfig(
            "self.cal_details_fr", width=e.width
        ))

        # Mouse wheel support
        def _on_mousewheel(event):
            self.cal_scroll_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        
        self.cal_scroll_canvas.bind("<Enter>", lambda e: self.cal_scroll_canvas.bind_all("<MouseWheel>", _on_mousewheel))
        self.cal_scroll_canvas.bind("<Leave>", lambda e: self.cal_scroll_canvas.unbind_all("<MouseWheel>"))

    def _cal_prev_month(self):
        if self.cal_month == 1:
            self.cal_month = 12
            self.cal_year -= 1
        else:
            self.cal_month -= 1
        self._update_calendar()
        self._update_details()

    def _cal_next_month(self):
        if self.cal_month == 12:
            self.cal_month = 1
            self.cal_year += 1
        else:
            self.cal_month += 1
        self._update_calendar()
        self._update_details()

    def _parse_date_str(self, date_str):
        if not date_str or not isinstance(date_str, str):
            return None
        m = re.search(r"([0-9]{2})-([0-9]{2})-([0-9]{4})", date_str)
        if m:
            try:
                day, month, year = map(int, m.groups())
                return datetime(year, month, day).date()
            except ValueError:
                return None
        return None

    def _get_events_for_date(self, target_date):
        events = []
        for r in self._records:
            sd = self._parse_date_str(r.get("start_date"))
            ed = self._parse_date_str(r.get("end_date"))
            bo = self._parse_date_str(r.get("bid_opening"))
            
            if sd and sd == target_date:
                events.append(("start", r))
            if ed and ed == target_date:
                events.append(("end", r))
            if bo and bo == target_date:
                events.append(("opening", r))
        return events

    def _update_calendar(self):
        self.cal_month_lbl.configure(text=f"{calendar.month_name[self.cal_month]} {self.cal_year}")
        
        for frame in self.cal_day_frames:
            try: frame.destroy()
            except: pass
        self.cal_day_frames.clear()

        c = calendar.Calendar(firstweekday=calendar.MONDAY)
        try:
            weeks = c.monthdatescalendar(self.cal_year, self.cal_month)
        except Exception as e:
            self._log("err", f"Calendar generation error: {e}")
            return

        for r_idx, week in enumerate(weeks, 1):
            for c_idx, dt in enumerate(week):
                is_curr = (dt.month == self.cal_month and dt.year == self.cal_year)
                card_bg = CARD if is_curr else BG
                text_color = TEXT if is_curr else MUTED
                
                day_card = tk.Frame(self.cal_grid_fr, bg=card_bg,
                                    highlightthickness=1,
                                    highlightbackground="#30363D")
                day_card.grid(row=r_idx, column=c_idx, sticky="nsew", padx=2, pady=2)
                self.cal_day_frames.append(day_card)
                
                # Check selection / today
                if dt == self.cal_selected_date:
                    day_card.configure(highlightbackground=ACCENT2, highlightthickness=2)
                elif dt == datetime.now().date():
                    day_card.configure(highlightbackground=SUCCESS, highlightthickness=2)
                    
                num_lbl = tk.Label(day_card, text=str(dt.day), font=("Segoe UI", 9, "bold"),
                                   bg=card_bg, fg=text_color)
                num_lbl.pack(anchor="ne", padx=4, pady=2)
                
                events = self._get_events_for_date(dt)
                
                for evt in events[:2]:
                    evt_type, r = evt
                    bid = r.get("bid_no", "GEM/...")
                    bid_short = bid.split("/")[-1] if "/" in bid else bid
                    txt = f"{evt_type.upper()}: {bid_short}"
                    
                    if evt_type == "end":
                        fg_c, bg_c = "#FF6B6B", "#2A1D1D"
                    elif evt_type == "opening":
                        fg_c, bg_c = SUCCESS, "#1A2E1A"
                    else:
                        fg_c, bg_c = ACCENT2, "#1A2A3A"
                        
                    evt_lbl = tk.Label(day_card, text=txt, font=("Segoe UI", 7, "bold"),
                                       bg=bg_c, fg=fg_c, anchor="w", padx=4, pady=1)
                    evt_lbl.pack(fill="x", padx=4, pady=1)
                    
                if len(events) > 2:
                    more_lbl = tk.Label(day_card, text=f"+{len(events)-2} more",
                                        font=("Segoe UI", 7, "bold"), bg=card_bg, fg=MUTED, anchor="center")
                    more_lbl.pack(fill="x", padx=4, pady=1)
                    
                def make_clickable(widget, date_val=dt):
                    widget.bind("<Button-1>", lambda e: self._select_date(date_val))
                
                make_clickable(day_card)
                for child in day_card.winfo_children():
                    make_clickable(child)

    def _select_date(self, target_date):
        self.cal_selected_date = target_date
        if target_date.month != self.cal_month or target_date.year != self.cal_year:
            self.cal_month = target_date.month
            self.cal_year = target_date.year
        self._update_calendar()
        self._update_details()

    def _update_details(self):
        for child in self.cal_details_fr.winfo_children():
            child.destroy()

        date_str = self.cal_selected_date.strftime("%A, %b %d, %Y")
        self.cal_sel_date_lbl.configure(text=f"Events for:\n{date_str}")

        events = self._get_events_for_date(self.cal_selected_date)
        if not events:
            lbl = tk.Label(self.cal_details_fr, text="No events on this day.", font=FL, bg=PANEL, fg=MUTED)
            lbl.pack(pady=20)
            return

        tenders_events = {}
        for evt_type, r in events:
            bid_no = r.get("bid_no", "GEM/...")
            if bid_no not in tenders_events:
                tenders_events[bid_no] = {"rec": r, "types": []}
            tenders_events[bid_no]["types"].append(evt_type)

        for bid_no, val in tenders_events.items():
            rec = val["rec"]
            types = val["types"]
            
            card_fr = tk.Frame(self.cal_details_fr, bg=CARD, highlightthickness=1, highlightbackground="#30363D", padx=10, pady=8)
            card_fr.pack(fill="x", padx=10, pady=5)
            
            tk.Label(card_fr, text=rec.get("bid_no","GEM/..."), font=("Segoe UI", 9, "bold"), bg=CARD, fg=TEXT, anchor="w").pack(fill="x")
            
            items = rec.get("items", rec.get("category", "N/A"))
            if len(items) > 60:
                items = items[:57] + "..."
            tk.Label(card_fr, text=items, font=("Segoe UI", 8), bg=CARD, fg=TEXTSUB, anchor="w", justify="left", wraplength=260).pack(fill="x", pady=2)
            
            tags_row = tk.Frame(card_fr, bg=CARD)
            tags_row.pack(fill="x", pady=2)
            for t in types:
                if t == "end":
                    lbl_text, fg, bg = "DEADLINE / END", "#FF6B6B", "#2A1D1D"
                elif t == "opening":
                    lbl_text, fg, bg = "BID OPENING", SUCCESS, "#1A2E1A"
                else:
                    lbl_text, fg, bg = "START DATE", ACCENT2, "#1A2A3A"
                tk.Label(tags_row, text=lbl_text, font=("Segoe UI", 7, "bold"), bg=bg, fg=fg, padx=4, pady=1).pack(side="left", padx=(0,4))
                
            dates_fr = tk.Frame(card_fr, bg=CARD)
            dates_fr.pack(fill="x", pady=2)
            
            def add_date_row(lbl, val):
                if val:
                    r_fr = tk.Frame(dates_fr, bg=CARD)
                    r_fr.pack(fill="x")
                    tk.Label(r_fr, text=lbl, font=("Segoe UI", 8), bg=CARD, fg=MUTED, width=10, anchor="w").pack(side="left")
                    tk.Label(r_fr, text=val, font=("Segoe UI", 8), bg=CARD, fg=TEXTSUB, anchor="w").pack(side="left")
                    
            add_date_row("End Date:", rec.get("end_date"))
            add_date_row("Opening:", rec.get("bid_opening"))
            add_date_row("Start Date:", rec.get("start_date"))
            
            act_fr = tk.Frame(card_fr, bg=CARD)
            act_fr.pack(fill="x", pady=(6, 0))
            
            if rec.get("bid_url"):
                def make_open_url(url=rec["bid_url"]):
                    return lambda: webbrowser.open(url)
                self._btn(act_fr, "🌐 Open URL", make_open_url(), bg=PANEL).pack(side="left")
                
            def make_locate(bid=rec.get("bid_no")):
                return lambda: self._locate_in_table(bid)
            self._btn(act_fr, "🔍 Locate", make_locate(), bg=PANEL).pack(side="right")

    def _locate_in_table(self, bid):
        self.notebook.select(self.tab_table)
        for iid in self.tv.get_children():
            if self.tv.set(iid, "bid_no") == bid:
                self.tv.selection_set(iid)
                self.tv.focus(iid)
                self.tv.see(iid)
                break

    def _on_tab_changed(self, event):
        try:
            selected_tab = self.notebook.index(self.notebook.select())
            if selected_tab == 1:
                self._update_calendar()
                self._update_details()
        except Exception as e:
            self._log("err", f"Tab changed error: {e}")
