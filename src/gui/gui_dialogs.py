import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from datetime import datetime

# Local imports
from config import BG, PANEL, CARD, ACCENT2, MUTED, TEXT, TEXTSUB, ERR, SUCCESS, FT, FL, TV_COLS
import db

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
        
        # API Key
        tk.Label(llm_frame, text="API Key:", font=FL, bg=PANEL, fg=TEXTSUB).grid(row=2, column=0, sticky="w", pady=3)
        key_var = tk.StringVar(value=db.load_settings().get("llm_api_key", ""))
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
        
        llm_frame.columnconfigure(1, weight=1)
        
        # Checkboxes for actions
        chk_frame = tk.Frame(llm_frame, bg=PANEL)
        chk_frame.grid(row=5, column=0, columnspan=2, sticky="w", pady=(6, 4))
        
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

        # Test Connection button and Status label
        test_frame = tk.Frame(llm_frame, bg=PANEL)
        test_frame.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        
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
            
            def thread_fn():
                success, msg = llm.test_llm_connection(prov, key, url, mdl)
                if success:
                    win.after(0, lambda: test_status_lbl.configure(fg=SUCCESS))
                    win.after(0, lambda: test_status_var.set("Status: Success!"))
                else:
                    win.after(0, lambda: test_status_lbl.configure(fg=ERR))
                    win.after(0, lambda: test_status_var.set(f"Status: Fail ({msg[:30]}...)"))
            
            threading.Thread(target=thread_fn, daemon=True).start()
            
        self._btn(test_frame, "Test Connection", run_test, bg=CARD).pack(side="left")

        def update_llm_fields_state(*args):
            prov = provider_var.get()
            if prov == "Disabled":
                key_ent.configure(state="disabled")
                url_ent.configure(state="disabled")
                model_ent.configure(state="disabled")
                chk_parse.configure(state="disabled")
                chk_map.configure(state="disabled")
            elif prov == "Google AI Studio (Gemini)":
                key_ent.configure(state="normal")
                url_ent.configure(state="disabled")
                model_ent.configure(state="normal")
                chk_parse.configure(state="normal")
                chk_map.configure(state="normal")
                # Pre-fill default model name if empty
                if not model_var.get().strip():
                    model_var.set("gemini-1.5-flash")
            elif prov == "Local LLM (LM Studio / Ollama)":
                key_ent.configure(state="normal")
                url_ent.configure(state="normal")
                model_ent.configure(state="normal")
                chk_parse.configure(state="normal")
                chk_map.configure(state="normal")
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
            db.save_setting("llm_api_key", key_var.get().strip())
            db.save_setting("llm_base_url", url_var.get().strip())
            db.save_setting("llm_model", model_var.get().strip())
            db.save_setting("llm_use_parsing", use_parsing_var.get())
            db.save_setting("llm_use_mapping", use_mapping_var.get())
            
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
                    self._update_matrix()
                elif selected_tab == 3:
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
                r["category"] = parser.map_category(raw_text)
                
            db.save_all_tenders(self._records)
            self._log("info", "Filter rules, Category mappings, and Field mappings updated.")
            self._refresh_table_view()
            
            # Refresh other tabs
            try:
                selected_tab = self.notebook.index(self.notebook.select())
                if selected_tab == 1:
                    self._update_calendar()
                elif selected_tab == 2:
                    self._update_matrix()
                elif selected_tab == 3:
                    self._update_analytics()
            except Exception:
                pass
                
            win.destroy()
            
        btn_fr = tk.Frame(win, bg=BG)
        btn_fr.pack(fill="x", side="bottom", pady=15)
        
        self._btn(btn_fr, "  Save & Apply  ", save_rules, bg=ACCENT2).pack(side="left", padx=(60, 10), expand=True, fill="x")
        self._btn(btn_fr, "  Cancel  ", win.destroy, bg=CARD).pack(side="right", padx=(10, 60), expand=True, fill="x")
