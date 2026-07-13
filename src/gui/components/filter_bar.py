"""
Filter bar component for tender table filtering.
Provides search, view filters, and date filtering options.
"""

import tkinter as tk
from tkinter import ttk
from datetime import datetime, timedelta

from config import PANEL, CARD, ACCENT, ACCENT2, MUTED, TEXT
from components.base_component import FilterComponent
from components.date_picker_button import DateRangePicker


class FilterBar(FilterComponent):
    """
    Filter bar with search, view filters, and date filtering.
    """
    
    def __init__(self, parent, app, table_tab, **kwargs):
        self.table_tab = table_tab
        super().__init__(parent, app, bg=PANEL, padx=10, pady=6, 
                       highlightthickness=1, highlightbackground="#30363D", **kwargs)
    
    def _build_ui(self):
        # Search box
        self.add_search_box("Search:", width=22, callback=self._on_search_change)
        
        # Semantic Search Checkbox
        self.semantic_search_var = tk.BooleanVar(value=False)
        self.add_checkbox("Semantic Search", default=False, callback=self._on_search_change)
        
        # View dropdown
        self.view_var = tk.StringVar(value="Wants (Matches)")
        self.add_dropdown("Filter:", 
                         ["All Tenders", "Wants (Matches)", "Don't Wants (Filtered)"],
                         "Wants (Matches)", callback=self._on_view_change, width=20)
        
        # Visual separator
        self.add_separator()
        
        # Status dropdown
        self.status_view_var = tk.StringVar(value="All")
        self.add_dropdown("Status:",
                         ["All", "Not Filed", "Filed", "Evaluating", "Awarded"],
                         "All", callback=self._on_status_change, width=15)
        
        # Visual separator
        self.add_separator()
        
        # Date filter type
        self.date_filter_type_var = tk.StringVar(value="None")
        self.add_dropdown("Date Type:",
                         ["None", "End Date", "Bid Opening", "Start Date"],
                         "None", callback=self._on_date_type_change, width=15)
        
        # Date filter preset
        self.date_filter_preset_var = tk.StringVar(value="All Dates")
        self.add_dropdown("Date Preset:",
                         ["All Dates", "Today", "This Week", "This Month", "Next 7 Days", "Next 30 Days"],
                         "All Dates", callback=self._on_date_preset_change, width=15)
        
        # Custom date range with date picker buttons
        self.date_range_picker = DateRangePicker(
            self, self.app, self.date_from_var, self.date_to_var,
            on_change=self._on_date_range_change
        )
        self.date_range_picker.pack(side="left", padx=(8, 0))
    
    def _on_search_change(self):
        """Handle search text change."""
        if hasattr(self.table_tab, 'refresh_table_view'):
            self.table_tab.refresh_table_view()
    
    def _on_view_change(self):
        """Handle view filter change."""
        if hasattr(self.table_tab, 'refresh_table_view'):
            self.table_tab.refresh_table_view()
    
    def _on_status_change(self):
        """Handle status filter change."""
        if hasattr(self.table_tab, 'refresh_table_view'):
            self.table_tab.refresh_table_view()
    
    def _on_date_type_change(self):
        """Handle date filter type change."""
        if hasattr(self.table_tab, 'refresh_table_view'):
            self.table_tab.refresh_table_view()
    
    def _on_date_preset_change(self):
        """Handle date preset change."""
        self._apply_date_preset()
        if hasattr(self.table_tab, 'refresh_table_view'):
            self.table_tab.refresh_table_view()
    
    def _on_date_range_change(self):
        """Handle custom date range change."""
        if hasattr(self.table_tab, 'refresh_table_view'):
            self.table_tab.refresh_table_view()
    
    def _apply_date_preset(self, initial=False):
        """Apply date preset to date range inputs."""
        preset = self.date_filter_preset_var.get()
        today = datetime.now().date()
        
        if preset == "All Dates":
            self.date_from_var.set("")
            self.date_to_var.set("")
        elif preset == "Today":
            self.date_from_var.set(today.strftime("%Y-%m-%d"))
            self.date_to_var.set(today.strftime("%Y-%m-%d"))
        elif preset == "This Week":
            start_of_week = today - timedelta(days=today.weekday())
            end_of_week = start_of_week + timedelta(days=6)
            self.date_from_var.set(start_of_week.strftime("%Y-%m-%d"))
            self.date_to_var.set(end_of_week.strftime("%Y-%m-%d"))
        elif preset == "This Month":
            start_of_month = today.replace(day=1)
            end_of_month = (start_of_month.replace(month=start_of_month.month % 12 + 1, day=1) - timedelta(days=1))
            self.date_from_var.set(start_of_month.strftime("%Y-%m-%d"))
            self.date_to_var.set(end_of_month.strftime("%Y-%m-%d"))
        elif preset == "Next 7 Days":
            self.date_from_var.set(today.strftime("%Y-%m-%d"))
            self.date_to_var.set((today + timedelta(days=7)).strftime("%Y-%m-%d"))
        elif preset == "Next 30 Days":
            self.date_from_var.set(today.strftime("%Y-%m-%d"))
            self.date_to_var.set((today + timedelta(days=30)).strftime("%Y-%m-%d"))
    
    def get_filter_values(self) -> dict:
        """Get all filter values as a dictionary."""
        return {
            'search': self.get_filter_value('search'),
            'semantic_search': self.semantic_search_var.get(),
            'view': self.view_var.get(),
            'status': self.status_view_var.get(),
            'date_type': self.date_filter_type_var.get(),
            'date_preset': self.date_filter_preset_var.get(),
            'date_from': self.date_from_var.get(),
            'date_to': self.date_to_var.get()
        }
    
    def reset_filters(self):
        """Reset all filters to default values."""
        super().reset_filters()
        self.semantic_search_var.set(False)
        self.view_var.set("Wants (Matches)")
        self.status_view_var.set("All")
        self.date_filter_type_var.set("None")
        self.date_filter_preset_var.set("All Dates")
        self.date_from_var.set("")
        self.date_to_var.set("")
        self._apply_date_preset()
