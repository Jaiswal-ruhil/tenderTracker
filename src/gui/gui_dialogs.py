# -*- coding: utf-8 -*-
import os
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
try:
    import keyring
except ImportError:
    keyring = None

# Local imports
from config import BG, PANEL, CARD, ACCENT, ACCENT2, MUTED, TEXT, TEXTSUB, ERR, SUCCESS, WARN, FT, FL, TV_COLS
import db

class LoadingDialog(tk.Toplevel):
    def __init__(self, parent, title="Please Wait", message="Processing...", task_fn=None):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.configure(bg=BG)
        self.transient(parent)
        self.grab_set()
        
        # Center the window relative to parent
        self.update_idletasks()
        w, h = 440, 240
        x = parent.winfo_rootx() + (parent.winfo_width() - w) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
        self.geometry(f"{w}x{h}+{max(0, x)}+{max(0, y)}")
        
        # Disable close button
        self.protocol("WM_DELETE_WINDOW", lambda: None)
        
        # Frame
        frame = tk.Frame(self, bg=PANEL, padx=15, pady=15, highlightthickness=1, highlightbackground="#30363D")
        frame.pack(fill="both", expand=True, padx=8, pady=8)
        
        # Messages
        lbl_msg = tk.Label(frame, text=message, font=FL, bg=PANEL, fg=TEXT, wraplength=400, justify="center")
        lbl_msg.pack(pady=(10, 5))
        
        # Progress Bar
        self.progress = ttk.Progressbar(frame, orient="horizontal", length=380, mode="determinate", style="TProgressbar")
        self.progress.pack(pady=(10, 5))
        
        # Current Step Label
        self.lbl_step = tk.Label(frame, text="Initializing...", font=("Segoe UI", 9), bg=PANEL, fg=TEXTSUB, wraplength=400, justify="center")
        self.lbl_step.pack(pady=(2, 5))
        
        # Loading indicator dots
        self.dots_var = tk.StringVar(value="...")
        self.lbl_dots = tk.Label(frame, text="...", font=("Segoe UI", 16, "bold"), bg=PANEL, fg=ACCENT2)
        self.lbl_dots.pack(pady=(5, 5))
        
        self.task_fn = task_fn
        self.exception = None
        self.result = None
        
        self._animate_dots()
        
        if self.task_fn:
            import threading
            threading.Thread(target=self._run_task, daemon=True).start()
            
    def update_progress(self, percent, message=None):
        def _update():
            if self.winfo_exists():
                self.progress["value"] = percent
                if message:
                    self.lbl_step.configure(text=message)
        self.after(0, _update)
            
    def _animate_dots(self):
        if not self.winfo_exists():
            return
        curr = self.dots_var.get()
        if curr == "...":
            nxt = "."
        elif curr == ".":
            nxt = ".."
        elif curr == "..":
            nxt = "..."
        else:
            nxt = "."
        self.dots_var.set(nxt)
        self.lbl_dots.configure(text=nxt)
        self.after(400, self._animate_dots)
        
    def _run_task(self):
        try:
            import inspect
            if self.task_fn:
                sig = inspect.signature(self.task_fn)
                if len(sig.parameters) > 0:
                    self.result = self.task_fn(self.update_progress)
                else:
                    self.result = self.task_fn()
        except Exception as e:
            self.exception = e
        finally:
            if self.winfo_exists():
                self.after(0, self.destroy)


