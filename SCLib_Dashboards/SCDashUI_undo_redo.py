"""
Undo/Redo System for Dashboard State Management

This module provides undo/redo functionality for plot and session states,
allowing users to revert changes and restore previous states.
"""

from typing import List, Optional, Dict, Any, Callable
from datetime import datetime
import copy
import json

from .SCDash_base_plot import BasePlot
from .SCDash_state_manager import PlotSession


class StateHistory:
    """
    Manages undo/redo history for plot or session states.
    
    This class maintains a stack of state snapshots, allowing users to
    navigate backwards (undo) and forwards (redo) through changes.
    """
    
    def __init__(self, max_history: int = 50):
        """
        Initialize state history.
        
        Args:
            max_history: Maximum number of states to keep in history
        """
        self.max_history = max_history
        self.history: List[Dict[str, Any]] = []
        self.current_index: int = -1
        self._save_callback: Optional[Callable[[], Dict[str, Any]]] = None
        self._restore_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    
    def set_callbacks(
        self,
        save_callback: Callable[[], Dict[str, Any]],
        restore_callback: Callable[[Dict[str, Any]], None]
    ) -> None:
        """
        Set callbacks for saving and restoring state.
        
        Args:
            save_callback: Function that returns current state as dict
            restore_callback: Function that restores state from dict
        """
        self._save_callback = save_callback
        self._restore_callback = restore_callback
    
    def save_state(self, description: Optional[str] = None) -> bool:
        """
        Save current state to history.
        
        Args:
            description: Optional description of this state
            
        Returns:
            True if state was saved, False if callbacks not set
        """
        if self._save_callback is None:
            return False
        
        state = self._save_callback()
        state["timestamp"] = datetime.now().isoformat()
        state["description"] = description or "State change"
        
        # Remove any states after current index (when undoing and then making new changes)
        if self.current_index < len(self.history) - 1:
            self.history = self.history[:self.current_index + 1]
        
        # Add new state
        # Use shallow copy with recursive dict copy for better performance than deepcopy
        # Since state only contains simple types (str, float, bool, None, dict, list), 
        # we can safely use a shallow copy approach
        def shallow_copy_dict(d):
            """Create a shallow copy of a dict, recursively copying nested dicts."""
            if not isinstance(d, dict):
                return d
            return {k: shallow_copy_dict(v) if isinstance(v, dict) else v for k, v in d.items()}
        
        state_copy = shallow_copy_dict(state)
        self.history.append(state_copy)
        
        # Limit history size
        if len(self.history) > self.max_history:
            self.history.pop(0)
        else:
            self.current_index += 1
        
        return True
    
    def can_undo(self) -> bool:
        """Check if undo is possible."""
        return self.current_index > 0
    
    def can_redo(self) -> bool:
        """Check if redo is possible."""
        return self.current_index < len(self.history) - 1
    
    def undo(self) -> bool:
        """
        Undo to previous state.
        
        Returns:
            True if undo was successful, False otherwise
        """
        if not self.can_undo():
            return False
        
        if self._restore_callback is None:
            return False
        
        self.current_index -= 1
        # No need to deepcopy - state is already a copy in history
        previous_state = self.history[self.current_index]
        
        # Remove metadata before restoring
        state_to_restore = {k: v for k, v in previous_state.items() 
                           if k not in ["timestamp", "description"]}
        
        self._restore_callback(state_to_restore)
        return True
    
    def redo(self) -> bool:
        """
        Redo to next state.
        
        Returns:
            True if redo was successful, False otherwise
        """
        if not self.can_redo():
            return False
        
        if self._restore_callback is None:
            return False
        
        self.current_index += 1
        # No need to deepcopy - state is already a copy in history
        next_state = self.history[self.current_index]
        
        # Remove metadata before restoring
        state_to_restore = {k: v for k, v in next_state.items() 
                           if k not in ["timestamp", "description"]}
        
        self._restore_callback(state_to_restore)
        return True
    
    def get_current_state_info(self) -> Optional[Dict[str, Any]]:
        """
        Get information about current state.
        
        Returns:
            Dictionary with timestamp and description, or None if no history
        """
        if self.current_index < 0 or self.current_index >= len(self.history):
            return None
        
        state = self.history[self.current_index]
        return {
            "timestamp": state.get("timestamp"),
            "description": state.get("description"),
            "index": self.current_index,
            "total": len(self.history)
        }
    
    def clear(self) -> None:
        """Clear all history."""
        self.history.clear()
        self.current_index = -1
    
    def get_history_summary(self) -> List[Dict[str, Any]]:
        """
        Get a summary of all states in history.
        
        Returns:
            List of state info dictionaries
        """
        return [
            {
                "index": i,
                "timestamp": state.get("timestamp"),
                "description": state.get("description"),
                "is_current": i == self.current_index
            }
            for i, state in enumerate(self.history)
        ]


