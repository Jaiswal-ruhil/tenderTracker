import tkinter as tk
from tkinter import ttk
import os
import json
import threading
import asyncio

# Local imports
from config import (
    PANEL, CARD, ACCENT, ACCENT2, MUTED, TEXT, TEXTSUB, SUCCESS, ERR, WARN,
    FL, FT
)
import db
import logger

class TenderDetailPanel(tk.Frame):
    def __init__(self, parent, app, table_tab):
        super().__init__(parent, bg=PANEL, highlightthickness=1, highlightbackground="#30363D", padx=12, pady=10)
        self.app = app
        self.table_tab = table_tab

        # Detail Title
        detail_title = tk.Label(self, text="TENDER DETAILS", font=FT, bg=PANEL, fg=TEXT)
        detail_title.pack(anchor="w", pady=(0, 6))

        self.detail_meta_lbl = tk.Label(
            self,
            text="No tender selected",
            font=("Segoe UI", 8, "bold"),
            bg=PANEL,
            fg=MUTED,
            anchor="w",
            justify="left"
        )
        self.detail_meta_lbl.pack(fill="x", pady=(0, 8))

        # Dashboard Matrix Mapping Frame
        self._current_rec = None
        self.matrix_frame = tk.LabelFrame(self, text="Dashboard Matrix Mapping", font=FL, bg=PANEL, fg=TEXTSUB, labelanchor="n", padx=6, pady=4)
        self.matrix_frame.pack(fill="x", pady=(0, 8))
        
        # Sugar Mill Dropdown
        tk.Label(self.matrix_frame, text="Sugar Mill:", font=FL, bg=PANEL, fg=TEXTSUB).grid(row=0, column=0, sticky="w", padx=(0, 4))
        self.sugar_mill_var = tk.StringVar()
        self.sugar_mill_cb = ttk.Combobox(self.matrix_frame, textvariable=self.sugar_mill_var, font=FL, state="readonly", width=18)
        from components.dashboard_tab import SUGARMILLS
        self.sugar_mill_cb["values"] = ["None"] + SUGARMILLS
        self.sugar_mill_cb.grid(row=0, column=1, sticky="ew", padx=(0, 4))
        
        # Item Category Dropdown
        tk.Label(self.matrix_frame, text="Category:", font=FL, bg=PANEL, fg=TEXTSUB).grid(row=1, column=0, sticky="w", padx=(0, 4), pady=(4, 0))
        self.item_category_var = tk.StringVar()
        self.item_category_cb = ttk.Combobox(self.matrix_frame, textvariable=self.item_category_var, font=FL, state="readonly", width=18)
        from components.dashboard_tab import CATEGORIES
        self.item_category_cb["values"] = ["None"] + CATEGORIES
        self.item_category_cb.grid(row=1, column=1, sticky="ew", padx=(0, 4), pady=(4, 0))
        
        self.matrix_frame.columnconfigure(1, weight=1)
        
        self.sugar_mill_cb.bind("<<ComboboxSelected>>", self._on_matrix_changed)
        self.item_category_cb.bind("<<ComboboxSelected>>", self._on_matrix_changed)

        # PDF Control Frame
        self.pdf_frame = tk.Frame(self, bg=PANEL)
        self.pdf_frame.pack(fill="x", pady=(0, 8))
        
        self.pdf_lbl = tk.Label(self.pdf_frame, text="PDF: Not Linked", font=FL, bg=PANEL, fg=TEXTSUB, anchor="w")
        self.pdf_lbl.pack(side="left", fill="x", expand=True)
        
        self.btn_open_pdf = self.app._btn(self.pdf_frame, "📄 Open", lambda: self.table_tab.open_associated_pdf(), bg=CARD)
        self.btn_open_pdf.pack(side="right", padx=2)
        
        self.btn_link_pdf = self.app._btn(self.pdf_frame, "🔗 Link", lambda: self.table_tab.link_associated_pdf(), bg=CARD)
        self.btn_link_pdf.pack(side="right", padx=2)
        
        self.btn_unlink_pdf = self.app._btn(self.pdf_frame, "❌", lambda: self.table_tab.unlink_associated_pdf(), bg=CARD)
        self.btn_unlink_pdf.pack(side="right", padx=2)

        self.detail_actions_fr = tk.Frame(self, bg=PANEL)
        self.detail_actions_fr.pack(fill="x", pady=(0, 10))
        self.btn_detail_want = self.app._btn(self.detail_actions_fr, "Keep", lambda: self.table_tab.mark_selected_want(), bg=CARD)
        self.btn_detail_want.pack(side="left", padx=(0, 6))
        self.btn_detail_dont_want = self.app._btn(self.detail_actions_fr, "Ignore", lambda: self.table_tab.mark_selected_dont_want(), bg=CARD, fg=ERR)
        self.btn_detail_dont_want.pack(side="left", padx=6)
        self.btn_detail_reset = self.app._btn(self.detail_actions_fr, "Reset Tag", lambda: self.table_tab.reset_selected_tag(), bg=CARD)
        self.btn_detail_reset.pack(side="left", padx=6)
        self.btn_detail_fetch = self.app._btn(self.detail_actions_fr, "Fetch Selected", lambda: self.table_tab.do_fetch_sel(), bg=CARD)
        self.btn_detail_fetch.pack(side="right", padx=(6, 0))
        self.btn_detail_filed = self.app._btn(self.detail_actions_fr, "Mark Filed", lambda: self.table_tab.set_selected_filing_status("Filed"), bg=ACCENT2)
        self.btn_detail_filed.pack(side="right", padx=(6, 0))

        # AI Actions Frame
        self.ai_actions_fr = tk.Frame(self, bg=PANEL)
        self.ai_actions_fr.pack(fill="x", pady=(0, 10))
        
        self.btn_ai_summary = self.app._btn(self.ai_actions_fr, "📝 AI Summary", lambda: self._generate_ai_summary(), bg="#2D333B", fg=ACCENT2)
        self.btn_ai_summary.pack(side="left", padx=(0, 6))
        
        self.btn_ai_risk = self.app._btn(self.ai_actions_fr, "⚠️ AI Risk", lambda: self._assess_ai_risk(), bg="#2D333B", fg=WARN)
        self.btn_ai_risk.pack(side="left", padx=6)
        
        self.btn_ai_recommend = self.app._btn(self.ai_actions_fr, "🎯 AI Recommend", lambda: self._get_ai_recommendation(), bg="#2D333B", fg=SUCCESS)
        self.btn_ai_recommend.pack(side="left", padx=6)

        # Detail Scrollable Text widget
        txt_fr = tk.Frame(self, bg=PANEL)
        txt_fr.pack(fill="both", expand=True)

        self.detail_txt = tk.Text(txt_fr, bg=CARD, fg=TEXT, insertbackground=TEXT,
                                  relief="flat", font=FL, wrap="word", highlightthickness=0,
                                  padx=12, pady=12)
        self.detail_txt.pack(side="left", fill="both", expand=True)

        detail_vsb = ttk.Scrollbar(txt_fr, orient="vertical", command=self.detail_txt.yview)
        detail_vsb.pack(side="right", fill="y")
        self.detail_txt.configure(yscrollcommand=detail_vsb.set)
        
        # Configure tags for detail_txt formatting & highlighting
        self.detail_txt.tag_configure("header", foreground=ACCENT2, font=("Segoe UI", 10, "bold"))
        self.detail_txt.tag_configure("label", foreground=MUTED, font=("Segoe UI", 9, "bold"))
        self.detail_txt.tag_configure("value", foreground=TEXT, font=("Segoe UI", 9))
        self.detail_txt.tag_configure("match_inc", background="#1A4A2A", foreground=SUCCESS, font=("Segoe UI", 9, "bold"))
        self.detail_txt.tag_configure("match_exc", background="#4A1A1A", foreground=ERR, font=("Segoe UI", 9, "bold"))
        self.detail_txt.tag_configure("match_search", background="#0A4D8C", foreground="#FFFFFF", font=("Segoe UI", 9, "bold"))
        self.detail_txt.tag_configure("match_firm_inc", background="#0A3C5C", foreground="#84D2FF", font=("Segoe UI", 9, "bold"))
        self.detail_txt.tag_configure("match_firm_loc", background="#2D1C4C", foreground="#C09EFF", font=("Segoe UI", 9, "bold"))
        self.detail_txt.tag_configure("match_firm_exc", background="#4A1A1A", foreground=ERR, font=("Segoe UI", 9, "bold"))

        # Initialize detail text state
        self.clear_detail_panel()

        # Bind MouseWheel events for self.detail_txt
        def on_detail_mousewheel(event):
            if event.num == 5 or event.delta < 0:
                self.detail_txt.yview_scroll(1, "units")
            elif event.num == 4 or event.delta > 0:
                self.detail_txt.yview_scroll(-1, "units")
        self.detail_txt.bind("<MouseWheel>", on_detail_mousewheel)
        self.detail_txt.bind("<Button-4>", on_detail_mousewheel)
        self.detail_txt.bind("<Button-5>", on_detail_mousewheel)

    @staticmethod
    def _firm_multi_values(value):
        if not value:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            return [v.strip() for v in value.split(",") if v.strip()]
        return []

    def clear_detail_panel(self):
        self.detail_txt.configure(state="normal")
        self.detail_txt.delete("1.0", "end")
        self.detail_txt.insert("end", "\n\nSelect a tender from the table to view its full details here.", "value")
        self.detail_txt.configure(state="disabled")

        if hasattr(self, "detail_meta_lbl"):
            self.detail_meta_lbl.configure(text="No tender selected", fg=MUTED)
        
        if hasattr(self, "pdf_lbl"):
            self.pdf_lbl.configure(text="PDF: Not Linked", fg=TEXTSUB)
            self.btn_open_pdf.configure(state="disabled")
            self.btn_unlink_pdf.configure(state="disabled")
            for btn in (
                getattr(self, "btn_detail_want", None),
                getattr(self, "btn_detail_dont_want", None),
                getattr(self, "btn_detail_reset", None),
                getattr(self, "btn_detail_fetch", None),
                getattr(self, "btn_detail_filed", None),
            ):
                if btn:
                    btn.configure(state="disabled")
        
        self._current_rec = None
        if hasattr(self, "sugar_mill_var"):
            self.sugar_mill_var.set("None")
            self.item_category_var.set("None")

    def on_treeview_select(self, event):
        sel = self.table_tab.table_view.tv.selection()
        if not sel:
            self.clear_detail_panel()
            return
            
        # Get selected record
        bid_no = self.table_tab.table_view.tv.set(sel[0], "bid_no")
        rec = None
        for r in self.app._records:
            if r.get("bid_no") == bid_no:
                rec = r
                break
        if not rec:
            self.clear_detail_panel()
            return

        self._current_rec = rec
        if hasattr(self, "sugar_mill_var"):
            self.sugar_mill_var.set(rec.get("sugar_mill") or "None")
            self.item_category_var.set(rec.get("item_category") or "None")
            
        # Update PDF frame widgets
        pdf_path = rec.get("pdf_path", "")
        if pdf_path:
            filename = os.path.basename(pdf_path)
            if len(filename) > 25:
                filename = filename[:22] + "..."
            self.pdf_lbl.configure(text=f"PDF: {filename}", fg=SUCCESS)
            self.btn_open_pdf.configure(state="normal")
            self.btn_unlink_pdf.configure(state="normal")
        else:
            self.pdf_lbl.configure(text="PDF: Not Linked", fg=TEXTSUB)
            self.btn_open_pdf.configure(state="disabled")
            self.btn_unlink_pdf.configure(state="disabled")

        for btn in (
            getattr(self, "btn_detail_want", None),
            getattr(self, "btn_detail_dont_want", None),
            getattr(self, "btn_detail_reset", None),
            getattr(self, "btn_detail_fetch", None),
            getattr(self, "btn_detail_filed", None),
        ):
            if btn:
                btn.configure(state="normal")

        status_bits = []
        if rec.get("matched_firm", "").strip():
            status_bits.append(f"Firm: {rec.get('matched_firm')}")
        status_bits.append(f"Status: {rec.get('filing_status', 'Not Filed') or 'Not Filed'}")
        if rec.get("is_want") is True:
            status_text = "Marked Keep"
            status_color = SUCCESS
        elif rec.get("is_want") is False:
            status_text = "Marked Ignore"
            status_color = ERR
        elif rec.get("is_want_derived", True):
            status_text = "Auto Match"
            status_color = ACCENT2
        else:
            status_text = "Filtered Out"
            status_color = WARN
        status_bits.insert(0, status_text)
        self.detail_meta_lbl.configure(text="   |   ".join(status_bits), fg=status_color)

        self.detail_txt.configure(state="normal")
        self.detail_txt.delete("1.0", "end")
        
        # Display fields in group categories
        categories = {
            "Basic Info": ["bid_no", "bid_url", "category", "items", "quantity", "location"],
            "Department Info": ["ministry", "dept", "organisation", "office"],
            "Dates & Schedule": ["start_date", "end_date", "bid_opening"],
            "Financial Details": ["est_value", "emd", "epbg", "min_turnover"],
            "Qualifications": ["exp_years", "contract_dur", "mii", "mse_pref", "mse_relax", "startup_relax"],
            "Status & Metadata": ["filing_status", "tags", "remarks", "pdf_path", "comments"]
        }
        
        # Mapping DB field keys to human readable labels
        labels = {
            "bid_no": "Bid Number", "bid_url": "Bid URL", "category": "Category", "items": "Items", 
            "quantity": "Quantity", "location": "Location/Consignee", "ministry": "Ministry", 
            "dept": "Department", "organisation": "Organisation", "office": "Office", 
            "start_date": "Start Date", "end_date": "End Date", "bid_opening": "Bid Opening Date", 
            "est_value": "Estimated Value", "emd": "EMD Required", "epbg": "ePBG Required", 
            "min_turnover": "Min Turnover", "exp_years": "Exp Years Required", "contract_dur": "Contract Duration", 
            "mii": "MII Compliant", "mse_pref": "MSE Pref", "mse_relax": "MSE Relaxation", 
            "startup_relax": "Startup Relaxation", "filing_status": "Filing Status", "tags": "Tags", 
            "remarks": "Remarks", "pdf_path": "Associated PDF", "comments": "Comments"
        }
        
        first = True
        for cat_name, fields in categories.items():
            if not first:
                self.detail_txt.insert("end", "\n\n")
            first = False
            
            # Print Category Header
            self.detail_txt.insert("end", f"■ {cat_name}\n", "header")
            self.detail_txt.insert("end", "─" * 32 + "\n", "label")
            
            for field in fields:
                val = rec.get(field, "")
                if field == "tags":
                    if isinstance(val, list):
                        val = ", ".join(val)
                    elif not val:
                        val = "None"
                elif isinstance(val, bool):
                    val = "Yes" if val else "No"
                else:
                    val = str(val).strip()
                    
                if not val:
                    val = "N/A"
                    
                lbl = labels.get(field, field.capitalize())
                self.detail_txt.insert("end", f"{lbl}: ", "label")
                self.detail_txt.insert("end", f"{val}\n", "value")
                
        # Highlight match words (include / exclude keywords)
        settings = db.load_settings()
        inc_raw = settings.get("include_keywords", "")
        exc_raw = settings.get("exclude_keywords", "")
        
        inc_kws = [k.strip() for k in inc_raw.split(",") if k.strip()]
        exc_kws = [k.strip() for k in exc_raw.split(",") if k.strip()]
        
        # Apply include tags (case-insensitive)
        for kw in inc_kws:
            start = "1.0"
            while True:
                pos = self.detail_txt.search(kw, start, stopindex="end", nocase=True)
                if not pos:
                    break
                end = f"{pos} + {len(kw)}c"
                self.detail_txt.tag_add("match_inc", pos, end)
                start = end
                
        # Apply exclude tags (case-insensitive)
        for kw in exc_kws:
            start = "1.0"
            while True:
                pos = self.detail_txt.search(kw, start, stopindex="end", nocase=True)
                if not pos:
                    break
                end = f"{pos} + {len(kw)}c"
                self.detail_txt.tag_add("match_exc", pos, end)
                start = end
                
        # Highlight firm-specific words
        firms = settings.get("firms", [])
        for firm in firms:
            # 1. Categories
            for kw in self._firm_multi_values(firm.get("categories", [])):
                start = "1.0"
                while True:
                    pos = self.detail_txt.search(kw, start, stopindex="end", nocase=True)
                    if not pos:
                        break
                    end = f"{pos} + {len(kw)}c"
                    self.detail_txt.tag_add("match_firm_inc", pos, end)
                    start = end
            # 2. Locations
            for kw in [k.strip() for k in firm.get("locations", "").split(",") if k.strip()]:
                start = "1.0"
                while True:
                    pos = self.detail_txt.search(kw, start, stopindex="end", nocase=True)
                    if not pos:
                        break
                    end = f"{pos} + {len(kw)}c"
                    self.detail_txt.tag_add("match_firm_loc", pos, end)
                    start = end
            # 3. Excludes
            for kw in [k.strip() for k in firm.get("exclude_keywords", "").split(",") if k.strip()]:
                start = "1.0"
                while True:
                    pos = self.detail_txt.search(kw, start, stopindex="end", nocase=True)
                    if not pos:
                        break
                    end = f"{pos} + {len(kw)}c"
                    self.detail_txt.tag_add("match_firm_exc", pos, end)
                    start = end
                
        # Highlight active search query
        search_query = self.table_tab.search_var.get().strip()
        if search_query:
            start = "1.0"
            while True:
                pos = self.detail_txt.search(search_query, start, stopindex="end", nocase=True)
                if not pos:
                    break
                end = f"{pos} + {len(search_query)}c"
                self.detail_txt.tag_add("match_search", pos, end)
                start = end
                
        self.detail_txt.configure(state="disabled")
    
    def _get_selected_tender(self):
        """Get the currently selected tender."""
        sel = self.table_tab.table_view.tv.selection()
        if not sel:
            return None
        bid_no = self.table_tab.table_view.tv.set(sel[0], "bid_no")
        for r in self.app._records:
            if r.get("bid_no") == bid_no:
                return r
        return None
    
    def _generate_ai_summary(self):
        """Generate AI summary for the selected tender."""
        tender = self._get_selected_tender()
        if not tender:
            return
        
        self.btn_ai_summary.configure(state="disabled", text="Generating...")
        
        def process():
            try:
                import ai_integration
                ai = ai_integration.get_ai_integration()
                
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    summary = loop.run_until_complete(ai.generate_tender_summary(tender))
                    self.after(0, lambda: self._display_ai_summary(summary))
                finally:
                    loop.close()
            except Exception as e:
                logger.log("err", f"AI summary generation failed: {e}")
                self.after(0, lambda: self._ai_operation_complete("summary", str(e)))
        
        thread = threading.Thread(target=process, daemon=True)
        thread.start()
    
    def _assess_ai_risk(self):
        """Assess AI risk for the selected tender."""
        tender = self._get_selected_tender()
        if not tender:
            return
        
        self.btn_ai_risk.configure(state="disabled", text="Assessing...")
        
        def process():
            try:
                import ai_integration
                ai = ai_integration.get_ai_integration()
                
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    risk = loop.run_until_complete(ai.assess_tender_risk(tender))
                    self.after(0, lambda: self._display_ai_risk(risk))
                finally:
                    loop.close()
            except Exception as e:
                logger.log("err", f"AI risk assessment failed: {e}")
                self.after(0, lambda: self._ai_operation_complete("risk", str(e)))
        
        thread = threading.Thread(target=process, daemon=True)
        thread.start()
    
    def _get_ai_recommendation(self):
        """Get AI recommendation for the selected tender."""
        tender = self._get_selected_tender()
        if not tender:
            return
        
        self.btn_ai_recommend.configure(state="disabled", text="Analyzing...")
        
        def process():
            try:
                import ai_integration
                ai = ai_integration.get_ai_integration()
                
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    recommendation = loop.run_until_complete(ai.generate_bid_recommendation(tender))
                    self.after(0, lambda: self._display_ai_recommendation(recommendation))
                finally:
                    loop.close()
            except Exception as e:
                logger.log("err", f"AI recommendation failed: {e}")
                self.after(0, lambda: self._ai_operation_complete("recommendation", str(e)))
        
        thread = threading.Thread(target=process, daemon=True)
        thread.start()
    
    def _display_ai_summary(self, summary):
        """Display AI summary in the detail panel."""
        self.btn_ai_summary.configure(state="normal", text="📝 AI Summary")
        
        self.detail_txt.configure(state="normal")
        self.detail_txt.delete("1.0", "end")
        
        self.detail_txt.insert("end", "■ AI-GENERATED SUMMARY\n", "header")
        self.detail_txt.insert("end", "─" * 32 + "\n\n", "label")
        
        self.detail_txt.insert("end", f"Executive Summary:\n", "label")
        self.detail_txt.insert("end", f"{summary.executive_summary}\n\n", "value")
        
        self.detail_txt.insert("end", f"Key Requirements:\n", "label")
        for req in summary.key_requirements:
            self.detail_txt.insert("end", f"• {req}\n", "value")
        self.detail_txt.insert("end", "\n")
        
        self.detail_txt.insert("end", f"Evaluation Criteria:\n", "label")
        for criteria in summary.evaluation_criteria:
            self.detail_txt.insert("end", f"• {criteria}\n", "value")
        self.detail_txt.insert("end", "\n")
        
        self.detail_txt.insert("end", f"Timeline: {summary.timeline}\n", "label")
        self.detail_txt.insert("end", f"Budget Indicators: {summary.budget_indicators}\n", "label")
        
        self.detail_txt.configure(state="disabled")
    
    def _display_ai_risk(self, risk):
        """Display AI risk assessment in the detail panel."""
        self.btn_ai_risk.configure(state="normal", text="⚠️ AI Risk")
        
        risk_colors = {
            "Low": SUCCESS,
            "Medium": WARN,
            "High": ERR,
            "Critical": "#FF0000"
        }
        
        self.detail_txt.configure(state="normal")
        self.detail_txt.delete("1.0", "end")
        
        self.detail_txt.insert("end", "■ AI RISK ASSESSMENT\n", "header")
        self.detail_txt.insert("end", "─" * 32 + "\n\n", "label")
        
        self.detail_txt.insert("end", f"Risk Level: ", "label")
        self.detail_txt.insert("end", f"{risk.risk_level}\n", f"risk_{risk.risk_level}")
        
        self.detail_txt.insert("end", f"Risk Score: {risk.risk_score:.2f}\n\n", "label")
        
        self.detail_txt.insert("end", f"Risk Factors:\n", "label")
        for factor in risk.risk_factors:
            self.detail_txt.insert("end", f"• {factor}\n", "value")
        self.detail_txt.insert("end", "\n")
        
        self.detail_txt.insert("end", f"Mitigation Suggestions:\n", "label")
        for suggestion in risk.mitigation_suggestions:
            self.detail_txt.insert("end", f"• {suggestion}\n", "value")
        
        for level, color in risk_colors.items():
            self.detail_txt.tag_configure(f"risk_{level}", foreground=color, font=("Segoe UI", 10, "bold"))
        
        self.detail_txt.configure(state="disabled")
    
    def _display_ai_recommendation(self, recommendation):
        """Display AI recommendation in the detail panel."""
        self.btn_ai_recommend.configure(state="normal", text="🎯 AI Recommend")
        
        rec_color = SUCCESS if recommendation.recommend else ERR
        
        self.detail_txt.configure(state="normal")
        self.detail_txt.delete("1.0", "end")
        
        self.detail_txt.insert("end", "■ AI BID RECOMMENDATION\n", "header")
        self.detail_txt.insert("end", "─" * 32 + "\n\n", "label")
        
        self.detail_txt.insert("end", f"Recommendation: ", "label")
        rec_text = "BID RECOMMENDED" if recommendation.recommend else "DO NOT BID"
        self.detail_txt.insert("end", f"{rec_text}\n", "recommendation")
        
        self.detail_txt.insert("end", f"Recommendation Score: {recommendation.recommendation_score:.2f}\n\n", "label")
        
        self.detail_txt.insert("end", f"Pros:\n", "label")
        for pro in recommendation.pros:
            self.detail_txt.insert("end", f"• {pro}\n", "value")
        self.detail_txt.insert("end", "\n")
        
        self.detail_txt.insert("end", f"Cons:\n", "label")
        for con in recommendation.cons:
            self.detail_txt.insert("end", f"• {con}\n", "value")
        self.detail_txt.insert("end", "\n")
        
        self.detail_txt.insert("end", f"Strategic Fit: {recommendation.strategic_fit}\n", "label")
        self.detail_txt.insert("end", f"Competitive Advantage: {recommendation.competitive_advantage}\n", "label")
        
        if recommendation.suggested_bid_price:
            self.detail_txt.insert("end", f"Suggested Bid Price: {recommendation.suggested_bid_price}\n", "label")
        
        self.detail_txt.tag_configure("recommendation", foreground=rec_color, font=("Segoe UI", 10, "bold"))
        
        self.detail_txt.configure(state="disabled")
    
    def _ai_operation_complete(self, operation, error):
        """Handle AI operation completion with error."""
        if operation == "summary":
            self.btn_ai_summary.configure(state="normal", text="📝 AI Summary")
        elif operation == "risk":
            self.btn_ai_risk.configure(state="normal", text="⚠️ AI Risk")
        elif operation == "recommendation":
            self.btn_ai_recommend.configure(state="normal", text="🎯 AI Recommend")
        
        self.detail_txt.configure(state="normal")
        self.detail_txt.delete("1.0", "end")
        self.detail_txt.insert("end", f"AI {operation} failed:\n{error}", "value")
        self.detail_txt.configure(state="disabled")

    def _on_matrix_changed(self, event=None):
        if not self._current_rec:
            return
        mill = self.sugar_mill_var.get()
        cat = self.item_category_var.get()
        bid_no = self._current_rec.get("bid_no")
        if not bid_no:
            return
            
        mill_val = None if mill == "None" else mill
        cat_val = None if cat == "None" else cat
        
        try:
            conn = db.get_conn()
            cursor = conn.cursor()
            cursor.execute("UPDATE bids SET sugar_mill = ?, item_category = ? WHERE bid_no = ?", (mill_val, cat_val, bid_no))
            conn.commit()
            conn.close()
            
            self._current_rec["sugar_mill"] = mill_val
            self._current_rec["item_category"] = cat_val
            
            # Reload application state to refresh table, calendar, dashboard
            self.app._reload()
            
            logger.log_ok(f"Updated matrix mapping for {bid_no}: Mill={mill_val}, Category={cat_val}")
        except Exception as e:
            logger.log_err(f"Failed to update matrix mapping: {e}")
