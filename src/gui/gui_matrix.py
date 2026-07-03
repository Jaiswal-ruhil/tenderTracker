import re
import tkinter as tk
from tkinter import ttk
import webbrowser

# Local imports
from config import BG, PANEL, CARD, ACCENT2, MUTED, TEXT, WARN, TEXTSUB, FL
import db

class MatrixTabMixin:
    def _build_matrix_tab(self):
        # Control bar at the top
        self.matrix_control_fr = tk.Frame(self.tab_matrix, bg=PANEL, padx=10, pady=6,
                                          highlightthickness=1, highlightbackground="#30363D")
        self.matrix_control_fr.pack(fill="x", side="top", pady=(0, 4))
        
        # Row Grouping
        tk.Label(self.matrix_control_fr, text="Rows (Y):", font=FL, bg=PANEL, fg=MUTED).pack(side="left", padx=(2, 4))
        self.matrix_row_var = tk.StringVar(value="Location")
        self.matrix_row_cb = ttk.Combobox(self.matrix_control_fr, textvariable=self.matrix_row_var,
                                          values=["Location", "Category", "Items", "Ministry", "Department", "Organisation", "Filing Status"],
                                          state="readonly", font=FL, width=12)
        self.matrix_row_cb.pack(side="left", padx=4)
        self.matrix_row_cb.bind("<<ComboboxSelected>>", lambda e: self._update_matrix())
        
        # Column Grouping
        tk.Label(self.matrix_control_fr, text="Columns (X):", font=FL, bg=PANEL, fg=MUTED).pack(side="left", padx=(10, 4))
        self.matrix_col_var = tk.StringVar(value="Category")
        self.matrix_col_cb = ttk.Combobox(self.matrix_control_fr, textvariable=self.matrix_col_var,
                                          values=["Category", "Items", "Location", "Ministry", "Department", "Organisation", "Filing Status"],
                                          state="readonly", font=FL, width=12)
        self.matrix_col_cb.pack(side="left", padx=4)
        self.matrix_col_cb.bind("<<ComboboxSelected>>", lambda e: self._update_matrix())
        
        # Filter dropdown
        tk.Label(self.matrix_control_fr, text="Filter:", font=FL, bg=PANEL, fg=MUTED).pack(side="left", padx=(10, 4))
        self.matrix_filter_var = tk.StringVar(value="All Tenders")
        self.matrix_filter_cb = ttk.Combobox(self.matrix_control_fr, textvariable=self.matrix_filter_var,
                                             values=["All Tenders", "Wants (Matches)", "Don't Wants (Filtered)"],
                                             state="readonly", font=FL, width=15)
        self.matrix_filter_cb.pack(side="left", padx=4)
        self.matrix_filter_cb.bind("<<ComboboxSelected>>", lambda e: self._update_matrix())
        
        # Search Box
        tk.Label(self.matrix_control_fr, text="Search:", font=FL, bg=PANEL, fg=MUTED).pack(side="left", padx=(10, 4))
        self.matrix_search_var = tk.StringVar()
        self.matrix_search_var.trace_add("write", lambda *args: self._update_matrix())
        self.matrix_search_ent = tk.Entry(self.matrix_control_fr, textvariable=self.matrix_search_var, bg=CARD, fg=TEXT,
                                          insertbackground=TEXT, relief="flat", font=FL, width=18,
                                          highlightthickness=1, highlightbackground="#30363D",
                                          highlightcolor=ACCENT2)
        self.matrix_search_ent.pack(side="left", padx=4)
        
        # Info Label (to show grid size)
        self.matrix_info_lbl = tk.Label(self.matrix_control_fr, text="", font=FL, bg=PANEL, fg=TEXTSUB)
        self.matrix_info_lbl.pack(side="right", padx=6)

        container = tk.Frame(self.tab_matrix, bg=BG)
        container.pack(fill="both", expand=True, padx=4, pady=4)
        
        vbar = ttk.Scrollbar(container, orient="vertical")
        hbar = ttk.Scrollbar(container, orient="horizontal")
        
        self.matrix_canvas = tk.Canvas(container, bg=BG, highlightthickness=0,
                                       xscrollcommand=hbar.set, yscrollcommand=vbar.set)
        
        vbar.configure(command=self.matrix_canvas.yview)
        hbar.configure(command=self.matrix_canvas.xview)
        
        vbar.pack(side="right", fill="y")
        hbar.pack(side="bottom", fill="x")
        self.matrix_canvas.pack(side="left", fill="both", expand=True)
        
        self.matrix_grid_fr = tk.Frame(self.matrix_canvas, bg=BG)
        self.matrix_canvas.create_window((0, 0), window=self.matrix_grid_fr, anchor="nw", tags="self.matrix_grid_fr")
        
        self.matrix_grid_fr.bind("<Configure>", lambda e: self.matrix_canvas.configure(
            scrollregion=self.matrix_canvas.bbox("all")
        ))
        
        def _on_matrix_mousewheel(event):
            self.matrix_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            
        def _on_matrix_shift_mousewheel(event):
            self.matrix_canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")
        
        self.matrix_canvas.bind("<Enter>", lambda e: (
            self.matrix_canvas.bind_all("<MouseWheel>", _on_matrix_mousewheel),
            self.matrix_canvas.bind_all("<Shift-MouseWheel>", _on_matrix_shift_mousewheel)
        ))
        self.matrix_canvas.bind("<Leave>", lambda e: (
            self.matrix_canvas.unbind_all("<MouseWheel>"),
            self.matrix_canvas.unbind_all("<Shift-MouseWheel>")
        ))

    def _update_matrix(self):
        for child in self.matrix_grid_fr.winfo_children():
            child.destroy()

        FIELD_MAP = {
            "Category": "category",
            "Location": "location",
            "Items": "items",
            "Ministry": "ministry",
            "Department": "dept",
            "Organisation": "organisation",
            "Filing Status": "filing_status"
        }

        settings = db.load_settings()
        inc_raw = settings.get("include_keywords", "")
        exc_raw = settings.get("exclude_keywords", "")
        inc_kws = [k.strip().lower() for k in inc_raw.split(",") if k.strip()]
        exc_kws = [k.strip().lower() for k in exc_raw.split(",") if k.strip()]

        view_filter = self.matrix_filter_var.get()
        search_text = self.matrix_search_var.get().strip().lower()

        # Filter records
        records_to_use = []
        for rec in self._records:
            is_want = self._get_tender_status(rec, inc_kws, exc_kws)
            if view_filter == "Wants (Matches)" and not is_want:
                continue
            if view_filter == "Don't Wants (Filtered)" and is_want:
                continue
            if search_text:
                combined_text = " ".join(str(v) for v in rec.values()).lower()
                if search_text not in combined_text:
                    continue
            records_to_use.append(rec)

        row_label = self.matrix_row_var.get()
        col_label = self.matrix_col_var.get()

        row_field = FIELD_MAP.get(row_label, "location")
        col_field = FIELD_MAP.get(col_label, "category")

        # Gather row and col headers dynamically
        row_vals = sorted(list(set(str(r.get(row_field, "")).strip() for r in records_to_use if str(r.get(row_field, "")).strip())))
        if any(not str(r.get(row_field, "")).strip() for r in records_to_use):
            row_vals.append("(Blank)")

        col_vals = sorted(list(set(str(r.get(col_field, "")).strip() for r in records_to_use if str(r.get(col_field, "")).strip())))
        if any(not str(r.get(col_field, "")).strip() for r in records_to_use):
            col_vals.append("(Blank)")

        if not records_to_use or not row_vals or not col_vals:
            self.matrix_info_lbl.configure(text="0 x 0 grid")
            lbl = tk.Label(self.matrix_grid_fr, text="No matching tenders found for the current filter/grouping.",
                           font=("Segoe UI", 9, "bold"), bg=BG, fg=MUTED)
            lbl.pack(pady=40, padx=40)
            return

        self.matrix_info_lbl.configure(text=f"{len(row_vals)} rows x {len(col_vals)} cols ({len(records_to_use)} tenders)")

        hdr_corner = tk.Frame(self.matrix_grid_fr, bg=PANEL, highlightthickness=1, highlightbackground="#30363D", padx=10, pady=8)
        hdr_corner.grid(row=0, column=0, sticky="nsew")
        tk.Label(hdr_corner, text=f"{row_label} \\ {col_label}", font=("Segoe UI", 9, "bold"), bg=PANEL, fg=MUTED).pack()

        for c_idx, c_val in enumerate(col_vals):
            hdr_cell = tk.Frame(self.matrix_grid_fr, bg=PANEL, highlightthickness=1, highlightbackground="#30363D", padx=10, pady=8, width=180)
            hdr_cell.grid(row=0, column=c_idx + 1, sticky="nsew")
            hdr_cell.grid_propagate(False)
            hdr_cell.configure(height=80)
            lbl = tk.Label(hdr_cell, text=c_val, font=("Segoe UI", 9, "bold"), bg=PANEL, fg=TEXT, wraplength=150, justify="center")
            lbl.pack(expand=True, fill="both")

        for r_idx, r_val in enumerate(row_vals):
            hdr_cell = tk.Frame(self.matrix_grid_fr, bg=PANEL, highlightthickness=1, highlightbackground="#30363D", padx=10, pady=8, width=220)
            hdr_cell.grid(row=r_idx + 1, column=0, sticky="nsew")
            hdr_cell.grid_propagate(False)
            hdr_cell.configure(height=120)
            lbl = tk.Label(hdr_cell, text=r_val, font=("Segoe UI", 9, "bold"), bg=PANEL, fg=TEXT, wraplength=200, justify="left")
            lbl.pack(expand=True, fill="both")

        def matches_val(rec, field, target_val):
            val = str(rec.get(field, "")).strip()
            if target_val == "(Blank)":
                return val == ""
            return val == target_val

        for r_idx, r_val in enumerate(row_vals):
            for c_idx, c_val in enumerate(col_vals):
                cell_recs = [r for r in records_to_use if matches_val(r, row_field, r_val) and matches_val(r, col_field, c_val)]

                cell_fr = tk.Frame(self.matrix_grid_fr, highlightthickness=1, highlightbackground="#30363D", width=180, height=120)
                cell_fr.grid(row=r_idx + 1, column=c_idx + 1, sticky="nsew")
                cell_fr.grid_propagate(False)

                if not cell_recs:
                    cell_fr.configure(bg=BG)
                    lbl = tk.Label(cell_fr, text="-", font=("Segoe UI", 9, "bold"), bg=BG, fg="#30363D")
                    lbl.pack(expand=True)
                else:
                    cell_fr.configure(bg=CARD)
                    rec = cell_recs[0]

                    bid = rec.get("bid_no", "GEM/...")
                    bid_short = bid.split("/")[-1] if "/" in bid else bid

                    bid_lbl = tk.Label(cell_fr, text=bid_short, font=("Segoe UI", 9, "bold"), bg=CARD, fg=ACCENT2, cursor="hand2")
                    bid_lbl.pack(anchor="w", padx=6, pady=(4, 0))

                    if rec.get("bid_url"):
                        bid_lbl.bind("<Button-1>", lambda e, url=rec["bid_url"]: webbrowser.open(url))

                    end_dt = rec.get("end_date", "")
                    if end_dt:
                        date_match = re.search(r"\d{2}-\d{2}-\d{4}", end_dt)
                        end_date_str = date_match.group(0) if date_match else end_dt
                    else:
                        end_date_str = "No End Date"

                    date_lbl = tk.Label(cell_fr, text=f"End: {end_date_str}", font=("Segoe UI", 8), bg=CARD, fg=MUTED)
                    date_lbl.pack(anchor="w", padx=6)

                    curr_status = rec.get("filing_status", "Evaluating")
                    if not curr_status or curr_status not in ("To Be Filed", "Evaluating", "Filed"):
                        curr_status = "Evaluating"

                    status_var = tk.StringVar(value=curr_status)
                    status_opts = ["To Be Filed", "Evaluating", "Filed"]

                    cb = ttk.Combobox(cell_fr, textvariable=status_var, values=status_opts, state="readonly", width=14, font=("Segoe UI", 8))
                    cb.pack(anchor="w", padx=6, pady=(8, 4))

                    def make_on_status_change(r_obj=rec, var=status_var):
                        return lambda e: self._update_tender_filing_status(r_obj, var.get())

                    cb.bind("<<ComboboxSelected>>", make_on_status_change())

                    if len(cell_recs) > 1:
                        cnt_lbl = tk.Label(cell_fr, text=f"+{len(cell_recs)-1} more", font=("Segoe UI", 7, "bold"), bg=CARD, fg=WARN)
                        cnt_lbl.pack(anchor="e", padx=6, pady=(0, 2))

    def _update_tender_filing_status(self, rec, new_status):
        bid_no = rec.get("bid_no")
        if not bid_no:
            return

        for r in self._records:
            if r.get("bid_no") == bid_no:
                r["filing_status"] = new_status
                break

        db.save_all_tenders(self._records)
        self._refresh_table_view()
        self._update_matrix()
        self._log("ok", f"Updated filing status for {bid_no} to '{new_status}'")
