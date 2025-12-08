"""
Specialized Plot Classes

This module provides specialized plot classes that extend BasePlot
for specific use cases:
- MAP_2DPlot: 2D map visualization
- PROBE_2DPlot: 2D probe data visualization
- PROBE_1DPlot: 1D probe data visualization
"""

import numpy as np
from typing import Optional, Tuple, Any, Callable
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
    
    def draw_crosshairs(
        self,
        bokeh_figure,
        x_coord: Optional[float] = None,
        y_coord: Optional[float] = None,
        line_color: str = "yellow",
        line_width: int = 2
    ) -> None:
        """
        Draw or update crosshairs on a Bokeh figure.
        
        This method manages crosshair line renderers, creating them if they don't exist
        or updating their positions if they do. The renderers are stored internally.
        
        Args:
            bokeh_figure: Bokeh figure object to draw crosshairs on
            x_coord: X coordinate for vertical crosshair line (uses crosshair_x if None)
            y_coord: Y coordinate for horizontal crosshair line (uses crosshair_y if None)
            line_color: Color of crosshair lines (default: "yellow")
            line_width: Width of crosshair lines (default: 2)
        
        Note:
            If crosshairs_enabled is False, this method does nothing.
            The renderers are stored in _crosshair_h_line and _crosshair_v_line attributes.
        """
        if not self.crosshairs_enabled:
            return
        
        # Use provided coordinates or fall back to stored crosshair position
        if x_coord is None:
            x_coord = self.crosshair_x
        if y_coord is None:
            y_coord = self.crosshair_y
        
        if x_coord is None or y_coord is None:
            return
        
        # Get plot range bounds
        x_min = float(bokeh_figure.x_range.start)
        x_max = float(bokeh_figure.x_range.end)
        y_min = float(bokeh_figure.y_range.start)
        y_max = float(bokeh_figure.y_range.end)
        
        # Initialize renderer storage if not exists
        if not hasattr(self, '_crosshair_h_line'):
            self._crosshair_h_line = None
        if not hasattr(self, '_crosshair_v_line'):
            self._crosshair_v_line = None
        
        # Draw or update horizontal line (across x-axis at y_coord)
        if self._crosshair_h_line is None or self._crosshair_h_line not in bokeh_figure.renderers:
            # Remove old renderer if it exists but isn't in the plot
            if self._crosshair_h_line is not None:
                try:
                    if self._crosshair_h_line in bokeh_figure.renderers:
                        bokeh_figure.renderers.remove(self._crosshair_h_line)
                except:
                    pass
            # Create new horizontal line renderer
            self._crosshair_h_line = bokeh_figure.line(
                x=[x_min, x_max],
                y=[y_coord, y_coord],
                line_color=line_color,
                line_width=line_width
            )
            # Ensure it's added to the plot
            if self._crosshair_h_line not in bokeh_figure.renderers:
                bokeh_figure.renderers.append(self._crosshair_h_line)
        else:
            # Update existing horizontal line position
            self._crosshair_h_line.data_source.data = {
                "x": [x_min, x_max],
                "y": [y_coord, y_coord],
            }
        
        # Draw or update vertical line (across y-axis at x_coord)
        if self._crosshair_v_line is None or self._crosshair_v_line not in bokeh_figure.renderers:
            # Remove old renderer if it exists but isn't in the plot
            if self._crosshair_v_line is not None:
                try:
                    if self._crosshair_v_line in bokeh_figure.renderers:
                        bokeh_figure.renderers.remove(self._crosshair_v_line)
                except:
                    pass
            # Create new vertical line renderer
            self._crosshair_v_line = bokeh_figure.line(
                x=[x_coord, x_coord],
                y=[y_min, y_max],
                line_color=line_color,
                line_width=line_width
            )
            # Ensure it's added to the plot
            if self._crosshair_v_line not in bokeh_figure.renderers:
                bokeh_figure.renderers.append(self._crosshair_v_line)
        else:
            # Update existing vertical line position
            self._crosshair_v_line.data_source.data = {
                "x": [x_coord, x_coord],
                "y": [y_min, y_max],
            }
        
        # Update stored crosshair position
        self.crosshair_x = x_coord
        self.crosshair_y = y_coord
    
    def clear_crosshairs(self, bokeh_figure) -> None:
        """
        Remove crosshairs from a Bokeh figure.
        
        Args:
            bokeh_figure: Bokeh figure object to remove crosshairs from
        """
        if hasattr(self, '_crosshair_h_line') and self._crosshair_h_line is not None:
            try:
                if self._crosshair_h_line in bokeh_figure.renderers:
                    bokeh_figure.renderers.remove(self._crosshair_h_line)
            except:
                pass
            self._crosshair_h_line = None
        
        if hasattr(self, '_crosshair_v_line') and self._crosshair_v_line is not None:
            try:
                if self._crosshair_v_line in bokeh_figure.renderers:
                    bokeh_figure.renderers.remove(self._crosshair_v_line)
            except:
                pass
            self._crosshair_v_line = None
    
    def update_color_scale(
        self,
        bokeh_figure,
        image_renderer,
        color_mapper,
        source,
        use_log: bool,
        colorbar: Optional[Any] = None,
        preserve_crosshairs: Optional[Callable[[], list]] = None,
        restore_crosshairs: Optional[Callable[[list], None]] = None,
    ) -> Tuple[Any, Any]:
        """
        Update the color scale (linear/log) for an image plot.
        
        This method handles switching between LinearColorMapper and LogColorMapper,
        recreating the image renderer, and preserving crosshairs.
        
        Args:
            bokeh_figure: Bokeh figure object
            image_renderer: Current image renderer (will be replaced)
            color_mapper: Current color mapper (will be replaced)
            source: ColumnDataSource with image data
            use_log: If True, use LogColorMapper; if False, use LinearColorMapper
            colorbar: Optional colorbar to update
            preserve_crosshairs: Optional function that returns list of crosshair renderers to preserve
            restore_crosshairs: Optional function that takes list of renderers and restores them
        
        Returns:
            Tuple of (new_color_mapper, new_image_renderer)
        """
        from bokeh.models import LinearColorMapper, LogColorMapper
        
        # Get current data to check for positive values (needed for log scale)
        current_data = None
        if 'image' in source.data and len(source.data['image']) > 0:
            current_data = np.array(source.data["image"][0])
        
        # Determine which mapper class to use
        if use_log:
            if current_data is not None and current_data.size > 0:
                positive_data = current_data[current_data > 0]
                if positive_data.size == 0:
                    # No positive values, fall back to linear
                    new_cls = LinearColorMapper
                    low = color_mapper.low if color_mapper.low > 0 else 0.001
                    high = color_mapper.high if color_mapper.high > 0 else 1.0
                else:
                    new_cls = LogColorMapper
                    # Use current ranges if positive, otherwise use data-based ranges
                    low = color_mapper.low if color_mapper.low > 0 else max(np.min(positive_data), 0.001)
                    high = color_mapper.high if color_mapper.high > 0 else np.max(positive_data)
            else:
                # No data available, use linear as fallback
                new_cls = LinearColorMapper
                low = color_mapper.low if color_mapper.low > 0 else 0.001
                high = color_mapper.high if color_mapper.high > 0 else 1.0
        else:
            new_cls = LinearColorMapper
            # Preserve current ranges
            low = color_mapper.low
            high = color_mapper.high
        
        # Create new color mapper - use self.palette (source of truth) instead of color_mapper.palette
        # This ensures the palette is preserved when switching between linear/log
        new_color_mapper = new_cls(palette=self.palette, low=low, high=high)
        
        # Preserve crosshair renderers if function provided
        crosshair_renderers = []
        if preserve_crosshairs is not None:
            try:
                crosshair_renderers = preserve_crosshairs()
            except:
                pass
        
        # Remove the old image renderer
        if image_renderer is not None and image_renderer in bokeh_figure.renderers:
            bokeh_figure.renderers.remove(image_renderer)
        
        # Re-add the renderer with the new color mapper
        new_image_renderer = bokeh_figure.image(
            "image", source=source, x="x", y="y", dw="dw", dh="dh", color_mapper=new_color_mapper,
        )
        
        # Restore crosshair renderers if function provided
        if restore_crosshairs is not None and crosshair_renderers:
            try:
                restore_crosshairs(crosshair_renderers)
            except:
                pass
        
        # Update colorbar if provided
        if colorbar is not None:
            colorbar.color_mapper = new_color_mapper
        
        # Update plot's color_scale state
        self.color_scale = ColorScale.LOG if use_log else ColorScale.LINEAR
        
        return new_color_mapper, new_image_renderer
    
    def update_palette(
        self,
        bokeh_figure,
        image_renderer,
        color_mapper,
        source,
        new_palette: str,
        colorbar: Optional[Any] = None,
        preserve_crosshairs: Optional[Callable[[], list]] = None,
        restore_crosshairs: Optional[Callable[[list], None]] = None,
    ) -> Tuple[Any, Any]:
        """
        Update the color palette for an image plot.
        
        This method recreates the color mapper with a new palette and updates
        the image renderer, preserving crosshairs.
        
        Args:
            bokeh_figure: Bokeh figure object
            image_renderer: Current image renderer (will be replaced)
            color_mapper: Current color mapper (will be replaced)
            source: ColumnDataSource with image data
            new_palette: New palette name (e.g., "Viridis256", "Plasma256")
            colorbar: Optional colorbar to update
            preserve_crosshairs: Optional function that returns list of crosshair renderers to preserve
            restore_crosshairs: Optional function that takes list of renderers and restores them
        
        Returns:
            Tuple of (new_color_mapper, new_image_renderer)
        """
        from bokeh.models import LinearColorMapper, LogColorMapper
        
        # Determine mapper class (preserve linear/log)
        mapper_cls = type(color_mapper)
        
        # Create new color mapper with new palette
        new_color_mapper = mapper_cls(
            palette=new_palette,
            low=color_mapper.low,
            high=color_mapper.high
        )
        
        # Preserve crosshair renderers if function provided
        crosshair_renderers = []
        if preserve_crosshairs is not None:
            try:
                crosshair_renderers = preserve_crosshairs()
            except:
                pass
        
        # Remove the old image renderer
        if image_renderer is not None and image_renderer in bokeh_figure.renderers:
            bokeh_figure.renderers.remove(image_renderer)
        
        # Re-add the renderer with the new color mapper
        new_image_renderer = bokeh_figure.image(
            "image", source=source, x="x", y="y", dw="dw", dh="dh", color_mapper=new_color_mapper,
        )
        
        # Restore crosshair renderers if function provided
        if restore_crosshairs is not None and crosshair_renderers:
            try:
                restore_crosshairs(crosshair_renderers)
            except:
                pass
        
        # Update colorbar if provided
        if colorbar is not None:
            colorbar.color_mapper = new_color_mapper
        
        # Update plot's palette state
        self.palette = new_palette
        
        return new_color_mapper, new_image_renderer


