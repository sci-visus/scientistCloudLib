"""
Base Plot Class for Dashboard Visualization Library

This module provides a generic plot class that can be specialized for
different plot types (MAP_2DPlot, PROBE_2DPlot, PROBE_1DPlot).

The class supports:
- Range management (min, max, dynamic/user specified)
- Color palette and colorbar
- Color scale (log/linear)
- Plot shape (square, custom, aspect ratio)
- Crosshairs (enabled/disabled with x, y values)
- Data mode (1D, 2D, 3D)
- Axes configuration (ticks, labels)
- Selection region (rectangle with min/max coordinates)
- State management (save/load JSON)
- Change tracking for logging
"""

import numpy as np
import json
from typing import Optional, Dict, List, Tuple, Any, Union
from enum import Enum
from datetime import datetime
import copy


class DataMode(Enum):
    """Data dimensionality modes"""
    MODE_1D = "1D"
    MODE_2D = "2D"
    MODE_3D = "3D"


class ColorScale(Enum):
    """Color scale types"""
    LINEAR = "linear"
    LOG = "log"


class PlotShapeMode(Enum):
    """Plot shape configuration modes"""
    SQUARE = "square"
    CUSTOM = "custom"
    ASPECT_RATIO = "aspect_ratio"


class RangeMode(Enum):
    """Range specification modes"""
    DYNAMIC = "dynamic"  # Automatically calculated from data
    USER_SPECIFIED = "user_specified"  # User-provided min/max values


