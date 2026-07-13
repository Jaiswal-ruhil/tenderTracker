"""
alert_viewer.py
~~~~~~~~~~~~~~~
GUI component for viewing and managing proactive alerts.
Shows alerts that require human intervention and allows users to resolve them.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from typing import List

# Local imports
from config import BG, PANEL, CARD, ACCENT, ACCENT2, MUTED, TEXT, TEXTSUB, ERR, WARN, SUCCESS, FL
from alert_system import Alert, AlertSeverity, AlertCategory, get_alert_system


class AlertViewer:
    """Dialog for viewing and managing alerts."""
    
    def __init__(self, parent, app):
        self.parent = parent
        self.app = app
        self.alert_system = get_alert_system(app._log)
        self.window = None
        self.alert_list = None
        self.alert_items = []
        
    def show(self):
        """Show the alert viewer dialog."""
        if self.window and self.window.winfo_exists():
            self.window.lift()
            self.window.focus_force()
            return
            
        self.window = tk.Toplevel(self.parent)
        self.window.title("Alerts & Issues")
        self.window.geometry("900x600")
        self.window.resizable(True, True)
        self.window.configure(bg=BG)
        
        # Center the window
        x = self.parent.winfo_x() + (self.parent.winfo_width() - 900) // 2
        y = self.parent.winfo_y() + (self.parent.winfo_height() - 600) // 2
        self.window.geometry(f"+{max(0, x)}+{max(0, y)}")
        
        self._build_ui()
        self._refresh_alerts()
        
        # Register alert handler to auto-refresh
        self.alert_system.register_handler(AlertCategory.SCRAPING, lambda a: self._on_new_alert(a))
        self.alert_system.register_handler(AlertCategory.DOCUMENT_PROCESSING, lambda a: self._on_new_alert(a))
        self.alert_system.register_handler(AlertCategory.FILING_WORKFLOW, lambda a: self._on_new_alert(a))
        self.alert_system.register_handler(AlertCategory.NETWORK, lambda a: self._on_new_alert(a))
        
        self.window.protocol("WM_DELETE_WINDOW", self._on_close)
    
    def _build_ui(self):
        """Build the alert viewer UI."""
        # Header
        header = tk.Frame(self.window, bg=PANEL, pady=12, padx=16)
        header.pack(fill="x")
        
        tk.Label(header, text="🔔 Alerts & Issues", font=("Segoe UI", 14, "bold"), 
                bg=PANEL, fg=TEXT).pack(side="left")
        
        # Filter buttons
        filter_frame = tk.Frame(header, bg=PANEL)
        filter_frame.pack(side="right")
        
        self.filter_var = tk.StringVar(value="all")
        
        filters = [
            ("All", "all"),
            ("Unresolved", "unresolved"),
            ("Critical", "critical"),
            ("Error", "error"),
            ("Warning", "warning")
        ]
        
        for i, (label, value) in enumerate(filters):
            rb = tk.Radiobutton(filter_frame, text=label, variable=self.filter_var, 
                               value=value, bg=PANEL, fg=TEXT, selectcolor=CARD,
                               activebackground=CARD, activeforeground=TEXT,
                               font=FL, indicatoron=0, padx=8, pady=4,
                               command=self._refresh_alerts)
            rb.pack(side="left", padx=2)
        
        # Alert list
        list_frame = tk.Frame(self.window, bg=PANEL)
        list_frame.pack(fill="both", expand=True, padx=16, pady=(8, 16))
        
        # Treeview for alerts
        columns = ("severity", "category", "title", "timestamp", "status")
        self.alert_list = ttk.Treeview(list_frame, columns=columns, show="headings", 
                                       selectmode="extended")
        
        self.alert_list.heading("severity", text="Severity")
        self.alert_list.heading("category", text="Category")
        self.alert_list.heading("title", text="Title")
        self.alert_list.heading("timestamp", text="Time")
        self.alert_list.heading("status", text="Status")
        
        self.alert_list.column("severity", width=80)
        self.alert_list.column("category", width=120)
        self.alert_list.column("title", width=300)
        self.alert_list.column("timestamp", width=150)
        self.alert_list.column("status", width=80)
        
        vsb = ttk.Scrollbar(list_frame, orient="vertical", command=self.alert_list.yview)
        hsb = ttk.Scrollbar(list_frame, orient="horizontal", command=self.alert_list.xview)
        self.alert_list.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        self.alert_list.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        
        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)
        
        self.alert_list.bind("<Double-1>", self._on_double_click)
        self.alert_list.bind("<Button-3>", self._show_context_menu)
        
        # Detail panel
        detail_frame = tk.Frame(self.window, bg=PANEL, height=200)
        detail_frame.pack(fill="x", padx=16, pady=(0, 16))
        
        self.detail_text = tk.Text(detail_frame, bg=CARD, fg=TEXT, wrap="word",
                                   font=("Segoe UI", 9), height=8, relief="flat",
                                   padx=12, pady=8)
        self.detail_text.pack(fill="both", expand=True)
        self.detail_text.configure(state="disabled")
        
        # Action buttons
        btn_frame = tk.Frame(self.window, bg=BG)
        btn_frame.pack(fill="x", padx=16, pady=(0, 16))
        
        self.app._btn(btn_frame, "📋 View Details", self._view_details, bg=CARD).pack(side="left", padx=2)
        self.app._btn(btn_frame, "✅ Mark Resolved", self._mark_resolved, bg=ACCENT2).pack(side="left", padx=2)
        self.app._btn(btn_frame, "🗑️ Clear Old Alerts", self._clear_old, bg=CARD).pack(side="left", padx=2)
        self.app._btn(btn_frame, "🔄 Refresh", self._refresh_alerts, bg=CARD).pack(side="left", padx=2)
        self.app._btn(btn_frame, "✖ Close", self._on_close, bg=CARD).pack(side="right", padx=2)
    
    def _refresh_alerts(self):
        """Refresh the alert list based on current filter."""
        if not self.alert_list:
            return
            
        # Clear existing items
        for item in self.alert_list.get_children():
            self.alert_list.delete(item)
        
        self.alert_items = []
        
        # Get alerts based on filter
        filter_value = self.filter_var.get()
        
        if filter_value == "all":
            alerts = self.alert_system.get_active_alerts(unresolved_only=False)
        elif filter_value == "unresolved":
            alerts = self.alert_system.get_active_alerts(unresolved_only=True)
        elif filter_value == "critical":
            alerts = self.alert_system.get_active_alerts(severity=AlertSeverity.CRITICAL)
        elif filter_value == "error":
            alerts = self.alert_system.get_active_alerts(severity=AlertSeverity.ERROR)
        elif filter_value == "warning":
            alerts = self.alert_system.get_active_alerts(severity=AlertSeverity.WARNING)
        else:
            alerts = self.alert_system.get_active_alerts(unresolved_only=False)
        
        # Sort by timestamp (newest first)
        alerts.sort(key=lambda a: a.timestamp, reverse=True)
        
        # Check for pending interventions
        pending_interventions = [a for a in alerts if getattr(a, '_pending_intervention', False) and not a.resolved]
        
        # Add alerts to list
        for alert in alerts:
            severity_text = alert.severity.value.upper()
            category_text = alert.category.value.replace("_", " ").title()
            time_text = alert.timestamp.strftime("%Y-%m-%d %H:%M")
            status_text = "Resolved" if alert.resolved else "Active"
            
            # Add intervention indicator
            if getattr(alert, '_pending_intervention', False) and not alert.resolved:
                status_text = "⚠️ Needs Action"
            
            item_id = self.alert_list.insert("", "end", values=(
                severity_text, category_text, alert.title, time_text, status_text
            ))
            
            # Color coding
            if alert.severity == AlertSeverity.CRITICAL:
                self.alert_list.tag_configure("critical", foreground=ERR)
                self.alert_list.item(item_id, tags=("critical",))
            elif alert.severity == AlertSeverity.ERROR:
                self.alert_list.tag_configure("error", foreground=ERR)
                self.alert_list.item(item_id, tags=("error",))
            elif alert.severity == AlertSeverity.WARNING:
                self.alert_list.tag_configure("warning", foreground=WARN)
                self.alert_list.item(item_id, tags=("warning",))
            
            self.alert_items.append((item_id, alert))
        
        # Update header with count
        active_count = len([a for a in alerts if not a.resolved])
        intervention_count = len(pending_interventions)
        
        if intervention_count > 0:
            self.window.title(f"Alerts & Issues ({active_count} active, {intervention_count} need action)")
        else:
            self.window.title(f"Alerts & Issues ({active_count} active)")
        
        # Auto-trigger intervention dialogs for pending critical alerts
        for alert in pending_interventions:
            if alert.requires_intervention:
                try:
                    result = self.alert_system.trigger_intervention(alert, self.parent, self.app)
                    if result:
                        alert._pending_intervention = False
                        self._refresh_alerts()
                        break  # Only show one intervention at a time
                except Exception as e:
                    self.app._log("error", f"Failed to trigger intervention: {e}")
    
    def _on_new_alert(self, alert):
        """Handle new alert notification."""
        if self.window and self.window.winfo_exists():
            self._refresh_alerts()
            # Flash window to get attention
            self.window.attributes("-topmost", True)
            self.window.after(100, lambda: self.window.attributes("-topmost", False))
    
    def _on_double_click(self, event):
        """Handle double-click on alert to view details."""
        self._view_details()
    
    def _show_context_menu(self, event):
        """Show context menu for alert."""
        item = self.alert_list.identify_row(event.y)
        if not item:
            return
            
        menu = tk.Menu(self.window, tearoff=0, bg=PANEL, fg=TEXT)
        menu.add_command(label="View Details", command=self._view_details)
        menu.add_command(label="Mark Resolved", command=self._mark_resolved)
        menu.add_separator()
        menu.add_command(label="Copy Alert Info", command=self._copy_alert_info)
        menu.post(event.x_root, event.y_root)
    
    def _get_selected_alert(self):
        """Get the currently selected alert."""
        selection = self.alert_list.selection()
        if not selection:
            return None
            
        for item_id, alert in self.alert_items:
            if item_id in selection:
                return alert
        return None
    
    def _view_details(self):
        """Show detailed information about selected alert."""
        alert = self._get_selected_alert()
        if not alert:
            messagebox.showinfo("No Selection", "Please select an alert to view details.", parent=self.window)
            return
        
        detail_text = f"""Title: {alert.title}
