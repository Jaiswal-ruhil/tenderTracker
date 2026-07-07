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
        self.geometry("380x150")
        self.resizable(False, False)
        self.configure(bg=BG)
        self.transient(parent)
        self.grab_set()
        
        # Center the window relative to parent
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")
        
        # Disable close button
        self.protocol("WM_DELETE_WINDOW", lambda: None)
        
        # Frame
        frame = tk.Frame(self, bg=PANEL, padx=15, pady=15, highlightthickness=1, highlightbackground="#30363D")
        frame.pack(fill="both", expand=True, padx=8, pady=8)
        
        # Messages
        lbl_msg = tk.Label(frame, text=message, font=FL, bg=PANEL, fg=TEXT, wraplength=340, justify="center")
        lbl_msg.pack(pady=(15, 10))
        
        # Loading indicator dots
        self.dots_var = tk.StringVar(value="...")
        self.lbl_dots = tk.Label(frame, text="...", font=("Segoe UI", 18, "bold"), bg=PANEL, fg=ACCENT2)
        self.lbl_dots.pack()
        
        self.task_fn = task_fn
        self.exception = None
        self.result = None
        
        self._animate_dots()
        
        if self.task_fn:
            import threading
            threading.Thread(target=self._run_task, daemon=True).start()
            
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
            self.result = self.task_fn()
        except Exception as e:
            self.exception = e
        finally:
            if self.winfo_exists():
                self.after(0, self.destroy)


