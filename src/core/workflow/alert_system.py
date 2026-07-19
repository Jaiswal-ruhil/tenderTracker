"""
alert_system.py
~~~~~~~~~~~~~~~
Proactive alert system for detecting and handling issues that require human intervention.
Monitors various stages of the application workflow and raises alerts when problems are detected.
"""

import os
import json
from datetime import datetime
from typing import Dict, List, Optional, Callable
from enum import Enum
import threading


class AlertSeverity(Enum):
    """Severity levels for alerts."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertCategory(Enum):
    """Categories of alerts based on workflow stage."""
    SCRAPING = "scraping"
    DOCUMENT_PROCESSING = "document_processing"
    FILING_WORKFLOW = "filing_workflow"
    DATABASE = "database"
    CONFIGURATION = "configuration"
    NETWORK = "network"
    FILE_SYSTEM = "file_system"


class Alert:
    """Represents a single alert."""
    
    def __init__(self, severity: AlertSeverity, category: AlertCategory, 
                 title: str, message: str, context: Dict = None,
                 suggested_actions: List[str] = None, requires_intervention: bool = False):
        self.severity = severity
        self.category = category
        self.title = title
        self.message = message
        self.context = context or {}
        self.suggested_actions = suggested_actions or []
        self.requires_intervention = requires_intervention
        self.timestamp = datetime.now()
        self.resolved = False
        self.resolution_notes = ""
    
    def to_dict(self) -> Dict:
        """Convert alert to dictionary for storage."""
        return {
            "severity": self.severity.value,
            "category": self.category.value,
            "title": self.title,
            "message": self.message,
            "context": self.context,
            "suggested_actions": self.suggested_actions,
            "requires_intervention": self.requires_intervention,
            "timestamp": self.timestamp.isoformat(),
            "resolved": self.resolved,
            "resolution_notes": self.resolution_notes
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Alert':
        """Create alert from dictionary."""
        alert = cls(
            severity=AlertSeverity(data["severity"]),
            category=AlertCategory(data["category"]),
            title=data["title"],
            message=data["message"],
            context=data.get("context", {}),
            suggested_actions=data.get("suggested_actions", []),
            requires_intervention=data.get("requires_intervention", False)
        )
        alert.timestamp = datetime.fromisoformat(data["timestamp"])
        alert.resolved = data.get("resolved", False)
        alert.resolution_notes = data.get("resolution_notes", "")
        return alert


class AlertSystem:
    """Central alert management system."""
    
    def __init__(self, log_fn=None):
        self.log_fn = log_fn or print
        self.alerts: List[Alert] = []
        self.alert_handlers: Dict[AlertCategory, List[Callable]] = {}
        self.lock = threading.Lock()
        self.max_alerts = 1000  # Maximum alerts to keep in memory
        self.alert_file = os.path.join(os.path.expanduser('~'), '.tendertracker_alerts.json')
        self._load_alerts()
    
    def _load_alerts(self):
        """Load alerts from persistent storage."""
        try:
            if os.path.exists(self.alert_file):
                with open(self.alert_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.alerts = [Alert.from_dict(a) for a in data]
                    self._trim_alerts()
        except Exception as e:
            self.log_fn(f"warning", f"Failed to load alerts: {e}")
    
    def _save_alerts(self):
        """Save alerts to persistent storage."""
        try:
            data = [a.to_dict() for a in self.alerts]
            with open(self.alert_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            self.log_fn(f"warning", f"Failed to save alerts: {e}")
    
    def _trim_alerts(self):
        """Keep only the most recent alerts."""
        if len(self.alerts) > self.max_alerts:
            self.alerts = self.alerts[-self.max_alerts:]
    
    def register_handler(self, category: AlertCategory, handler: Callable):
        """Register a handler function for a specific alert category."""
        if category not in self.alert_handlers:
            self.alert_handlers[category] = []
        self.alert_handlers[category].append(handler)
    
    def trigger_intervention(self, alert: Alert, parent_window=None, app=None):
        """Trigger human intervention dialog for critical alerts.
        
        Args:
            alert: The alert requiring intervention
            parent_window: Parent window for the dialog
            app: Application instance for logging
            
        Returns:
            User's action choice, or None if cancelled/not applicable
        """
        if not alert.requires_intervention:
            return None
        
        try:
            from gui.components.intervention_dialog import show_intervention_dialog
            if parent_window and app:
                return show_intervention_dialog(parent_window, app, alert)
        except ImportError:
            # GUI components not available, log and continue
            self.log_fn("warn", f"Intervention dialog not available for alert: {alert.title}")
        except Exception as e:
            self.log_fn("error", f"Failed to show intervention dialog: {e}")
        
        return None
    
    def create_alert(self, severity: AlertSeverity, category: AlertCategory,
                     title: str, message: str, context: Dict = None,
                     suggested_actions: List[str] = None, requires_intervention: bool = False) -> Alert:
        """Create and process a new alert."""
        alert = Alert(
            severity=severity,
            category=category,
            title=title,
            message=message,
            context=context,
            suggested_actions=suggested_actions,
            requires_intervention=requires_intervention
        )
        
        with self.lock:
            self.alerts.append(alert)
            self._trim_alerts()
            self._save_alerts()
        
        # Log the alert
        log_level = severity.value
        self.log_fn(log_level, f"[{category.value.upper()}] {title}: {message}")
        
        # Trigger handlers
        if category in self.alert_handlers:
            for handler in self.alert_handlers[category]:
                try:
                    handler(alert)
                except Exception as e:
                    self.log_fn("error", f"Alert handler failed: {e}")
        
        # Auto-trigger intervention for critical alerts if GUI is available
        if alert.requires_intervention and alert.severity in [AlertSeverity.ERROR, AlertSeverity.CRITICAL]:
            # Store alert for later intervention triggering (will be called by GUI)
            alert._pending_intervention = True
        
        return alert
    
    def get_active_alerts(self, severity: AlertSeverity = None, 
                         category: AlertCategory = None, 
                         unresolved_only: bool = True) -> List[Alert]:
        """Get filtered list of alerts."""
        alerts = self.alerts
        
        if unresolved_only:
            alerts = [a for a in alerts if not a.resolved]
        
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        
        if category:
            alerts = [a for a in alerts if a.category == category]
        
        return alerts
    
    def resolve_alert(self, alert: Alert, resolution_notes: str = ""):
        """Mark an alert as resolved."""
        with self.lock:
            alert.resolved = True
            alert.resolution_notes = resolution_notes
            self._save_alerts()
        
        self.log_fn("info", f"Resolved alert: {alert.title}")
    
    def clear_old_alerts(self, days: int = 30):
        """Clear alerts older than specified days."""
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(days=days)
        
        with self.lock:
            self.alerts = [a for a in self.alerts if a.timestamp > cutoff]
            self._save_alerts()
        
        self.log_fn("info", f"Cleared alerts older than {days} days")


# Global alert system instance
_alert_system = None


def get_alert_system(log_fn=None) -> AlertSystem:
    """Get or create the global alert system instance."""
    global _alert_system
    if _alert_system is None:
        _alert_system = AlertSystem(log_fn)
    return _alert_system


def alert_scraping_issue(title: str, message: str, context: Dict = None, 
                         severity: AlertSeverity = AlertSeverity.WARNING) -> Alert:
    """Convenience function for scraping-related alerts."""
    system = get_alert_system()
    suggested_actions = [
        "Check internet connection",
        "Verify GEM website is accessible",
        "Try manual scraping",
        "Check for CAPTCHA or login requirements"
    ]
    return system.create_alert(
        severity=severity,
        category=AlertCategory.SCRAPING,
        title=title,
        message=message,
        context=context,
        suggested_actions=suggested_actions,
        requires_intervention=severity in [AlertSeverity.ERROR, AlertSeverity.CRITICAL]
    )


def alert_document_issue(title: str, message: str, context: Dict = None,
                        severity: AlertSeverity = AlertSeverity.WARNING) -> Alert:
    """Convenience function for document processing alerts."""
    system = get_alert_system()
    suggested_actions = [
        "Check PDF file integrity",
        "Verify document extraction settings",
        "Review LLM configuration",
        "Manually review document content"
    ]
    return system.create_alert(
        severity=severity,
        category=AlertCategory.DOCUMENT_PROCESSING,
        title=title,
        message=message,
        context=context,
        suggested_actions=suggested_actions,
        requires_intervention=severity in [AlertSeverity.ERROR, AlertSeverity.CRITICAL]
    )


def alert_filing_issue(title: str, message: str, context: Dict = None,
                      severity: AlertSeverity = AlertSeverity.WARNING) -> Alert:
    """Convenience function for filing workflow alerts."""
    system = get_alert_system()
    suggested_actions = [
        "Check folder structure and permissions",
        "Verify COMMON folder exists",
        "Review firm document configuration",
        "Check available disk space"
    ]
    return system.create_alert(
        severity=severity,
        category=AlertCategory.FILING_WORKFLOW,
        title=title,
        message=message,
        context=context,
        suggested_actions=suggested_actions,
        requires_intervention=severity in [AlertSeverity.ERROR, AlertSeverity.CRITICAL]
    )


def alert_network_issue(title: str, message: str, context: Dict = None,
                       severity: AlertSeverity = AlertSeverity.WARNING) -> Alert:
    """Convenience function for network-related alerts."""
    system = get_alert_system()
    suggested_actions = [
        "Check internet connection",
        "Verify proxy settings",
        "Check firewall settings",
        "Retry operation"
    ]
    return system.create_alert(
        severity=severity,
        category=AlertCategory.NETWORK,
        title=title,
        message=message,
        context=context,
        suggested_actions=suggested_actions,
        requires_intervention=severity in [AlertSeverity.CRITICAL]
    )
