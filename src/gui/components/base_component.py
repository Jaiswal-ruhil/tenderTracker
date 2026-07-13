"""
Base component classes for modular GUI architecture.
Provides common functionality and patterns for reusable UI components.
"""

import tkinter as tk
from tkinter import ttk
from abc import ABC, abstractmethod
from typing import Callable, Optional, Dict, Any, List

from config import BG, PANEL, CARD, ACCENT, ACCENT2, MUTED, TEXT, TEXTSUB, SUCCESS, ERR, WARN


class BaseComponent(tk.Frame, ABC):
    """
    Abstract base class for all GUI components.
    Provides common initialization and lifecycle methods.
    """
    
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, bg=kwargs.pop('bg', BG), **kwargs)
        self.app = app
        self.parent = parent
        self._callbacks = {}
        self._state = {}
        
        self._build_ui()
        self._bind_events()
    
    @abstractmethod
    def _build_ui(self):
        """Build the component's UI. Must be implemented by subclasses."""
        pass
    
    def _bind_events(self):
        """Bind event handlers. Override in subclasses if needed."""
        pass
    
    def register_callback(self, event_name: str, callback: Callable):
        """Register a callback for a specific event."""
        self._callbacks[event_name] = callback
    
    def trigger_callback(self, event_name: str, *args, **kwargs):
        """Trigger a registered callback."""
        if event_name in self._callbacks:
            self._callbacks[event_name](*args, **kwargs)
    
    def set_state(self, key: str, value: Any):
        """Set a state value."""
        self._state[key] = value
    
    def get_state(self, key: str, default: Any = None) -> Any:
        """Get a state value."""
        return self._state.get(key, default)
    
    def update_ui(self):
        """Update the UI based on current state. Override in subclasses."""
        pass
    
    def refresh(self):
        """Refresh the component. Override in subclasses."""
        pass


class ToolbarComponent(BaseComponent):
    """
    Base class for toolbar/action bar components.
    Provides common button creation and layout patterns.
    """
    
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, app, **kwargs)
        self.buttons = []
    
    def add_button(self, text: str, callback: Callable, 
                   bg: str = CARD, fg: str = TEXT, 
                   padx: int = 2, pady: int = 2,
                   **kwargs) -> tk.Button:
        """Add a button to the toolbar."""
        btn = self.app._btn(self, text, callback, bg=bg, fg=fg, pad=0, **kwargs)
        btn.pack(side="right", padx=padx, pady=pady)
        self.buttons.append(btn)
        return btn
    
    def add_button_left(self, text: str, callback: Callable,
                       bg: str = CARD, fg: str = TEXT,
                       padx: int = 2, pady: int = 2,
                       **kwargs) -> tk.Button:
        """Add a button to the left side of the toolbar."""
        btn = self.app._btn(self, text, callback, bg=bg, fg=fg, pad=0, **kwargs)
        btn.pack(side="left", padx=padx, pady=pady)
        self.buttons.append(btn)
        return btn
    
    def add_separator(self):
        """Add a visual separator."""
        tk.Label(self, text="│", font=("Segoe UI", 9), bg=self.cget('bg'), 
                fg="#30363D").pack(side="left", padx=(6, 6))
    
    def enable_all(self):
        """Enable all buttons in the toolbar."""
        for btn in self.buttons:
            btn.configure(state="normal")
    
    def disable_all(self):
        """Disable all buttons in the toolbar."""
        for btn in self.buttons:
            btn.configure(state="disabled")


