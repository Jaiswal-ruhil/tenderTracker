import os
import datetime
import tkinter as tk
from tkinter import ttk, messagebox

import db

# UI Style constants
BG = "#0D1117"
CARD = "#161B22"
CARD_ALT = "#21262D"
PANEL = "#21262D"
BORDER_COLOR = "#30363D"
TEXT = "#C9D1D9"
MUTED = "#8B949E"
SUCCESS = "#2EA043"
WARN = "#F0883E"
ERR = "#F85149"
ACCENT = "#58A6FF"
ACCENT2 = "#BC8CFF"

CATEGORIES = ["Nickel screen", "Packing jointing", "Light", "Motor", "Cable", "Gas", "VFD", "OTHERS"]
SUGARMILLS = [
    "NAJIBABAD", "ANOOPSHAHR", "SULTANPUR", "NANPARA", "BELRAYAN", "SAMPURNANAGAR", "RAMALA", 
    "MORNA", "GHOSI", "NANAUTA", "SEMIKHERA", "SARSAWAN", "MAHMUDABAD", "TILHAR", "BISALPUR", 
    "POWAYAN", "PURANPUR", "BAGPAT", "GAJRAULLA", "FEDRATION", "CORPORATION", "KAIAMGANJ", 
    "SATHIAON", "BUDAUN", "BILASPUR"
]

