"""
intervention_dialog.py
~~~~~~~~~~~~~~~~~~~~~~~
Dialog for handling human intervention queries when the app encounters issues
that require user decision or action.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import List, Callable, Optional

# Local imports
from config import BG, PANEL, CARD, ACCENT, ACCENT2, MUTED, TEXT, TEXTSUB, ERR, WARN, SUCCESS, FL
from alert_system import Alert, AlertSeverity


class InterventionDialog:
    """Dialog for handling human intervention queries."""
    
    def __init__(self, parent, app, alert: Alert):
        self.parent = parent
        self.app = app
        self.alert = alert
        self.window = None
        self.result = None
        self.user_notes = ""
        
    def show(self) -> Optional[str]:
        """Show the intervention dialog and return user's choice.
        
        Returns:
            User's choice/action, or None if cancelled
        """
        self.window = tk.Toplevel(self.parent)
        self.window.title(f"⚠️ Intervention Required: {self.alert.title}")
        self.window.configure(bg=BG)
        self.window.resizable(True, True)
        
        screen_w = self.window.winfo_screenwidth()
        screen_h = self.window.winfo_screenheight()
        init_w = min(660, max(520, screen_w - 40))
        init_h = min(580, max(420, screen_h - 60))
        self.window.minsize(520, 420)
        
        parent_h = self.parent.winfo_height() if hasattr(self.parent, 'winfo_height') else 600
        x = self.parent.winfo_x() + (self.parent.winfo_width() - init_w) // 2
        y = self.parent.winfo_y() + (parent_h - init_h) // 2
        self.window.geometry(f"{init_w}x{init_h}+{max(0, x)}+{max(0, y)}")
        self.window.grab_set()  # Make modal
        
        self._build_ui()
        
        # Wait for user response
        self.window.wait_window()
        return self.result
    
    def _build_ui(self):
        """Build the intervention dialog UI."""
        # Header with severity indicator
        header = tk.Frame(self.window, bg=PANEL, pady=16, padx=20)
        header.pack(fill="x")
        
        severity_color = ERR if self.alert.severity in [AlertSeverity.ERROR, AlertSeverity.CRITICAL] else WARN
        severity_icon = "🔴" if self.alert.severity == AlertSeverity.CRITICAL else "🟠" if self.alert.severity == AlertSeverity.ERROR else "🟡"
        
        tk.Label(header, text=f"{severity_icon} {self.alert.severity.value.upper()}", 
                font=("Segoe UI", 12, "bold"), bg=PANEL, fg=severity_color).pack(side="left")
        
        tk.Label(header, text=f"Category: {self.alert.category.value.replace('_', ' ').title()}", 
                font=("Segoe UI", 9), bg=PANEL, fg=MUTED).pack(side="right")
        
        # Title and message
        content_frame = tk.Frame(self.window, bg=BG, padx=20, pady=(8, 16))
        content_frame.pack(fill="both", expand=True)
        
        tk.Label(content_frame, text=self.alert.title, font=("Segoe UI", 14, "bold"), 
                bg=BG, fg=TEXT).pack(anchor="w", pady=(0, 8))
        
        message_text = tk.Text(content_frame, bg=CARD, fg=TEXT, wrap="word",
                               font=("Segoe UI", 10), height=6, relief="flat",
                               padx=12, pady=8)
        message_text.pack(fill="x")
        message_text.insert("1.0", self.alert.message)
        message_text.configure(state="disabled")
        
        # Suggested actions
        if self.alert.suggested_actions:
            tk.Label(content_frame, text="Suggested Actions:", font=("Segoe UI", 10, "bold"), 
                    bg=BG, fg=TEXT).pack(anchor="w", pady=(16, 8))
            
            actions_frame = tk.Frame(content_frame, bg=CARD, padx=12, pady=12)
            actions_frame.pack(fill="x")
            
            for i, action in enumerate(self.alert.suggested_actions):
                action_row = tk.Frame(actions_frame, bg=CARD)
                action_row.pack(fill="x", pady=4)
                
                tk.Label(action_row, text=f"•", bg=CARD, fg=MUTED, font=("Segoe UI", 10)).pack(side="left")
                tk.Label(action_row, text=action, bg=CARD, fg=TEXTSUB, 
                        font=("Segoe UI", 10), wraplength=500).pack(side="left", padx=8)
        
        # Context information
        if self.alert.context:
            tk.Label(content_frame, text="Additional Context:", font=("Segoe UI", 10, "bold"), 
                    bg=BG, fg=TEXT).pack(anchor="w", pady=(16, 8))
            
            context_text = tk.Text(content_frame, bg=CARD, fg=TEXTSUB, wrap="word",
                                   font=("Segoe UI", 9), height=4, relief="flat",
                                   padx=12, pady=8)
            context_text.pack(fill="x")
            
            context_str = "\n".join(f"{k}: {v}" for k, v in self.alert.context.items())
            context_text.insert("1.0", context_str)
            context_text.configure(state="disabled")
        
        # User notes
        tk.Label(content_frame, text="Your Notes (optional):", font=("Segoe UI", 10, "bold"), 
                bg=BG, fg=TEXT).pack(anchor="w", pady=(16, 4))
        
        self.notes_var = tk.StringVar()
        notes_entry = tk.Entry(content_frame, textvariable=self.notes_var, bg=CARD, fg=TEXT,
                               insertbackground=TEXT, relief="flat", font=FL)
        notes_entry.pack(fill="x", ipady=6)
        
        # Action buttons
        btn_frame = tk.Frame(self.window, bg=BG, padx=20, pady=16)
        btn_frame.pack(fill="x")
        
        # Default actions based on alert type
        actions = self._get_default_actions()
        
        for action in actions:
            self.app._btn(btn_frame, action["label"], 
                         lambda a=action: self._handle_action(a),
                         bg=action.get("bg", CARD)).pack(side="left", padx=4, expand=True, fill="x")
        
        self.app._btn(btn_frame, "Cancel", self._cancel, bg=CARD).pack(side="right", padx=4)
    
    def _get_default_actions(self) -> List[dict]:
        """Get default actions based on alert category and severity."""
        actions = []
        
        if self.alert.category.value == "scraping":
            actions.extend([
                {"label": "🔄 Retry", "action": "retry", "bg": ACCENT2},
                {"label": "⏭️ Skip & Continue", "action": "skip", "bg": CARD},
                {"label": "🔧 Manual Fix", "action": "manual", "bg": CARD}
            ])
        elif self.alert.category.value == "document_processing":
            actions.extend([
                {"label": "🔄 Retry", "action": "retry", "bg": ACCENT2},
                {"label": "📝 Manual Entry", "action": "manual", "bg": CARD},
                {"label": "⏭️ Skip Document", "action": "skip", "bg": CARD}
            ])
        elif self.alert.category.value == "filing_workflow":
            actions.extend([
                {"label": "🔄 Retry", "action": "retry", "bg": ACCENT2},
                {"label": "📁 Manual Folder", "action": "manual", "bg": CARD},
                {"label": "⏭️ Skip Filing", "action": "skip", "bg": CARD}
            ])
        elif self.alert.category.value == "network":
            actions.extend([
                {"label": "🔄 Retry", "action": "retry", "bg": ACCENT2},
                {"label": "⏸️ Pause & Check", "action": "pause", "bg": CARD},
                {"label": "⏭️ Continue Offline", "action": "skip", "bg": CARD}
            ])
        else:
            actions.extend([
                {"label": "🔄 Retry", "action": "retry", "bg": ACCENT2},
                {"label": "⏭️ Continue", "action": "skip", "bg": CARD},
                {"label": "🔧 Manual Fix", "action": "manual", "bg": CARD}
            ])
        
        return actions
    
    def _handle_action(self, action: dict):
        """Handle user's action choice."""
        self.result = action["action"]
        self.user_notes = self.notes_var.get()
        
        # Log the intervention
        self.app._log("info", f"User intervention: {action['label']} for alert '{self.alert.title}'")
        
        # Resolve the alert with user's action
        from alert_system import get_alert_system
        alert_system = get_alert_system(self.app._log)
        resolution_notes = f"User action: {action['label']}"
        if self.user_notes:
            resolution_notes += f"\nNotes: {self.user_notes}"
        alert_system.resolve_alert(self.alert, resolution_notes)
        
        self.window.destroy()
    
    def _cancel(self):
        """Handle cancel action."""
        self.result = None
        self.app._log("info", f"User cancelled intervention for alert '{self.alert.title}'")
        self.window.destroy()


def show_intervention_dialog(parent, app, alert: Alert) -> Optional[str]:
    """Convenience function to show an intervention dialog.
    
    Args:
        parent: Parent window
        app: Application instance
        alert: Alert requiring intervention
        
    Returns:
        User's action choice, or None if cancelled
    """
    dialog = InterventionDialog(parent, app, alert)
    return dialog.show()
