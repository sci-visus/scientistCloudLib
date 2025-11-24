"""
Specialized Plot Classes

This module provides specialized plot classes that extend BasePlot
for specific use cases:
- MAP_2DPlot: 2D map visualization
- PROBE_2DPlot: 2D probe data visualization
- PROBE_1DPlot: 1D probe data visualization
"""

import numpy as np
from typing import Optional, Tuple
from .SCDash_base_plot import BasePlot, DataMode, ColorScale, PlotShapeMode, RangeMode


class MAP_2DPlot(BasePlot):
    """
    Specialized plot class for 2D map visualizations.
    
    This class is optimized for displaying 2D spatial data with
    coordinate systems, crosshairs, and selection regions.
    """
    
    def __init__(
        self,
        title: str = "Map View",
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
        crosshairs_enabled: bool = True,
        crosshair_x: Optional[float] = None,
        crosshair_y: Optional[float] = None,
        x_axis_label: Optional[str] = None,
        y_axis_label: Optional[str] = None,
        needs_flip: bool = False,
        track_changes: bool = True,
    ):
        """
        Initialize a MAP_2DPlot instance.
        
        Args:
            title: Plot title (default: "Map View")
            data: 2D numpy array for map data
            x_coords: X-axis coordinate array
            y_coords: Y-axis coordinate array
            palette: Color palette name
            color_scale: Color scale type
            range_mode: Range calculation mode
            range_min: Minimum value for color range
            range_max: Maximum value for color range
            plot_shape_mode: Plot shape mode
            plot_width: Plot width in pixels
            plot_height: Plot height in pixels
            plot_min_size: Minimum plot size
            plot_max_size: Maximum plot size
            plot_scale: Scale percentage for aspect ratio mode
            crosshairs_enabled: Whether crosshairs are visible (default: True)
            crosshair_x: X coordinate of crosshair
            crosshair_y: Y coordinate of crosshair
            x_axis_label: X-axis label
            y_axis_label: Y-axis label
            needs_flip: Whether axes need to be flipped
            track_changes: Whether to track state changes
        """
        # Validate data is 2D if provided
        if data is not None and len(data.shape) != 2:
            raise ValueError(f"MAP_2DPlot requires 2D data, got shape {data.shape}")
        
        super().__init__(
            title=title,
            data_mode=DataMode.MODE_2D,
            data=data,
            x_coords=x_coords,
            y_coords=y_coords,
            palette=palette,
            color_scale=color_scale,
            range_mode=range_mode,
            range_min=range_min,
            range_max=range_max,
            plot_shape_mode=plot_shape_mode,
            plot_width=plot_width,
            plot_height=plot_height,
            plot_min_size=plot_min_size,
            plot_max_size=plot_max_size,
            plot_scale=plot_scale,
            crosshairs_enabled=crosshairs_enabled,
            crosshair_x=crosshair_x,
            crosshair_y=crosshair_y,
            x_axis_label=x_axis_label,
            y_axis_label=y_axis_label,
            needs_flip=needs_flip,
            track_changes=track_changes,
        )
        
        # Set default axis labels if not provided
        if self.x_axis_label is None and self.x_coords is not None:
            self.x_axis_label = "X Position"
        if self.y_axis_label is None and self.y_coords is not None:
            self.y_axis_label = "Y Position"
    
    def get_data_shape(self) -> Optional[Tuple[int, int]]:
        """
        Get the shape of the 2D data array.
        
        Returns:
            Tuple of (height, width) or None if no data
        """
        if self.data is None:
            return None
        return self.data.shape
    
    def get_coordinate_ranges(self) -> Optional[Tuple[float, float, float, float]]:
        """
        Get the coordinate ranges (x_min, x_max, y_min, y_max).
        
        Returns:
            Tuple of (x_min, x_max, y_min, y_max) or None if coordinates not available
        """
        if self.x_coords is None or self.y_coords is None:
            return None
        
        return (
            float(self.x_coords.min()),
            float(self.x_coords.max()),
            float(self.y_coords.min()),
            float(self.y_coords.max())
        )