Severity: {alert.severity.value.upper()}
Category: {alert.category.value.replace('_', ' ').title()}
Time: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
Status: {'Resolved' if alert.resolved else 'Active'}

Message:
{alert.message}

Context:
{self._format_dict(alert.context)}

Suggested Actions:
{chr(10).join(f'• {action}' for action in alert.suggested_actions) if alert.suggested_actions else 'None'}

Resolution Notes:
{alert.resolution_notes if alert.resolved else 'Not resolved yet'}
"""
        
        self.detail_text.configure(state="normal")
        self.detail_text.delete("1.0", "end")
        self.detail_text.insert("1.0", detail_text)
        self.detail_text.configure(state="disabled")
    
    def _format_dict(self, d):
        """Format dictionary for display."""
        if not d:
            return "None"
        return "\n".join(f"  {k}: {v}" for k, v in d.items())
    
    def _mark_resolved(self):
        """Mark selected alert as resolved."""
        alert = self._get_selected_alert()
        if not alert:
            messagebox.showinfo("No Selection", "Please select an alert to resolve.", parent=self.window)
            return
        
        if alert.resolved:
            messagebox.showinfo("Already Resolved", "This alert is already resolved.", parent=self.window)
            return
        
        # Ask for resolution notes
        notes = messagebox.askstring("Resolution Notes", 
                                     "Enter resolution notes (optional):", 
                                     parent=self.window)
        
        self.alert_system.resolve_alert(alert, notes or "")
        self._refresh_alerts()
        self.app._log("ok", f"Resolved alert: {alert.title}")
    
    def _copy_alert_info(self):
        """Copy alert information to clipboard."""
        alert = self._get_selected_alert()
        if not alert:
            return
        
        info = f"{alert.title} - {alert.message}"
        self.window.clipboard_clear()
        self.window.clipboard_append(info)
        self.app._log("info", "Copied alert info to clipboard")
    
    def _clear_old(self):
        """Clear alerts older than 30 days."""
        if messagebox.askyesno("Clear Old Alerts", 
                              "Clear alerts older than 30 days?", 
                              parent=self.window):
            self.alert_system.clear_old_alerts(days=30)
            self._refresh_alerts()
            self.app._log("info", "Cleared old alerts")
    
    def _on_close(self):
        """Handle window close."""
        if self.window:
            self.window.destroy()
            self.window = None
