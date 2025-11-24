"""
State Management for Plot Sessions

This module provides utilities for managing plot sessions, including:
- Saving and loading complete session states
- Tracking changes across multiple plots
- Exporting change logs for user experience analysis
"""

import json
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from pathlib import Path
import copy

from .SCDash_base_plot import BasePlot


class PlotSession:
    """
    Manages a collection of plots with session-level state management.
    
    This class tracks multiple plots together, allowing for:
    - Saving/loading entire sessions
    - Tracking changes across all plots
    - Exporting session logs
    """
    
    def __init__(self, session_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None):
        """
        Initialize a plot session.
        
        Args:
            session_id: Unique identifier for this session
            metadata: Additional metadata (e.g., user_id, dataset_id, timestamp)
        """
        self.session_id = session_id or f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.metadata = metadata or {}
        self.metadata.setdefault("created_at", datetime.now().isoformat())
        self.metadata.setdefault("last_updated", datetime.now().isoformat())
        
        self.plots: Dict[str, BasePlot] = {}
        self.session_changes: List[Dict[str, Any]] = []
    
    def add_plot(self, plot_id: str, plot: BasePlot) -> None:
        """
        Add a plot to the session.
        
        Args:
            plot_id: Unique identifier for the plot
            plot: BasePlot instance
        """
        if plot_id in self.plots:
            raise ValueError(f"Plot with id '{plot_id}' already exists in session")
        
        self.plots[plot_id] = plot
        self._record_session_change("add_plot", {"plot_id": plot_id, "plot_type": type(plot).__name__})
    
    def get_plot(self, plot_id: str) -> Optional[BasePlot]:
        """
        Get a plot by ID.
        
        Args:
            plot_id: Plot identifier
            
        Returns:
            BasePlot instance or None if not found
        """
        return self.plots.get(plot_id)
    
    def remove_plot(self, plot_id: str) -> bool:
        """
        Remove a plot from the session.
        
        Args:
            plot_id: Plot identifier
            
        Returns:
            True if plot was removed, False if not found
        """
        if plot_id not in self.plots:
            return False
        
        del self.plots[plot_id]
        self._record_session_change("remove_plot", {"plot_id": plot_id})
        return True
    
    def get_session_state(self, include_data: bool = False) -> Dict[str, Any]:
        """
        Get the complete session state.
        
        Args:
            include_data: Whether to include data arrays in plot states
            
        Returns:
            Dictionary containing session state
        """
        state = {
            "session_id": self.session_id,
            "metadata": {
                **self.metadata,
                "last_updated": datetime.now().isoformat()
            },
            "plots": {
                plot_id: {
                    **plot.get_state(include_data=include_data),
                    "plot_type": type(plot).__name__  # Include plot type for reconstruction
                }
                for plot_id, plot in self.plots.items()
            }
        }
        return state
    
    def get_session_state_json(self, include_data: bool = False, indent: int = 2) -> str:
        """
        Get the complete session state as JSON.
        
        Args:
            include_data: Whether to include data arrays
            indent: JSON indentation level
            
        Returns:
            JSON string containing session state
        """
        state = self.get_session_state(include_data=include_data)
        return json.dumps(state, indent=indent, default=str)
    
    def save_session(self, filepath: Union[str, Path], include_data: bool = False) -> None:
        """
        Save session state to a JSON file.
        
        Args:
            filepath: Path to save the session file
            include_data: Whether to include data arrays
        """
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        state_json = self.get_session_state_json(include_data=include_data)
        filepath.write_text(state_json)
        
        self._record_session_change("save_session", {
            "filepath": str(filepath),
            "include_data": include_data
        })
    
    def load_session(self, filepath: Union[str, Path], restore_data: bool = False) -> None:
        """
        Load session state from a JSON file.
        
        Args:
            filepath: Path to the session file
            restore_data: Whether to restore data arrays
        """
        filepath = Path(filepath)
        state_json = filepath.read_text()
        state = json.loads(state_json)
        
        self.session_id = state.get("session_id", self.session_id)
        self.metadata = state.get("metadata", {})
        
        # Clear existing plots
        self.plots.clear()
        
        # Note: This is a simplified load - in practice, you'd need to
        # reconstruct the appropriate plot types from the state
        # For now, we'll just store the state and let the caller handle reconstruction
        self._loaded_plot_states = state.get("plots", {})
        
        self._record_session_change("load_session", {
            "filepath": str(filepath),
            "restore_data": restore_data,
            "num_plots": len(self._loaded_plot_states)
        })
    
    def get_change_log(self) -> List[Dict[str, Any]]:
        """
        Get the complete change log for the session.
        
        Returns:
            List of change records from all plots plus session-level changes
        """
        log = []
        
        # Add session-level changes
        log.extend(copy.deepcopy(self.session_changes))
        
        # Add plot-level changes
        for plot_id, plot in self.plots.items():
            plot_changes = plot.get_change_history()
            for change in plot_changes:
                change["plot_id"] = plot_id
                log.append(change)
        
        # Sort by timestamp
        log.sort(key=lambda x: x.get("timestamp", ""))
        
        return log
    
    def export_change_log(self, filepath: Union[str, Path], format: str = "json") -> None:
        """
        Export the change log to a file.
        
        Args:
            filepath: Path to save the change log
            format: Export format ("json" or "txt")
        """
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        change_log = self.get_change_log()
        
        if format == "json":
            log_json = json.dumps(change_log, indent=2, default=str)
            filepath.write_text(log_json)
        elif format == "txt":
            lines = []
            lines.append(f"Change Log for Session: {self.session_id}")
            lines.append(f"Created: {self.metadata.get('created_at', 'Unknown')}")
            lines.append(f"Last Updated: {self.metadata.get('last_updated', 'Unknown')}")
            lines.append("=" * 80)
            lines.append("")
            
            for change in change_log:
                timestamp = change.get("timestamp", "Unknown")
                action = change.get("action", "Unknown")
                plot_id = change.get("plot_id", "Session")
                details = change.get("details", {})
                
                lines.append(f"[{timestamp}] {plot_id}: {action}")
                if details:
                    for key, value in details.items():
                        lines.append(f"  {key}: {value}")
                lines.append("")
            
            filepath.write_text("\n".join(lines))
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def _record_session_change(self, action: str, details: Dict[str, Any]) -> None:
        """
        Record a session-level change.
        
        Args:
            action: Action that caused the change
            details: Change details
        """
        change_record = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "details": details,
            "session_id": self.session_id
        }
        self.session_changes.append(change_record)
        self.metadata["last_updated"] = datetime.now().isoformat()
    
    def clear_change_logs(self) -> None:
        """Clear all change logs (session and plot level)."""
        self.session_changes.clear()
        for plot in self.plots.values():
            plot.clear_change_history()
    
    def reset_session(self) -> None:
        """Reset all plots to their initial states."""
        for plot in self.plots.values():
            plot.reset_state()
        self._record_session_change("reset_session", {})


def create_session_from_state(state: Union[Dict[str, Any], str]) -> PlotSession:
    """
    Create a PlotSession from a state dictionary or JSON string.
    
    Args:
        state: Session state dictionary or JSON string
        
    Returns:
        PlotSession instance
    """
    if isinstance(state, str):
        state = json.loads(state)
    
    session_id = state.get("session_id", None)
    metadata = state.get("metadata", {})
    
    session = PlotSession(session_id=session_id, metadata=metadata)
    
    # Note: Plot reconstruction would need to be handled by the caller
    # based on plot type information in the state
    # This is a placeholder for the loaded states
    session._loaded_plot_states = state.get("plots", {})
    
    return session

