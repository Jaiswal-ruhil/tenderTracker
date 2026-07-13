"""
Component registry for dynamic component loading and management.
"""

from typing import Dict, Type, Optional, Any
import importlib

from components.base_component import BaseComponent


class ComponentRegistry:
    """
    Registry for managing GUI components.
    Allows dynamic component loading and instantiation.
    """
    
    def __init__(self):
        self._components: Dict[str, Type[BaseComponent]] = {}
        self._instances: Dict[str, BaseComponent] = {}
    
    def register(self, name: str, component_class: Type[BaseComponent]):
        """Register a component class."""
        self._components[name] = component_class
    
    def get(self, name: str) -> Optional[Type[BaseComponent]]:
        """Get a registered component class."""
        return self._components.get(name)
    
    def create(self, name: str, parent, app, **kwargs) -> Optional[BaseComponent]:
        """Create an instance of a registered component."""
        component_class = self.get(name)
        if component_class:
            instance = component_class(parent, app, **kwargs)
            self._instances[name] = instance
            return instance
        return None
    
    def get_instance(self, name: str) -> Optional[BaseComponent]:
        """Get an existing component instance."""
        return self._instances.get(name)
    
    def unregister(self, name: str):
        """Unregister a component."""
        if name in self._components:
            del self._components[name]
        if name in self._instances:
            del self._instances[name]
    
    def list_components(self) -> list:
        """List all registered component names."""
        return list(self._components.keys())


# Global registry instance
_registry = ComponentRegistry()


def register_component(name: str, component_class: Type[BaseComponent]):
    """Register a component in the global registry."""
    _registry.register(name, component_class)


def get_component(name: str) -> Optional[Type[BaseComponent]]:
    """Get a component class from the global registry."""
    return _registry.get(name)


def create_component(name: str, parent, app, **kwargs) -> Optional[BaseComponent]:
    """Create a component instance from the global registry."""
    return _registry.create(name, parent, app, **kwargs)


def get_component_instance(name: str) -> Optional[BaseComponent]:
    """Get a component instance from the global registry."""
    return _registry.get_instance(name)


# Auto-register core components
def _auto_register_components():
    """Auto-register core components."""
    try:
        from components.filter_bar import FilterBar
        register_component('filter_bar', FilterBar)
    except ImportError:
        pass
    
    try:
        from components.ai_filter_bar import AIFilterBar
        register_component('ai_filter_bar', AIFilterBar)
    except ImportError:
        pass
    
    try:
        from components.action_bar import ActionBar
        register_component('action_bar', ActionBar)
    except ImportError:
        pass
    
    try:
        from components.summary_bar import SummaryBar
        register_component('summary_bar', SummaryBar)
    except ImportError:
        pass
    
    try:
        from components.side_panel import TenderDetailPanel
        register_component('detail_panel', TenderDetailPanel)
    except ImportError:
        pass
    
    try:
        from components.table_view import TendersTableView
        register_component('table_view', TendersTableView)
    except ImportError:
        pass
    
    try:
        from components.date_picker_button import DatePickerButton
        register_component('date_picker_button', DatePickerButton)
    except ImportError:
        pass
    
    try:
        from components.date_picker_button import DateRangePicker
        register_component('date_range_picker', DateRangePicker)
    except ImportError:
        pass


# Auto-register on import
_auto_register_components()