def draw_crosshairs_from_indices(
    map_plot: MAP_2DPlot,
    bokeh_figure,
    x_index: int,
    y_index: int,
    x_coords: Optional[np.ndarray] = None,
    y_coords: Optional[np.ndarray] = None,
    rect_storage: Optional[Any] = None,
) -> None:
    """
    Draw crosshairs on a plot using array indices.
    
    This is a utility function that converts indices to coordinates and calls
    the plot's draw_crosshairs method. It eliminates duplication between
    draw_cross1() and draw_cross1b() type functions.
    
    Args:
        map_plot: MAP_2DPlot instance to draw crosshairs on
        bokeh_figure: Bokeh figure object
        x_index: X index in the coordinate arrays
        y_index: Y index in the coordinate arrays
        x_coords: Optional X coordinate array (uses map_plot.get_flipped_x_coords() if None)
        y_coords: Optional Y coordinate array (uses map_plot.get_flipped_y_coords() if None)
        rect_storage: Optional object to store crosshair line references (for backward compatibility)
    """
    if map_plot is None:
        return
    
    # Get coordinates - use provided or get from plot
    if x_coords is None:
        x_coords = map_plot.get_flipped_x_coords()
    if y_coords is None:
        y_coords = map_plot.get_flipped_y_coords()
    
    if x_coords is None or y_coords is None:
        return
    
    # Convert indices to coordinates
    plot_x_coord = x_coords[x_index] if x_index < len(x_coords) else x_coords[-1]
    plot_y_coord = y_coords[y_index] if y_index < len(y_coords) else y_coords[-1]
    
    # Use the plot class method to draw crosshairs
    map_plot.draw_crosshairs(bokeh_figure, plot_x_coord, plot_y_coord)
    
    # Store in rect_storage for backward compatibility (if provided)
    if rect_storage is not None:
        if hasattr(map_plot, '_crosshair_h_line'):
            rect_storage.h1line = map_plot._crosshair_h_line
        if hasattr(map_plot, '_crosshair_v_line'):
            rect_storage.v1line = map_plot._crosshair_v_line