class DialogsMixin:
    def _show_settings(self):
        window_height = 1300
        window_width = 1000
        win = tk.Toplevel(self)
        win.grab_set()
        win.transient(self)
        win.title("Settings")
        win.configure(bg=BG)
        win.resizable(True, True)
        win.minsize(1000, 1300)

        x = self.winfo_x() + (self.winfo_width() - window_width) // 2
        y = self.winfo_y() + (self.winfo_height() - window_height) // 2
        win.geometry(f"{window_width}x{window_height}+{max(0, x)}+{max(0, y)}")

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
        self._btn(btn_db_row, "Restore Database...", lambda: self._restore_db(win), bg=CARD).pack(side="left", padx=6)
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

        # Tender PDF Download Frame
        pdf_frame = tk.Frame(win, bg=PANEL, padx=12, pady=10, highlightthickness=1, highlightbackground="#30363D")
        pdf_frame.pack(fill="x", padx=15, pady=6)

        tk.Label(pdf_frame, text="Tender PDF Download Folder:", font=("Segoe UI", 9, "bold"), bg=PANEL, fg=MUTED).pack(anchor="w")
        default_pdf_folder = os.path.join(os.path.expanduser("~"), "Documents", "TenderPDFs")
        configured_pdf_folder = db.load_settings().get("pdf_save_folder") or default_pdf_folder
        pdf_path_var = tk.StringVar(value=configured_pdf_folder.replace(os.path.expanduser("~"), "~"))
        pdf_lbl = tk.Label(pdf_frame, textvariable=pdf_path_var, font=FL, bg=PANEL, fg=TEXTSUB, anchor="w")
        pdf_lbl.pack(fill="x", pady=(4, 0))

        def run_pdf_folder_change():
            selected_dir = filedialog.askdirectory(
                title="Select Tender PDF Download Folder",
                initialdir=configured_pdf_folder,
                parent=win,
            )
            if selected_dir:
                resolved_dir = os.path.abspath(selected_dir)
                db.save_setting("pdf_save_folder", resolved_dir)
                pdf_path_var.set(resolved_dir.replace(os.path.expanduser("~"), "~"))
                self._log("ok", f"Tender PDF download folder changed to: {resolved_dir}")

        self._btn(pdf_frame, "Change Folder...", run_pdf_folder_change, bg=CARD).pack(anchor="w", pady=(4, 0))

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

        # LLM Frame
        llm_frame = tk.Frame(win, bg=PANEL, padx=12, pady=10, highlightthickness=1, highlightbackground="#30363D")
        llm_frame.pack(fill="x", padx=15, pady=6)
        
        tk.Label(llm_frame, text="LLM Service Integration:", font=("Segoe UI", 9, "bold"), bg=PANEL, fg=MUTED).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        
        # Provider Selection
        tk.Label(llm_frame, text="LLM Provider:", font=FL, bg=PANEL, fg=TEXTSUB).grid(row=1, column=0, sticky="w", pady=3)
        
        provider_var = tk.StringVar(value=db.load_settings().get("llm_provider", "Disabled"))
        provider_cb = ttk.Combobox(llm_frame, textvariable=provider_var, values=["Disabled", "Google AI Studio (Gemini)", "Local LLM (LM Studio / Ollama)"], state="readonly", font=FL)
        provider_cb.grid(row=1, column=1, sticky="ew", padx=(10, 0), pady=3)
        
        # API Key (stored securely in OS keyring)
        tk.Label(llm_frame, text="API Key:", font=FL, bg=PANEL, fg=TEXTSUB).grid(row=2, column=0, sticky="w", pady=3)
        saved_key = None
        if keyring:
            try:
                saved_key = keyring.get_password('tendertracker', 'llm_api_key')
            except Exception:
                saved_key = None
        if not saved_key:
            saved_key = db.load_settings().get("llm_api_key", "")
        key_var = tk.StringVar(value=saved_key or db.load_settings().get("llm_api_key", ""))
        key_ent = tk.Entry(llm_frame, textvariable=key_var, show="*", bg=CARD, fg=TEXT, insertbackground=TEXT, relief="flat", font=FL,
                           highlightthickness=1, highlightbackground="#30363D", highlightcolor=ACCENT2)
        key_ent.grid(row=2, column=1, sticky="ew", padx=(10, 0), pady=3)
        
        # Base URL
        url_lbl = tk.Label(llm_frame, text="API Base URL:", font=FL, bg=PANEL, fg=TEXTSUB)
        url_lbl.grid(row=3, column=0, sticky="w", pady=3)
        url_var = tk.StringVar(value=db.load_settings().get("llm_base_url", "http://localhost:1234/v1"))
        url_ent = tk.Entry(llm_frame, textvariable=url_var, bg=CARD, fg=TEXT, insertbackground=TEXT, relief="flat", font=FL,
                           highlightthickness=1, highlightbackground="#30363D", highlightcolor=ACCENT2)
        url_ent.grid(row=3, column=1, sticky="ew", padx=(10, 0), pady=3)
        
        # Model Name
        model_lbl = tk.Label(llm_frame, text="Model Name:", font=FL, bg=PANEL, fg=TEXTSUB)
        model_lbl.grid(row=4, column=0, sticky="w", pady=3)
        model_var = tk.StringVar(value=db.load_settings().get("llm_model", "gemini-1.5-flash"))
        model_ent = tk.Entry(llm_frame, textvariable=model_var, bg=CARD, fg=TEXT, insertbackground=TEXT, relief="flat", font=FL,
                            highlightthickness=1, highlightbackground="#30363D", highlightcolor=ACCENT2)
        model_ent.grid(row=4, column=1, sticky="ew", padx=(10, 0), pady=3)
        
        # Classification Model (llm_classification_model)
        class_model_lbl = tk.Label(llm_frame, text="Classification Model:", font=FL, bg=PANEL, fg=TEXTSUB)
        class_model_lbl.grid(row=5, column=0, sticky="w", pady=3)
        class_model_var = tk.StringVar(value=db.load_settings().get("llm_classification_model", ""))
        class_model_ent = tk.Entry(llm_frame, textvariable=class_model_var, bg=CARD, fg=TEXT, insertbackground=TEXT, relief="flat", font=FL,
                                   highlightthickness=1, highlightbackground="#30363D", highlightcolor=ACCENT2)
        class_model_ent.grid(row=5, column=1, sticky="ew", padx=(10, 0), pady=3)
        
        # Embedding Model (llm_embedding_model)
        embed_lbl = tk.Label(llm_frame, text="Embedding Model:", font=FL, bg=PANEL, fg=TEXTSUB)
        embed_lbl.grid(row=6, column=0, sticky="w", pady=3)
        embed_var = tk.StringVar(value=db.load_settings().get("llm_embedding_model", "nomic-embed-text"))
        embed_ent = tk.Entry(llm_frame, textvariable=embed_var, bg=CARD, fg=TEXT, insertbackground=TEXT, relief="flat", font=FL,
                            highlightthickness=1, highlightbackground="#30363D", highlightcolor=ACCENT2)
        embed_ent.grid(row=6, column=1, sticky="ew", padx=(10, 0), pady=3)

        # Optional start command (used if server not reachable)
        start_lbl = tk.Label(llm_frame, text="Start Command:", font=FL, bg=PANEL, fg=TEXTSUB)
        start_lbl.grid(row=7, column=0, sticky="w", pady=3)
        start_var = tk.StringVar(value=db.load_settings().get("llm_start_cmd", ""))
        start_ent = tk.Entry(llm_frame, textvariable=start_var, bg=CARD, fg=TEXT, insertbackground=TEXT, relief="flat", font=FL,
                    highlightthickness=1, highlightbackground="#30363D", highlightcolor=ACCENT2)
        start_ent.grid(row=7, column=1, sticky="ew", padx=(10, 0), pady=3)
        
        # Parallel Workers (llm_max_parallel)
        parallel_lbl = tk.Label(llm_frame, text="Parallel Workers:", font=FL, bg=PANEL, fg=TEXTSUB)
        parallel_lbl.grid(row=8, column=0, sticky="w", pady=3)
        parallel_var = tk.StringVar(value=str(db.load_settings().get("llm_max_parallel", 8)))
        parallel_ent = tk.Entry(llm_frame, textvariable=parallel_var, bg=CARD, fg=TEXT, insertbackground=TEXT, relief="flat", font=FL,
                               highlightthickness=1, highlightbackground="#30363D", highlightcolor=ACCENT2)
        parallel_ent.grid(row=8, column=1, sticky="ew", padx=(10, 0), pady=3)
        
        llm_frame.columnconfigure(1, weight=1)
        
        # Checkboxes for actions
        chk_frame = tk.Frame(llm_frame, bg=PANEL)
        chk_frame.grid(row=9, column=0, columnspan=2, sticky="w", pady=(6, 4))
        
        use_parsing_var = tk.BooleanVar(value=db.load_settings().get("llm_use_parsing", False))
        chk_parse = tk.Checkbutton(chk_frame, text="Use LLM for parsing tender text & PDFs",
                                   variable=use_parsing_var, bg=PANEL, fg=TEXT, selectcolor=BG,
                                   activebackground=PANEL, activeforeground=TEXT,
                                   font=FL, relief="flat", highlightthickness=0)
        chk_parse.pack(anchor="w")
        
        use_mapping_var = tk.BooleanVar(value=db.load_settings().get("llm_use_mapping", False))
        chk_map = tk.Checkbutton(chk_frame, text="Use LLM for intelligent category mapping",
                                 variable=use_mapping_var, bg=PANEL, fg=TEXT, selectcolor=BG,
                                 activebackground=PANEL, activeforeground=TEXT,
                                 font=FL, relief="flat", highlightthickness=0)
        chk_map.pack(anchor="w")

        use_agent_var = tk.BooleanVar(value=db.load_settings().get("llm_use_agent", False))
        chk_agent = tk.Checkbutton(
            chk_frame,
            text="Use Agentic Parser (tool-calling loop, Local LLM only)",
            variable=use_agent_var, bg=PANEL, fg=TEXT, selectcolor=BG,
            activebackground=PANEL, activeforeground=TEXT,
            font=FL, relief="flat", highlightthickness=0
        )
        chk_agent.pack(anchor="w")

        # Test Connection button and Status label
        test_frame = tk.Frame(llm_frame, bg=PANEL)
        test_frame.grid(row=10, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        
        test_status_var = tk.StringVar(value="Status: Ready")
        test_status_lbl = tk.Label(test_frame, textvariable=test_status_var, font=("Segoe UI", 8, "italic"), bg=PANEL, fg=TEXTSUB, anchor="w")
        test_status_lbl.pack(side="right", fill="x", expand=True, padx=(10, 0))
        
        import threading
        import llm
        
        def run_test():
            prov = provider_var.get()
            key = key_var.get().strip()
            url = url_var.get().strip()
            mdl = model_var.get().strip()
            
            if prov == "Disabled":
                test_status_lbl.configure(fg=WARN)
                test_status_var.set("Status: Select a provider first.")
                return
                
            test_status_lbl.configure(fg=MUTED)
            test_status_var.set("Status: Connecting...")
            
            def perform_connect():
                start_cmd_val = start_var.get().strip()
                try:
                    llm.ensure_server_running(url, start_cmd_val)
                except Exception:
                    pass
                return llm.test_llm_connection(prov, key, url, mdl)
                
            dlg = LoadingDialog(win, "Testing Connection", "Testing LLM connection and pre-warming model...", perform_connect)
            win.wait_window(dlg)
            
            if dlg.exception:
                test_status_lbl.configure(fg=ERR)
                test_status_var.set(f"Status: Fail ({str(dlg.exception)[:30]}...)")
            elif dlg.result:
                success, msg = dlg.result
                if success:
                    test_status_lbl.configure(fg=SUCCESS)
                    test_status_var.set("Status: Success!")
                else:
                    test_status_lbl.configure(fg=ERR)
                    test_status_var.set(f"Status: Fail ({msg[:30]}...)")
            
        def run_eject():
            prov = provider_var.get()
            url = url_var.get().strip()
            key = key_var.get().strip()
            
            if prov != "Local LLM (LM Studio / Ollama)":
                test_status_lbl.configure(fg=WARN)
                test_status_var.set("Status: Eject is for Local LLM.")
                return
                
            test_status_lbl.configure(fg=MUTED)
            test_status_var.set("Status: Ejecting...")
            
            def perform_eject():
                llm.unload_local_models(url, key)
                return True
                
            dlg = LoadingDialog(win, "Ejecting Models", "Ejecting loaded models from local server...", perform_eject)
            win.wait_window(dlg)
            
            if dlg.exception:
                test_status_lbl.configure(fg=ERR)
                test_status_var.set(f"Status: Fail ({str(dlg.exception)[:30]}...)")
            else:
                test_status_lbl.configure(fg=SUCCESS)
                test_status_var.set("Status: Ejected successfully.")
            
        self._btn(test_frame, "Test Connection", run_test, bg=CARD).pack(side="left")
        self._btn(test_frame, "Eject LLM", run_eject, bg=CARD).pack(side="left", padx=(6, 0))
 
        def update_llm_fields_state(*args):
            prov = provider_var.get()
            if prov == "Disabled":
                key_ent.configure(state="disabled")
                url_ent.configure(state="disabled")
                model_ent.configure(state="disabled")
                class_model_ent.configure(state="disabled")
                embed_ent.configure(state="disabled")
                parallel_ent.configure(state="disabled")
                chk_parse.configure(state="disabled")
                chk_map.configure(state="disabled")
                chk_agent.configure(state="disabled")
            elif prov == "Google AI Studio (Gemini)":
                key_ent.configure(state="normal")
                url_ent.configure(state="disabled")
                model_ent.configure(state="normal")
                class_model_ent.configure(state="normal")
                embed_ent.configure(state="disabled")
                parallel_ent.configure(state="normal")
                chk_parse.configure(state="normal")
                chk_map.configure(state="normal")
                chk_agent.configure(state="disabled")  # agent is local-only
                # Pre-fill default model name if empty
                if not model_var.get().strip():
                    model_var.set("gemini-1.5-flash")
            elif prov == "Local LLM (LM Studio / Ollama)":
                key_ent.configure(state="normal")
                url_ent.configure(state="normal")
                model_ent.configure(state="normal")
                class_model_ent.configure(state="normal")
                embed_ent.configure(state="normal")
                parallel_ent.configure(state="normal")
                chk_parse.configure(state="normal")
                chk_map.configure(state="normal")
                chk_agent.configure(state="normal")
                # Pre-fill default url/model if empty
                if not url_var.get().strip():
                    url_var.set("http://localhost:1234/v1")
                if not model_var.get().strip():
                    model_var.set("local-model")
                    
        provider_var.trace_add("write", update_llm_fields_state)
        update_llm_fields_state()
 
        # Bottom Close Button
        def save_and_close():
            db.save_setting("excel_filename_pattern", pattern_var.get().strip())
            db.save_setting("selenium_headless", headless_var.get())
            # Save LLM Settings
            db.save_setting("llm_provider", provider_var.get())
            # Store API key securely in keyring when available
            if keyring:
                try:
                    key_to_store = key_var.get().strip()
                    if key_to_store:
                        keyring.set_password('tendertracker', 'llm_api_key', key_to_store)
                except Exception:
                    # Fallback to settings file if keyring unavailable
                    db.save_setting("llm_api_key", key_var.get().strip())
            else:
                db.save_setting("llm_api_key", key_var.get().strip())
            db.save_setting("llm_base_url", url_var.get().strip())
            db.save_setting("llm_model", model_var.get().strip())
            db.save_setting("llm_classification_model", class_model_var.get().strip())
            db.save_setting("llm_embedding_model", embed_var.get().strip())
            db.save_setting("llm_start_cmd", start_var.get().strip())
            try:
                parallel_val = int(parallel_var.get().strip())
                db.save_setting("llm_max_parallel", parallel_val)
            except ValueError:
                db.save_setting("llm_max_parallel", 8)
            db.save_setting("llm_use_parsing", use_parsing_var.get())
            db.save_setting("llm_use_mapping", use_mapping_var.get())
            db.save_setting("llm_use_agent", use_agent_var.get())
            
            self._log("info", "Settings saved successfully.")
            win.destroy()
            
        btn_fr = tk.Frame(win, bg=BG)
        btn_fr.pack(fill="x", side="bottom", pady=12)
        self._btn(btn_fr, "  Close  ", save_and_close, bg=ACCENT2).pack(anchor="center")
        
        win.protocol("WM_DELETE_WINDOW", save_and_close)

    def _change_db_location(self, parent_win=None):
        initial = os.path.dirname(db.DB_FILE) if db.DB_FILE else ""
        selected_dir = filedialog.askdirectory(
            title="Select New Folder for Database (tenders_db.db)",
            initialdir=initial,
            parent=parent_win or self
        )
        if not selected_dir:
            return
            
        new_db_path = os.path.join(os.path.abspath(selected_dir), "tenders_db.db")
        old_db_path = db.DB_FILE
        
        if old_db_path and os.path.abspath(new_db_path) == os.path.abspath(old_db_path):
            messagebox.showinfo("Database Location", "Selected folder is the same as the current database location.", parent=parent_win or self)
            return
            
        # Ask if they want to copy the existing database to the new location
        copy_existing = False
        if old_db_path and os.path.exists(old_db_path):
            copy_existing = messagebox.askyesno(
                "Copy Existing Database?",
                "Do you want to copy your existing database (with all tenders and history) to the new location?\n\n"
                "Click 'Yes' to copy the current database.\n"
                "Click 'No' to switch to the new folder (which will create a new empty database if one does not exist).",
                parent=parent_win or self
            )
            
        if copy_existing:
            import shutil
            try:
                # If target file exists, ask to overwrite
                if os.path.exists(new_db_path):
                    overwrite = messagebox.askyesno(
                        "Overwrite Existing Database?",
                        f"A database file already exists at the new location:\n{new_db_path}\n\nDo you want to overwrite it with the current database?",
                        parent=parent_win or self
                    )
                    if not overwrite:
                        return
                
                # Copy the file
                shutil.copy2(old_db_path, new_db_path)
                self._log("ok", f"Copied database from {old_db_path} to {new_db_path}")
            except Exception as e:
                self._log("err", f"Failed to copy database file: {e}")
                messagebox.showerror("Error", f"Failed to copy database file:\n{e}", parent=parent_win or self)
                return

        # Save setting and initialize path
        try:
            db.save_configured_db_path(new_db_path)
            db.init_db_path(new_db_path)
            
            # Setup logger to the new log file path
            import logger
            logger.setup_file_logger(new_db_path)
            
            self._log("ok", f"Database relocated to: {new_db_path}")
            
            # Reload all tenders from the new database path into the GUI
            self._records = db.load_all_tenders()
            self._refresh_table_view()
            if hasattr(self, "_update_analytics"):
                self._update_analytics()
            if hasattr(self, "_update_calendar"):
                self._update_calendar()
                self._update_details()
                
            messagebox.showinfo("Success", f"Database successfully relocated to:\n{new_db_path}", parent=parent_win or self)
        except Exception as e:
            self._log("err", f"Failed to relocate database: {e}")
            messagebox.showerror("Error", f"Failed to relocate database:\n{e}", parent=parent_win or self)

    def _show_firms_dialog(self):
        win = tk.Toplevel(self)
        win.grab_set()
        win.transient(self)
        win.title("Manage Firms")
        win.configure(bg=BG)
        win.resizable(True, True)
        win.minsize(980, 660)

        x = self.winfo_x() + (self.winfo_width() - 1060) // 2
        y = self.winfo_y() + (self.winfo_height() - 720) // 2
        win.geometry(f"1060x720+{max(0, x)}+{max(0, y)}")

        # ── Accent colours used only in this dialog ──────────────────────
        DOC_UPLOADED   = "#2EA043"   # green when file present
        DOC_MISSING    = "#D29922"   # amber when path saved but file gone
        DOC_NONE       = "#484F58"   # grey when nothing uploaded
        ROW_ALT        = "#1C2128"   # alternating doc-row background
        SECTION_LINE   = "#30363D"
        CHIP_BG        = "#1C3557"
        CHIP_FG        = "#79C0FF"
        UPLOAD_BG      = "#1C3557"

        def normalize_multi_value(value):
            if isinstance(value, list):
                raw_items = value
            else:
                raw_items = str(value or "").split(",")
            items = []
            for item in raw_items:
                cleaned = str(item).strip()
                if cleaned and cleaned not in items:
                    items.append(cleaned)
            return items

        def display_multi_value(value):
            return ", ".join(normalize_multi_value(value))

        # Document type definitions: (key, icon, label, optional)
        DOCUMENT_TYPES = [
            ("gst",           "📄", "GST Certificate",        False),
            ("pan",           "🪪", "PAN Card",                False),
            ("msme",          "🏭", "MSME Certificate",        True),
            ("itr_1",         "📊", "ITR – Year 1",            False),
            ("itr_2",         "📊", "ITR – Year 2",            False),
            ("itr_3",         "📊", "ITR – Year 3",            False),
            ("bs_1",          "📑", "Balance Sheet – Year 1",  False),
            ("bs_2",          "📑", "Balance Sheet – Year 2",  False),
            ("bs_3",          "📑", "Balance Sheet – Year 3",  False),
            ("turnover_cert", "📜", "Turnover Certificate",    False),
            ("shareholder",   "👥", "Shareholder Pattern",     True),
        ]
        REQUIRED_KEYS = {k for k, _, _, opt in DOCUMENT_TYPES if not opt}
        TOTAL_REQUIRED = len(REQUIRED_KEYS)

        def _doc_completion(documents: dict) -> tuple:
            """Returns (uploaded_required, total_required, has_all_optional)."""
            uploaded = sum(1 for k in REQUIRED_KEYS if documents.get(k, "").strip())
            return uploaded, TOTAL_REQUIRED

        # Load firms from settings
        settings = db.load_settings()
        firms_list = []
        for firm in settings.get("firms", []):
            firms_list.append({
                "name": firm.get("name", ""),
                "categories": normalize_multi_value(firm.get("categories", [])),
                "locations": firm.get("locations", ""),
                "exclude_keywords": firm.get("exclude_keywords", ""),
                "documents": firm.get("documents", {}),
            })

        # ── Title bar ────────────────────────────────────────────────────
        title_bar = tk.Frame(win, bg=PANEL, pady=10,
                             highlightthickness=1, highlightbackground=SECTION_LINE)
        title_bar.pack(fill="x", side="top")
        tk.Label(title_bar, text="🏢  Manage Firms", font=("Segoe UI", 13, "bold"),
                 bg=PANEL, fg=TEXT).pack(side="left", padx=16)
        firm_count_var = tk.StringVar(value=f"{len(firms_list)} firm(s)")
        tk.Label(title_bar, textvariable=firm_count_var,
                 font=("Segoe UI", 9), bg=PANEL, fg=MUTED).pack(side="left", padx=(0, 0))

        # ── Bottom bar (packed before main so it stays pinned) ────────────
        bot_fr = tk.Frame(win, bg=PANEL, pady=10,
                          highlightthickness=1, highlightbackground=SECTION_LINE)
        bot_fr.pack(fill="x", side="bottom")

        # ── Main split ───────────────────────────────────────────────────
        main_fr = tk.Frame(win, bg=BG)
        main_fr.pack(fill="both", expand=True, padx=0, pady=0)
        main_fr.columnconfigure(0, weight=0, minsize=230)
        main_fr.columnconfigure(1, weight=1)
        main_fr.rowconfigure(0, weight=1)

        # ── LEFT: Firm list panel ────────────────────────────────────────
        left_fr = tk.Frame(main_fr, bg=PANEL,
                           highlightthickness=1, highlightbackground=SECTION_LINE)
        left_fr.grid(row=0, column=0, sticky="nsew")
        left_fr.rowconfigure(1, weight=1)
        left_fr.columnconfigure(0, weight=1)

        left_hdr = tk.Frame(left_fr, bg=PANEL, pady=8)
        left_hdr.grid(row=0, column=0, sticky="ew", padx=10)
        tk.Label(left_hdr, text="FIRMS", font=("Segoe UI", 8, "bold"),
                 bg=PANEL, fg=MUTED).pack(side="left")

        # Scrollable custom listbox area
        list_canvas = tk.Canvas(left_fr, bg=PANEL, highlightthickness=0)
        list_scroll = ttk.Scrollbar(left_fr, orient="vertical", command=list_canvas.yview)
        list_canvas.configure(yscrollcommand=list_scroll.set)
        list_canvas.grid(row=1, column=0, sticky="nsew")
        list_scroll.grid(row=1, column=1, sticky="ns")

        list_inner = tk.Frame(list_canvas, bg=PANEL)
        _list_win = list_canvas.create_window((0, 0), window=list_inner, anchor="nw")

        def _on_list_configure(e):
            list_canvas.configure(scrollregion=list_canvas.bbox("all"))
        def _on_list_canvas_configure(e):
            list_canvas.itemconfig(_list_win, width=e.width)
        list_inner.bind("<Configure>", _on_list_configure)
        list_canvas.bind("<Configure>", _on_list_canvas_configure)

        ttk.Separator(left_fr, orient="horizontal").grid(row=2, column=0, columnspan=2, sticky="ew")
        lbtn_fr = tk.Frame(left_fr, bg=PANEL, pady=8)
        lbtn_fr.grid(row=3, column=0, columnspan=2, sticky="ew", padx=8)

        # Track selected index for custom card list
        _selected_idx = [None]
        _card_frames  = []  # list of (outer_frame, inner widgets)

        def _make_firm_card(idx, firm_data, selected=False):
            """Build a single firm card widget inside list_inner."""
            card_bg  = ACCENT2 + "22" if selected else PANEL   # subtle blue tint
            border_c = ACCENT2 if selected else SECTION_LINE

            outer = tk.Frame(list_inner, bg=border_c,
                             highlightthickness=0, pady=1)
            outer.pack(fill="x", padx=6, pady=3)

            inner = tk.Frame(outer, bg=card_bg if selected else CARD,
                             padx=10, pady=8, cursor="hand2")
            inner.pack(fill="x")

            name = firm_data.get("name", "Unnamed")
            cats = firm_data.get("categories", [])
            docs = firm_data.get("documents", {})
            up, tot = _doc_completion(docs)
            cat_cnt = len(cats) if isinstance(cats, list) else len(normalize_multi_value(cats))

            name_lbl = tk.Label(inner, text=name,
                                font=("Segoe UI", 10, "bold" if selected else "normal"),
                                bg=inner.cget("bg"), fg=TEXT if selected else TEXT,
                                anchor="w")
            name_lbl.pack(fill="x")

            meta_fr = tk.Frame(inner, bg=inner.cget("bg"))
            meta_fr.pack(fill="x", pady=(3, 0))

            # Category badge
            cat_badge = tk.Label(meta_fr,
                                 text=f"  {cat_cnt} cat  ",
                                 font=("Segoe UI", 7, "bold"),
                                 bg="#238636", fg="#AFFFB0",
                                 padx=2, pady=1)
            cat_badge.pack(side="left", padx=(0, 4))

            # Docs badge
            doc_color = "#238636" if up == tot else ("#D29922" if up > 0 else CARD)
            doc_fg    = "#AFFFB0" if up == tot else ("#FFE08A" if up > 0 else MUTED)
            doc_badge = tk.Label(meta_fr,
                                 text=f"  {up}/{tot} docs  ",
                                 font=("Segoe UI", 7, "bold"),
                                 bg=doc_color, fg=doc_fg,
                                 padx=2, pady=1)
            doc_badge.pack(side="left")

            # Click binding — all children
            def _click(e, i=idx):
                _on_card_click(i)
            for w in [outer, inner, name_lbl, meta_fr, cat_badge, doc_badge]:
                w.bind("<Button-1>", _click)

            return outer

        def _on_card_click(idx):
            _selected_idx[0] = idx
            _refresh_cards(selected=idx)
            if 0 <= idx < len(firms_list):
                _show_form(firms_list[idx], idx=idx)

        def _refresh_cards(selected=None):
            for w in list_inner.winfo_children():
                w.destroy()
            _card_frames.clear()
            for i, f in enumerate(firms_list):
                card = _make_firm_card(i, f, selected=(i == selected))
                _card_frames.append(card)
            if not firms_list:
                tk.Label(list_inner, text="No firms yet",
                         font=FL, bg=PANEL, fg=MUTED).pack(pady=20)
            firm_count_var.set(f"{len(firms_list)} firm(s)")

        # ── RIGHT: Scrollable form ────────────────────────────────────────
        right_fr = tk.Frame(main_fr, bg=BG)
        right_fr.grid(row=0, column=1, sticky="nsew")
        right_fr.columnconfigure(0, weight=1)
        right_fr.rowconfigure(0, weight=1)

        # Placeholder
        placeholder_fr = tk.Frame(right_fr, bg=BG)
        placeholder_fr.grid(row=0, column=0, sticky="nsew")
        placeholder_fr.rowconfigure(0, weight=1)
        placeholder_fr.columnconfigure(0, weight=1)
        tk.Label(placeholder_fr,
                 text="🏢",
                 font=("Segoe UI", 48), bg=BG, fg="#30363D"
                 ).grid(row=0, column=0, pady=(60, 4))
        tk.Label(placeholder_fr,
                 text="Select a firm from the left\nor click  + Add  to create one",
                 font=("Segoe UI", 11), bg=BG, fg=MUTED, justify="center"
                 ).grid(row=1, column=0)

        # Scrollable canvas
        _form_canvas = tk.Canvas(right_fr, bg=BG, highlightthickness=0)
        _form_scroll = ttk.Scrollbar(right_fr, orient="vertical", command=_form_canvas.yview)
        _form_canvas.configure(yscrollcommand=_form_scroll.set)

        form_fr = tk.Frame(_form_canvas, bg=BG, padx=18, pady=10)
        _form_win = _form_canvas.create_window((0, 0), window=form_fr, anchor="nw")

        def _on_form_configure(e):
            _form_canvas.configure(scrollregion=_form_canvas.bbox("all"))
        def _on_canvas_configure(e):
            _form_canvas.itemconfig(_form_win, width=e.width)
        form_fr.bind("<Configure>", _on_form_configure)
        _form_canvas.bind("<Configure>", _on_canvas_configure)

        def _bind_mw(widget):
            widget.bind("<MouseWheel>",
                lambda e: _form_canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
            for ch in widget.winfo_children():
                _bind_mw(ch)
        form_fr.bind("<Map>", lambda e: _bind_mw(form_fr))

        # ── Helper: section header ────────────────────────────────────────
        def _section_header(parent, icon, title, subtitle=None):
            fr = tk.Frame(parent, bg=BG)
            fr.pack(fill="x", pady=(16, 6))
            ttk.Separator(fr, orient="horizontal").pack(fill="x", pady=(0, 6))
            hdr = tk.Frame(fr, bg=BG)
            hdr.pack(fill="x")
            tk.Label(hdr, text=icon, font=("Segoe UI", 11),
                     bg=BG, fg=TEXT).pack(side="left", padx=(0, 6))
            tk.Label(hdr, text=title, font=("Segoe UI", 9, "bold"),
                     bg=BG, fg=TEXT).pack(side="left")
            if subtitle:
                tk.Label(hdr, text=subtitle, font=("Segoe UI", 8),
                         bg=BG, fg=TEXTSUB).pack(side="left", padx=(10, 0))

        # ── Helper: field row ─────────────────────────────────────────────
        def _field(parent, label, hint=None):
            fr = tk.Frame(parent, bg=BG)
            fr.pack(fill="x", pady=(0, 10))
            lbl_fr = tk.Frame(fr, bg=BG)
            lbl_fr.pack(fill="x")
            tk.Label(lbl_fr, text=label, font=("Segoe UI", 8, "bold"),
                     bg=BG, fg=MUTED).pack(side="left")
            if hint:
                tk.Label(lbl_fr, text=hint, font=("Segoe UI", 7),
                         bg=BG, fg=TEXTSUB).pack(side="left", padx=(8, 0))
            var = tk.StringVar()
            ent = tk.Entry(fr, textvariable=var, bg=CARD, fg=TEXT,
                           insertbackground=TEXT, relief="flat",
                           font=("Segoe UI", 10),
                           highlightthickness=1,
                           highlightbackground=SECTION_LINE,
                           highlightcolor=ACCENT2)
            ent.pack(fill="x", pady=(4, 0), ipady=6)
            return var, ent

        # ── Firm Name ─────────────────────────────────────────────────────
        nm_hdr = tk.Frame(form_fr, bg=BG)
        nm_hdr.pack(fill="x", pady=(0, 4))
        tk.Label(nm_hdr, text="Firm Name", font=("Segoe UI", 8, "bold"),
                 bg=BG, fg=MUTED).pack(side="left")
        name_var = tk.StringVar()
        name_ent = tk.Entry(form_fr, textvariable=name_var, bg=CARD, fg=TEXT,
                            insertbackground=TEXT, relief="flat",
                            font=("Segoe UI", 12, "bold"),
                            highlightthickness=1,
                            highlightbackground=SECTION_LINE,
                            highlightcolor=ACCENT2)
        name_ent.pack(fill="x", pady=(0, 4), ipady=7)

        # ── Categories section ────────────────────────────────────────────
        _section_header(form_fr, "🏷️", "Product Categories",
                        "tenders are matched against these keywords")

        cat_section = tk.Frame(form_fr, bg=BG)
        cat_section.pack(fill="x", pady=(0, 4))

        cat_hdr_fr = tk.Frame(cat_section, bg=BG)
        cat_hdr_fr.pack(fill="x")
        live_match_lbl = tk.Label(cat_hdr_fr, text="", font=("Segoe UI", 8),
                                  bg=BG, fg=SUCCESS)
        live_match_lbl.pack(side="right", padx=4)

        # Chips panel
        chips_outer = tk.Frame(cat_section, bg=CARD,
                               highlightthickness=1, highlightbackground=SECTION_LINE)
        chips_outer.pack(fill="x", pady=(4, 0))

        chips_canvas = tk.Canvas(chips_outer, bg=CARD, highlightthickness=0, height=110)
        chips_canvas.pack(fill="both", expand=True, padx=4, pady=4)
        chips_frame = tk.Frame(chips_canvas, bg=CARD)
        chips_window = chips_canvas.create_window((0, 0), window=chips_frame, anchor="nw")
        chips_frame.bind("<Configure>",
            lambda e: chips_canvas.configure(scrollregion=chips_canvas.bbox("all")))
        chips_canvas.bind("<Configure>",
            lambda e: chips_canvas.itemconfig(chips_window, width=e.width))

        current_categories = []

        def _update_live_count():
            try:
                cats = [c.lower() for c in current_categories if c]
                if not cats:
                    live_match_lbl.configure(text="")
                    return
                count = sum(
                    1 for r in self._records
                    if any(kw in " ".join([
                        str(r.get("items", "")), str(r.get("category", "")),
                        str(r.get("dept", "")), str(r.get("bid_no", ""))
                    ]).lower() for kw in cats)
                )
                live_match_lbl.configure(
                    text=f"~{count} tender{'s' if count != 1 else ''} matched",
                    fg=SUCCESS if count > 0 else MUTED
                )
            except Exception:
                live_match_lbl.configure(text="")

        def _rebuild_chips():
            for w in chips_frame.winfo_children():
                w.destroy()
            col = 0
            row_fr = None
            MAX_COLS = 5
            for i, cat in enumerate(current_categories):
                if col % MAX_COLS == 0:
                    row_fr = tk.Frame(chips_frame, bg=CARD)
                    row_fr.pack(anchor="w", pady=2, padx=4)
                    col = 0
                chip = tk.Frame(row_fr, bg=CHIP_BG,
                                highlightthickness=1, highlightbackground=ACCENT2)
                chip.pack(side="left", padx=(0, 6), pady=1)
                tk.Label(chip, text=cat, font=("Segoe UI", 9),
                         bg=CHIP_BG, fg=CHIP_FG, padx=6, pady=3).pack(side="left")
                def _make_rm(idx=i):
                    def _rm():
                        current_categories.pop(idx)
                        _rebuild_chips()
                        _update_live_count()
                    return _rm
                tk.Button(chip, text="×", command=_make_rm(),
                          bg=CHIP_BG, fg=ERR, relief="flat",
                          font=("Segoe UI", 9, "bold"), padx=4, pady=2,
                          activebackground="#2D2D2D", cursor="hand2", bd=0
                          ).pack(side="right")
                col += 1
            if not current_categories:
                tk.Label(chips_frame, text="No categories yet — add below",
                         font=FL, bg=CARD, fg=MUTED).pack(padx=8, pady=12)
            chips_frame.update_idletasks()
            chips_canvas.configure(scrollregion=chips_canvas.bbox("all"))

        # Add category row
        add_row = tk.Frame(cat_section, bg=BG)
        add_row.pack(fill="x", pady=(8, 0))

        settings_now = db.load_settings()
        mappings_now = settings_now.get("category_mappings") or []
        known_cats = sorted({m["name"] for m in mappings_now if m.get("name")})

        cat_combo_var = tk.StringVar()
        cat_combo = ttk.Combobox(add_row, textvariable=cat_combo_var,
                                 values=known_cats, font=FL, width=24)
        cat_combo.pack(side="left", padx=(0, 6), ipady=4)
        cat_combo.set("Type or select a category...")

        def _add_category(e=None):
            raw = cat_combo_var.get().strip()
            if not raw or raw == "Type or select a category...":
                return
            changed = False
            for item in [x.strip() for x in raw.split(",") if x.strip()]:
                if item and item not in current_categories:
                    current_categories.append(item)
                    changed = True
            if changed:
                _rebuild_chips()
                _update_live_count()
            cat_combo_var.set("")
            cat_combo.set("Type or select a category...")

        cat_combo.bind("<Return>", _add_category)
        cat_combo.bind("<<ComboboxSelected>>", _add_category)
        self._btn(add_row, "+ Add", _add_category, bg=ACCENT2).pack(side="left")

        # Quick-add pills
        quick_fr = tk.Frame(cat_section, bg=BG)
        quick_fr.pack(fill="x", pady=(6, 0))
        tk.Label(quick_fr, text="Quick:", font=("Segoe UI", 8),
                 bg=BG, fg=MUTED).pack(side="left", padx=(0, 6))
        for qc in ["Motor", "Cables", "Electrodes", "VFD", "Welding",
                   "Wire", "LED", "Nickel", "Screen", "Jointing", "Carbon Brush"]:
            def _qfn(kw=qc):
                def _q():
                    if kw not in current_categories:
                        current_categories.append(kw)
                        _rebuild_chips()
                        _update_live_count()
                return _q
            tk.Button(quick_fr, text=qc, command=_qfn(),
                      bg=CARD, fg=TEXTSUB, relief="flat", font=("Segoe UI", 8),
                      padx=6, pady=3, activebackground=ACCENT2,
                      activeforeground=TEXT, cursor="hand2", bd=0
                      ).pack(side="left", padx=(0, 3), pady=2)

        # ── Matching Settings section ─────────────────────────────────────
        _section_header(form_fr, "⚙️", "Matching Settings")

        loc_var, _ = _field(form_fr, "Location Keywords",
                            "comma-separated  (blank = all locations)")
        exc_var, _ = _field(form_fr, "Exclude Keywords",
                            "comma-separated  (tenders with these are skipped)")

        # ── Documents section ─────────────────────────────────────────────
        _section_header(form_fr, "📂", "Compliance Documents",
                        "optional fields marked ★")

        # Progress bar row
        prog_fr = tk.Frame(form_fr, bg=BG)
        prog_fr.pack(fill="x", pady=(0, 8))
        prog_text_var = tk.StringVar(value="")
        prog_lbl = tk.Label(prog_fr, textvariable=prog_text_var,
                            font=("Segoe UI", 8, "bold"), bg=BG, fg=MUTED)
        prog_lbl.pack(side="left")
        prog_canvas = tk.Canvas(prog_fr, bg=CARD, highlightthickness=0,
                                height=6, width=260)
        prog_canvas.pack(side="right")
        prog_bar = None

        def _refresh_doc_progress():
            nonlocal prog_bar
            up = sum(1 for k in REQUIRED_KEYS if doc_vars.get(k, tk.StringVar()).get().strip())
            pct = up / TOTAL_REQUIRED
            w = prog_canvas.winfo_width() or 260
            bar_w = max(4, int(w * pct))
            prog_canvas.delete("all")
            prog_canvas.create_rectangle(0, 0, w, 6, fill=CARD, outline="")
            color = DOC_UPLOADED if pct == 1.0 else (DOC_MISSING if pct > 0 else DOC_NONE)
            if bar_w > 0:
                prog_canvas.create_rectangle(0, 0, bar_w, 6,
                                             fill=color, outline="")
            prog_text_var.set(f"{up}/{TOTAL_REQUIRED} required docs")
            prog_lbl.configure(fg=DOC_UPLOADED if pct == 1.0 else MUTED)

        prog_canvas.bind("<Configure>", lambda e: _refresh_doc_progress())

        docs_outer = tk.Frame(form_fr, bg=CARD,
                              highlightthickness=1, highlightbackground=SECTION_LINE)
        docs_outer.pack(fill="x", pady=(0, 10))

        doc_vars = {}

        def _make_doc_row(parent, key, icon, label, optional, row_idx):
            row_bg = ROW_ALT if row_idx % 2 == 0 else CARD
            row = tk.Frame(parent, bg=row_bg)
            row.pack(fill="x")

            # Left: icon + label
            left_col = tk.Frame(row, bg=row_bg, width=200)
            left_col.pack(side="left", padx=(10, 4), pady=6)
            left_col.pack_propagate(False)

            icon_lbl = tk.Label(left_col, text=icon,
                                font=("Segoe UI", 11), bg=row_bg, fg=TEXT)
            icon_lbl.pack(side="left", padx=(0, 5))

            opt_marker = " ★" if optional else ""
            tk.Label(left_col, text=f"{label}{opt_marker}",
                     font=("Segoe UI", 9, "italic" if optional else "normal"),
                     bg=row_bg,
                     fg=TEXTSUB if optional else TEXT,
                     anchor="w").pack(side="left", fill="x")

            # Middle: status indicator + filename
            mid_col = tk.Frame(row, bg=row_bg)
            mid_col.pack(side="left", fill="x", expand=True, padx=(0, 6))

            path_var = tk.StringVar(value="")
            doc_vars[key] = path_var

            status_dot = tk.Label(mid_col, text="●", font=("Segoe UI", 10),
                                  bg=row_bg, fg=DOC_NONE)
            status_dot.pack(side="left", padx=(0, 4))

            name_lbl = tk.Label(mid_col, text="Not uploaded",
                                font=("Segoe UI", 8), bg=row_bg, fg=TEXTSUB,
                                anchor="w", cursor="hand2")
            name_lbl.pack(side="left", fill="x", expand=True)

            def _update_display(pv=path_var, nl=name_lbl, sd=status_dot, rbg=row_bg):
                p = pv.get().strip()
                if p and os.path.exists(p):
                    base = os.path.basename(p)
                    short = base[:36] + "..." if len(base) > 36 else base
                    nl.configure(text=short, fg=DOC_UPLOADED, cursor="hand2")
                    sd.configure(fg=DOC_UPLOADED)
                elif p:
                    nl.configure(text="⚠ File missing", fg=DOC_MISSING)
                    sd.configure(fg=DOC_MISSING)
                else:
                    nl.configure(text="Not uploaded", fg=TEXTSUB)
                    sd.configure(fg=DOC_NONE)
                _refresh_doc_progress()

            path_var.trace_add("write",
                lambda *a, pv=path_var, nl=name_lbl, sd=status_dot:
                    _update_display(pv, nl, sd))

            def _open_doc(pv=path_var):
                p = pv.get().strip()
                if p and os.path.exists(p):
                    try:
                        os.startfile(p)
                    except Exception:
                        import subprocess
                        try: subprocess.Popen(["xdg-open", p])
                        except Exception: pass
                elif p:
                    messagebox.showwarning(
                        "File Not Found", f"File no longer exists:\n{p}", parent=win)
                else:
                    messagebox.showinfo(
                        "No File", "No document uploaded yet.", parent=win)

            name_lbl.bind("<Button-1>", lambda e, pv=path_var: _open_doc(pv))

            # Right: Upload / Clear buttons
            btn_col = tk.Frame(row, bg=row_bg)
            btn_col.pack(side="right", padx=(0, 8), pady=4)

            def _upload(pv=path_var, lbl=label):
                fpath = filedialog.askopenfilename(
                    title=f"Select {lbl}",
                    filetypes=[
                        ("Documents",
                         "*.pdf *.PDF *.jpg *.jpeg *.png *.tiff *.tif"
                         " *.bmp *.xlsx *.xls *.doc *.docx"),
                        ("PDF Files", "*.pdf *.PDF"),
                        ("Images", "*.jpg *.jpeg *.png *.tiff *.tif *.bmp"),
                        ("All Files", "*.*"),
                    ],
                    parent=win
                )
                if fpath:
                    pv.set(fpath)

            def _clear(pv=path_var):
                pv.set("")

            self._btn(btn_col, "📁  Upload", _upload,
                      bg=UPLOAD_BG, fg="#79C0FF").pack(side="left", padx=(0, 4))
            self._btn(btn_col, "✕", _clear,
                      bg=CARD, fg=ERR).pack(side="left")

        # Draw doc rows with thin separator between groups
        groups = [
            ("Identity & Registration",
             [(k, ic, lb, op) for k, ic, lb, op in DOCUMENT_TYPES
              if k in ("gst", "pan", "msme")]),
            ("Income Tax Returns (3 Years)",
             [(k, ic, lb, op) for k, ic, lb, op in DOCUMENT_TYPES
              if k.startswith("itr")]),
            ("Balance Sheets (3 Years)",
             [(k, ic, lb, op) for k, ic, lb, op in DOCUMENT_TYPES
              if k.startswith("bs")]),
            ("Financial Certificates",
             [(k, ic, lb, op) for k, ic, lb, op in DOCUMENT_TYPES
              if k in ("turnover_cert", "shareholder")]),
        ]

        row_idx = 0
        for g_title, g_rows in groups:
            # Group sub-header inside the card
            g_hdr = tk.Frame(docs_outer, bg="#1A2029")
            g_hdr.pack(fill="x")
            tk.Label(g_hdr, text=f"  {g_title}",
                     font=("Segoe UI", 7, "bold"),
                     bg="#1A2029", fg=MUTED,
                     anchor="w", pady=4).pack(fill="x")
            for key, icon, label, optional in g_rows:
                _make_doc_row(docs_outer, key, icon, label, optional, row_idx)
                row_idx += 1

        tk.Frame(docs_outer, bg=CARD, height=4).pack(fill="x")

        # Initial progress render
        _refresh_doc_progress()

        # ── Form action buttons ────────────────────────────────────────────
        action_fr = tk.Frame(form_fr, bg=BG, pady=8)
        action_fr.pack(fill="x")
        _editing_idx = [None]

        def _save_current_firm():
            n = name_var.get().strip()
            if not n:
                messagebox.showerror("Error", "Firm Name is required.", parent=win)
                return
            if not current_categories:
                messagebox.showerror(
                    "Error", "Add at least one product category.", parent=win)
                return
            docs = {k: v.get() for k, v in doc_vars.items() if v.get().strip()}
            fd = {
                "name": n,
                "categories": list(current_categories),
                "locations": loc_var.get().strip(),
                "exclude_keywords": exc_var.get().strip(),
                "documents": docs,
            }
            if _editing_idx[0] is None:
                firms_list.append(fd)
                new_idx = len(firms_list) - 1
            else:
                firms_list[_editing_idx[0]] = fd
                new_idx = _editing_idx[0]
            _refresh_cards(selected=new_idx)
            _selected_idx[0] = new_idx
            _show_placeholder()
            _editing_idx[0] = None

        def _discard_form():
            _show_placeholder()
            _editing_idx[0] = None

        self._btn(action_fr, "💾  Save Firm", _save_current_firm,
                  bg=ACCENT).pack(side="left", padx=(0, 10), ipadx=6)
        self._btn(action_fr, "✕  Discard", _discard_form,
                  bg=CARD).pack(side="left")

        # ── Show / hide helpers ───────────────────────────────────────────
        def _show_form(firm_data=None, idx=None):
            placeholder_fr.grid_forget()
            _form_canvas.grid(row=0, column=0, sticky="nsew")
            _form_scroll.grid(row=0, column=1, sticky="ns")
            right_fr.columnconfigure(1, weight=0)
            _form_canvas.yview_moveto(0)
            name_var.set(firm_data.get("name", "") if firm_data else "")
            loc_var.set(firm_data.get("locations", "") if firm_data else "")
            exc_var.set(firm_data.get("exclude_keywords", "") if firm_data else "")
            current_categories.clear()
            if firm_data:
                current_categories.extend(
                    normalize_multi_value(firm_data.get("categories", [])))
            _rebuild_chips()
            _update_live_count()
            existing_docs = firm_data.get("documents", {}) if firm_data else {}
            for k, pv in doc_vars.items():
                pv.set(existing_docs.get(k, ""))
            _refresh_doc_progress()
            _editing_idx[0] = idx
            name_ent.focus_set()

        def _show_placeholder():
            _form_canvas.grid_forget()
            _form_scroll.grid_forget()
            placeholder_fr.grid(row=0, column=0, sticky="nsew")
            _refresh_cards(selected=None)
            _selected_idx[0] = None

        # ── Left button bar ───────────────────────────────────────────────
        def _delete_firm():
            idx = _selected_idx[0]
            if idx is None:
                messagebox.showwarning(
                    "Warning", "Select a firm first.", parent=win)
                return
            nm = firms_list[idx].get("name", "this firm")
            if messagebox.askyesno(
                    "Confirm Delete", f"Delete '{nm}'?", parent=win):
                firms_list.pop(idx)
                _show_placeholder()

        self._btn(lbtn_fr, "+ Add", lambda: _show_form(None, idx=None),
                  bg=ACCENT).pack(side="left", padx=(0, 4), fill="x", expand=True)
        self._btn(lbtn_fr, "🗑 Delete", _delete_firm,
                  bg=CARD, fg=ERR).pack(side="left", fill="x", expand=True)

        _refresh_cards()

        # ── Bottom bar content ────────────────────────────────────────────
        def save_all_firms():
            db.save_setting("firms", firms_list)
            self._log("ok", f"Saved {len(firms_list)} firm(s) to settings.")

            def do_re_evaluate():
                settings_inner = db.load_settings()
                inc_raw = settings_inner.get("include_keywords", "")
                exc_raw = settings_inner.get("exclude_keywords", "")
                inc_kws = [k.strip().lower() for k in inc_raw.split(",") if k.strip()]
                exc_kws = [k.strip().lower() for k in exc_raw.split(",") if k.strip()]
                updated_count = 0
                for r in self._records:
                    old_want = r.get("is_want_derived")
                    old_firm = r.get("matched_firm", "")
                    is_want = self._get_tender_status(r, inc_kws, exc_kws)
                    r["is_want_derived"] = is_want
                    if (old_want != r.get("is_want_derived")
                            or old_firm != r.get("matched_firm", "")):
                        updated_count += 1
                if updated_count > 0:
                    db.save_all_tenders(self._records)
                self.after(0, self._refresh_table_view)
                if hasattr(self, "_update_analytics"):
                    self.after(0, self._update_analytics)
                if hasattr(self, "_update_calendar"):
                    self.after(0, self._update_calendar)
                    self.after(0, self._update_details)
                self.after(0, lambda: self._log(
                    "ok", f"Re-evaluated: {updated_count} tender(s) updated."))

            LoadingDialog(self, title="Applying Rules",
                          message="Re-evaluating matching rules on all tenders...",
                          task_fn=do_re_evaluate)
            win.destroy()

        self._btn(bot_fr, "✓  Save & Apply to All Tenders", save_all_firms,
                  bg=ACCENT2).pack(side="right", padx=20, ipadx=12, ipady=2)
        self._btn(bot_fr, "Cancel", win.destroy,
                  bg=CARD).pack(side="right", padx=(0, 8))

    def _backup_db(self, parent_win=None):
        parent = parent_win or self
        if not os.path.exists(db.DB_FILE):
            messagebox.showwarning("Backup Failed", "No database file exists yet to back up.", parent=parent)
            return
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"tenders_db_backup_{timestamp}.db"
        
        dest_path = filedialog.asksaveasfilename(
            title="Backup Database",
            initialfile=default_name,
            filetypes=[("Database Files", "*.db"), ("All Files", "*.*")],
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

    def _restore_db(self, parent_win=None):
        parent = parent_win or self
        src_path = filedialog.askopenfilename(
            title="Restore Database",
            filetypes=[("Database Files", "*.db"), ("All Files", "*.*")],
            parent=parent
        )
        if not src_path:
            return
            
        confirm = messagebox.askyesno(
            "Confirm Restore",
            "Are you sure you want to restore the database from backup?\n\n"
            "This will overwrite all current tenders with the backup data. This action cannot be undone.",
            parent=parent
        )
        if not confirm:
            return
            
        try:
            import shutil
            os.makedirs(os.path.dirname(db.DB_FILE), exist_ok=True)
            shutil.copy2(src_path, db.DB_FILE)
            self._records = db.load_all_tenders()
            self._refresh_table_view()
            # Also refresh other tabs if active
            try:
                selected_tab = self.notebook.index(self.notebook.select())
                if selected_tab == 1:
                    self._update_calendar()
                elif selected_tab == 2:
                    self._update_analytics()
            except Exception:
                pass
            self._log("ok", f"Database restored successfully from: {src_path}")
            messagebox.showinfo("Restore Successful", "Database successfully restored from backup.", parent=parent)
        except Exception as e:
            self._log("err", f"Restore failed: {e}")
            messagebox.showerror("Restore Error", f"Failed to restore database:\n\n{e}", parent=parent)

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
            db.save_all_tenders([])
            self._records = []
            self._refresh_table_view()
            self._log("ok", "Database cleared successfully.")
            messagebox.showinfo("Database Cleared", "Local database cleared successfully.", parent=parent)
        except Exception as e:
            self._log("err", f"Failed to clear database: {e}")
            messagebox.showerror("Error", f"Failed to clear database: {e}", parent=parent)

    def _show_tags_dialog(self):
        sel = self.tv.selection()
        if not sel:
            messagebox.showwarning("No Rows Selected", "Please select at least one tender to manage tags.", parent=self)
            return

        selected_bids = []
        for iid in sel:
            bid = self.tv.set(iid, "bid_no")
            if bid:
                selected_bids.append(bid)

        if not selected_bids:
            return

        win = tk.Toplevel(self)
        win.grab_set()
        win.transient(self)
        win.title("Manage Tags")
        win.configure(bg=BG)
        win.resizable(False, False)

        x = self.winfo_x() + (self.winfo_width() - 400) // 2
        y = self.winfo_y() + (self.winfo_height() - 500) // 2
        win.geometry(f"400x500+{max(0, x)}+{max(0, y)}")

        tk.Label(win, text="Manage Tender Tags", font=FT, bg=BG, fg=TEXT).pack(pady=(12, 10))

        # List frame for checkboxes
        list_frame = tk.Frame(win, bg=PANEL, highlightthickness=1, highlightbackground="#30363D")
        list_frame.pack(fill="both", expand=True, padx=20, pady=6)

        # Scrollable canvas
        canvas = tk.Canvas(list_frame, bg=PANEL, highlightthickness=0)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        
        checkbox_fr = tk.Frame(canvas, bg=PANEL)
        canvas.create_window((0, 0), window=checkbox_fr, anchor="nw", tags="checkbox_fr")
        
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        checkbox_fr.bind("<Configure>", lambda e: canvas.configure(
            scrollregion=canvas.bbox("all")
        ))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(
            "checkbox_fr", width=e.width
        ))

        # Check existing tags on selected bids
        initial_tags = set()
        for r in self._records:
            if r.get("bid_no") in selected_bids:
                t_list = r.get("tags", [])
                if isinstance(t_list, str):
                    t_list = [t.strip() for t in t_list.split(",") if t.strip()]
                for t in t_list:
                    initial_tags.add(t)

        settings = db.load_settings()
        defined_tags = settings.get("defined_tags", ["Urgent", "Review", "Follow-up", "Sugar Mill"])
        
        chk_vars = {}
        
        def render_tags_list():
            for child in checkbox_fr.winfo_children():
                child.destroy()
                
            nonlocal defined_tags
            settings_inner = db.load_settings()
            defined_tags = settings_inner.get("defined_tags", ["Urgent", "Review", "Follow-up", "Sugar Mill"])
            
            for tag in defined_tags:
                row_fr = tk.Frame(checkbox_fr, bg=PANEL)
                row_fr.pack(fill="x", padx=10, pady=2)
                
                if tag not in chk_vars:
                    var = tk.BooleanVar(value=(tag in initial_tags))
                    chk_vars[tag] = var
                else:
                    var = chk_vars[tag]
                    
                chk = tk.Checkbutton(row_fr, text=tag, variable=var, bg=PANEL, fg=TEXT, selectcolor=BG,
                                     activebackground=PANEL, activeforeground=TEXT, font=FL, relief="flat",
                                     highlightthickness=0)
                chk.pack(side="left")
                
                def make_delete(t=tag):
                    return lambda: delete_tag_globally(t)
                del_btn = tk.Button(row_fr, text="×", command=make_delete(), bg=CARD, fg=ERR, relief="flat",
                                    font=("Segoe UI", 8, "bold"), padx=4, pady=0, activebackground=ACCENT2, cursor="hand2")
                del_btn.pack(side="right")

        def delete_tag_globally(tag_to_del):
            confirm = messagebox.askyesno(
                "Delete Tag",
                f"Are you sure you want to delete the tag '{tag_to_del}' globally?\n\nThis will remove it from all records.",
                parent=win
            )
            if not confirm:
                return
            settings_inner = db.load_settings()
            tags = settings_inner.get("defined_tags", ["Urgent", "Review", "Follow-up", "Sugar Mill"])
            if tag_to_del in tags:
                tags.remove(tag_to_del)
                db.save_setting("defined_tags", tags)
            
            for r in self._records:
                t_list = r.get("tags", [])
                if isinstance(t_list, str):
                    t_list = [t.strip() for t in t_list.split(",") if t.strip()]
                if tag_to_del in t_list:
                    t_list.remove(tag_to_del)
                    r["tags"] = t_list
            db.save_all_tenders(self._records)
            
            if tag_to_del in chk_vars:
                del chk_vars[tag_to_del]
            render_tags_list()
            self._refresh_table_view()

        # Add tag UI
        add_fr = tk.Frame(win, bg=BG)
        add_fr.pack(fill="x", padx=20, pady=6)
        
        new_tag_var = tk.StringVar()
        new_tag_ent = tk.Entry(add_fr, textvariable=new_tag_var, bg=CARD, fg=TEXT, insertbackground=TEXT,
                               relief="flat", font=FL, highlightthickness=1, highlightbackground="#30363D",
                               highlightcolor=ACCENT2)
        new_tag_ent.pack(side="left", fill="x", expand=True, padx=(0, 6))
        
        def add_new_tag_definition():
            val = new_tag_var.get().strip()
            if not val:
                return
            settings_inner = db.load_settings()
            tags = settings_inner.get("defined_tags", ["Urgent", "Review", "Follow-up", "Sugar Mill"])
            if val not in tags:
                tags.append(val)
                db.save_setting("defined_tags", tags)
            new_tag_var.set("")
            chk_vars[val] = tk.BooleanVar(value=True)
            render_tags_list()
            
        self._btn(add_fr, "Add Tag", add_new_tag_definition, bg=CARD).pack(side="right")

        def apply_selected_tags():
            selected_tags = [t for t, var in chk_vars.items() if var.get()]
            
            for r in self._records:
                if r.get("bid_no") in selected_bids:
                    r["tags"] = selected_tags
                    
            db.save_all_tenders(self._records)
            self._refresh_table_view()
            self._log("ok", f"Updated tags for {len(selected_bids)} tender(s).")
            win.destroy()
            
        btn_fr = tk.Frame(win, bg=BG)
        btn_fr.pack(fill="x", side="bottom", pady=15)
        
        self._btn(btn_fr, "  Apply  ", apply_selected_tags, bg=ACCENT2).pack(side="left", padx=(40, 10), expand=True, fill="x")
        self._btn(btn_fr, "  Cancel  ", win.destroy, bg=CARD).pack(side="right", padx=(10, 40), expand=True, fill="x")

        render_tags_list()
    def _show_comments_dialog(self):
        sel = self.tv.selection()
        if not sel:
            messagebox.showwarning("No Rows Selected", "Please select a tender to view or add comments.", parent=self)
            return

        iid = sel[0]
        bid_no = self.tv.set(iid, "bid_no")
        if not bid_no:
            return

        # Find the record
        rec = None
        for r in self._records:
            if r.get("bid_no") == bid_no:
                rec = r
                break
        
        if not rec:
            return

        current_comments = rec.get("comments") or ""

        win = tk.Toplevel(self)
        win.grab_set()
        win.transient(self)
        win.title(f"Tender Comments - {bid_no}")
        win.configure(bg=BG)
        win.resizable(False, False)

        x = self.winfo_x() + (self.winfo_width() - 480) // 2
        y = self.winfo_y() + (self.winfo_height() - 320) // 2
        win.geometry(f"480x320+{max(0, x)}+{max(0, y)}")

        tk.Label(win, text=f"Comments for {bid_no}", font=FT, bg=BG, fg=TEXT).pack(pady=(12, 10))

        btn_fr = tk.Frame(win, bg=BG)
        btn_fr.pack(fill="x", side="bottom", pady=12, padx=20)

        txt_frame = tk.Frame(win, bg=PANEL, highlightthickness=1, highlightbackground="#30363D")
        txt_frame.pack(fill="both", expand=True, padx=20, pady=6)

        comments_text = tk.Text(txt_frame, bg=CARD, fg=TEXT, insertbackground=TEXT,
                                relief="flat", font=FL, wrap="word", highlightthickness=0,
                                padx=8, pady=8)
        comments_text.pack(fill="both", expand=True)
        comments_text.insert("1.0", current_comments)

        def save_comments():
            comments = comments_text.get("1.0", "end-1c").strip()
            # Save to database
            import db
            db.upsert_tender_field(bid_no, "comments", comments)
            
            # Clear embedding to trigger re-embedding with new comments
            db.upsert_tender_field(bid_no, "embedding", None)
            
            # Update local record
            rec["comments"] = comments
            rec["embedding"] = None
            
            # Trigger background embedding in background thread
            try:
                import vector_search
                vector_search.start_background_embedding_worker()
            except Exception as ex:
                self._log("warn", f"Could not restart background embedder: {ex}")
            
            # Refresh table tab and details side panel
            self._refresh_table_view()
            
            # Run active learning to immediately apply any comment rules
            try:
                db.apply_active_learning_from_comments()
                # Reload the record from the database to reflect active learning corrections
                updated_rec = db.get_tender(bid_no)
                if updated_rec:
                    rec.update(updated_rec)
            except Exception as al_err:
                self._log("warn", f"Could not apply active learning: {al_err}")
                
            if hasattr(self, "table_tab") and self.table_tab and hasattr(self.table_tab, "detail_panel") and self.table_tab.detail_panel:
                self.table_tab.detail_panel.on_treeview_select(None)
                
            self._log("ok", f"Saved comments for bid {bid_no}. Regenerating embedding in background.")
            win.destroy()

        self._btn(btn_fr, "Save Comments", save_comments, bg=ACCENT2).pack(side="right", padx=4)
        self._btn(btn_fr, "Cancel", win.destroy, bg=CARD).pack(side="right", padx=4)


    def _show_filter_rules_dialog(self):
        win = tk.Toplevel(self)
        win.grab_set()
        win.transient(self)
        win.title("Filter & Refinement Rules")
        win.configure(bg=BG)
        win.resizable(False, False)
        
        x = self.winfo_x() + (self.winfo_width() - 550) // 2
        y = self.winfo_y() + (self.winfo_height() - 680) // 2
        win.geometry(f"550x680+{max(0, x)}+{max(0, y)}")
        
        tk.Label(win, text="Keyword Refinement Rules", font=FT, bg=BG, fg=TEXT).pack(pady=(12, 4))
        
        settings = db.load_settings()
        inc_raw = settings.get("include_keywords", "")
        exc_raw = settings.get("exclude_keywords", "")
        
        inc_kws = [k.strip().lower() for k in inc_raw.split(",") if k.strip()]
        exc_kws = [k.strip().lower() for k in exc_raw.split(",") if k.strip()]

        # Load category mappings
        mappings_data = settings.get("category_mappings") or []

        def style_mini_btn(btn, normal_bg=CARD, hover_bg="#30363D", fg=TEXT):
            btn.configure(bg=normal_bg, fg=fg, relief="flat", activebackground=hover_bg, activeforeground=TEXT, cursor="hand2", font=FL)
            btn.bind("<Enter>", lambda e: btn.configure(bg=hover_bg))
            btn.bind("<Leave>", lambda e: btn.configure(bg=normal_bg))

        def remove_keyword(val, lst, txt_widget, is_include):
            if val in lst:
                lst.remove(val)
            render_chips(txt_widget, lst, is_include)

        def add_keyword(entry_widget, lst, txt_widget, is_include):
            val = entry_widget.get().strip().lower()
            if not val:
                return
            new_kws = [k.strip() for k in val.split(",") if k.strip()]
            for kw in new_kws:
                if kw not in lst:
                    lst.append(kw)
            entry_widget.delete(0, "end")
            render_chips(txt_widget, lst, is_include)

        def clear_all(lst, txt_widget, is_include):
            lst.clear()
            render_chips(txt_widget, lst, is_include)

        def render_chips(txt_widget, kw_list, is_include):
            txt_widget.configure(state="normal")
            txt_widget.delete("1.0", "end")
            
            bg_color = "#1A3A2A" if is_include else "#3A1A1A"
            border_color = SUCCESS if is_include else ERR
            
            for kw in kw_list:
                chip = tk.Frame(txt_widget, bg=bg_color, highlightthickness=1, highlightbackground=border_color, padx=6, pady=2)
                
                lbl = tk.Label(chip, text=kw, font=FL, bg=bg_color, fg=TEXT)
                lbl.pack(side="left")
                
                def make_remove(val=kw, lst=kw_list, w=txt_widget, inc=is_include):
                    return lambda: remove_keyword(val, lst, w, inc)
                    
                btn = tk.Button(chip, text="×", font=("Segoe UI", 9, "bold"), bg=bg_color, fg=MUTED,
                                activebackground=bg_color, activeforeground=TEXT, relief="flat",
                                cursor="hand2", command=make_remove(), padx=2, pady=0)
                btn.pack(side="left", padx=(4, 0))
                
                btn.bind("<Enter>", lambda e, b=btn: b.configure(fg=ERR))
                btn.bind("<Leave>", lambda e, b=btn: b.configure(fg=MUTED))
                
                txt_widget.window_create("end", window=chip)
                txt_widget.insert("end", " ")
                
            txt_widget.configure(state="disabled")

        # Create Notebook for tabs
        nb = ttk.Notebook(win)
        nb.pack(fill="both", expand=True, padx=10, pady=(5, 5))
        
        tab_filters = tk.Frame(nb, bg=BG)
        tab_mappings = tk.Frame(nb, bg=BG)
        tab_val_mappings = tk.Frame(nb, bg=BG)
        
        nb.add(tab_filters, text="  Keyword Filters  ")
        nb.add(tab_mappings, text="  Category Mappings  ")
        nb.add(tab_val_mappings, text="  Field Mappings  ")

        # ── Tab 1: Keyword Filters ──
        # ── Include Section ──
        inc_frame = tk.Frame(tab_filters, bg=PANEL, padx=12, pady=10, highlightthickness=1, highlightbackground="#30363D")
        inc_frame.pack(fill="both", expand=True, padx=15, pady=6)
        
        inc_hdr = tk.Frame(inc_frame, bg=PANEL)
        inc_hdr.pack(fill="x")
        tk.Label(inc_hdr, text="Include Keywords (Wants):", font=("Segoe UI", 9, "bold"), bg=PANEL, fg=MUTED).pack(side="left")
        
        inc_clear_btn = tk.Button(inc_hdr, text="Clear All")
        inc_clear_btn.pack(side="right")
        style_mini_btn(inc_clear_btn, normal_bg=PANEL, hover_bg="#2A1B1B", fg=ERR)
        
        tk.Label(inc_frame, text="Tenders matching these words are labeled as 'Wants'.", font=("Segoe UI", 8), bg=PANEL, fg=TEXTSUB).pack(anchor="w", pady=(2, 4))
        
        inc_input_row = tk.Frame(inc_frame, bg=PANEL)
        inc_input_row.pack(fill="x", pady=4)
        
        inc_entry = tk.Entry(inc_input_row, bg=CARD, fg=TEXT, insertbackground=TEXT, relief="flat", font=FL,
                             highlightthickness=1, highlightbackground="#30363D", highlightcolor=ACCENT2)
        inc_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        
        inc_add_btn = tk.Button(inc_input_row, text="  + Add  ")
        inc_add_btn.pack(side="right")
        style_mini_btn(inc_add_btn, normal_bg=CARD, hover_bg="#30363D", fg=TEXT)
        
        # Chip Container
        inc_chip_fr = tk.Frame(inc_frame, bg=CARD, highlightthickness=1, highlightbackground="#30363D")
        inc_chip_fr.pack(fill="both", expand=True, pady=(4, 0))
        
        inc_txt = tk.Text(inc_chip_fr, bg=CARD, fg=TEXT, insertbackground=TEXT, relief="flat", font=FL, wrap="word", height=4)
        inc_sb = ttk.Scrollbar(inc_chip_fr, orient="vertical", command=inc_txt.yview)
        inc_txt.configure(yscrollcommand=inc_sb.set)
        inc_sb.pack(side="right", fill="y")
        inc_txt.pack(side="left", fill="both", expand=True, padx=4, pady=4)

        inc_clear_btn.configure(command=lambda: clear_all(inc_kws, inc_txt, True))
        inc_add_btn.configure(command=lambda: add_keyword(inc_entry, inc_kws, inc_txt, True))
        inc_entry.bind("<Return>", lambda e: add_keyword(inc_entry, inc_kws, inc_txt, True))

        # ── Exclude Section ──
        exc_frame = tk.Frame(tab_filters, bg=PANEL, padx=12, pady=10, highlightthickness=1, highlightbackground="#30363D")
        exc_frame.pack(fill="both", expand=True, padx=15, pady=6)
        
        exc_hdr = tk.Frame(exc_frame, bg=PANEL)
        exc_hdr.pack(fill="x")
        tk.Label(exc_hdr, text="Exclude Keywords (Don't Wants):", font=("Segoe UI", 9, "bold"), bg=PANEL, fg=MUTED).pack(side="left")
        
        exc_clear_btn = tk.Button(exc_hdr, text="Clear All")
        exc_clear_btn.pack(side="right")
        style_mini_btn(exc_clear_btn, normal_bg=PANEL, hover_bg="#2A1B1B", fg=ERR)
        
        tk.Label(exc_frame, text="Tenders matching these words are ignored as 'Don't Wants'.", font=("Segoe UI", 8), bg=PANEL, fg=TEXTSUB).pack(anchor="w", pady=(2, 4))
        
        exc_input_row = tk.Frame(exc_frame, bg=PANEL)
        exc_input_row.pack(fill="x", pady=4)
        
        exc_entry = tk.Entry(exc_input_row, bg=CARD, fg=TEXT, insertbackground=TEXT, relief="flat", font=FL,
                             highlightthickness=1, highlightbackground="#30363D", highlightcolor=ACCENT2)
        exc_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        
        exc_add_btn = tk.Button(exc_input_row, text="  + Add  ")
        exc_add_btn.pack(side="right")
        style_mini_btn(exc_add_btn, normal_bg=CARD, hover_bg="#30363D", fg=TEXT)
        
        # Chip Container
        exc_chip_fr = tk.Frame(exc_frame, bg=CARD, highlightthickness=1, highlightbackground="#30363D")
        exc_chip_fr.pack(fill="both", expand=True, pady=(4, 0))
        
        exc_txt = tk.Text(exc_chip_fr, bg=CARD, fg=TEXT, insertbackground=TEXT, relief="flat", font=FL, wrap="word", height=4)
        exc_sb = ttk.Scrollbar(exc_chip_fr, orient="vertical", command=exc_txt.yview)
        exc_txt.configure(yscrollcommand=exc_sb.set)
        exc_sb.pack(side="right", fill="y")
        exc_txt.pack(side="left", fill="both", expand=True, padx=4, pady=4)

        exc_clear_btn.configure(command=lambda: clear_all(exc_kws, exc_txt, False))
        exc_add_btn.configure(command=lambda: add_keyword(exc_entry, exc_kws, exc_txt, False))
        exc_entry.bind("<Return>", lambda e: add_keyword(exc_entry, exc_kws, exc_txt, False))

        render_chips(inc_txt, inc_kws, True)
        render_chips(exc_txt, exc_kws, False)

        # ── Tab 2: Category Mappings ──
        map_frame = tk.Frame(tab_mappings, bg=PANEL, padx=12, pady=10, highlightthickness=1, highlightbackground="#30363D")
        map_frame.pack(fill="both", expand=True, padx=15, pady=6)
        
        # Category Selector Row
        sel_fr = tk.Frame(map_frame, bg=PANEL)
        sel_fr.pack(fill="x", pady=(4, 8))
        
        tk.Label(sel_fr, text="Select Category:", font=("Segoe UI", 9, "bold"), bg=PANEL, fg=MUTED).pack(side="left", padx=(0, 6))
        
        cat_cb = ttk.Combobox(sel_fr, state="readonly", font=FL)
        cat_cb.pack(side="left", fill="x", expand=True, padx=(0, 6))
        
        def add_category():
            new_name = simpledialog.askstring("New Category", "Enter standard category name:", parent=win)
            if not new_name:
                return
            new_name_clean = new_name.strip()
            if not new_name_clean:
                return
            for m in mappings_data:
                if m["name"].lower() == new_name_clean.lower():
                    messagebox.showwarning("Duplicate Category", f"Category '{new_name_clean}' already exists.", parent=win)
                    return
            mappings_data.append({"name": new_name_clean, "keywords": []})
            refresh_cat_list(new_name_clean)
            
        def delete_category():
            sel = cat_cb.get()
            if not sel:
                return
            confirm = messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete the category '{sel}' and its mapping keywords?", parent=win)
            if not confirm:
                return
            idx_to_remove = -1
            for idx, m in enumerate(mappings_data):
                if m["name"] == sel:
                    idx_to_remove = idx
                    break
            if idx_to_remove != -1:
                mappings_data.pop(idx_to_remove)
            refresh_cat_list()
            
        cat_new_btn = tk.Button(sel_fr, text=" + New ", command=add_category)
        cat_new_btn.pack(side="left", padx=2)
        style_mini_btn(cat_new_btn, normal_bg=CARD, hover_bg="#30363D", fg=TEXT)
        
        cat_del_btn = tk.Button(sel_fr, text=" 🗑 Delete ", command=delete_category)
        cat_del_btn.pack(side="left", padx=2)
        style_mini_btn(cat_del_btn, normal_bg=CARD, hover_bg="#2A1B1B", fg=ERR)

        # Keyword management for Category
        map_hdr = tk.Frame(map_frame, bg=PANEL)
        map_hdr.pack(fill="x", pady=(8, 2))
        tk.Label(map_hdr, text="Mapping Keywords for Selected:", font=("Segoe UI", 9, "bold"), bg=PANEL, fg=MUTED).pack(side="left")
        # Button to review LLM suggestions
        def open_llm_suggestions():
            pending = db.load_settings().get("llm_pending_keyword_suggestions", {}) or {}
            if not pending:
                messagebox.showinfo("No Suggestions", "No pending LLM keyword suggestions found.", parent=win)
                return
            sug_win = tk.Toplevel(win)
            sug_win.grab_set()
            sug_win.transient(win)
            sug_win.title("LLM Suggested Keywords")
            sug_win.configure(bg=BG)
            sug_win.geometry("600x400")

            tk.Label(sug_win, text="LLM Suggested Keywords — Review and accept to merge into mappings", font=FT, bg=BG, fg=TEXT).pack(pady=(8,6))

            list_fr = tk.Frame(sug_win, bg=PANEL, padx=8, pady=8)
            list_fr.pack(fill="both", expand=True, padx=10, pady=6)

            canvas = tk.Canvas(list_fr, bg=PANEL, highlightthickness=0)
            vsb = ttk.Scrollbar(list_fr, orient="vertical", command=canvas.yview)
            inner = tk.Frame(canvas, bg=PANEL)
            canvas.create_window((0,0), window=inner, anchor="nw")
            canvas.configure(yscrollcommand=vsb.set)
            vsb.pack(side="right", fill="y")
            canvas.pack(side="left", fill="both", expand=True)

            def on_cfg(e):
                canvas.configure(scrollregion=canvas.bbox("all"))
            inner.bind("<Configure>", on_cfg)

            # Render suggestions
            rows = []
            for cat, kws in pending.items():
                fr = tk.Frame(inner, bg=CARD, padx=8, pady=6, highlightthickness=1, highlightbackground="#30363D")
                fr.pack(fill="x", pady=6, padx=6)
                tk.Label(fr, text=cat, font=("Segoe UI",9,"bold"), bg=CARD, fg=TEXT).pack(anchor="w")
                tk.Label(fr, text=", ".join(kws), font=("Segoe UI",8), bg=CARD, fg=TEXTSUB, wraplength=520, justify="left").pack(anchor="w", pady=(4,6))

                btn_row = tk.Frame(fr, bg=CARD)
                btn_row.pack(fill="x")

                def make_accept(c=cat, ks=kws):
                    def _accept():
                        settings_inner = db.load_settings()
                        mappings_inner = settings_inner.get("category_mappings") or []
                        # Find or create category entry
                        ent = None
                        for m in mappings_inner:
                            if m.get("name","").lower() == c.lower():
                                ent = m
                                break
                        if not ent:
                            ent = {"name": c, "keywords": []}
                            mappings_inner.append(ent)
                        for k in ks:
                            if k not in ent["keywords"]:
                                ent["keywords"].append(k)
                        db.save_setting("category_mappings", mappings_inner)
                        # remove pending
                        pending2 = settings_inner.get("llm_pending_keyword_suggestions", {}) or {}
                        if c in pending2:
                            pending2.pop(c, None)
                        db.save_setting("llm_pending_keyword_suggestions", pending2)
                        messagebox.showinfo("Accepted", f"Merged suggestions into category '{c}'", parent=sug_win)
                        sug_win.destroy()
                    return _accept

                def make_reject(c=cat):
                    def _reject():
                        settings_inner = db.load_settings()
                        pending2 = settings_inner.get("llm_pending_keyword_suggestions", {}) or {}
                        if c in pending2:
                            pending2.pop(c, None)
                        db.save_setting("llm_pending_keyword_suggestions", pending2)
                        messagebox.showinfo("Discarded", f"Discarded suggestions for '{c}'", parent=sug_win)
                        sug_win.destroy()
                    return _reject

                tk.Button(btn_row, text="Accept & Merge", command=make_accept(), bg=ACCENT2).pack(side="left", padx=6)
                tk.Button(btn_row, text="Discard", command=make_reject(), bg=CARD).pack(side="left", padx=6)

            return

        sug_btn = tk.Button(map_hdr, text="🔍 Review LLM Suggestions", command=open_llm_suggestions)
        sug_btn.pack(side="right")
        style_mini_btn(sug_btn, normal_bg=PANEL, hover_bg="#30363D", fg=TEXT)
        
        def clear_map_kws():
            m = get_selected_mapping()
            if not m:
                return
            m["keywords"].clear()
            render_chips(map_txt, m["keywords"], True)
            
        map_clear_btn = tk.Button(map_hdr, text="Clear All", command=clear_map_kws)
        map_clear_btn.pack(side="right")
        style_mini_btn(map_clear_btn, normal_bg=PANEL, hover_bg="#2A1B1B", fg=ERR)
        
        tk.Label(map_frame, text="Tenders containing ALL of these words will map to this category.", font=("Segoe UI", 8), bg=PANEL, fg=TEXTSUB).pack(anchor="w", pady=(0, 4))
        
        map_input_row = tk.Frame(map_frame, bg=PANEL)
        map_input_row.pack(fill="x", pady=4)
        
        map_entry = tk.Entry(map_input_row, bg=CARD, fg=TEXT, insertbackground=TEXT, relief="flat", font=FL,
                             highlightthickness=1, highlightbackground="#30363D", highlightcolor=ACCENT2)
        map_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        
        def add_map_kw():
            m = get_selected_mapping()
            if not m:
                return
            val = map_entry.get().strip().lower()
            if not val:
                return
            new_kws = [k.strip() for k in val.split(",") if k.strip()]
            for kw in new_kws:
                if kw not in m["keywords"]:
                    m["keywords"].append(kw)
            map_entry.delete(0, "end")
            render_chips(map_txt, m["keywords"], True)
            
        map_add_btn = tk.Button(map_input_row, text="  + Add  ", command=add_map_kw)
        map_add_btn.pack(side="right")
        style_mini_btn(map_add_btn, normal_bg=CARD, hover_bg="#30363D", fg=TEXT)
        map_entry.bind("<Return>", lambda e: add_map_kw())
        
        # Chip Container for Category
        map_chip_fr = tk.Frame(map_frame, bg=CARD, highlightthickness=1, highlightbackground="#30363D")
        map_chip_fr.pack(fill="both", expand=True, pady=(4, 0))
        
        map_txt = tk.Text(map_chip_fr, bg=CARD, fg=TEXT, insertbackground=TEXT, relief="flat", font=FL, wrap="word", height=4)
        map_sb = ttk.Scrollbar(map_chip_fr, orient="vertical", command=map_txt.yview)
        map_txt.configure(yscrollcommand=map_sb.set)
        map_sb.pack(side="right", fill="y")
        map_txt.pack(side="left", fill="both", expand=True, padx=4, pady=4)

        def get_selected_mapping():
            sel = cat_cb.get()
            for m in mappings_data:
                if m["name"] == sel:
                    return m
            return None
            
        def on_cat_change(event=None):
            m = get_selected_mapping()
            if m:
                render_chips(map_txt, m["keywords"], True)
            else:
                map_txt.configure(state="normal")
                map_txt.delete("1.0", "end")
                map_txt.configure(state="disabled")
                
        cat_cb.bind("<<ComboboxSelected>>", on_cat_change)
        
        def refresh_cat_list(select_name=None):
            names = [m["name"] for m in mappings_data]
            cat_cb.configure(values=names)
            if names:
                if select_name in names:
                    cat_cb.set(select_name)
                else:
                    cat_cb.set(names[0])
            else:
                cat_cb.set("")
            on_cat_change()
            
        refresh_cat_list()

        # ── Tab 3: Field Value Mappings ──
        val_mappings_data = settings.get("value_mappings", [])
        
        # Build maps for human-readable labels to DB columns
        id_to_label = {col[0]: col[1] for col in TV_COLS}
        label_to_id = {col[1]: col[0] for col in TV_COLS}
        
        # Scrollable treeview inside Field Mappings
        tree_frame = tk.Frame(tab_val_mappings, bg=PANEL, padx=10, pady=10, highlightthickness=1, highlightbackground="#30363D")
        tree_frame.pack(fill="both", expand=True, padx=15, pady=6)
        
        val_cols = ("field", "key", "phrase")
        val_tree = ttk.Treeview(tree_frame, columns=val_cols, show="headings", height=5)
        val_tree.heading("field", text="Table Header")
        val_tree.heading("key", text="Mapped Key")
        val_tree.heading("phrase", text="Phrases to Link To")
        
        val_tree.column("field", width=120, anchor="w")
        val_tree.column("key", width=100, anchor="w")
        val_tree.column("phrase", width=260, anchor="w")
        
        val_vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=val_tree.yview)
        val_tree.configure(yscrollcommand=val_vsb.set)
        val_vsb.pack(side="right", fill="y")
        val_tree.pack(side="left", fill="both", expand=True)
        
        def refresh_val_tree():
            for row in val_tree.get_children():
                val_tree.delete(row)
            for rule in val_mappings_data:
                field_id = rule.get("field", "")
                field_lbl = id_to_label.get(field_id, field_id)
                val_tree.insert("", "end", values=(field_lbl, rule.get("key", ""), rule.get("phrase", "")))
                
        refresh_val_tree()
        
        # Add New Rule Form
        input_frame = tk.Frame(tab_val_mappings, bg=PANEL, padx=12, pady=10, highlightthickness=1, highlightbackground="#30363D")
        input_frame.pack(fill="x", padx=15, pady=6)
        
        tk.Label(input_frame, text="Add New Field Mapping Rule:", font=("Segoe UI", 9, "bold"), bg=PANEL, fg=MUTED).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))
        
        tk.Label(input_frame, text="Table Header:", font=FL, bg=PANEL, fg=TEXTSUB).grid(row=1, column=0, sticky="w", pady=3)
        field_labels = sorted(list(id_to_label.values()))
        field_sel_cb = ttk.Combobox(input_frame, values=field_labels, state="readonly", font=FL)
        field_sel_cb.grid(row=1, column=1, sticky="ew", padx=(10, 0), pady=3)
        if field_labels:
            default_sel = "Consignee/Location" if "Consignee/Location" in field_labels else field_labels[0]
            field_sel_cb.set(default_sel)
            
        tk.Label(input_frame, text="Mapped Key:", font=FL, bg=PANEL, fg=TEXTSUB).grid(row=2, column=0, sticky="w", pady=3)
        key_entry_var = tk.StringVar()
        key_entry = tk.Entry(input_frame, textvariable=key_entry_var, bg=CARD, fg=TEXT, insertbackground=TEXT, relief="flat", font=FL, highlightthickness=1, highlightbackground="#30363D", highlightcolor=ACCENT2)
        key_entry.grid(row=2, column=1, sticky="ew", padx=(10, 0), pady=3)
        
        tk.Label(input_frame, text="Phrase to Link:", font=FL, bg=PANEL, fg=TEXTSUB).grid(row=3, column=0, sticky="nw", pady=3)
        phrase_txt = tk.Text(input_frame, bg=CARD, fg=TEXT, insertbackground=TEXT, relief="flat", font=FL, height=3, highlightthickness=1, highlightbackground="#30363D", highlightcolor=ACCENT2, wrap="word")
        phrase_txt.grid(row=3, column=1, sticky="ew", padx=(10, 0), pady=3)
        
        input_frame.columnconfigure(1, weight=1)
        
        # Action Buttons
        btn_row = tk.Frame(tab_val_mappings, bg=BG)
        btn_row.pack(fill="x", padx=15, pady=4)
        
        def add_val_mapping():
            lbl = field_sel_cb.get()
            field_id = label_to_id.get(lbl, lbl)
            key_val = key_entry_var.get().strip()
            phrase_val = phrase_txt.get("1.0", "end").strip()
            
            if not key_val:
                messagebox.showwarning("Validation Error", "Mapped Key is required.", parent=win)
                return
            if not phrase_val:
                messagebox.showwarning("Validation Error", "Phrase to Link is required.", parent=win)
                return
                
            for rule in val_mappings_data:
                if rule.get("field") == field_id and rule.get("phrase") == phrase_val:
                    messagebox.showwarning("Duplicate Rule", "A mapping for this field and phrase already exists.", parent=win)
                    return
                    
            val_mappings_data.append({
                "field": field_id,
                "key": key_val,
                "phrase": phrase_val
            })
            key_entry_var.set("")
            phrase_txt.delete("1.0", "end")
            refresh_val_tree()
            
        def delete_val_mapping():
            sel = val_tree.selection()
            if not sel:
                messagebox.showwarning("No Selection", "Please select a mapping rule to delete.", parent=win)
                return
            for iid in sel:
                vals = val_tree.item(iid, "values")
                field_lbl, key_val, phrase_val = vals
                field_id = label_to_id.get(field_lbl, field_lbl)
                for idx, rule in enumerate(val_mappings_data):
                    if rule.get("field") == field_id and rule.get("key") == key_val and rule.get("phrase") == phrase_val:
                        val_mappings_data.pop(idx)
                        break
            refresh_val_tree()
            
        add_btn = tk.Button(btn_row, text=" + Add Mapping Rule ", command=add_val_mapping)
        add_btn.pack(side="left", padx=2)
        style_mini_btn(add_btn, normal_bg=CARD, hover_bg="#30363D", fg=TEXT)
        
        del_btn = tk.Button(btn_row, text=" 🗑 Delete Rule ", command=delete_val_mapping)
        del_btn.pack(side="right", padx=2)
        style_mini_btn(del_btn, normal_bg=CARD, hover_bg="#2A1B1B", fg=ERR)

        def save_rules():
            # Save cleaned comma-separated list
            clean_inc = ",".join(k.strip().lower() for k in inc_kws if k.strip())
            clean_exc = ",".join(k.strip().lower() for k in exc_kws if k.strip())
            db.save_setting("include_keywords", clean_inc)
            db.save_setting("exclude_keywords", clean_exc)
            
            # Save Category Mappings
            clean_mappings = []
            for m in mappings_data:
                clean_kws = [k.strip().lower() for k in m.get("keywords", []) if k.strip()]
                clean_mappings.append({"name": m["name"].strip(), "keywords": clean_kws})
            db.save_setting("category_mappings", clean_mappings)

            # Save Field Value Mappings
            db.save_setting("value_mappings", val_mappings_data)
            
            # Re-map all existing tenders in the DB!
            import parser
            for r in self._records:
                # 1. Apply value mappings first
                db.apply_value_mappings(r)
                # 2. Apply category mappings next
                raw_text = r.get("items") or r.get("category") or ""
                r["category"] = parser.map_category(raw_text, allow_llm=False)
                
            db.save_all_tenders(self._records)
            self._log("info", "Filter rules, Category mappings, and Field mappings updated.")
            self._refresh_table_view()
            
            # Refresh other tabs
            try:
                selected_tab = self.notebook.index(self.notebook.select())
                if selected_tab == 1:
                    self._update_calendar()
                elif selected_tab == 2:
                    self._update_analytics()
            except Exception:
                pass
                
            win.destroy()
            
        btn_fr = tk.Frame(win, bg=BG)
        btn_fr.pack(fill="x", side="bottom", pady=15)
        
        self._btn(btn_fr, "  Save & Apply  ", save_rules, bg=ACCENT2).pack(side="left", padx=(60, 10), expand=True, fill="x")
        self._btn(btn_fr, "  Cancel  ", win.destroy, bg=CARD).pack(side="right", padx=(10, 60), expand=True, fill="x")
