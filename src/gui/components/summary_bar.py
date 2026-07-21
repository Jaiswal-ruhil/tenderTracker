"""
summary_bar.py
~~~~~~~~~~~~~~
Modern Summary Bar component for displaying key tender statistics,
metric chips, and financial totals with rich dark-theme aesthetics.
"""

import tkinter as tk
from config import PANEL, CARD, TEXT, TEXTSUB, MUTED, ACCENT, SUCCESS, WARN, ACCENT2
from components.base_component import StatusComponent


class SummaryBar(StatusComponent):
    """
    Summary bar displaying tender statistics with modern styled metric badges.
    """
    
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, app, bg=PANEL, padx=12, pady=6,
                       highlightthickness=1, highlightbackground="#30363D", **kwargs)
    
    def _build_ui(self):
        self.container = tk.Frame(self, bg=PANEL)
        self.container.pack(fill="x", expand=True)

        # Fallback text label for legacy custom text calls
        self.summary_lbl = tk.Label(
            self.container,
            text="",
            font=("Segoe UI", 9, "bold"),
            bg=PANEL,
            fg=TEXTSUB,
            anchor="w"
        )
        # Keep summary_lbl hidden unless set_custom_summary is called with raw non-structured text
        self.status_labels['summary'] = self.summary_lbl

        # Metric Badges Frame
        self.chips_frame = tk.Frame(self.container, bg=PANEL)
        self.chips_frame.pack(side="left", fill="x", expand=True)

        self._chips = {}
        self._create_chip("visible", "📊 Visible", "0", fg=TEXT, bg=CARD)
        self._create_chip("wants", "🎯 Want to Bid", "0", fg="#56D364", bg="#1C3322")
        self._create_chip("not_filed", "⏳ Filing Pending", "0", fg="#E3B341", bg="#3B2E10")
        self._create_chip("firm_matched", "🏢 Firm Matched", "0", fg="#58A6FF", bg="#162D4D")
        self._create_chip("total_val", "💰 Total Value", "₹0", fg="#39D353", bg=CARD)

    def _create_chip(self, key: str, label_str: str, val_str: str, fg: str, bg: str):
        frame = tk.Frame(self.chips_frame, bg=bg, highlightthickness=1, highlightbackground="#30363D", padx=8, pady=2)
        frame.pack(side="left", padx=(0, 8))

        lbl = tk.Label(frame, text=label_str + ": ", font=("Segoe UI", 8, "bold"), bg=bg, fg=MUTED)
        lbl.pack(side="left")

        val_lbl = tk.Label(frame, text=val_str, font=("Segoe UI", 9, "bold"), bg=bg, fg=fg)
        val_lbl.pack(side="left")

        self._chips[key] = (frame, val_lbl)

    def update_summary(self, visible: int = 0, wants: int = 0, 
                      not_filed: int = 0, firm_matched: int = 0,
                      total_val: str = None):
        """Update the summary statistics chips."""
        if self.summary_lbl.winfo_viewable():
            self.summary_lbl.pack_forget()
        self.chips_frame.pack(side="left", fill="x", expand=True)

        self._chips["visible"][1].configure(text=str(visible))
        self._chips["wants"][1].configure(text=str(wants))
        self._chips["not_filed"][1].configure(text=str(not_filed))
        self._chips["firm_matched"][1].configure(text=str(firm_matched))
        if total_val:
            self._chips["total_val"][1].configure(text=total_val)

    def set_custom_summary(self, text: str):
        """Set custom summary text or parse structured summary string."""
        if not text:
            return
        
        # Check if string matches "Visible: X Wants: Y Not Filed: Z Firm Matched: W"
        if "Visible:" in text and "Wants:" in text:
            try:
                parts = text.split()
                visible = parts[parts.index("Visible:") + 1] if "Visible:" in parts else "0"
                wants = parts[parts.index("Wants:") + 1] if "Wants:" in parts else "0"
                not_filed = parts[parts.index("Not") + 2] if "Not" in parts and "Filed:" in parts else "0"
                firm_matched = parts[parts.index("Matched:") + 1] if "Matched:" in parts else "0"
                
                self.update_summary(visible, wants, not_filed, firm_matched)
                return
            except Exception:
                pass

        # Fallback for custom arbitrary strings
        self.chips_frame.pack_forget()
        self.summary_lbl.configure(text=text)
        self.summary_lbl.pack(fill="x")
