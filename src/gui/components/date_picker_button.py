"""
Date picker button component with hidden calendar popup.
Provides a button that reveals a date picker when clicked.
"""

import tkinter as tk
from datetime import datetime
from typing import Optional, Callable

from config import PANEL, CARD, ACCENT, TEXT, MUTED
from components.date_picker import DatePickerPopup


class DatePickerButton(tk.Frame):
    """
    Button that reveals a date picker popup when clicked.
    Shows the selected date in the button text.
    """
    
    def __init__(self, parent, app, date_var: Optional[tk.StringVar] = None,
                 placeholder: str = "Select Date", on_change: Optional[Callable] = None,
                 **kwargs):
        bg = kwargs.pop('bg', PANEL)
        super().__init__(parent, bg=bg, **kwargs)
        
        self.app = app
        self.placeholder = placeholder
        self.on_change = on_change
        
        # Date variable
        if date_var is None:
            self.date_var = tk.StringVar()
        else:
            self.date_var = date_var
        
        # Track popup state
        self.popup = None
        
        self._build_ui()
    
    def _build_ui(self):
        """Build the button UI."""
        self.btn = tk.Button(
            self,
            text=self.placeholder,
            command=self._show_date_picker,
            bg=CARD,
            fg=TEXT,
            relief="flat",
            font=("Segoe UI", 9),
            padx=8,
            pady=4,
            activebackground=ACCENT,
            activeforeground=PANEL,
            cursor="hand2",
            highlightthickness=1,
            highlightbackground="#30363D"
        )
        self.btn.pack(fill="both", expand=True)
        
        # Update button text when date changes
        self.date_var.trace_add("write", self._update_button_text)
        
        # Initial button text update
        self._update_button_text()
    
    def _update_button_text(self, *args):
        """Update button text based on selected date."""
        date_str = self.date_var.get().strip()
        if date_str:
            self.btn.configure(text=f"📅 {date_str}")
        else:
            self.btn.configure(text=f"📅 {self.placeholder}")
        
        # Call on_change callback if provided
        if self.on_change:
            self.on_change(date_str)
    
    def _show_date_picker(self):
        """Show the date picker popup."""
        if self.popup is not None:
            return  # Already showing
        
        # Get button position
        self.btn.update_idletasks()
        x = self.btn.winfo_rootx()
        y = self.btn.winfo_rooty() + self.btn.winfo_height()
        
        # Create popup
        self.popup = DatePickerPopup(self, self.date_var, x, y)
        
        # Clean up when popup is closed
        self.popup.bind("<Destroy>", self._on_popup_destroy)
    
    def _on_popup_destroy(self, event):
        """Handle popup destruction."""
        self.popup = None
    
    def get_date(self) -> str:
        """Get the selected date."""
        return self.date_var.get()
    
    def set_date(self, date_str: str):
        """Set the selected date."""
        self.date_var.set(date_str)
    
    def clear_date(self):
        """Clear the selected date."""
        self.date_var.set("")
    
    def is_date_selected(self) -> bool:
        """Check if a date is selected."""
        return bool(self.date_var.get().strip())


class DateRangePicker(tk.Frame):
    """
    Date range picker with from/to date buttons.
    Provides two date picker buttons for selecting a date range.
    """
    
    def __init__(self, parent, app, from_var: Optional[tk.StringVar] = None,
                 to_var: Optional[tk.StringVar] = None,
                 on_change: Optional[Callable] = None, **kwargs):
        bg = kwargs.pop('bg', PANEL)
        super().__init__(parent, bg=bg, **kwargs)
        
        self.app = app
        self.on_change = on_change
        
        # Date variables
        self.from_var = from_var or tk.StringVar()
        self.to_var = to_var or tk.StringVar()
        
        self._build_ui()
    
    def _build_ui(self):
        """Build the date range picker UI."""
        # From date label
        tk.Label(self, text="From:", font=("Segoe UI", 9), 
                bg=PANEL, fg=MUTED).pack(side="left")
        
        # From date picker button
        self.from_picker = DatePickerButton(
            self, self.app, self.from_var,
            placeholder="Start Date",
            on_change=self._on_date_change
        )
        self.from_picker.pack(side="left", padx=(4, 8))
        
        # To date label
        tk.Label(self, text="To:", font=("Segoe UI", 9), 
                bg=PANEL, fg=MUTED).pack(side="left")
        
        # To date picker button
        self.to_picker = DatePickerButton(
            self, self.app, self.to_var,
            placeholder="End Date",
            on_change=self._on_date_change
        )
        self.to_picker.pack(side="left", padx=(4, 8))
    
    def _on_date_change(self, date_str):
        """Handle date change from either picker."""
        if self.on_change:
            self.on_change()
    
    def get_date_range(self) -> tuple:
        """Get the selected date range as (from_date, to_date)."""
        return (self.from_var.get(), self.to_var.get())
    
    def set_date_range(self, from_date: str, to_date: str):
        """Set the date range."""
        self.from_var.set(from_date)
        self.to_var.set(to_date)
    
    def clear_date_range(self):
        """Clear both dates."""
        self.from_var.set("")
        self.to_var.set("")
    
    def is_range_complete(self) -> bool:
        """Check if both dates are selected."""
        return bool(self.from_var.get().strip() and self.to_var.get().strip())
