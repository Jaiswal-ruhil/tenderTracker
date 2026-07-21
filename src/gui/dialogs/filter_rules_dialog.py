# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

# Local imports
from config import BG, PANEL, CARD, ACCENT2, MUTED, TEXT, TEXTSUB, ERR, SUCCESS, WARN, FT, FL, TV_COLS
import db
from .loading_dialog import LoadingDialog

class FilterRulesDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.grab_set()
        self.transient(parent)
        self.title("Filter & Refinement Rules")
        self.resizable(True, True)
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        init_w = min(620, max(500, screen_w - 40))
        init_h = min(740, max(520, screen_h - 60))
        self.minsize(500, 480)

        x = parent.winfo_x() + (parent.winfo_width() - init_w) // 2
        y = parent.winfo_y() + (parent.winfo_height() - init_h) // 2
        self.geometry(f"{init_w}x{init_h}+{max(0, x)}+{max(0, y)}")
        
        tk.Label(self, text="Keyword Refinement Rules", font=FT, bg=BG, fg=TEXT).pack(pady=(12, 4))
        
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
        nb = ttk.Notebook(self)
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
            new_name = simpledialog.askstring("New Category", "Enter standard category name:", parent=self)
            if not new_name:
                return
            new_name_clean = new_name.strip()
            if not new_name_clean:
                return
            for m in mappings_data:
                if m["name"].lower() == new_name_clean.lower():
                    messagebox.showwarning("Duplicate Category", f"Category '{new_name_clean}' already exists.", parent=self)
                    return
            mappings_data.append({"name": new_name_clean, "keywords": []})
            refresh_cat_list(new_name_clean)
            
        def delete_category():
            sel = cat_cb.get()
            if not sel:
                return
            confirm = messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete the category '{sel}' and its mapping keywords?", parent=self)
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
                messagebox.showinfo("No Suggestions", "No pending LLM keyword suggestions found.", parent=self)
                return
            sug_win = tk.Toplevel(self)
            sug_win.grab_set()
            sug_win.transient(self)
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
                messagebox.showwarning("Validation Error", "Mapped Key is required.", parent=self)
                return
            if not phrase_val:
                messagebox.showwarning("Validation Error", "Phrase to Link is required.", parent=self)
                return
                
            for rule in val_mappings_data:
                if rule.get("field") == field_id and rule.get("phrase") == phrase_val:
                    messagebox.showwarning("Duplicate Rule", "A mapping for this field and phrase already exists.", parent=self)
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
                messagebox.showwarning("No Selection", "Please select a mapping rule to delete.", parent=self)
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
            for r in self.parent._records:
                db.apply_value_mappings(r)
                raw_text = r.get("items") or r.get("category") or ""
                r["category"] = parser.map_category(raw_text, allow_llm=False)
                
            db.save_all_tenders(self.parent._records)
            self._log("info", "Filter rules, Category mappings, and Field mappings updated.")
            self.parent._refresh_table_view()
            
            # Refresh other tabs
            try:
                selected_tab = self.parent.notebook.index(self.parent.notebook.select())
                if selected_tab == self.parent.notebook.index(self.parent.tab_calendar):
                    self.parent._update_calendar()
                elif selected_tab == self.parent.notebook.index(self.parent.tab_analytics):
                    self.parent._update_analytics()
            except Exception:
                pass
                
            self.destroy()
            
        btn_fr = tk.Frame(self, bg=BG)
        btn_fr.pack(fill="x", side="bottom", pady=15)
        
        self._btn(btn_fr, "  Save & Apply  ", save_rules, bg=ACCENT2).pack(side="left", padx=(60, 10), expand=True, fill="x")
        self._btn(btn_fr, "  Cancel  ", self.destroy, bg=CARD).pack(side="right", padx=(10, 60), expand=True, fill="x")

    def _btn(self, *args, **kwargs):
        return self.parent._btn(*args, **kwargs)

    def _log(self, *args, **kwargs):
        return self.parent._log(*args, **kwargs)