class DialogsMixin:
    def _show_settings(self):
        win = tk.Toplevel(self)
        win.grab_set()
        win.transient(self)
        win.title("Settings")
        win.configure(bg=BG)
        win.resizable(False, False)

        x = self.winfo_x() + (self.winfo_width() - 600) // 2
        y = self.winfo_y() + (self.winfo_height() - 740) // 2
        win.geometry(f"600x740+{max(0, x)}+{max(0, y)}")

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
        win.resizable(False, False)
        
        x = self.winfo_x() + (self.winfo_width() - 700) // 2
        y = self.winfo_y() + (self.winfo_height() - 500) // 2
        win.geometry(f"700x500+{max(0, x)}+{max(0, y)}")
        
        tk.Label(win, text="Manage Firms & Matching Rules", font=FT, bg=BG, fg=TEXT).pack(pady=(12, 10))

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
        
        # Load firms from settings
        settings = db.load_settings()
        firms_list = []
        for firm in settings.get("firms", []):
            firms_list.append({
                "name": firm.get("name", ""),
                "categories": normalize_multi_value(firm.get("categories", [])),
                "locations": firm.get("locations", ""),
                "exclude_keywords": firm.get("exclude_keywords", "")
            })
        
        # Frame for Treeview
        tree_fr = tk.Frame(win, bg=BG)
        tree_fr.pack(fill="both", expand=True, padx=20, pady=5)
        
        # Scrollbars
        scroll_y = ttk.Scrollbar(tree_fr, orient="vertical")
        scroll_y.pack(side="right", fill="y")
        scroll_x = ttk.Scrollbar(tree_fr, orient="horizontal")
        scroll_x.pack(side="bottom", fill="x")
        
        # Treeview definition
        cols = ("name", "categories", "locations", "exclude_keywords")
        tv = ttk.Treeview(tree_fr, columns=cols, show="headings",
                          selectmode="browse", yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
        tv.pack(fill="both", expand=True)
        
        scroll_y.configure(command=tv.yview)
        scroll_x.configure(command=tv.xview)
        
        # Set headings & widths
        tv.heading("name", text="Firm Name")
        tv.heading("categories", text="Categories")
        tv.heading("locations", text="Location Keywords")
        tv.heading("exclude_keywords", text="Exclude Keywords")
        
        tv.column("name", width=140, anchor="w")
        tv.column("categories", width=220, anchor="w")
        tv.column("locations", width=140, anchor="w")
        tv.column("exclude_keywords", width=140, anchor="w")
        
        # Insert current firms
        def refresh_tree():
            for child in tv.get_children():
                tv.delete(child)
            for idx, firm in enumerate(firms_list):
                tv.insert("", "end", iid=str(idx), values=(
                    firm.get("name", ""),
                    display_multi_value(firm.get("categories", [])),
                    firm.get("locations", ""),
                    firm.get("exclude_keywords", "")
                ))
                
        refresh_tree()
        
        # Form for Add/Edit
        def open_firm_form(edit_idx=None):
            form_win = tk.Toplevel(win)
            form_win.grab_set()
            form_win.transient(win)
            form_win.title("Add Firm" if edit_idx is None else "Edit Firm")
            form_win.configure(bg=BG)
            form_win.resizable(False, False)
            
            fx = win.winfo_x() + (win.winfo_width() - 500) // 2
            fy = win.winfo_y() + (win.winfo_height() - 430) // 2
            form_win.geometry(f"500x430+{max(0, fx)}+{max(0, fy)}")
            
            # Fields
            tk.Label(form_win, text="Firm Configuration", font=FT, bg=BG, fg=TEXT).pack(pady=(12, 10))
            
            grid_fr = tk.Frame(form_win, bg=PANEL, padx=15, pady=15, highlightthickness=1, highlightbackground="#30363D")
            grid_fr.pack(fill="both", expand=True, padx=20, pady=5)
            
            # Firm Name
            tk.Label(grid_fr, text="Firm Name:", font=FL, bg=PANEL, fg=TEXTSUB).grid(row=0, column=0, sticky="w", pady=6)
            name_var = tk.StringVar()
            name_ent = tk.Entry(grid_fr, textvariable=name_var, bg=CARD, fg=TEXT, insertbackground=TEXT, relief="flat", font=FL,
                                highlightthickness=1, highlightbackground="#30363D", highlightcolor=ACCENT2, width=30)
            name_ent.grid(row=0, column=1, sticky="w", padx=10, pady=6)
            
            # Categories
            tk.Label(grid_fr, text="Categories:", font=FL, bg=PANEL, fg=TEXTSUB).grid(row=1, column=0, sticky="nw", pady=6)
            
            # Retrieve existing category options
            settings = db.load_settings()
            mappings = settings.get("category_mappings")
            if not mappings:
                try:
                    from config import CATEGORY_MAPPING
                    mappings = [{"name": val, "keywords": kws} for kws, val in CATEGORY_MAPPING]
                except Exception:
                    mappings = []
            category_options = sorted(list(set(m["name"] for m in mappings if m.get("name"))))

            cat_picker_fr = tk.Frame(grid_fr, bg=PANEL)
            cat_picker_fr.grid(row=1, column=1, sticky="w", padx=10, pady=6)

            cat_listbox = tk.Listbox(
                cat_picker_fr,
                selectmode="extended",
                exportselection=False,
                height=7,
                width=30,
                bg=CARD,
                fg=TEXT,
                selectbackground=ACCENT2,
                selectforeground=TEXT,
                relief="flat",
                highlightthickness=1,
                highlightbackground="#30363D",
                font=FL
            )
            cat_listbox.pack(fill="x")
            for option in category_options:
                cat_listbox.insert("end", option)

            cat_preview_var = tk.StringVar(value="Selected: None")
            tk.Label(cat_picker_fr, textvariable=cat_preview_var, font=("Segoe UI", 8), bg=PANEL, fg=MUTED, anchor="w", justify="left").pack(fill="x", pady=(4, 0))

            custom_cat_var = tk.StringVar()
            custom_cat_row = tk.Frame(cat_picker_fr, bg=PANEL)
            custom_cat_row.pack(fill="x", pady=(6, 0))
            custom_cat_ent = tk.Entry(
                custom_cat_row,
                textvariable=custom_cat_var,
                bg=CARD,
                fg=TEXT,
                insertbackground=TEXT,
                relief="flat",
                font=FL,
                highlightthickness=1,
                highlightbackground="#30363D",
                highlightcolor=ACCENT2,
                width=22
            )
            custom_cat_ent.pack(side="left", fill="x", expand=True)

            def get_selected_categories():
                return [cat_listbox.get(i) for i in cat_listbox.curselection()]

            def refresh_category_preview():
                selected = get_selected_categories()
                cat_preview_var.set(f"Selected: {', '.join(selected)}" if selected else "Selected: None")

            def add_custom_categories():
                raw = custom_cat_var.get().strip()
                if not raw:
                    return
                new_items = normalize_multi_value(raw)
                existing = [cat_listbox.get(i) for i in range(cat_listbox.size())]
                for item in new_items:
                    if item not in existing:
                        cat_listbox.insert("end", item)
                        existing.append(item)
                custom_cat_var.set("")
                refresh_category_preview()

            self._btn(custom_cat_row, "Add", add_custom_categories, bg=CARD).pack(side="left", padx=(6, 0))
            cat_listbox.bind("<<ListboxSelect>>", lambda e: refresh_category_preview())
            
            # Locations
            tk.Label(grid_fr, text="Locations:", font=FL, bg=PANEL, fg=TEXTSUB).grid(row=2, column=0, sticky="w", pady=6)
            loc_var = tk.StringVar()
            loc_ent = tk.Entry(grid_fr, textvariable=loc_var, bg=CARD, fg=TEXT, insertbackground=TEXT, relief="flat", font=FL,
                               highlightthickness=1, highlightbackground="#30363D", highlightcolor=ACCENT2, width=30)
            loc_ent.grid(row=2, column=1, sticky="w", padx=10, pady=6)
            
            # Exclude Keywords
            tk.Label(grid_fr, text="Excludes:", font=FL, bg=PANEL, fg=TEXTSUB).grid(row=3, column=0, sticky="w", pady=6)
            exc_var = tk.StringVar()
            exc_ent = tk.Entry(grid_fr, textvariable=exc_var, bg=CARD, fg=TEXT, insertbackground=TEXT, relief="flat", font=FL,
                               highlightthickness=1, highlightbackground="#30363D", highlightcolor=ACCENT2, width=30)
            exc_ent.grid(row=3, column=1, sticky="w", padx=10, pady=6)
            
            # Pre-populate if editing
            if edit_idx is not None:
                firm_data = firms_list[edit_idx]
                name_var.set(firm_data.get("name", ""))
                loc_var.set(firm_data.get("locations", ""))
                exc_var.set(firm_data.get("exclude_keywords", ""))
                selected_categories = normalize_multi_value(firm_data.get("categories", []))
                current_options = [cat_listbox.get(i) for i in range(cat_listbox.size())]
                for cat in selected_categories:
                    if cat not in current_options:
                        cat_listbox.insert("end", cat)
                        current_options.append(cat)
                for idx, option in enumerate(current_options):
                    if option in selected_categories:
                        cat_listbox.selection_set(idx)
                refresh_category_preview()
                
            def save_form():
                n = name_var.get().strip()
                add_custom_categories()
                c = get_selected_categories()
                l = loc_var.get().strip()
                e = exc_var.get().strip()
                
                if not n:
                    messagebox.showerror("Error", "Firm Name is required.", parent=form_win)
                    return
                if not c:
                    messagebox.showerror("Error", "Select at least one category for the firm.", parent=form_win)
                    return
                    
                firm_data = {
                    "name": n,
                    "categories": c,
                    "locations": l,
                    "exclude_keywords": e
                }
                
                if edit_idx is None:
                    firms_list.append(firm_data)
                else:
                    firms_list[edit_idx] = firm_data
                    
                refresh_tree()
                form_win.destroy()
                
            btn_fr2 = tk.Frame(form_win, bg=BG)
            btn_fr2.pack(fill="x", side="bottom", pady=10)
            self._btn(btn_fr2, "Save", save_form, bg=ACCENT).pack(side="left", padx=(50, 10), expand=True, fill="x")
            self._btn(btn_fr2, "Cancel", form_win.destroy, bg=CARD).pack(side="right", padx=(10, 50), expand=True, fill="x")
            
        def add_firm():
            open_firm_form()
            
        def edit_firm():
            sel = tv.selection()
            if not sel:
                messagebox.showwarning("Warning", "Select a firm to edit.", parent=win)
                return
            idx = int(sel[0])
            open_firm_form(edit_idx=idx)
            
        def delete_firm():
            sel = tv.selection()
            if not sel:
                messagebox.showwarning("Warning", "Select a firm to delete.", parent=win)
                return
            idx = int(sel[0])
            firm_name = firms_list[idx].get("name", "this firm")
            confirm = messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete '{firm_name}'?", parent=win)
            if confirm:
                firms_list.pop(idx)
                refresh_tree()
                
        # Action buttons frame
        act_fr = tk.Frame(win, bg=BG)
        act_fr.pack(fill="x", padx=20, pady=10)
        
        self._btn(act_fr, "+ Add Firm", add_firm, bg=CARD).pack(side="left", padx=(0, 6))
        self._btn(act_fr, "⚙ Edit Selected", edit_firm, bg=CARD).pack(side="left", padx=6)
        self._btn(act_fr, "🗑 Delete Selected", delete_firm, bg=CARD, fg=ERR).pack(side="left", padx=6)
        
        def save_all_firms():
            db.save_setting("firms", firms_list)
            self._log("ok", f"Saved {len(firms_list)} firm(s) to settings.")
            
            # Show loading/processing dialog during database re-evaluation
            def do_re_evaluate():
                settings_inner = db.load_settings()
                inc_raw = settings_inner.get("include_keywords", "")
                exc_raw = settings_inner.get("exclude_keywords", "")
                inc_kws = [k.strip().lower() for k in inc_raw.split(",") if k.strip()]
                exc_kws = [k.strip().lower() for k in exc_raw.split(",") if k.strip()]
                
                # Update all records in memory
                updated_count = 0
                for r in self._records:
                    old_want = r.get("is_want_derived")
                    old_firm = r.get("matched_firm", "")
                    
                    is_want = self._get_tender_status(r, inc_kws, exc_kws)
                    r["is_want_derived"] = is_want
                    
                    if old_want != r.get("is_want_derived") or old_firm != r.get("matched_firm", ""):
                        updated_count += 1
                
                if updated_count > 0:
                    db.save_all_tenders(self._records)
                    
                self.after(0, self._refresh_table_view)
                if hasattr(self, "_update_analytics"):
                    self.after(0, self._update_analytics)
                if hasattr(self, "_update_calendar"):
                    self.after(0, self._update_calendar)
                    self.after(0, self._update_details)
                
                self.after(0, lambda: self._log("ok", f"Re-evaluated database: {updated_count} tenders updated based on new firm rules."))
                
            LoadingDialog(self, title="Applying Rules", message="Re-evaluating matching rules on database...", task_fn=do_re_evaluate)
            win.destroy()
            
        btn_fr = tk.Frame(win, bg=BG)
        btn_fr.pack(fill="x", side="bottom", pady=15)
        
        self._btn(btn_fr, "Save & Apply to Database", save_all_firms, bg=ACCENT2).pack(side="left", padx=(80, 10), expand=True, fill="x")
        self._btn(btn_fr, "Cancel", win.destroy, bg=CARD).pack(side="right", padx=(10, 80), expand=True, fill="x")

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
        mappings_data = settings.get("category_mappings")
        if not mappings_data:
            try:
                from config import CATEGORY_MAPPING
                mappings_data = [{"name": val, "keywords": kws} for kws, val in CATEGORY_MAPPING]
            except Exception:
                mappings_data = []

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
                        mappings_inner = settings_inner.get("category_mappings")
                        if not mappings_inner:
                            try:
                                from config import CATEGORY_MAPPING
                                mappings_inner = [{"name": val, "keywords": kws} for kws, val in CATEGORY_MAPPING]
                            except Exception:
                                mappings_inner = []
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
