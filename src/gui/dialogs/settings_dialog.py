# -*- coding: utf-8 -*-
import os
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
try:
    import keyring
except ImportError:
    keyring = None

# Local imports
from config import BG, PANEL, CARD, ACCENT2, MUTED, TEXT, TEXTSUB, ERR, SUCCESS, WARN, FT, FL
import db
from .loading_dialog import LoadingDialog

class SettingsDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.grab_set()
        self.transient(parent)
        self.title("Settings")
        self.configure(bg=BG)
        self.resizable(True, True)
        
        window_height = 900
        window_width = 1000
        self.minsize(1000, 700)

        x = parent.winfo_x() + (parent.winfo_width() - window_width) // 2
        y = parent.winfo_y() + (parent.winfo_height() - window_height) // 2
        self.geometry(f"{window_width}x{window_height}+{max(0, x)}+{max(0, y)}")

        # Title Label
        tk.Label(self, text="Application Settings", font=FT, bg=BG, fg=TEXT).pack(pady=(12, 10))

        # DB Frame
        db_frame = tk.Frame(self, bg=PANEL, padx=12, pady=10, highlightthickness=1, highlightbackground="#30363D")
        db_frame.pack(fill="x", padx=15, pady=6)
        
        tk.Label(db_frame, text="Local Database Storage Location:", font=("Segoe UI", 9, "bold"), bg=PANEL, fg=MUTED).pack(anchor="w")
        
        db_path_var = tk.StringVar(value=db.DB_FILE.replace(os.path.expanduser("~"), "~"))
        db_lbl = tk.Label(db_frame, textvariable=db_path_var, font=FL, bg=PANEL, fg=TEXTSUB, anchor="w")
        db_lbl.pack(fill="x", pady=(4, 4))
        
        def run_db_change():
            self._change_db_location(parent_win=self)
            db_path_var.set(db.DB_FILE.replace(os.path.expanduser("~"), "~"))
            
        btn_db_row = tk.Frame(db_frame, bg=PANEL)
        btn_db_row.pack(fill="x", pady=(4, 0))
        self._btn(btn_db_row, "Relocate Database...", run_db_change, bg=CARD).pack(side="left", padx=(0, 6))
        self._btn(btn_db_row, "Backup Database...", lambda: self._backup_db(self), bg=CARD).pack(side="left", padx=6)
        self._btn(btn_db_row, "Restore Database...", lambda: self._restore_db(self), bg=CARD).pack(side="left", padx=6)
        self._btn(btn_db_row, "Clear Database", lambda: self._clear_db(self), bg=CARD, fg=ERR).pack(side="right")

        # Excel Frame
        ex_frame = tk.Frame(self, bg=PANEL, padx=12, pady=10, highlightthickness=1, highlightbackground="#30363D")
        ex_frame.pack(fill="x", padx=15, pady=6)
        
        tk.Label(ex_frame, text="Excel Export Folder:", font=("Segoe UI", 9, "bold"), bg=PANEL, fg=MUTED).pack(anchor="w")
        
        ex_path_var = tk.StringVar(value=self.parent.save_folder.get().replace(os.path.expanduser("~"), "~"))
        ex_lbl = tk.Label(ex_frame, textvariable=ex_path_var, font=FL, bg=PANEL, fg=TEXTSUB, anchor="w")
        ex_lbl.pack(side="left", fill="x", expand=True, pady=(4, 0))
        
        def run_ex_change():
            d = filedialog.askdirectory(title="Select folder for Excel Tenders Sheets", initialdir=self.parent.save_folder.get(), parent=self)
            if d:
                resolved_dir = os.path.abspath(d)
                self.parent.save_folder.set(resolved_dir)
                db.save_setting("excel_save_folder", resolved_dir)
                ex_path_var.set(resolved_dir.replace(os.path.expanduser("~"), "~"))
                self._log("ok", f"Excel export folder changed to: {resolved_dir}")
                
        self._btn(ex_frame, "Change Folder...", run_ex_change, bg=CARD).pack(side="right")

        # Tender PDF Download Frame
        pdf_frame = tk.Frame(self, bg=PANEL, padx=12, pady=10, highlightthickness=1, highlightbackground="#30363D")
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
                parent=self,
            )
            if selected_dir:
                resolved_dir = os.path.abspath(selected_dir)
                db.save_setting("pdf_save_folder", resolved_dir)
                pdf_path_var.set(resolved_dir.replace(os.path.expanduser("~"), "~"))
                self._log("ok", f"Tender PDF download folder changed to: {resolved_dir}")

        self._btn(pdf_frame, "Change Folder...", run_pdf_folder_change, bg=CARD).pack(anchor="w", pady=(4, 0))

        # Excel Pattern Frame
        pat_frame = tk.Frame(self, bg=PANEL, padx=12, pady=10, highlightthickness=1, highlightbackground="#30363D")
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
        opt_frame = tk.Frame(self, bg=PANEL, padx=12, pady=8, highlightthickness=1, highlightbackground="#30363D")
        opt_frame.pack(fill="x", padx=15, pady=6)
        
        headless_var = tk.BooleanVar(value=db.load_settings().get("selenium_headless", False))
        chk = tk.Checkbutton(opt_frame, text="Run Chrome in Headless (Silent) Mode for Selenium fetching",
                             variable=headless_var, bg=PANEL, fg=TEXT, selectcolor=BG,
                             activebackground=PANEL, activeforeground=TEXT,
                             font=FL, relief="flat", highlightthickness=0)
        chk.pack(anchor="w")

        # LLM Frame
        llm_frame = tk.Frame(self, bg=PANEL, padx=12, pady=10, highlightthickness=1, highlightbackground="#30363D")
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
                
            dlg = LoadingDialog(self, "Testing Connection", "Testing LLM connection and pre-warming model...", perform_connect)
            self.wait_window(dlg)
            
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
                
            dlg = LoadingDialog(self, "Ejecting Models", "Ejecting loaded models from local server...", perform_eject)
            self.wait_window(dlg)
            
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
            self.destroy()
            
        btn_fr = tk.Frame(self, bg=BG)
        btn_fr.pack(fill="x", side="bottom", pady=12)
        self._btn(btn_fr, "  Close  ", save_and_close, bg=ACCENT2).pack(anchor="center")
        
        self.protocol("WM_DELETE_WINDOW", save_and_close)

    def _btn(self, *args, **kwargs):
        return self.parent._btn(*args, **kwargs)

    def _log(self, *args, **kwargs):
        return self.parent._log(*args, **kwargs)

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
            self.parent._records = db.load_all_tenders()
            self.parent._refresh_table_view()
            if hasattr(self.parent, "_update_analytics"):
                self.parent._update_analytics()
            if hasattr(self.parent, "_update_calendar"):
                self.parent._update_calendar()
                self.parent._update_details()
                
            messagebox.showinfo("Success", f"Database successfully relocated to:\n{new_db_path}", parent=parent_win or self)
        except Exception as e:
            self._log("err", f"Failed to relocate database: {e}")
            messagebox.showerror("Error", f"Failed to relocate database:\n{e}", parent=parent_win or self)

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
            self.parent._records = db.load_all_tenders()
            self.parent._refresh_table_view()
            # Also refresh other tabs if active
            try:
                selected_tab = self.parent.notebook.index(self.parent.notebook.select())
                if selected_tab == self.parent.notebook.index(self.parent.tab_calendar):
                    self.parent._update_calendar()
                elif selected_tab == self.parent.notebook.index(self.parent.tab_analytics):
                    self.parent._update_analytics()
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
            self.parent._records = []
            self.parent._refresh_table_view()
            self._log("ok", "Database cleared successfully.")
            messagebox.showinfo("Database Cleared", "Local database cleared successfully.", parent=parent)
        except Exception as e:
            self._log("err", f"Failed to clear database: {e}")
            messagebox.showerror("Error", f"Failed to clear database: {e}", parent=parent)
