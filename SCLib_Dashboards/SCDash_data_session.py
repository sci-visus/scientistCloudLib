"""
Data Session Management

This module provides session management that integrates both plots and data processors,
allowing for complete dashboard state persistence.
"""

import json
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from pathlib import Path
import copy

from .SCDash_state_manager import PlotSession
from .SCData_base_processor import BaseDataProcessor


class DataPlotSession(PlotSession):
    """
    Extended session that manages both plots and data processors together.
    
    This class extends PlotSession to include data processor state management,
    allowing for complete dashboard state persistence including data source configuration.
    """
    
    def __init__(self, session_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None):
        """
        Initialize a data-plot session.
        
        Args:
            session_id: Unique identifier for this session
            metadata: Additional metadata
        """
        super().__init__(session_id=session_id, metadata=metadata)
        self.data_processors: Dict[str, BaseDataProcessor] = {}
    
    def add_data_processor(self, processor_id: str, processor: BaseDataProcessor) -> None:
        """
        Add a data processor to the session.
        
        Args:
            processor_id: Unique identifier for the processor
            processor: BaseDataProcessor instance
        """
        if processor_id in self.data_processors:
            raise ValueError(f"Processor with id '{processor_id}' already exists in session")
        
        self.data_processors[processor_id] = processor
        self._record_session_change("add_data_processor", {
            "processor_id": processor_id,
            "processor_type": type(processor).__name__,
            "filename": processor.filename
        })
    
    def get_data_processor(self, processor_id: str) -> Optional[BaseDataProcessor]:
        """
        Get a data processor by ID.
        
        Args:
            processor_id: Processor identifier
            
        Returns:
            BaseDataProcessor instance or None if not found
        """
        return self.data_processors.get(processor_id)
    
    def remove_data_processor(self, processor_id: str) -> bool:
        """
        Remove a data processor from the session.
        
        Args:
            processor_id: Processor identifier
            
        Returns:
            True if processor was removed, False if not found
        """
        if processor_id not in self.data_processors:
            return False
        
        processor = self.data_processors[processor_id]
        processor.close()
        del self.data_processors[processor_id]
        self._record_session_change("remove_data_processor", {"processor_id": processor_id})
        return True
    
    def get_session_state(self, include_data: bool = False) -> Dict[str, Any]:
        """
        Get the complete session state including data processors.
        
        Args:
            include_data: Whether to include data arrays in plot/processor states
            
        Returns:
            Dictionary containing session state
        """
        state = super().get_session_state(include_data=include_data)
        
        # Add data processor states
        state["data_processors"] = {
            processor_id: processor.get_state(include_data=include_data)
            for processor_id, processor in self.data_processors.items()
        }
        
        return state
    
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
            "include_data": include_data,
            "num_plots": len(self.plots),
            "num_processors": len(self.data_processors)
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
        
        # Clear existing plots and processors
        self.plots.clear()
        self.data_processors.clear()
        
        # Store loaded states (reconstruction would need format-specific logic)
        self._loaded_plot_states = state.get("plots", {})
        self._loaded_processor_states = state.get("data_processors", {})
        
        self._record_session_change("load_session", {
            "filepath": str(filepath),
            "restore_data": restore_data,
            "num_plots": len(self._loaded_plot_states),
            "num_processors": len(self._loaded_processor_states)
        })
    
    def get_change_log(self) -> List[Dict[str, Any]]:
        """
        Get the complete change log for the session.
        
        Returns:
            List of change records from all plots and processors plus session-level changes
        """
        log = []
        
        # Add session-level changes
        log.extend(copy.deepcopy(self.session_changes))
        
        # Add plot-level changes
        for plot_id, plot in self.plots.items():
            plot_changes = plot.get_change_history()
            for change in plot_changes:
                change["plot_id"] = plot_id
                change["component_type"] = "plot"
                log.append(change)
        
        # Add processor-level changes
        for processor_id, processor in self.data_processors.items():
            processor_changes = processor.get_change_history()
            for change in processor_changes:
                change["processor_id"] = processor_id
                change["component_type"] = "processor"
                log.append(change)
        
        # Sort by timestamp
        log.sort(key=lambda x: x.get("timestamp", ""))
        
        return log
    
    def clear_change_logs(self) -> None:
        """Clear all change logs (session, plot, and processor level)."""
        self.session_changes.clear()
        for plot in self.plots.values():
            plot.clear_change_history()
        for processor in self.data_processors.values():
            processor.clear_change_history()
    
    def reset_session(self) -> None:
        """Reset all plots and processors to their initial states."""
        for plot in self.plots.values():
            plot.reset_state()
        for processor in self.data_processors.values():
            processor.reset_state()
        self._record_session_change("reset_session", {})
    
    def close_all(self) -> None:
        """Close all data processors and clean up resources."""
        for processor in self.data_processors.values():
            processor.close()
        self.data_processors.clear()


def create_data_plot_session_from_state(state: Union[Dict[str, Any], str]) -> DataPlotSession:
    """
    Create a DataPlotSession from a state dictionary or JSON string.
    
    Args:
        state: Session state dictionary or JSON string
        
    Returns:
        DataPlotSession instance
    """
    if isinstance(state, str):
        state = json.loads(state)
    
    session_id = state.get("session_id", None)
    metadata = state.get("metadata", {})
    
    session = DataPlotSession(session_id=session_id, metadata=metadata)
    
    # Store loaded states (reconstruction would need format-specific logic)
    session._loaded_plot_states = state.get("plots", {})
    session._loaded_processor_states = state.get("data_processors", {})
    
    return session