class BasePlot:
    """
    Base class for dashboard plots with comprehensive state management.
    
    This class encapsulates all plot configuration and data, providing
    methods for state serialization, change tracking, and reset operations.
    """
    
    def __init__(
        self,
        title: str = "Plot",
        data_mode: DataMode = DataMode.MODE_2D,
        data: Optional[np.ndarray] = None,
        x_coords: Optional[np.ndarray] = None,
        y_coords: Optional[np.ndarray] = None,
        palette: str = "Viridis256",
        color_scale: ColorScale = ColorScale.LINEAR,
        range_mode: RangeMode = RangeMode.DYNAMIC,
        range_min: Optional[float] = None,
        range_max: Optional[float] = None,
        plot_shape_mode: PlotShapeMode = PlotShapeMode.SQUARE,
        plot_width: int = 400,
        plot_height: int = 400,
        plot_min_size: int = 200,
        plot_max_size: int = 400,
        plot_scale: float = 100.0,
        crosshairs_enabled: bool = False,
        crosshair_x: Optional[float] = None,
        crosshair_y: Optional[float] = None,
        x_axis_label: Optional[str] = None,
        y_axis_label: Optional[str] = None,
        x_ticks: Optional[List[float]] = None,
        y_ticks: Optional[List[float]] = None,
        x_tick_labels: Optional[List[str]] = None,
        y_tick_labels: Optional[List[str]] = None,
        select_region_enabled: bool = False,
        select_region_min_x: Optional[float] = None,
        select_region_min_y: Optional[float] = None,
        select_region_max_x: Optional[float] = None,
        select_region_max_y: Optional[float] = None,
        needs_flip: bool = False,
        track_changes: bool = True,
    ):
        """
        Initialize a BasePlot instance.
        
        Args:
            title: Plot title
            data_mode: Data dimensionality (1D, 2D, or 3D)
            data: NumPy array containing plot data
            x_coords: X-axis coordinate array
            y_coords: Y-axis coordinate array
            palette: Color palette name (e.g., "Viridis256")
            color_scale: Color scale type (LINEAR or LOG)
            range_mode: Range calculation mode (DYNAMIC or USER_SPECIFIED)
            range_min: Minimum value for color range (if user specified)
            range_max: Maximum value for color range (if user specified)
            plot_shape_mode: Plot shape mode (SQUARE, CUSTOM, or ASPECT_RATIO)
            plot_width: Plot width in pixels (for CUSTOM mode)
            plot_height: Plot height in pixels (for CUSTOM mode)
            plot_min_size: Minimum plot size in pixels (for SQUARE/ASPECT_RATIO)
            plot_max_size: Maximum plot size in pixels (for SQUARE/ASPECT_RATIO)
            plot_scale: Scale percentage for ASPECT_RATIO mode (0-100)
            crosshairs_enabled: Whether crosshairs are visible
            crosshair_x: X coordinate of crosshair
            crosshair_y: Y coordinate of crosshair
            x_axis_label: X-axis label
            y_axis_label: Y-axis label
            x_ticks: X-axis tick positions
            y_ticks: Y-axis tick positions
            x_tick_labels: X-axis tick labels
            y_tick_labels: Y-axis tick labels
            select_region_enabled: Whether selection region is visible
            select_region_min_x: Selection region minimum X
            select_region_min_y: Selection region minimum Y
            select_region_max_x: Selection region maximum X
            select_region_max_y: Selection region maximum Y
            needs_flip: Whether axes need to be flipped (transposed)
            track_changes: Whether to track state changes for logging
        """
        # Core properties
        self.title = title
        self.data_mode = data_mode
        self.data = data
        self.x_coords = x_coords
        self.y_coords = y_coords
        self.needs_flip = needs_flip
        
        # Color configuration
        self.palette = palette
        self.color_scale = color_scale
        self.range_mode = range_mode
        self.range_min = range_min
        self.range_max = range_max
        
        # Plot shape configuration
        self.plot_shape_mode = plot_shape_mode
        self.plot_width = plot_width
        self.plot_height = plot_height
        self.plot_min_size = plot_min_size
        self.plot_max_size = plot_max_size
        self.plot_scale = plot_scale
        
        # Crosshairs
        self.crosshairs_enabled = crosshairs_enabled
        self.crosshair_x = crosshair_x
        self.crosshair_y = crosshair_y
        
        # Axes configuration
        self.x_axis_label = x_axis_label
        self.y_axis_label = y_axis_label
        self.x_ticks = x_ticks if x_ticks is not None else []
        self.y_ticks = y_ticks if y_ticks is not None else []
        self.x_tick_labels = x_tick_labels if x_tick_labels is not None else []
        self.y_tick_labels = y_tick_labels if y_tick_labels is not None else []
        
        # Selection region
        self.select_region_enabled = select_region_enabled
        self.select_region_min_x = select_region_min_x
        self.select_region_min_y = select_region_min_y
        self.select_region_max_x = select_region_max_x
        self.select_region_max_y = select_region_max_y
        
        # State management
        self.track_changes = track_changes
        self._change_history: List[Dict[str, Any]] = []
        self._initial_state = self._capture_state(include_data=False)
        
        # Calculate initial range if dynamic and data is available
        if self.range_mode == RangeMode.DYNAMIC and self.data is not None:
            self._calculate_dynamic_range()
    
    def _calculate_dynamic_range(self) -> Tuple[float, float]:
        """
        Calculate dynamic range from data using percentile method.
        
        Returns:
            Tuple of (min_value, max_value) using 1st and 99th percentiles
        """
        if self.data is None or self.data.size == 0:
            return 0.0, 1.0
        
        data_flat = self.data.flatten() if self.data.ndim > 1 else self.data
        data_flat = data_flat[~np.isnan(data_flat)]
        
        if data_flat.size == 0:
            return 0.0, 1.0
        
        p1 = float(np.percentile(data_flat, 1))
        p99 = float(np.percentile(data_flat, 99))
        
        self.range_min = p1
        self.range_max = p99
        
        return p1, p99
    
    def _capture_state(self, include_data: bool = False) -> Dict[str, Any]:
        """
        Capture current state as a dictionary.
        
        Args:
            include_data: Whether to include data arrays in the state
            
        Returns:
            Dictionary containing all plot state
        """
        state = {
            "title": self.title,
            "data_mode": self.data_mode.value,
            "palette": self.palette,
            "color_scale": self.color_scale.value,
            "range_mode": self.range_mode.value,
            "range_min": self.range_min,
            "range_max": self.range_max,
            "plot_shape_mode": self.plot_shape_mode.value,
            "plot_width": self.plot_width,
            "plot_height": self.plot_height,
            "plot_min_size": self.plot_min_size,
            "plot_max_size": self.plot_max_size,
            "plot_scale": self.plot_scale,
            "crosshairs_enabled": self.crosshairs_enabled,
            # Save crosshair position as simple tuple (x, y) instead of separate properties
            "crosshair": (self.crosshair_x, self.crosshair_y) if (self.crosshair_x is not None and self.crosshair_y is not None) else None,
            # NOTE: Axis labels and ticks are NOT saved - they are automatically derived from
            # coordinate selections in tmp_dashboard and recalculated from coordinate arrays.
            # This reduces undo/redo state size and improves performance.
            # "x_axis_label": self.x_axis_label,
            # "y_axis_label": self.y_axis_label,
            # "x_ticks": self.x_ticks,
            # "y_ticks": self.y_ticks,
            # "x_tick_labels": self.x_tick_labels,
            # "y_tick_labels": self.y_tick_labels,
            "select_region_enabled": self.select_region_enabled,
            "select_region_min_x": self.select_region_min_x,
            "select_region_min_y": self.select_region_min_y,
            "select_region_max_x": self.select_region_max_x,
            "select_region_max_y": self.select_region_max_y,
            "needs_flip": self.needs_flip,
        }
        
        if include_data:
            if self.data is not None:
                state["data"] = self.data.tolist()
                state["data_shape"] = list(self.data.shape)
                state["data_dtype"] = str(self.data.dtype)
            if self.x_coords is not None:
                state["x_coords"] = self.x_coords.tolist()
            if self.y_coords is not None:
                state["y_coords"] = self.y_coords.tolist()
        
        return state
    
    def get_state(self, include_data: bool = False) -> Dict[str, Any]:
        """
        Get current state as a dictionary.
        
        Args:
            include_data: Whether to include data arrays in the state
            
        Returns:
            Dictionary containing all plot state
        """
        return self._capture_state(include_data=include_data)
    
    def get_state_json(self, include_data: bool = False, indent: int = 2) -> str:
        """
        Get current state as a JSON string.
        
        Args:
            include_data: Whether to include data arrays in the state
            indent: JSON indentation level
            
        Returns:
            JSON string containing all plot state
        """
        state = self.get_state(include_data=include_data)
        return json.dumps(state, indent=indent, default=str)
    
    def load_state(self, state: Union[Dict[str, Any], str], restore_data: bool = False) -> None:
        """
        Load state from a dictionary or JSON string.
        
        Args:
            state: State dictionary or JSON string
            restore_data: Whether to restore data arrays (if present in state)
        """
        if isinstance(state, str):
            state = json.loads(state)
        
        # Restore all properties
        self.title = state.get("title", self.title)
        self.data_mode = DataMode(state.get("data_mode", self.data_mode.value))
        self.palette = state.get("palette", self.palette)
        self.color_scale = ColorScale(state.get("color_scale", self.color_scale.value))
        self.range_mode = RangeMode(state.get("range_mode", self.range_mode.value))
        self.range_min = state.get("range_min", self.range_min)
        self.range_max = state.get("range_max", self.range_max)
        self.plot_shape_mode = PlotShapeMode(state.get("plot_shape_mode", self.plot_shape_mode.value))
        self.plot_width = state.get("plot_width", self.plot_width)
        self.plot_height = state.get("plot_height", self.plot_height)
        self.plot_min_size = state.get("plot_min_size", self.plot_min_size)
        self.plot_max_size = state.get("plot_max_size", self.plot_max_size)
        self.plot_scale = state.get("plot_scale", self.plot_scale)
        self.crosshairs_enabled = state.get("crosshairs_enabled", self.crosshairs_enabled)
        # Restore crosshair position from tuple (backward compatible with old format)
        crosshair = state.get("crosshair", None)
        if crosshair is not None and isinstance(crosshair, (list, tuple)) and len(crosshair) == 2:
            self.crosshair_x, self.crosshair_y = crosshair[0], crosshair[1]
        elif "crosshair_x" in state or "crosshair_y" in state:
            # Backward compatibility: restore from old separate properties if present
            self.crosshair_x = state.get("crosshair_x", self.crosshair_x)
            self.crosshair_y = state.get("crosshair_y", self.crosshair_y)
        # NOTE: Axis labels and ticks are NOT restored - they are automatically recalculated
        # from coordinate arrays when the plot is displayed. This keeps undo/redo state smaller.
        # self.x_axis_label = state.get("x_axis_label", self.x_axis_label)
        # self.y_axis_label = state.get("y_axis_label", self.y_axis_label)
        # self.x_ticks = state.get("x_ticks", self.x_ticks)
        # self.y_ticks = state.get("y_ticks", self.y_ticks)
        # self.x_tick_labels = state.get("x_tick_labels", self.x_tick_labels)
        # self.y_tick_labels = state.get("y_tick_labels", self.y_tick_labels)
        self.select_region_enabled = state.get("select_region_enabled", self.select_region_enabled)
        self.select_region_min_x = state.get("select_region_min_x", self.select_region_min_x)
        self.select_region_min_y = state.get("select_region_min_y", self.select_region_min_y)
        self.select_region_max_x = state.get("select_region_max_x", self.select_region_max_x)
        self.select_region_max_y = state.get("select_region_max_y", self.select_region_max_y)
        self.needs_flip = state.get("needs_flip", self.needs_flip)
        
        # Restore data if requested and available
        if restore_data:
            if "data" in state and "data_shape" in state:
                self.data = np.array(state["data"]).reshape(tuple(state["data_shape"]))
            if "x_coords" in state:
                self.x_coords = np.array(state["x_coords"])
            if "y_coords" in state:
                self.y_coords = np.array(state["y_coords"])
        
        # Recalculate range if dynamic
        if self.range_mode == RangeMode.DYNAMIC and self.data is not None:
            self._calculate_dynamic_range()
        
        # Track this change
        if self.track_changes:
            self._record_change("load_state", {"restore_data": restore_data})
    
    def _record_change(self, action: str, details: Dict[str, Any]) -> None:
        """
        Record a state change for logging purposes.
        
        Args:
            action: Action that caused the change (e.g., "set_range", "update_data")
            details: Dictionary with change details
        """
        if not self.track_changes:
            return
        
        change_record = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "details": details,
            "state_snapshot": self._capture_state(include_data=False)
        }
        self._change_history.append(change_record)
    
    def get_change_history(self) -> List[Dict[str, Any]]:
        """
        Get the history of state changes.
        
        Returns:
            List of change records
        """
        return copy.deepcopy(self._change_history)
    
    def clear_change_history(self) -> None:
        """Clear the change history."""
        self._change_history = []
    
    def reset_range(self) -> None:
        """Reset range to dynamic calculation based on current data."""
        if self.data is not None:
            self.range_mode = RangeMode.DYNAMIC
            self._calculate_dynamic_range()
            if self.track_changes:
                self._record_change("reset_range", {
                    "new_range_min": self.range_min,
                    "new_range_max": self.range_max
                })
    
    def reset_state(self) -> None:
        """Reset plot to initial state (excluding data)."""
        self.load_state(self._initial_state, restore_data=False)
        if self.track_changes:
            self._record_change("reset_state", {})
    
    def set_range(self, min_val: float, max_val: float, mode: RangeMode = RangeMode.USER_SPECIFIED) -> None:
        """
        Set the color range.
        
        Args:
            min_val: Minimum value
            max_val: Maximum value
            mode: Range mode (default: USER_SPECIFIED)
        """
        old_min, old_max = self.range_min, self.range_max
        self.range_min = min_val
        self.range_max = max_val
        self.range_mode = mode
        
        if self.track_changes:
            self._record_change("set_range", {
                "old_min": old_min,
                "old_max": old_max,
                "new_min": min_val,
                "new_max": max_val,
                "mode": mode.value
            })
    
    def set_palette(self, palette: str) -> None:
        """
        Set the color palette.
        
        Args:
            palette: Palette name (e.g., "Viridis256")
        """
        old_palette = self.palette
        self.palette = palette
        
        if self.track_changes:
            self._record_change("set_palette", {
                "old_palette": old_palette,
                "new_palette": palette
            })
    
    def set_color_scale(self, scale: ColorScale) -> None:
        """
        Set the color scale type.
        
        Args:
            scale: Color scale (LINEAR or LOG)
        """
        old_scale = self.color_scale
        self.color_scale = scale
        
        if self.track_changes:
            self._record_change("set_color_scale", {
                "old_scale": old_scale.value,
                "new_scale": scale.value
            })
    
    def set_crosshair(self, x: Optional[float] = None, y: Optional[float] = None, enabled: Optional[bool] = None) -> None:
        """
        Set crosshair position and visibility.
        
        Args:
            x: X coordinate (None to keep current)
            y: Y coordinate (None to keep current)
            enabled: Whether crosshairs are visible (None to keep current)
        """
        old_x, old_y, old_enabled = self.crosshair_x, self.crosshair_y, self.crosshairs_enabled
        
        if x is not None:
            self.crosshair_x = x
        if y is not None:
            self.crosshair_y = y
        if enabled is not None:
            self.crosshairs_enabled = enabled
        
        if self.track_changes:
            self._record_change("set_crosshair", {
                "old_x": old_x,
                "old_y": old_y,
                "old_enabled": old_enabled,
                "new_x": self.crosshair_x,
                "new_y": self.crosshair_y,
                "new_enabled": self.crosshairs_enabled
            })
    
    def set_select_region(
        self,
        min_x: Optional[float] = None,
        min_y: Optional[float] = None,
        max_x: Optional[float] = None,
        max_y: Optional[float] = None,
        enabled: Optional[bool] = None
    ) -> None:
        """
        Set selection region coordinates.
        
        Args:
            min_x: Minimum X coordinate
            min_y: Minimum Y coordinate
            max_x: Maximum X coordinate
            max_y: Maximum Y coordinate
            enabled: Whether selection region is visible
        """
        old_region = {
            "min_x": self.select_region_min_x,
            "min_y": self.select_region_min_y,
            "max_x": self.select_region_max_x,
            "max_y": self.select_region_max_y,
            "enabled": self.select_region_enabled
        }
        
        if min_x is not None:
            self.select_region_min_x = min_x
        if min_y is not None:
            self.select_region_min_y = min_y
        if max_x is not None:
            self.select_region_max_x = max_x
        if max_y is not None:
            self.select_region_max_y = max_y
        if enabled is not None:
            self.select_region_enabled = enabled
        
        if self.track_changes:
            self._record_change("set_select_region", {
                "old_region": old_region,
                "new_region": {
                    "min_x": self.select_region_min_x,
                    "min_y": self.select_region_min_y,
                    "max_x": self.select_region_max_x,
                    "max_y": self.select_region_max_y,
                    "enabled": self.select_region_enabled
                }
            })
    
    def update_data(self, data: np.ndarray) -> None:
        """
        Update plot data and recalculate range if dynamic.
        
        Args:
            data: New data array
        """
        old_shape = self.data.shape if self.data is not None else None
        self.data = data
        
        if self.range_mode == RangeMode.DYNAMIC:
            self._calculate_dynamic_range()
        
        if self.track_changes:
            self._record_change("update_data", {
                "old_shape": old_shape,
                "new_shape": list(data.shape) if data is not None else None
            })
    
    def calculate_plot_dimensions(self) -> Tuple[int, int]:
        """
        Calculate plot dimensions based on current shape mode.
        
        Returns:
            Tuple of (width, height) in pixels
        """
        if self.plot_shape_mode == PlotShapeMode.SQUARE:
            width = height = max(self.plot_min_size, min(self.plot_max_size, self.plot_max_size))
        
        elif self.plot_shape_mode == PlotShapeMode.CUSTOM:
            width = max(self.plot_min_size, self.plot_width)
            height = max(self.plot_min_size, self.plot_height)
        
        elif self.plot_shape_mode == PlotShapeMode.ASPECT_RATIO:
            if self.x_coords is not None and self.y_coords is not None:
                aspect_ratio = (self.y_coords.max() - self.y_coords.min()) / (self.x_coords.max() - self.x_coords.min())
            else:
                aspect_ratio = 1.0
            
            scale_factor = self.plot_scale / 100.0
            base_size = int(self.plot_max_size * scale_factor)
            
            if aspect_ratio > 1:  # Taller than wide
                height = int(base_size)
                width = int(base_size / aspect_ratio)
            else:  # Wider than tall or square
                width = int(base_size)
                height = int(base_size * aspect_ratio)
            
            # Ensure minimum size
            min_size = int(self.plot_min_size * scale_factor)
            if width < min_size or height < min_size:
                scale = max(min_size / width, min_size / height)
                width = int(width * scale)
                height = int(height * scale)
        
        else:
            width = height = self.plot_max_size
        
        return width, height
    
    def get_flipped_data(self) -> Optional[np.ndarray]:
        """
        Get data with flip applied if needed.
        
        For 2D data, flipping means transposing (swapping axes).
        The original data is not modified - this returns a view or copy.
        
        Returns:
            Flipped data if needs_flip is True, otherwise original data
        """
        if not self.needs_flip or self.data is None:
            return self.data
        
        # Only flip 2D data (transpose)
        if len(self.data.shape) == 2:
            return np.transpose(self.data)
        
        # For other dimensions, return original (flipping not applicable)
        return self.data
    
    def get_flipped_x_coords(self) -> Optional[np.ndarray]:
        """
        Get X coordinates with flip applied if needed.
        
        IMPORTANT: The coordinate arrays (px, py) ALWAYS map to x-axis and y-axis respectively.
        We only transpose the DATA if dimensions don't match, but coordinates never swap.
        
        Example: If we have data (z, u) and user provides px (for x-axis) and py (for y-axis):
        - If size(z) == len(px) and size(u) == len(py): NO transpose, data stays (z, u)
        - Otherwise: transpose data to (u, z), but px still goes on x-axis, py still goes on y-axis
        
        After transpose (z, u) -> (u, z):
        - Bokeh: data.shape[0] = u (y-axis) → uses py
        - Bokeh: data.shape[1] = z (x-axis) → uses px
        
        Returns:
            X coordinates (px) - these ALWAYS go on x-axis, regardless of flip
        """
        # Coordinates never swap - px always goes on x-axis, py always goes on y-axis
        return self.x_coords
    
    def get_flipped_y_coords(self) -> Optional[np.ndarray]:
        """
        Get Y coordinates with flip applied if needed.
        
        IMPORTANT: The coordinate arrays (px, py) ALWAYS map to x-axis and y-axis respectively.
        We only transpose the DATA if dimensions don't match, but coordinates never swap.
        
        Example: If we have data (z, u) and user provides px (for x-axis) and py (for y-axis):
        - If size(z) == len(px) and size(u) == len(py): NO transpose, data stays (z, u)
        - Otherwise: transpose data to (u, z), but px still goes on x-axis, py still goes on y-axis
        
        After transpose (z, u) -> (u, z):
        - Bokeh: data.shape[0] = u (y-axis) → uses py
        - Bokeh: data.shape[1] = z (x-axis) → uses px
        
        Returns:
            Y coordinates (py) - these ALWAYS go on y-axis, regardless of flip
        """
        # Coordinates never swap - px always goes on x-axis, py always goes on y-axis
        return self.y_coords
    
    def get_flipped_x_axis_label(self) -> Optional[str]:
        """
        Get X axis label with flip applied if needed.
        
        IMPORTANT: When data is transposed, coordinates and labels do NOT swap.
        - px (x_coords) ALWAYS goes on x-axis, py (y_coords) ALWAYS goes on y-axis
        - x_axis_label is the label for px, so it ALWAYS goes on x-axis
        - y_axis_label is the label for py, so it ALWAYS goes on y-axis
        - We only transpose the DATA, not the coordinates or labels
        
        Returns:
            X axis label (px label) - always goes on x-axis, regardless of flip
        """
        # Labels never swap - x_axis_label always goes on x-axis, y_axis_label always goes on y-axis
        return self.x_axis_label
    
    def get_flipped_y_axis_label(self) -> Optional[str]:
        """
        Get Y axis label with flip applied if needed.
        
        IMPORTANT: When data is transposed, coordinates and labels do NOT swap.
        - px (x_coords) ALWAYS goes on x-axis, py (y_coords) ALWAYS goes on y-axis
        - x_axis_label is the label for px, so it ALWAYS goes on x-axis
        - y_axis_label is the label for py, so it ALWAYS goes on y-axis
        - We only transpose the DATA, not the coordinates or labels
        
        Returns:
            Y axis label (py label) - always goes on y-axis, regardless of flip
        """
        # Labels never swap - x_axis_label always goes on x-axis, y_axis_label always goes on y-axis
        return self.y_axis_label
    
    def get_flipped_x_ticks(self) -> Optional[List[float]]:
        """
        Get X axis ticks with flip applied if needed.
        
        When flipped, X and Y ticks are swapped.
        
        Returns:
            Y ticks if needs_flip is True, otherwise X ticks
        """
        if not self.needs_flip:
            return self.x_ticks
        
        # When flipped, X ticks become Y ticks
        return self.y_ticks
    
    def get_flipped_y_ticks(self) -> Optional[List[float]]:
        """
        Get Y axis ticks with flip applied if needed.
        
        When flipped, X and Y ticks are swapped.
        
        Returns:
            X ticks if needs_flip is True, otherwise Y ticks
        """
        if not self.needs_flip:
            return self.y_ticks
        
        # When flipped, Y ticks become X ticks
        return self.x_ticks
    
    def get_flipped_x_tick_labels(self) -> Optional[List[str]]:
        """
        Get X axis tick labels with flip applied if needed.
        
        When flipped, X and Y tick labels are swapped.
        
        Returns:
            Y tick labels if needs_flip is True, otherwise X tick labels
        """
        if not self.needs_flip:
            return self.x_tick_labels
        
        # When flipped, X tick labels become Y tick labels
        return self.y_tick_labels
    
    def get_flipped_y_tick_labels(self) -> Optional[List[str]]:
        """
        Get Y axis tick labels with flip applied if needed.
        
        When flipped, X and Y tick labels are swapped.
        
        Returns:
            X tick labels if needs_flip is True, otherwise Y tick labels
        """
        if not self.needs_flip:
            return self.y_tick_labels
        
        # When flipped, Y tick labels become X tick labels
        return self.x_tick_labels