class PROBE_2DPlot(BasePlot):
    """
    Specialized plot class for 2D probe data visualizations.
    
    This class is optimized for displaying 2D probe data (e.g., from 4D volumes)
    with support for selection regions and coordinate systems.
    """
    
    def __init__(
        self,
        title: str = "Probe View (2D)",
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
        needs_flip: bool = False,
        track_changes: bool = True,
    ):
        """
        Initialize a PROBE_2DPlot instance.
        
        Args:
            title: Plot title (default: "Probe View (2D)")
            data: 2D numpy array for probe data
            x_coords: X-axis coordinate array (e.g., z dimension)
            y_coords: Y-axis coordinate array (e.g., u dimension)
            palette: Color palette name
            color_scale: Color scale type
            range_mode: Range calculation mode
            range_min: Minimum value for color range
            range_max: Maximum value for color range
            plot_shape_mode: Plot shape mode
            plot_width: Plot width in pixels
            plot_height: Plot height in pixels
            plot_min_size: Minimum plot size
            plot_max_size: Maximum plot size
            plot_scale: Scale percentage for aspect ratio mode
            crosshairs_enabled: Whether crosshairs are visible
            crosshair_x: X coordinate of crosshair
            crosshair_y: Y coordinate of crosshair
            x_axis_label: X-axis label (e.g., "Probe X" or "Z")
            y_axis_label: Y-axis label (e.g., "Probe Y" or "U")
            needs_flip: Whether axes need to be flipped
            track_changes: Whether to track state changes
        """
        # Validate data is 2D if provided
        if data is not None and len(data.shape) != 2:
            raise ValueError(f"PROBE_2DPlot requires 2D data, got shape {data.shape}")
        
        super().__init__(
            title=title,
            data_mode=DataMode.MODE_2D,
            data=data,
            x_coords=x_coords,
            y_coords=y_coords,
            palette=palette,
            color_scale=color_scale,
            range_mode=range_mode,
            range_min=range_min,
            range_max=range_max,
            plot_shape_mode=plot_shape_mode,
            plot_width=plot_width,
            plot_height=plot_height,
            plot_min_size=plot_min_size,
            plot_max_size=plot_max_size,
            plot_scale=plot_scale,
            crosshairs_enabled=crosshairs_enabled,
            crosshair_x=crosshair_x,
            crosshair_y=crosshair_y,
            x_axis_label=x_axis_label,
            y_axis_label=y_axis_label,
            needs_flip=needs_flip,
            track_changes=track_changes,
        )
        
        # Set default axis labels if not provided
        if self.x_axis_label is None:
            self.x_axis_label = "Probe X"
        if self.y_axis_label is None:
            self.y_axis_label = "Probe Y"
    
    def get_data_shape(self) -> Optional[Tuple[int, int]]:
        """
        Get the shape of the 2D data array.
        
        Returns:
            Tuple of (height, width) or None if no data
        """
        if self.data is None:
            return None
        return self.data.shape


