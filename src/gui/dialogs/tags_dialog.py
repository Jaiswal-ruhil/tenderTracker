# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk, messagebox

# Local imports
from config import BG, PANEL, CARD, ACCENT2, TEXT, TEXTSUB, ERR, FT, FL
import db

class TagsDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.grab_set()
        self.transient(parent)
        self.title("Manage Tags")
        self.configure(bg=BG)
        self.resizable(False, False)

        x = parent.winfo_x() + (parent.winfo_width() - 400) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 500) // 2
        self.geometry(f"400x500+{max(0, x)}+{max(0, y)}")

        sel = self.parent.tv.selection()
        if not sel:
            messagebox.showwarning("No Rows Selected", "Please select at least one tender to manage tags.", parent=self)
            self.destroy()
            return

        selected_bids = []
        for iid in sel:
            bid = self.parent.tv.set(iid, "bid_no")
            if bid:
                selected_bids.append(bid)

        if not selected_bids:
            self.destroy()
            return

        tk.Label(self, text="Manage Tender Tags", font=FT, bg=BG, fg=TEXT).pack(pady=(12, 10))

        # List frame for checkboxes
        list_frame = tk.Frame(self, bg=PANEL, highlightthickness=1, highlightbackground="#30363D")
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
        for r in self.parent._records:
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
                parent=self
            )
            if not confirm:
                return
            settings_inner = db.load_settings()
            tags = settings_inner.get("defined_tags", ["Urgent", "Review", "Follow-up", "Sugar Mill"])
            if tag_to_del in tags:
                tags.remove(tag_to_del)
                db.save_setting("defined_tags", tags)
            
            for r in self.parent._records:
                t_list = r.get("tags", [])
                if isinstance(t_list, str):
                    t_list = [t.strip() for t in t_list.split(",") if t.strip()]
                if tag_to_del in t_list:
                    t_list.remove(tag_to_del)
                    r["tags"] = t_list
            db.save_all_tenders(self.parent._records)
            
            if tag_to_del in chk_vars:
                del chk_vars[tag_to_del]
            render_tags_list()
            self.parent._refresh_table_view()

        # Add tag UI
        add_fr = tk.Frame(self, bg=BG)
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
            
            for r in self.parent._records:
                if r.get("bid_no") in selected_bids:
                    r["tags"] = selected_tags
                    
            db.save_all_tenders(self.parent._records)
            self.parent._refresh_table_view()
            self._log("ok", f"Updated tags for {len(selected_bids)} tender(s).")
            self.destroy()
            
        btn_fr = tk.Frame(self, bg=BG)
        btn_fr.pack(fill="x", side="bottom", pady=15)
        
        self._btn(btn_fr, "  Apply  ", apply_selected_tags, bg=ACCENT2).pack(side="left", padx=(40, 10), expand=True, fill="x")
        self._btn(btn_fr, "  Cancel  ", self.destroy, bg=CARD).pack(side="right", padx=(10, 40), expand=True, fill="x")

        render_tags_list()

    def _btn(self, *args, **kwargs):
        return self.parent._btn(*args, **kwargs)

    def _log(self, *args, **kwargs):
        return self.parent._log(*args, **kwargs)
