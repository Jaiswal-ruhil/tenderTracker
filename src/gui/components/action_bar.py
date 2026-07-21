"""
action_bar.py
~~~~~~~~~~~~~
Action bar component for table header actions and batch operations,
featuring styled icons, row counter badges, and responsive action triggers.
"""

import tkinter as tk
from config import BG, CARD, ACCENT, ERR, TEXT, TEXTSUB, MUTED, ACCENT2
from components.base_component import ToolbarComponent


class ActionBar(ToolbarComponent):
    """
    Action bar with modern styled buttons for table operations.
    """
    
    def __init__(self, parent, app, table_tab, **kwargs):
        self.table_tab = table_tab
        super().__init__(parent, app, bg=BG, padx=4, pady=4, **kwargs)
    
    def _build_ui(self):
        # Left side - title & row count badge
        self.left_frame = tk.Frame(self, bg=BG)
        self.left_frame.pack(side="left", fill="y", padx=4)

        tk.Label(
            self.left_frame, 
            text="📋 Parsed Tenders", 
            font=("Segoe UI", 10, "bold"), 
            bg=BG, 
            fg=TEXT
        ).pack(side="left", padx=(0, 6))

        # Badge container for row count
        self.badge_frame = tk.Frame(
            self.left_frame, 
            bg="#21262D", 
            highlightthickness=1, 
            highlightbackground="#30363D", 
            padx=8, 
            pady=1
        )
        self.badge_frame.pack(side="left", padx=4)

        self.count_lbl = tk.Label(
            self.badge_frame, 
            text="0 rows", 
            font=("Segoe UI", 8, "bold"), 
            bg="#21262D", 
            fg=ACCENT2
        )
        self.count_lbl.pack(side="left")
        
        # Right side - action buttons with icons & high contrast colors
        self.add_button("📊 Export Excel", self._on_save_excel, bg=ACCENT, fg="#FFFFFF", padx=6)
        self.add_button("📁 Process Local PDFs", self._on_process_pdfs, bg="#21262D", fg=TEXT, padx=4)
        self.add_button("🌐 Fetch Selected", self._on_fetch_sel, bg="#21262D", fg=TEXT, padx=4)
        self.add_button("🗑️ Delete Selected", self._on_delete_sel, bg="#21262D", fg=ERR, padx=4)
        self.add_button("☑️ Select All", self._on_select_all, bg="#21262D", fg=TEXT, padx=4)
    
    def _on_save_excel(self):
        """Handle save to excel button."""
        if hasattr(self.table_tab, 'save_selected'):
            self.table_tab.save_selected()
    
    def _on_process_pdfs(self):
        """Handle process local PDFs button."""
        if hasattr(self.app, '_do_process_local_pdfs'):
            self.app._do_process_local_pdfs()
    
    def _on_fetch_sel(self):
        """Handle fetch selected button."""
        if hasattr(self.app, '_do_fetch_sel'):
            self.app._do_fetch_sel()
    
    def _on_delete_sel(self):
        """Handle delete selected button."""
        if hasattr(self.table_tab, 'del_sel'):
            self.table_tab.del_sel()
    
    def _on_select_all(self):
        """Handle select all button."""
        if hasattr(self.table_tab, 'sel_all'):
            self.table_tab.sel_all()
    
    def update_count(self, count: int):
        """Update the row count label badge."""
        self.count_lbl.configure(text=f"{count} tenders")