class PROBE_1DPlot(BasePlot):
    """
    Specialized plot class for 1D probe data visualizations.
    
    This class is optimized for displaying 1D line plots (e.g., from 3D volumes)
    with support for range selection and coordinate systems.
    """
    
    def __init__(
        self,
        title: str = "Probe View (1D)",
        data: Optional[np.ndarray] = None,
        x_coords: Optional[np.ndarray] = None,
        palette: str = "Viridis256",
        color_scale: ColorScale = ColorScale.LINEAR,
        range_mode: RangeMode = RangeMode.DYNAMIC,
        range_min: Optional[float] = None,
        range_max: Optional[float] = None,
        plot_width: int = 400,
        plot_height: int = 300,
        crosshairs_enabled: bool = False,
        x_axis_label: Optional[str] = None,
        y_axis_label: Optional[str] = None,
        select_region_enabled: bool = True,
        select_region_min_x: Optional[float] = None,
        select_region_max_x: Optional[float] = None,
        track_changes: bool = True,
    ):
        """
        Initialize a PROBE_1DPlot instance.
        
        Args:
            title: Plot title (default: "Probe View (1D)")
            data: 1D numpy array for probe data
            x_coords: X-axis coordinate array (probe coordinates)
            palette: Color palette name (not used for 1D, but kept for consistency)
            color_scale: Color scale type (applies to y-axis for log scale)
            range_mode: Range calculation mode (for y-axis)
            range_min: Minimum value for y-axis range
            range_max: Maximum value for y-axis range
            plot_width: Plot width in pixels
            plot_height: Plot height in pixels
            crosshairs_enabled: Whether crosshairs are visible
            x_axis_label: X-axis label (e.g., "Probe Index" or coordinate name)
            y_axis_label: Y-axis label (default: "Intensity")
            select_region_enabled: Whether selection region is visible (default: True)
            select_region_min_x: Selection region minimum X (for range selection)
            select_region_max_x: Selection region maximum X (for range selection)
            track_changes: Whether to track state changes
        """
        # Validate data is 1D if provided
        if data is not None and len(data.shape) != 1:
            raise ValueError(f"PROBE_1DPlot requires 1D data, got shape {data.shape}")
        
        super().__init__(
            title=title,
            data_mode=DataMode.MODE_1D,
            data=data,
            x_coords=x_coords,
            y_coords=None,  # 1D plots don't have y_coords
            palette=palette,
            color_scale=color_scale,
            range_mode=range_mode,
            range_min=range_min,
            range_max=range_max,
            plot_shape_mode=PlotShapeMode.CUSTOM,  # 1D plots use custom dimensions
            plot_width=plot_width,
            plot_height=plot_height,
            plot_min_size=200,
            plot_max_size=400,
            plot_scale=100.0,
            crosshairs_enabled=crosshairs_enabled,
            crosshair_x=None,
            crosshair_y=None,
            x_axis_label=x_axis_label,
            y_axis_label=y_axis_label,
            select_region_enabled=select_region_enabled,
            select_region_min_x=select_region_min_x,
            select_region_min_y=None,  # 1D plots only use x for selection
            select_region_max_x=select_region_max_x,
            select_region_max_y=None,  # 1D plots only use x for selection
            needs_flip=False,  # 1D plots don't need flipping
            track_changes=track_changes,
        )
        
        # Set default axis labels if not provided
        if self.x_axis_label is None:
            self.x_axis_label = "Probe Index"
        if self.y_axis_label is None:
            self.y_axis_label = "Intensity"
    
    def get_data_length(self) -> Optional[int]:
        """
        Get the length of the 1D data array.
        
        Returns:
            Length of data array or None if no data
        """
        if self.data is None:
            return None
        return len(self.data)
    
    def get_x_range(self) -> Optional[Tuple[float, float]]:
        """
        Get the X coordinate range.
        
        Returns:
            Tuple of (x_min, x_max) or None if coordinates not available
        """
        if self.x_coords is None:
            return None
        
        return (
            float(self.x_coords.min()),
            float(self.x_coords.max())
        )
    
    def get_y_range(self) -> Optional[Tuple[float, float]]:
        """
        Get the Y data range.
        
        Returns:
            Tuple of (y_min, y_max) or None if no data
        """
        if self.data is None:
            return None
        
        return (
            float(self.data.min()),
            float(self.data.max())
        )
    
    def set_select_range(self, min_x: Optional[float] = None, max_x: Optional[float] = None) -> None:
        """
        Set selection range for 1D plot (convenience method).
        
        Args:
            min_x: Minimum X coordinate
            max_x: Maximum X coordinate
        """
        self.set_select_region(
            min_x=min_x,
            min_y=None,
            max_x=max_x,
            max_y=None,
            enabled=True if (min_x is not None or max_x is not None) else None
        )
    
    def get_select_range(self) -> Optional[Tuple[float, float]]:
        """
        Get the current selection range.
        
        Returns:
            Tuple of (min_x, max_x) or None if no selection
        """
        if not self.select_region_enabled:
            return None
        
        if self.select_region_min_x is None or self.select_region_max_x is None:
            return None
        
        return (self.select_region_min_x, self.select_region_max_x)