class DashboardTab(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=BG)
        self.app = app
        
        self.matrix_data = {}
        self.card_widgets = {}
        
        self._build_ui()
        
    def _build_ui(self):
        # 1. Top Control Bar
        top_bar = tk.Frame(self, bg=PANEL, pady=8, padx=12, highlightthickness=1, highlightbackground=BORDER_COLOR)
        top_bar.pack(fill="x")
        
        tk.Label(top_bar, text="Sugarmill Tender Status Matrix", font=("Segoe UI", 12, "bold"), bg=PANEL, fg=TEXT).pack(side="left")
        
        # Info text
        info_lbl = tk.Label(top_bar, text=" (SQLite Database Live Feed) ", font=("Segoe UI", 9, "italic"), bg=PANEL, fg=MUTED)
        info_lbl.pack(side="left", padx=10)
        
        # Refresh Button
        self.app._btn(top_bar, "🔄 Refresh Live", self.load_data, bg=ACCENT2).pack(side="right", padx=5)
        
        # 2. Stats Dashboard Cards Panel
        self.stats_frame = tk.Frame(self, bg=BG, pady=10, padx=12)
        self.stats_frame.pack(fill="x")
        
        card_configs = [
            ("DUE", "0", "#D23D33"),
            ("FILED", "0", SUCCESS),
            ("EVALUATING", "0", ACCENT),
            ("NOT FILED", "0", "#6E7681"),
            ("MISSED", "0", ERR),
            ("TOTAL ACTIVE", "0", PANEL)
        ]
        
        for i, (label, val, bg_col) in enumerate(card_configs):
            self.stats_frame.columnconfigure(i, weight=1, uniform="equal")
            card = tk.Frame(self.stats_frame, bg=CARD, highlightthickness=1, highlightbackground=BORDER_COLOR, padx=10, pady=8)
            card.grid(row=0, column=i, sticky="nsew", padx=6)
            
            # Colored left indicator bar
            indicator = tk.Frame(card, bg=bg_col, width=4)
            indicator.pack(side="left", fill="y", padx=(0, 8))
            
            info_fr = tk.Frame(card, bg=CARD)
            info_fr.pack(side="left", fill="both", expand=True)
            
            tk.Label(info_fr, text=label, font=("Segoe UI", 8, "bold"), bg=CARD, fg=MUTED, anchor="w").pack(fill="x")
            val_lbl = tk.Label(info_fr, text=val, font=("Segoe UI", 16, "bold"), bg=CARD, fg=TEXT, anchor="w")
            val_lbl.pack(fill="x")
            
            self.card_widgets[label] = val_lbl

        # 3. Scrollable Canvas for Matrix Grid
        grid_container = tk.Frame(self, bg=BG)
        grid_container.pack(fill="both", expand=True, padx=12, pady=(0, 10))
        
        self.canvas = tk.Canvas(grid_container, bg=BG, highlightthickness=0)
        vsb = ttk.Scrollbar(grid_container, orient="vertical", command=self.canvas.yview)
        hsb = ttk.Scrollbar(grid_container, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")
        self.canvas.pack(side="left", fill="both", expand=True)
        
        self.grid_fr = tk.Frame(self.canvas, bg=BG)
        self.canvas_window = self.canvas.create_window((0, 0), window=self.grid_fr, anchor="nw")
        
        self.grid_fr.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        
        # Mousewheel binding logic
        def _on_mousewheel(event):
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        def _bind_mw(e):
            self.canvas.bind_all("<MouseWheel>", _on_mousewheel)
        def _unbind_mw(e):
            self.canvas.unbind_all("<MouseWheel>")
            
        self.canvas.bind("<Enter>", _bind_mw)
        self.canvas.bind("<Leave>", _unbind_mw)
        
    def load_data(self):
        self.app._set_status("Loading dashboard from SQLite...", ACCENT2)
        try:
            records = self.app._records
            
            matrix_data = {}
            for rec in records:
                sugar_mill = rec.get("sugar_mill")
                category = rec.get("item_category")
                if not sugar_mill or not category:
                    continue
                    
                sugar_mill_str = str(sugar_mill).strip().upper()
                category_str = str(category).strip()
                
                # Normalise categories
                mapped_cat = None
                for cat in CATEGORIES:
                    if cat.lower() == category_str.lower():
                        mapped_cat = cat
                        break
                if not mapped_cat:
                    mapped_cat = "OTHERS"
                    
                if sugar_mill_str not in matrix_data:
                    matrix_data[sugar_mill_str] = {}
                    
                bid_no = rec.get("bid_no", "")
                parts = bid_no.split("/")
                tender_id_str = parts[-1] if parts else bid_no
                
                closing_date = rec.get("end_date") or ""
                emd_val = rec.get("emd") or ""
                
                remarks = rec.get("remarks") or rec.get("comments") or ""
                processing_val = ""
                if remarks:
                    clean_remarks = remarks
                    if remarks.startswith("[GeM:"):
                        end_idx = remarks.find("]")
                        if end_idx != -1:
                            clean_remarks = remarks[end_idx+1:].strip()
                    processing_val = clean_remarks
                    
                status_val = rec.get("filing_status") or "Not Filed"
                
                matrix_data[sugar_mill_str][mapped_cat] = {
                    "tender_id": tender_id_str,
                    "due_date": closing_date,
                    "emd": emd_val,
                    "processing": processing_val,
                    "status": status_val,
                    "bid_no": bid_no,
                    "record": rec
                }
                
            self.matrix_data = matrix_data
            self._render_grid()
            self.app._set_status("Dashboard loaded from SQLite", SUCCESS)
        except Exception as e:
            self._render_empty_grid(f"Error loading dashboard: {e}")
            self.app._log("err", f"Dashboard load failed: {e}")
            
    def _render_empty_grid(self, msg):
        for widget in self.grid_fr.winfo_children():
            widget.destroy()
            
        lbl = tk.Label(self.grid_fr, text=msg, font=("Segoe UI", 10, "italic"), bg=BG, fg=ERR, pady=40)
        lbl.pack(fill="both", expand=True)
        self.app._set_status("Dashboard failed to load.", ERR)
        
    def _render_grid(self):
        for widget in self.grid_fr.winfo_children():
            widget.destroy()
            
        # 1. Recompute Stats counters
        due_count = 0
        filed_count = 0
        eval_count = 0
        not_filed_count = 0
        missed_count = 0
        total_active = 0
        
        for mill in SUGARMILLS:
            categories_data = self.matrix_data.get(mill, {})
            for cat in CATEGORIES:
                info = categories_data.get(cat)
                if not info:
                    continue
                    
                total_active += 1
                closing_date = info["due_date"]
                filing_status = info["status"]
                
                final_status = self._get_dynamic_status(closing_date, filing_status)
                
                if final_status in ("DUE TODAY", "DUE TOMORROW"):
                    due_count += 1
                elif final_status == "FILED":
                    filed_count += 1
                elif final_status == "EVALUATING":
                    eval_count += 1
                elif final_status == "NOT FILED":
                    not_filed_count += 1
                elif final_status == "MISSED":
                    missed_count += 1
                    
        self.card_widgets["DUE"].config(text=str(due_count))
        self.card_widgets["FILED"].config(text=str(filed_count))
        self.card_widgets["EVALUATING"].config(text=str(eval_count))
        self.card_widgets["NOT FILED"].config(text=str(not_filed_count))
        self.card_widgets["MISSED"].config(text=str(missed_count))
        self.card_widgets["TOTAL ACTIVE"].config(text=str(total_active))
        
        # 2. Build Grid Layout
        headers = ["Sugarmill", "Description"] + CATEGORIES + ["totals"]
        for col_idx, h in enumerate(headers):
            lbl = tk.Label(self.grid_fr, text=h, font=("Segoe UI", 9, "bold"), bg=PANEL, fg=TEXT,
                           padx=12, pady=8, highlightthickness=1, highlightbackground=BORDER_COLOR)
            lbl.grid(row=0, column=col_idx, sticky="nsew")
            
        row_offset = 1
        for b_idx, mill in enumerate(SUGARMILLS):
            card_bg = CARD if b_idx % 2 == 0 else CARD_ALT
            categories_data = self.matrix_data.get(mill, {})
            
            # Sugarmill Label (spans 5 rows)
            mill_lbl = tk.Label(self.grid_fr, text=mill, font=("Segoe UI", 9, "bold"), bg=card_bg, fg=TEXT,
                                padx=10, pady=5, highlightthickness=1, highlightbackground=BORDER_COLOR)
            mill_lbl.grid(row=row_offset, column=0, rowspan=5, sticky="nsew")
            
            descriptions = ["tender id", "Date closing", "emd", "processing", "status"]
            for r_idx, desc in enumerate(descriptions):
                lbl = tk.Label(self.grid_fr, text=desc, font=("Segoe UI", 8, "italic"), bg=card_bg, fg=MUTED,
                               padx=8, pady=3, anchor="w", highlightthickness=1, highlightbackground=BORDER_COLOR)
                lbl.grid(row=row_offset + r_idx, column=1, sticky="nsew")
                
            unique_tenders = set()
            for c_idx, cat in enumerate(CATEGORIES, 2):
                info = categories_data.get(cat)
                
                # Render 5 sub-cells
                for r_idx in range(5):
                    cell_val = ""
                    fg_col = TEXT
                    font_style = ("Segoe UI", 9)
                    cursor_type = ""
                    
                    if info:
                        t_id = info["tender_id"]
                        unique_tenders.add(t_id)
                        
                        closing_date = info["due_date"]
                        emd_val = info["emd"]
                        processing_val = info["processing"]
                        filing_status = info["status"]
                        
                        final_status = self._get_dynamic_status(closing_date, filing_status)
                        
                        if r_idx == 0:
                            cell_val = t_id
                            fg_col = ACCENT
                            font_style = ("Segoe UI", 9, "underline")
                            cursor_type = "hand2"
                        elif r_idx == 1:
                            cell_val = closing_date
                        elif r_idx == 2:
                            cell_val = emd_val
                        elif r_idx == 3:
                            cell_val = processing_val
                        elif r_idx == 4:
                            cell_val = final_status
                            if final_status == "FILED":
                                fg_col = SUCCESS
                                font_style = ("Segoe UI", 9, "bold")
                            elif final_status in ("DUE TODAY", "DUE TOMORROW"):
                                fg_col = WARN
                                font_style = ("Segoe UI", 9, "bold")
                            elif final_status == "MISSED":
                                fg_col = ERR
                                font_style = ("Segoe UI", 9, "bold")
                            elif final_status == "EVALUATING":
                                fg_col = ACCENT
                            elif final_status == "NOT FILED":
                                fg_col = MUTED
                                
                    display_text = str(cell_val)
                    if len(display_text) > 28:
                        display_text = display_text[:25] + "..."
                        
                    cell_lbl = tk.Label(self.grid_fr, text=display_text, font=font_style, bg=card_bg, fg=fg_col,
                                       padx=8, pady=3, highlightthickness=1, highlightbackground=BORDER_COLOR)
                    cell_lbl.grid(row=row_offset + r_idx, column=c_idx, sticky="nsew")
                    if cursor_type:
                        cell_lbl.configure(cursor=cursor_type)
                    
                    # Bind interactive events on tender ID cell
                    if info and r_idx == 0:
                        cell_lbl.bind("<Button-1>", lambda e, b=info["record"]: self._highlight_tender_in_table(b))
                        cell_lbl.bind("<Double-Button-1>", lambda e, b=info["record"]: self._edit_tender_comments(b))
                        self._add_tooltip(cell_lbl, f"Click to view in table\nDouble-click to edit comments\nBid No: GEM/2026/B/{info['tender_id']}")
                    elif cell_val:
                        self._add_tooltip(cell_lbl, str(cell_val))

            # Totals column
            tot_val = len(unique_tenders)
            tot_lbl = tk.Label(self.grid_fr, text=str(tot_val), font=("Segoe UI", 10, "bold"), bg=card_bg, fg=TEXT,
                               padx=10, highlightthickness=1, highlightbackground=BORDER_COLOR)
            tot_lbl.grid(row=row_offset, column=10, rowspan=5, sticky="nsew")
            
            row_offset += 5
            
        self.grid_fr.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        
    def _get_dynamic_status(self, end_date_str, filing_status):
        fs_upper = str(filing_status).strip().upper()
        if fs_upper in ("FILED", "NOT FILED"):
            return fs_upper
            
        closing_date = None
        if end_date_str:
            for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
                try:
                    closing_date = datetime.datetime.strptime(end_date_str.split()[0], fmt).date()
                    break
                except:
                    pass
                    
        if not closing_date:
            return fs_upper if fs_upper else "EVALUATING"
            
        today = datetime.date.today()
        if closing_date < today:
            return "MISSED"
        elif closing_date == today:
            return "DUE TODAY"
        elif closing_date == today + datetime.timedelta(days=1):
            return "DUE TOMORROW"
        else:
            return "EVALUATING"
            
    def _highlight_tender_in_table(self, bid_info):
        if not bid_info:
            return
        bid_no = bid_info["bid_no"]
        self.app.notebook.select(self.app.tab_table)
        self.app.table_tab.search_var.set(bid_no)
        self.app.table_tab.refresh_table_view()
        
        for iid in self.app.table_tab.tv.get_children():
            row_bid = self.app.table_tab.tv.set(iid, "bid_no")
            if row_bid == bid_no:
                self.app.table_tab.tv.selection_set(iid)
                self.app.table_tab.tv.see(iid)
                self.app.table_tab.detail_panel.on_treeview_select(None)
                break
                
    def _edit_tender_comments(self, bid_info):
        if not bid_info:
            return
        from dialogs.comments_dialog import CommentsDialog
        CommentsDialog(self.app, bid_info["bid_no"])
        self.load_data()
        
    def _add_tooltip(self, widget, text):
        def enter(event):
            self.tooltip = tk.Toplevel(self)
            self.tooltip.wm_overrideredirect(True)
            self.tooltip.wm_geometry(f"+{event.x_root + 15}+{event.y_root + 10}")
            lbl = tk.Label(self.tooltip, text=text, bg="#1C2128", fg=TEXT, 
                           font=("Segoe UI", 9), relief="solid", borderwidth=1, padx=6, pady=4)
            lbl.pack()
        def leave(event):
            if hasattr(self, "tooltip") and self.tooltip:
                self.tooltip.destroy()
                self.tooltip = None
        widget.bind("<Enter>", enter)
        widget.bind("<Leave>", leave)
