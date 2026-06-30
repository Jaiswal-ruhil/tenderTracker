import re
import tkinter as tk
from tkinter import ttk
import webbrowser

# Local imports
from config import BG, PANEL, CARD, ACCENT2, MUTED, TEXT, WARN
import db

class MatrixTabMixin:
    def _build_matrix_tab(self):
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
            
        locations = sorted(list(set(r.get("location", "").strip() for r in self._records if r.get("location", "").strip())))
        categories = sorted(list(set(r.get("category", "").strip() for r in self._records if r.get("category", "").strip())))
        
        if not locations or not categories:
            lbl = tk.Label(self.matrix_grid_fr, text="No tenders with Location and Category details found.",
                           font=("Segoe UI", 9, "bold"), bg=BG, fg=MUTED)
            lbl.pack(pady=40, padx=40)
            return
            
        hdr_corner = tk.Frame(self.matrix_grid_fr, bg=PANEL, highlightthickness=1, highlightbackground="#30363D", padx=10, pady=8)
        hdr_corner.grid(row=0, column=0, sticky="nsew")
        tk.Label(hdr_corner, text="Location \\ Category", font=("Segoe UI", 9, "bold"), bg=PANEL, fg=MUTED).pack()
        
        for c_idx, cat in enumerate(categories):
            hdr_cell = tk.Frame(self.matrix_grid_fr, bg=PANEL, highlightthickness=1, highlightbackground="#30363D", padx=10, pady=8, width=180)
            hdr_cell.grid(row=0, column=c_idx + 1, sticky="nsew")
            hdr_cell.grid_propagate(False)
            hdr_cell.configure(height=80)
            lbl = tk.Label(hdr_cell, text=cat, font=("Segoe UI", 9, "bold"), bg=PANEL, fg=TEXT, wraplength=150, justify="center")
            lbl.pack(expand=True, fill="both")
            
        for r_idx, loc in enumerate(locations):
            hdr_cell = tk.Frame(self.matrix_grid_fr, bg=PANEL, highlightthickness=1, highlightbackground="#30363D", padx=10, pady=8, width=220)
            hdr_cell.grid(row=r_idx + 1, column=0, sticky="nsew")
            hdr_cell.grid_propagate(False)
            hdr_cell.configure(height=120)
            lbl = tk.Label(hdr_cell, text=loc, font=("Segoe UI", 9, "bold"), bg=PANEL, fg=TEXT, wraplength=200, justify="left")
            lbl.pack(expand=True, fill="both")
            
        for r_idx, loc in enumerate(locations):
            for c_idx, cat in enumerate(categories):
                cell_recs = [r for r in self._records if r.get("location", "").strip() == loc and r.get("category", "").strip() == cat]
                
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
                    
                    curr_status = rec.get("filing_status", "Not Filed")
                    if not curr_status:
                        curr_status = "Not Filed"
                        
                    status_var = tk.StringVar(value=curr_status)
                    status_opts = ["Not Filed", "Draft", "Submitted", "Exempt"]
                    if curr_status not in status_opts:
                        status_opts.append(curr_status)
                        
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
        self._log("ok", f"Updated filing status for {bid_no} to '{new_status}'")
