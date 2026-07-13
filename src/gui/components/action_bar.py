"""
Action bar component for table header actions.
Provides buttons for common table operations.
"""

from config import BG, CARD, ACCENT, ERR
from components.base_component import ToolbarComponent


class ActionBar(ToolbarComponent):
    """
    Action bar with buttons for table operations.
    """
    
    def __init__(self, parent, app, table_tab, **kwargs):
        self.table_tab = table_tab
        super().__init__(parent, app, bg=BG, **kwargs)
    
    def _build_ui(self):
        # Left side - title and count
        tk.Label(self, text="Parsed Tenders", font=("Segoe UI", 9, "bold"), 
                bg=BG, fg="#8B949E").pack(side="left")
        
        self.count_lbl = tk.Label(self, text="0 rows", font=("Segoe UI", 9), 
                                  bg=BG, fg="#8B949E")
        self.count_lbl.pack(side="left", padx=8)
        
        # Right side - action buttons
        self.add_button("Save Selected to Excel", self._on_save_excel, 
                       bg=ACCENT, padx=10)
        self.add_button("Process Local PDFs", self._on_process_pdfs, 
                       bg="#2D333B")
        self.add_button("Fetch Selected (Selenium)", self._on_fetch_sel, 
                       bg="#2D333B")
        self.add_button("Delete Selected", self._on_delete_sel, 
                       bg=CARD, fg=ERR)
        self.add_button("Select All", self._on_select_all, bg=CARD)
    
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
        """Update the row count label."""
        self.count_lbl.configure(text=f"{count} rows")