class FilterComponent(BaseComponent):
    """
    Base class for filter/search components.
    Provides common filter UI patterns.
    """
    
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, app, **kwargs)
        self.filter_vars = {}
        self.filter_widgets = {}
    
    def add_search_box(self, label: str = "Search:", width: int = 22,
                      callback: Optional[Callable] = None) -> tk.Entry:
        """Add a search entry box."""
        tk.Label(self, text=label, font=("Segoe UI", 9), 
                bg=PANEL, fg=MUTED).pack(side="left")
        
        var = tk.StringVar()
        if callback:
            var.trace_add("write", lambda *args: callback())
        
        entry = tk.Entry(self, textvariable=var, bg=CARD, fg=TEXT,
                        insertbackground=TEXT, relief="flat", 
                        font=("Segoe UI", 9), width=width,
                        highlightthickness=1, highlightbackground="#30363D",
                        highlightcolor=ACCENT2)
        entry.pack(side="left", padx=(4, 15))
        
        self.filter_vars['search'] = var
        self.filter_widgets['search'] = entry
        return entry
    
    def add_dropdown(self, label: str, values: List[str], 
                    default: str, callback: Optional[Callable] = None,
                    width: int = 20) -> ttk.Combobox:
        """Add a dropdown filter."""
        tk.Label(self, text=label, font=("Segoe UI", 9), 
                bg=PANEL, fg=MUTED).pack(side="left")
        
        from tkinter import ttk
        var = tk.StringVar(value=default)
        combo = ttk.Combobox(self, textvariable=var, values=values,
                           state="readonly", font=("Segoe UI", 9), width=width)
        combo.pack(side="left", padx=4)
        
        if callback:
            combo.bind("<<ComboboxSelected>>", lambda e: callback())
        
        self.filter_vars[label.lower()] = var
        self.filter_widgets[label.lower()] = combo
        return combo
    
    def add_checkbox(self, text: str, default: bool = False,
                    callback: Optional[Callable] = None) -> tk.Checkbutton:
        """Add a checkbox filter."""
        var = tk.BooleanVar(value=default)
        cb = tk.Checkbutton(self, text=text, variable=var,
                          bg=PANEL, fg=TEXT, selectcolor=CARD, 
                          activebackground=PANEL, activeforeground=TEXT,
                          font=("Segoe UI", 9))
        cb.pack(side="left", padx=(0, 15))
        
        if callback:
            cb.configure(command=callback)
        
        self.filter_vars[text.lower().replace(' ', '_')] = var
        self.filter_widgets[text.lower().replace(' ', '_')] = cb
        return cb
    
    def get_filter_value(self, key: str) -> Any:
        """Get the value of a filter."""
        var = self.filter_vars.get(key)
        return var.get() if var else None
    
    def set_filter_value(self, key: str, value: Any):
        """Set the value of a filter."""
        var = self.filter_vars.get(key)
        if var:
            var.set(value)
    
    def reset_filters(self):
        """Reset all filters to default values."""
        for var in self.filter_vars.values():
            if isinstance(var, tk.StringVar):
                var.set("")
            elif isinstance(var, tk.BooleanVar):
                var.set(False)


class StatusComponent(BaseComponent):
    """
    Base class for status/summary components.
    Provides common status display patterns.
    """
    
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, app, **kwargs)
        self.status_labels = {}
    
    def add_status_item(self, key: str, label: str, default: str = "0",
                       fg: str = TEXTSUB) -> tk.Label:
        """Add a status item to the component."""
        lbl = tk.Label(self, text=f"{label}: {default}", 
                      font=("Segoe UI", 8, "bold"),
                      bg=PANEL, fg=fg, anchor="w")
        lbl.pack(side="left", padx=(0, 15))
        self.status_labels[key] = lbl
        return lbl
    
    def update_status(self, key: str, value: str, fg: Optional[str] = None):
        """Update a status item."""
        lbl = self.status_labels.get(key)
        if lbl:
            parts = lbl.cget("text").split(":")
            if len(parts) >= 2:
                new_text = f"{parts[0]}: {value}"
                lbl.configure(text=new_text)
                if fg:
                    lbl.configure(fg=fg)
    
    def set_summary_text(self, text: str):
        """Set the entire summary text."""
        if hasattr(self, 'summary_lbl'):
            self.summary_lbl.configure(text=text)


class CardComponent(BaseComponent):
    """
    Base class for card-like container components.
    Provides common card styling and layout.
    """
    
    def __init__(self, parent, app, title: str = "", **kwargs):
        bg = kwargs.pop('bg', PANEL)
        super().__init__(parent, app, bg=bg, padx=10, pady=6,
                       highlightthickness=1, highlightbackground="#30363D", **kwargs)
        
        self.title = title
        if title:
            self._add_header()
    
    def _add_header(self):
        """Add a header to the card."""
        header = tk.Frame(self, bg=self.cget('bg'))
        header.pack(fill="x", pady=(0, 6))
        
        tk.Label(header, text=self.title, font=("Segoe UI", 9, "bold"),
                bg=self.cget('bg'), fg=MUTED).pack(side="left")
    
    def add_content_frame(self) -> tk.Frame:
        """Add a content frame to the card."""
        content = tk.Frame(self, bg=self.cget('bg'))
        content.pack(fill="both", expand=True)
        return content
