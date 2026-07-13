"""
Summary bar component for table statistics.
Displays counts and summary information about tenders.
"""

from config import PANEL, TEXTSUB
from components.base_component import StatusComponent


class SummaryBar(StatusComponent):
    """
    Summary bar displaying tender statistics.
    """
    
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, app, bg=PANEL, padx=10, pady=6,
                       highlightthickness=1, highlightbackground="#30363D", **kwargs)
    
    def _build_ui(self):
        self.summary_lbl = tk.Label(
            self,
            text="Visible: 0   Wants: 0   Not Filed: 0   Firm Matched: 0",
            font=("Segoe UI", 8, "bold"),
            bg=PANEL,
            fg=TEXTSUB,
            anchor="w"
        )
        self.summary_lbl.pack(fill="x")
        self.status_labels['summary'] = self.summary_lbl
    
    def update_summary(self, visible: int = 0, wants: int = 0, 
                      not_filed: int = 0, firm_matched: int = 0):
        """Update the summary statistics."""
        text = f"Visible: {visible}   Wants: {wants}   Not Filed: {not_filed}   Firm Matched: {firm_matched}"
        self.summary_lbl.configure(text=text)
    
    def set_custom_summary(self, text: str):
        """Set a custom summary text."""
        self.summary_lbl.configure(text=text)
