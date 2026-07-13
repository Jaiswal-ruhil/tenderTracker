"""
AI-powered filter bar component with natural language processing.
Extends the standard filter bar with AI capabilities for smart filtering.
"""

import tkinter as tk
from tkinter import ttk
import asyncio
from datetime import datetime, timedelta

from config import PANEL, CARD, ACCENT, ACCENT2, MUTED, TEXT, SUCCESS, WARN
from components.base_component import FilterComponent
from components.date_picker_button import DateRangePicker


class AIFilterBar(FilterComponent):
    """
    AI-enhanced filter bar with natural language search and smart filtering.
    """
    
    def __init__(self, parent, app, table_tab, **kwargs):
        self.table_tab = table_tab
        self.ai_enabled = tk.BooleanVar(value=False)
        self.natural_query_var = tk.StringVar()
        super().__init__(parent, app, bg=PANEL, padx=10, pady=6, 
                       highlightthickness=1, highlightbackground="#30363D", **kwargs)
    
    def _build_ui(self):
        # AI Toggle
        self.ai_toggle = tk.Checkbutton(
            self, text="🤖 AI Smart Filter", variable=self.ai_enabled,
            bg=PANEL, fg=ACCENT2, selectcolor=CARD, activebackground=PANEL, 
            activeforeground=ACCENT2, font=("Segoe UI", 9, "bold"),
            command=self._on_ai_toggle
        )
        self.ai_toggle.pack(side="left", padx=(0, 15))
        
        # Natural Language Query (shown when AI is enabled)
        self.ai_frame = tk.Frame(self, bg=PANEL)
        
        tk.Label(self.ai_frame, text="Ask AI:", font=("Segoe UI", 9), 
                bg=PANEL, fg=ACCENT2).pack(side="left")
        
        self.natural_query_ent = tk.Entry(
            self.ai_frame, textvariable=self.natural_query_var, 
            bg=CARD, fg=TEXT, insertbackground=TEXT, relief="flat", 
            font=("Segoe UI", 9), width=35,
            highlightthickness=1, highlightbackground="#30363D",
            highlightcolor=ACCENT2
        )
        self.natural_query_ent.pack(side="left", padx=(4, 8))
        self.natural_query_ent.bind("<Return>", self._on_natural_query)
        
        self.process_btn = self.app._btn(
            self.ai_frame, "Process", self._on_natural_query, 
            bg=ACCENT, fg=TEXT
        )
        self.process_btn.pack(side="left", padx=2)
        
        # Visual separator
        tk.Label(self, text="│", font=("Segoe UI", 9), bg=PANEL, 
                fg="#30363D").pack(side="left", padx=(15, 15))
        
        # Standard filters (always available)
        self._add_standard_filters()
    
    def _add_standard_filters(self):
        """Add standard filter controls."""
        # Search box
        self.add_search_box("Search:", width=22, callback=self._on_search_change)
        
        # View dropdown
        self.view_var = tk.StringVar(value="Wants (Matches)")
        self.add_dropdown("Filter:", 
                         ["All Tenders", "Wants (Matches)", "Don't Wants (Filtered)", "AI Recommended"],
                         "Wants (Matches)", callback=self._on_view_change, width=20)
        
        # Visual separator
        self.add_separator()
        
        # Status dropdown
        self.status_view_var = tk.StringVar(value="All")
        self.add_dropdown("Status:",
                         ["All", "Not Filed", "Filed", "Evaluating", "Awarded", "High Risk"],
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
    
    def _on_ai_toggle(self):
        """Handle AI toggle."""
        if self.ai_enabled.get():
            self.ai_frame.pack(side="left", padx=(0, 15))
            self.natural_query_ent.focus()
        else:
            self.ai_frame.pack_forget()
            self.natural_query_var.set("")
        
        if hasattr(self.table_tab, 'refresh_table_view'):
            self.table_tab.refresh_table_view()
    
    def _on_natural_query(self, event=None):
        """Handle natural language query processing."""
        query = self.natural_query_var.get().strip()
        if not query:
            return
        
        # Disable button during processing
        self.process_btn.configure(state="disabled", text="Processing...")
        
        # Process in background to avoid UI freeze
        self._process_natural_query_async(query)
    
    def _process_natural_query_async(self, query):
        """Process natural language query asynchronously."""
        import threading
        
        def process():
            try:
                import ai_integration
                ai = ai_integration.get_ai_integration()
                
                # Run async function in event loop
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    result = loop.run_until_complete(ai.process_natural_language_query(query))
                    
                    # Apply filters from AI interpretation
                    filters = result.interpreted_filters
                    
                    # Update filter UI with AI results
                    if filters.get("category"):
                        self.view_var.set("All Tenders")  # Reset to allow category filter
                        # Could add category-specific logic here
                    
                    if filters.get("location"):
                        # Could add location-specific logic
                        pass
                    
                    if filters.get("max_value") or filters.get("min_value"):
                        # Could add value range logic
                        pass
                    
                    # Update search with extracted terms
                    if filters.get("keywords"):
                        self.set_filter_value('search', ' '.join(filters['keywords']))
                    
                    # Refresh table
                    self.after(0, lambda: self._on_ai_query_complete(result))
                    
                finally:
                    loop.close()
                    
            except Exception as e:
                self.after(0, lambda: self._on_ai_query_error(str(e)))
        
        thread = threading.Thread(target=process, daemon=True)
        thread.start()
    
    def _on_ai_query_complete(self, result):
        """Handle successful AI query processing."""
        self.process_btn.configure(state="normal", text="Process")
        
        # Show AI interpretation
        interpretation = f"AI interpreted: {result.category_focus or 'General'}"
        if result.location_focus:
            interpretation += f" in {result.location_focus}"
        if result.value_range:
            interpretation += f" (value: {result.value_range[0]}-{result.value_range[1]})"
        
        # Could show this in a tooltip or status bar
        print(interpretation)  # For now, print to console
        
        # Refresh table view
        if hasattr(self.table_tab, 'refresh_table_view'):
            self.table_tab.refresh_table_view()
    
    def _on_ai_query_error(self, error):
        """Handle AI query processing error."""
        self.process_btn.configure(state="normal", text="Process")
        print(f"AI query error: {error}")  # For now, print to console
    
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
            'ai_enabled': self.ai_enabled.get(),
            'natural_query': self.natural_query_var.get(),
            'search': self.get_filter_value('search'),
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
        self.ai_enabled.set(False)
        self.ai_frame.pack_forget()
        self.natural_query_var.set("")
        self.view_var.set("Wants (Matches)")
        self.status_view_var.set("All")
        self.date_filter_type_var.set("None")
        self.date_filter_preset_var.set("All Dates")
        self.date_from_var.set("")
        self.date_to_var.set("")
        self._apply_date_preset()
