"""
filter_bar.py
~~~~~~~~~~~~~
Filter bar component for tender table filtering.
Provides search, view filters, status filters, date filtering, and quick reset.
"""

import tkinter as tk
from tkinter import ttk
from datetime import datetime, timedelta

from config import PANEL, CARD, ACCENT, ACCENT2, MUTED, TEXT, TEXTSUB, ERR
from components.base_component import FilterComponent
from components.date_picker_button import DateRangePicker


class FilterBar(FilterComponent):
    """
    Filter bar with modern search, view filters, date filtering, and quick reset.
    """
    
    def __init__(self, parent, app, table_tab, **kwargs):
        self.table_tab = table_tab
        self.date_from_var = tk.StringVar(value="")
        self.date_to_var = tk.StringVar(value="")
        super().__init__(parent, app, bg=PANEL, padx=10, pady=6, 
                       highlightthickness=1, highlightbackground="#30363D", **kwargs)
    
    def _build_ui(self):
        # 1. Search Box with Clear Button
        search_frame = tk.Frame(self, bg=PANEL)
        search_frame.pack(side="left", padx=(0, 10))

        tk.Label(search_frame, text="🔍 Search:", font=("Segoe UI", 9, "bold"), 
                 bg=PANEL, fg=MUTED).pack(side="left", padx=(0, 4))
        
        var = tk.StringVar()
        var.trace_add("write", lambda *args: self._on_search_change())
        self.filter_vars['search'] = var

        self.search_entry = tk.Entry(
            search_frame, textvariable=var, bg=CARD, fg=TEXT,
            insertbackground=TEXT, relief="flat", font=("Segoe UI", 9), width=22,
            highlightthickness=1, highlightbackground="#30363D", highlightcolor=ACCENT2
        )
        self.search_entry.pack(side="left", padx=(0, 4))

        # Clear search button
        self.clear_btn = tk.Button(
            search_frame, text="✖", font=("Segoe UI", 8, "bold"), bg=CARD, fg=MUTED,
            activebackground="#21262D", activeforeground=ERR, bd=0, cursor="hand2",
            command=lambda: var.set("")
        )
        self.clear_btn.pack(side="left")

        # 2. Semantic Search Checkbox
        self.semantic_search_var = tk.BooleanVar(value=False)
        self.add_checkbox("Semantic Search", default=False, callback=self._on_search_change)
        
        # 3. View Filter Dropdown
        self.view_var = tk.StringVar(value="Wants (Matches)")
        self.add_dropdown("Filter:", 
                         ["All Tenders", "Wants (Matches)", "Don't Wants (Filtered)"],
                         "Wants (Matches)", callback=self._on_view_change, width=18)
        
        self.add_separator()
        
        # 4. Status Filter Dropdown
        self.status_view_var = tk.StringVar(value="All")
        self.add_dropdown("Status:",
                         ["All", "Not Filed", "Filed", "Evaluating", "Awarded"],
                         "All", callback=self._on_status_change, width=12)
        
        self.add_separator()
        
        # 5. Date Filter Controls
        self.date_filter_type_var = tk.StringVar(value="None")
        self.add_dropdown("Date Type:",
                         ["None", "End Date", "Bid Opening", "Start Date"],
                         "None", callback=self._on_date_type_change, width=12)
        
        self.date_filter_preset_var = tk.StringVar(value="All Dates")
        self.add_dropdown("Preset:",
                         ["All Dates", "Today", "This Week", "This Month", "Next 7 Days", "Next 30 Days"],
                         "All Dates", callback=self._on_date_preset_change, width=12)
        
        # Custom date range with date picker buttons
        self.date_range_picker = DateRangePicker(
            self, self.app, self.date_from_var, self.date_to_var,
            on_change=self._on_date_range_change
        )
        self.date_range_picker.pack(side="left", padx=(6, 8))

        # 6. Reset Filters Button
        reset_btn = tk.Button(
            self, text="🔄 Reset Filters", font=("Segoe UI", 8, "bold"),
            bg="#21262D", fg=TEXTSUB, activebackground="#30363D", activeforeground=TEXT,
            bd=0, padx=8, pady=3, cursor="hand2", command=self.reset_filters
        )
        reset_btn.pack(side="right", padx=(8, 0))
    
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
        if 'search' in self.filter_vars:
            self.filter_vars['search'].set("")
        self.semantic_search_var.set(False)
        self.view_var.set("Wants (Matches)")
        self.status_view_var.set("All")
        self.date_filter_type_var.set("None")
        self.date_filter_preset_var.set("All Dates")
        self.date_from_var.set("")
        self.date_to_var.set("")
        self._apply_date_preset()
        if hasattr(self.table_tab, 'refresh_table_view'):
            self.table_tab.refresh_table_view()