def set_axis_labels(
    bokeh_figure,
    x_label: Optional[str] = None,
    y_label: Optional[str] = None,
) -> None:
    """
    Set axis labels on a Bokeh figure.
    
    Args:
        bokeh_figure: Bokeh figure object
        x_label: X-axis label (None to leave unchanged)
        y_label: Y-axis label (None to leave unchanged)
    """
    if x_label is not None:
        bokeh_figure.xaxis.axis_label = x_label
    if y_label is not None:
        bokeh_figure.yaxis.axis_label = y_label


def set_ticks_from_coords(
    bokeh_figure,
    coords: np.ndarray,
    axis: str = 'x',
    sample_interval: Optional[int] = None,
    num_ticks: int = 10,
    format_str: str = "{:.1f}",
) -> None:
    """
    Set axis ticks from a coordinate array with automatic sampling.
    
    This function samples coordinates at regular intervals and creates
    formatted tick labels, then applies them to the specified axis.
    
    Args:
        bokeh_figure: Bokeh figure object
        coords: Coordinate array to sample ticks from
        axis: Which axis to set ('x' or 'y')
        sample_interval: Interval for sampling (e.g., 10 means every 10th coordinate).
                        If None, automatically calculates to get approximately num_ticks.
        num_ticks: Target number of ticks (used if sample_interval is None)
        format_str: Format string for tick labels (default: "{:.1f}")
    
    Example:
        set_ticks_from_coords(plot2, x_coords, axis='x', num_ticks=10)
        # Samples every 10th coordinate and formats as "{:.1f}"
    """
    if coords is None or len(coords) == 0:
        return
    
    # Calculate sample interval if not provided
    if sample_interval is None:
        sample_interval = max(1, len(coords) // num_ticks)
    
    # Sample coordinates and create formatted labels
    tick_positions = []
    tick_labels = []
    for i in range(0, len(coords), sample_interval):
        tick_positions.append(coords[i])
        tick_labels.append(format_str.format(coords[i]))
    
    # Apply to the specified axis
    axis_obj = bokeh_figure.xaxis if axis.lower() == 'x' else bokeh_figure.yaxis
    axis_obj.ticker = tick_positions
    axis_obj.major_label_overrides = dict(zip(tick_positions, tick_labels))


def set_ticks_from_coords_both_axes(
    bokeh_figure,
    x_coords: Optional[np.ndarray] = None,
    y_coords: Optional[np.ndarray] = None,
    x_sample_interval: Optional[int] = None,
    y_sample_interval: Optional[int] = None,
    x_num_ticks: int = 10,
    y_num_ticks: int = 10,
    x_format_str: str = "{:.1f}",
    y_format_str: str = "{:.1f}",
) -> None:
    """
    Set ticks for both X and Y axes from coordinate arrays.
    
    Convenience function that calls set_ticks_from_coords for both axes.
    
    Args:
        bokeh_figure: Bokeh figure object
        x_coords: X-axis coordinate array (None to skip)
        y_coords: Y-axis coordinate array (None to skip)
        x_sample_interval: Sampling interval for X axis
        y_sample_interval: Sampling interval for Y axis
        x_num_ticks: Target number of ticks for X axis
        y_num_ticks: Target number of ticks for Y axis
        x_format_str: Format string for X-axis tick labels
        y_format_str: Format string for Y-axis tick labels
    """
    if x_coords is not None:
        set_ticks_from_coords(
            bokeh_figure,
            x_coords,
            axis='x',
            sample_interval=x_sample_interval,
            num_ticks=x_num_ticks,
            format_str=x_format_str,
        )
    
    if y_coords is not None:
        set_ticks_from_coords(
            bokeh_figure,
            y_coords,
            axis='y',
            sample_interval=y_sample_interval,
            num_ticks=y_num_ticks,
            format_str=y_format_str,
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

