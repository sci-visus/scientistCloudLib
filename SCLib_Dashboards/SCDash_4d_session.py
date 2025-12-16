"""
4D Dashboard Session Management

This module provides a specialized session class for 4D dashboards that extends
PlotSession with 4D-specific metadata and convenience methods.
"""

from typing import Dict, Optional, Any
from datetime import datetime

from .SCDash_state_manager import PlotSession


class FourDDashboardSession(PlotSession):
    """
    Specialized session for 4D dashboards.
    
    This class extends PlotSession to include 4D-specific metadata such as:
    - Volume dataset selections (main and B variants)
    - Coordinate dataset selections (map and probe)
    - Plot mode configurations (ratio vs single dataset)
    - User information
    
    This provides a structured way to save and restore 4D dashboard states
    across different dashboard implementations.
    """
    
    def __init__(
        self,
        session_id: Optional[str] = None,
        volume_picked: Optional[str] = None,
        plot1_single_dataset_picked: Optional[str] = None,
        presample_picked: Optional[str] = None,
        postsample_picked: Optional[str] = None,
        x_coords_picked: Optional[str] = None,
        y_coords_picked: Optional[str] = None,
        probe_x_coords_picked: Optional[str] = None,
        probe_y_coords_picked: Optional[str] = None,
        volume_picked_b: Optional[str] = None,
        plot1b_single_dataset_picked: Optional[str] = None,
        presample_picked_b: Optional[str] = None,
        postsample_picked_b: Optional[str] = None,
        probe_x_coords_picked_b: Optional[str] = None,
        probe_y_coords_picked_b: Optional[str] = None,
        user_email: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize a 4D dashboard session.
        
        Args:
            session_id: Unique identifier for this session (auto-generated if None)
            volume_picked: Main volume dataset path
            plot1_single_dataset_picked: Plot1 single dataset path (if not using ratio mode)
            presample_picked: Presample dataset path for ratio mode
            postsample_picked: Postsample dataset path for ratio mode
            x_coords_picked: Map X coordinates dataset path
            y_coords_picked: Map Y coordinates dataset path
            probe_x_coords_picked: Probe X coordinates dataset path
            probe_y_coords_picked: Probe Y coordinates dataset path
            volume_picked_b: Volume B dataset path (for Plot2B)
            plot1b_single_dataset_picked: Plot1B single dataset path
            presample_picked_b: Presample B dataset path
            postsample_picked_b: Postsample B dataset path
            probe_x_coords_picked_b: Probe X coordinates B dataset path
            probe_y_coords_picked_b: Probe Y coordinates B dataset path
            user_email: User email for session tracking
            **kwargs: Additional metadata to include
        """
        # Build metadata dictionary with 4D-specific fields
        metadata = {
            "dashboard_type": "4d",
            "dataset_path": volume_picked or "unknown",
            "volume_picked": volume_picked,
            "plot1_single_dataset_picked": plot1_single_dataset_picked,
            "presample_picked": presample_picked,
            "postsample_picked": postsample_picked,
            "x_coords_picked": x_coords_picked,
            "y_coords_picked": y_coords_picked,
            "probe_x_coords_picked": probe_x_coords_picked,
            "probe_y_coords_picked": probe_y_coords_picked,
            "volume_picked_b": volume_picked_b,
            "plot1b_single_dataset_picked": plot1b_single_dataset_picked,
            "presample_picked_b": presample_picked_b,
            "postsample_picked_b": postsample_picked_b,
            "probe_x_coords_picked_b": probe_x_coords_picked_b,
            "probe_y_coords_picked_b": probe_y_coords_picked_b,
            "plot1_mode": "single" if plot1_single_dataset_picked else "ratio",
            "plot1b_mode": "single" if plot1b_single_dataset_picked else "ratio",
            "plot1b_enabled": bool(plot1b_single_dataset_picked or presample_picked_b),
            "plot2b_enabled": bool(volume_picked_b),
            "user_email": user_email,
            **kwargs
        }
        
        # Generate session_id if not provided
        if session_id is None:
            session_id = f"4d_dashboard_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        super().__init__(session_id=session_id, metadata=metadata)
    
    @property
    def volume_picked(self) -> Optional[str]:
        """Get the main volume dataset path."""
        return self.metadata.get("volume_picked")
    
    @property
    def plot1_mode(self) -> str:
        """Get Plot1 mode ('single' or 'ratio')."""
        return self.metadata.get("plot1_mode", "ratio")
    
    @property
    def plot1b_enabled(self) -> bool:
        """Check if Plot1B is enabled."""
        return self.metadata.get("plot1b_enabled", False)
    
    @property
    def plot2b_enabled(self) -> bool:
        """Check if Plot2B is enabled."""
        return self.metadata.get("plot2b_enabled", False)
    
    def update_dataset_selections(
        self,
        volume_picked: Optional[str] = None,
        plot1_single_dataset_picked: Optional[str] = None,
        presample_picked: Optional[str] = None,
        postsample_picked: Optional[str] = None,
        x_coords_picked: Optional[str] = None,
        y_coords_picked: Optional[str] = None,
        probe_x_coords_picked: Optional[str] = None,
        probe_y_coords_picked: Optional[str] = None,
        volume_picked_b: Optional[str] = None,
        plot1b_single_dataset_picked: Optional[str] = None,
        presample_picked_b: Optional[str] = None,
        postsample_picked_b: Optional[str] = None,
        probe_x_coords_picked_b: Optional[str] = None,
        probe_y_coords_picked_b: Optional[str] = None,
    ) -> None:
        """
        Update dataset selections in the session metadata.
        
        Args:
            volume_picked: Main volume dataset path (None to keep current)
            plot1_single_dataset_picked: Plot1 single dataset path
            presample_picked: Presample dataset path
            postsample_picked: Postsample dataset path
            x_coords_picked: Map X coordinates dataset path
            y_coords_picked: Map Y coordinates dataset path
            probe_x_coords_picked: Probe X coordinates dataset path
            probe_y_coords_picked: Probe Y coordinates dataset path
            volume_picked_b: Volume B dataset path
            plot1b_single_dataset_picked: Plot1B single dataset path
            presample_picked_b: Presample B dataset path
            postsample_picked_b: Postsample B dataset path
            probe_x_coords_picked_b: Probe X coordinates B dataset path
            probe_y_coords_picked_b: Probe Y coordinates B dataset path
        """
        if volume_picked is not None:
            self.metadata["volume_picked"] = volume_picked
            self.metadata["dataset_path"] = volume_picked
        
        if plot1_single_dataset_picked is not None:
            self.metadata["plot1_single_dataset_picked"] = plot1_single_dataset_picked
            self.metadata["plot1_mode"] = "single" if plot1_single_dataset_picked else "ratio"
        
        if presample_picked is not None:
            self.metadata["presample_picked"] = presample_picked
        
        if postsample_picked is not None:
            self.metadata["postsample_picked"] = postsample_picked
        
        if x_coords_picked is not None:
            self.metadata["x_coords_picked"] = x_coords_picked
        
        if y_coords_picked is not None:
            self.metadata["y_coords_picked"] = y_coords_picked
        
        if probe_x_coords_picked is not None:
            self.metadata["probe_x_coords_picked"] = probe_x_coords_picked
        
        if probe_y_coords_picked is not None:
            self.metadata["probe_y_coords_picked"] = probe_y_coords_picked
        
        if volume_picked_b is not None:
            self.metadata["volume_picked_b"] = volume_picked_b
            self.metadata["plot2b_enabled"] = bool(volume_picked_b)
        
        if plot1b_single_dataset_picked is not None:
            self.metadata["plot1b_single_dataset_picked"] = plot1b_single_dataset_picked
            self.metadata["plot1b_mode"] = "single" if plot1b_single_dataset_picked else "ratio"
        
        if presample_picked_b is not None:
            self.metadata["presample_picked_b"] = presample_picked_b
            self.metadata["plot1b_enabled"] = bool(plot1b_single_dataset_picked or presample_picked_b)
        
        if postsample_picked_b is not None:
            self.metadata["postsample_picked_b"] = postsample_picked_b
        
        if probe_x_coords_picked_b is not None:
            self.metadata["probe_x_coords_picked_b"] = probe_x_coords_picked_b
        
        if probe_y_coords_picked_b is not None:
            self.metadata["probe_y_coords_picked_b"] = probe_y_coords_picked_b
        
        self.metadata["last_updated"] = datetime.now().isoformat()
        self._record_session_change("update_dataset_selections", {
            "volume_picked": volume_picked,
            "plot1_mode": self.metadata.get("plot1_mode"),
            "plot1b_enabled": self.metadata.get("plot1b_enabled"),
            "plot2b_enabled": self.metadata.get("plot2b_enabled"),
        })


def create_4d_session_from_process_4dnexus(process_4dnexus, user_email: Optional[str] = None) -> FourDDashboardSession:
    """
    Create a FourDDashboardSession from a Process4dNexus instance.
    
    This is a convenience function that extracts all dataset selections from
    a Process4dNexus object and creates a properly configured session.
    
    Args:
        process_4dnexus: Process4dNexus instance with dataset selections
        user_email: Optional user email for session tracking
        
    Returns:
        FourDDashboardSession instance with all dataset selections configured
    """
    return FourDDashboardSession(
        volume_picked=getattr(process_4dnexus, 'volume_picked', None),
        plot1_single_dataset_picked=getattr(process_4dnexus, 'plot1_single_dataset_picked', None),
        presample_picked=getattr(process_4dnexus, 'presample_picked', None),
        postsample_picked=getattr(process_4dnexus, 'postsample_picked', None),
        x_coords_picked=getattr(process_4dnexus, 'x_coords_picked', None),
        y_coords_picked=getattr(process_4dnexus, 'y_coords_picked', None),
        probe_x_coords_picked=getattr(process_4dnexus, 'probe_x_coords_picked', None),
        probe_y_coords_picked=getattr(process_4dnexus, 'probe_y_coords_picked', None),
        volume_picked_b=getattr(process_4dnexus, 'volume_picked_b', None),
        plot1b_single_dataset_picked=getattr(process_4dnexus, 'plot1b_single_dataset_picked', None),
        presample_picked_b=getattr(process_4dnexus, 'presample_picked_b', None),
        postsample_picked_b=getattr(process_4dnexus, 'postsample_picked_b', None),
        probe_x_coords_picked_b=getattr(process_4dnexus, 'probe_x_coords_picked_b', None),
        probe_y_coords_picked_b=getattr(process_4dnexus, 'probe_y_coords_picked_b', None),
        user_email=user_email,
    )