class PlotStateHistory(StateHistory):
    """
    State history manager for a single plot.
    """
    
    def __init__(self, plot: BasePlot, max_history: int = 50):
        """
        Initialize plot state history.
        
        Args:
            plot: BasePlot instance to track
            max_history: Maximum number of states to keep
        """
        super().__init__(max_history)
        self.plot = plot
        
        # Set up callbacks
        self.set_callbacks(
            save_callback=self._save_plot_state,
            restore_callback=self._restore_plot_state
        )
        
        # Save initial state
        self.save_state("Initial state")
    
    def _save_plot_state(self) -> Dict[str, Any]:
        """Save current plot state."""
        return self.plot.get_state(include_data=False)
    
    def _restore_plot_state(self, state: Dict[str, Any]) -> None:
        """Restore plot state."""
        self.plot.load_state(state, restore_data=False)


class SessionStateHistory(StateHistory):
    """
    State history manager for a plot session.
    """
    
    def __init__(self, session: PlotSession, max_history: int = 50):
        """
        Initialize session state history.
        
        Args:
            session: PlotSession instance to track
            max_history: Maximum number of states to keep
        """
        super().__init__(max_history)
        self.session = session
        
        # Set up callbacks
        self.set_callbacks(
            save_callback=self._save_session_state,
            restore_callback=self._restore_session_state
        )
        
        # Save initial state
        self.save_state("Initial session state")
    
    def _save_session_state(self) -> Dict[str, Any]:
        """Save current session state."""
        return self.session.get_session_state(include_data=False)
    
    def _restore_session_state(self, state: Dict[str, Any]) -> None:
        """Restore session state."""
        # Note: This is a simplified restore - in practice, you'd need to
        # reconstruct plots from their state based on plot type
        # For now, we'll update existing plots if they match
        
        session_id = state.get("session_id")
        if session_id:
            self.session.session_id = session_id
        
        metadata = state.get("metadata", {})
        if metadata:
            self.session.metadata.update(metadata)
        
        plots_state = state.get("plots", {})
        for plot_id, plot_state in plots_state.items():
            if plot_id in self.session.plots:
                # Restore existing plot
                self.session.plots[plot_id].load_state(plot_state, restore_data=False)
            # Note: New plots would need to be created based on plot_type in state


def create_undo_redo_callbacks(
    history: StateHistory,
    undo_button: Any,
    redo_button: Any,
    status_div: Optional[Any] = None
) -> Dict[str, Callable]:
    """
    Create callback functions for undo/redo buttons.
    
    Args:
        history: StateHistory instance
        undo_button: Button widget for undo
        redo_button: Button widget for redo
        status_div: Optional status display widget
        
    Returns:
        Dictionary with 'undo' and 'redo' callback functions
    """
    def update_button_states():
        """Update button enabled states based on history."""
        undo_button.disabled = not history.can_undo()
        redo_button.disabled = not history.can_redo()
        
        if status_div:
            info = history.get_current_state_info()
            if info:
                status_text = (
                    f"State {info['index'] + 1} of {info['total']}: "
                    f"{info['description']}"
                )
                status_div.text = status_text
    
    def on_undo():
        """Undo callback."""
        if history.undo():
            update_button_states()
            if status_div:
                status_div.text = "Undo successful"
        else:
            if status_div:
                status_div.text = "Cannot undo - already at initial state"
    
    def on_redo():
        """Redo callback."""
        if history.redo():
            update_button_states()
            if status_div:
                status_div.text = "Redo successful"
        else:
            if status_div:
                status_div.text = "Cannot redo - already at latest state"
    
    # Initial button state update
    update_button_states()
    
    return {
        "undo": on_undo,
        "redo": on_redo,
        "update": update_button_states
    }

