"""
State Synchronization Utilities

This module provides utilities for synchronizing UI widget states with
plot objects and processor objects, enabling bidirectional updates.
"""

from typing import Optional, Callable, Any, Dict, List
import numpy as np

from .SCDash_base_plot import BasePlot, RangeMode, ColorScale, PlotShapeMode
from .SCDashUI_plot_controls import create_range_inputs, create_color_scale_selector, create_palette_selector
from .SCDashUI_base_components import create_text_input, create_select, create_radio_button_group


def sync_plot_to_range_inputs(
    plot: BasePlot,
    min_input: Any,
    max_input: Any,
) -> None:
    """
    Update range input widgets from plot state.
    
    Args:
        plot: BasePlot instance
        min_input: TextInput widget for minimum value
        max_input: TextInput widget for maximum value
    """
    if plot.range_mode == RangeMode.USER_SPECIFIED:
        min_input.value = str(plot.range_min)
        max_input.value = str(plot.range_max)
    elif plot.range_mode == RangeMode.DYNAMIC and plot.data is not None:
        # Calculate dynamic range
        data_flat = plot.data.flatten() if plot.data.ndim > 1 else plot.data
        data_flat = data_flat[~np.isnan(data_flat)]
        if data_flat.size > 0:
            p1 = float(np.percentile(data_flat, 1))
            p99 = float(np.percentile(data_flat, 99))
            min_input.value = str(p1)
            max_input.value = str(p99)


def sync_range_inputs_to_plot(
    plot: BasePlot,
    min_input: Any,
    max_input: Any,
) -> bool:
    """
    Update plot range from input widgets.
    
    Args:
        plot: BasePlot instance
        min_input: TextInput widget for minimum value
        max_input: TextInput widget for maximum value
        
    Returns:
        True if update was successful, False otherwise
    """
    try:
        min_val = float(min_input.value)
        max_val = float(max_input.value)
        
        if min_val >= max_val:
            return False
        
        plot.set_range(min_val, max_val)
        return True
    except (ValueError, TypeError):
        return False


def sync_plot_to_color_scale_selector(
    plot: BasePlot,
    selector: Any,
) -> None:
    """
    Update color scale selector from plot state.
    
    Args:
        plot: BasePlot instance
        selector: RadioButtonGroup widget for color scale
    """
    if plot.color_scale == ColorScale.LINEAR:
        selector.active = 0
    elif plot.color_scale == ColorScale.LOG:
        selector.active = 1


def sync_color_scale_selector_to_plot(
    plot: BasePlot,
    selector: Any,
    update_callback: Optional[Callable[[bool], None]] = None,
) -> None:
    """
    Update plot color scale from selector widget.
    
    Args:
        plot: BasePlot instance
        selector: RadioButtonGroup widget for color scale
        update_callback: Optional callback function(use_log: bool) to update Bokeh color mapper
    """
    use_log = selector.active == 1
    if selector.active == 0:
        plot.set_color_scale(ColorScale.LINEAR)
    elif selector.active == 1:
        plot.set_color_scale(ColorScale.LOG)
    
    # Call the update callback to actually change the Bokeh color mapper
    if update_callback is not None:
        try:
            update_callback(use_log)
        except Exception as e:
            print(f"⚠️ Error updating color scale: {e}")
            import traceback
            traceback.print_exc()


def sync_plot_to_palette_selector(
    plot: BasePlot,
    selector: Any,
) -> None:
    """
    Update palette selector from plot state.
    
    Args:
        plot: BasePlot instance
        selector: Select widget for palette
    """
    selector.value = plot.palette


def sync_palette_selector_to_plot(
    plot: BasePlot,
    selector: Any,
) -> None:
    """
    Update plot palette from selector widget.
    
    Args:
        plot: BasePlot instance
        selector: Select widget for palette
    """
    plot.set_palette(selector.value)


def sync_plot_to_shape_controls(
    plot: BasePlot,
    shape_selector: Any,
    custom_width_input: Any,
    custom_height_input: Any,
    scale_input: Any,
    min_size_input: Any,
    max_size_input: Any,
) -> None:
    """
    Update plot shape controls from plot state.
    
    Args:
        plot: BasePlot instance
        shape_selector: RadioButtonGroup for shape mode
        custom_width_input: TextInput for custom width
        custom_height_input: TextInput for custom height
        scale_input: TextInput for scale percentage
        min_size_input: TextInput for minimum size
        max_size_input: TextInput for maximum size
    """
    # Set shape mode
    if plot.plot_shape_mode == PlotShapeMode.SQUARE:
        shape_selector.active = 0
    elif plot.plot_shape_mode == PlotShapeMode.CUSTOM:
        shape_selector.active = 1
    elif plot.plot_shape_mode == PlotShapeMode.ASPECT_RATIO:
        shape_selector.active = 2
    
    # Set custom dimensions
    if plot.plot_width is not None:
        custom_width_input.value = str(int(plot.plot_width))
    if plot.plot_height is not None:
        custom_height_input.value = str(int(plot.plot_height))
    
    # Set scale (if aspect ratio mode)
    if plot.plot_scale is not None:
        scale_input.value = str(int(plot.plot_scale * 100))  # Convert to percentage
    
    # Set size limits
    if plot.plot_min_size is not None:
        min_size_input.value = str(int(plot.plot_min_size))
    if plot.plot_max_size is not None:
        max_size_input.value = str(int(plot.plot_max_size))


def sync_shape_controls_to_plot(
    plot: BasePlot,
    shape_selector: Any,
    custom_width_input: Any,
    custom_height_input: Any,
    scale_input: Any,
    min_size_input: Any,
    max_size_input: Any,
) -> None:
    """
    Update plot shape from control widgets.
    
    Args:
        plot: BasePlot instance
        shape_selector: RadioButtonGroup for shape mode
        custom_width_input: TextInput for custom width
        custom_height_input: TextInput for custom height
        scale_input: TextInput for scale percentage
        min_size_input: TextInput for minimum size
        max_size_input: TextInput for maximum size
    """
    # Update shape mode
    if shape_selector.active == 0:
        plot.plot_shape_mode = PlotShapeMode.SQUARE
    elif shape_selector.active == 1:
        plot.plot_shape_mode = PlotShapeMode.CUSTOM
    elif shape_selector.active == 2:
        plot.plot_shape_mode = PlotShapeMode.ASPECT_RATIO
    
    # Update dimensions
    try:
        if custom_width_input.value:
            plot.plot_width = int(custom_width_input.value)
        if custom_height_input.value:
            plot.plot_height = int(custom_height_input.value)
    except (ValueError, TypeError):
        pass
    
    # Update scale
    try:
        if scale_input.value:
            plot.plot_scale = float(scale_input.value) / 100.0  # Convert from percentage
    except (ValueError, TypeError):
        pass
    
    # Update size limits
    try:
        if min_size_input.value:
            plot.plot_min_size = int(min_size_input.value)
        if max_size_input.value:
            plot.plot_max_size = int(max_size_input.value)
    except (ValueError, TypeError):
        pass


def sync_plot_to_crosshair_display(
    plot: BasePlot,
    x_display: Any,
    y_display: Any,
) -> None:
    """
    Update crosshair display widgets from plot state.
    
    Args:
        plot: BasePlot instance
        x_display: Widget to display X crosshair value
        y_display: Widget to display Y crosshair value
    """
    if plot.crosshairs_enabled:
        if x_display:
            x_display.text = f"    X: {plot.crosshair_x:.3f}" if plot.crosshair_x is not None else "    X: --"
        if y_display:
            y_display.text = f"    Y: {plot.crosshair_y:.3f}" if plot.crosshair_y is not None else "    Y: --"


def sync_plot_to_selection_display(
    plot: BasePlot,
    display: Any,
) -> None:
    """
    Update selection region display from plot state.
    
    Args:
        plot: BasePlot instance
        display: Widget to display selection region
    """
    if plot.select_region_enabled:
        min_x = plot.select_region_min_x or 0
        min_y = plot.select_region_min_y or 0
        max_x = plot.select_region_max_x or 0
        max_y = plot.select_region_max_y or 0
        
        display.text = (
            f"Selection: ({min_x:.1f}, {min_y:.1f}) to ({max_x:.1f}, {max_y:.1f})"
        )


def create_sync_callbacks(
    plot: BasePlot,
    min_input: Any,
    max_input: Any,
    color_scale_selector: Any,
    palette_selector: Any,
    color_scale_update_callback: Optional[Callable[[bool], None]] = None,
) -> Dict[str, Callable]:
    """
    Create callback functions that sync UI widgets to plot state.
    
    Args:
        plot: BasePlot instance
        min_input: Range minimum input widget
        max_input: Range maximum input widget
        color_scale_selector: Color scale selector widget
        palette_selector: Palette selector widget
        color_scale_update_callback: Optional callback function(use_log: bool) to update Bokeh color mapper
        
    Returns:
        Dictionary of callback functions
    """
    def on_range_change(attr, old, new):
        sync_range_inputs_to_plot(plot, min_input, max_input)
    
    def on_color_scale_change(attr, old, new):
        # Pass the update callback to actually change the Bokeh color mapper
        sync_color_scale_selector_to_plot(plot, color_scale_selector, update_callback=color_scale_update_callback)
    
    def on_palette_change(attr, old, new):
        sync_palette_selector_to_plot(plot, palette_selector)
    
    return {
        "range": on_range_change,
        "color_scale": on_color_scale_change,
        "palette": on_palette_change,
    }


def sync_all_plot_ui(
    plot: BasePlot,
    min_input: Any,
    max_input: Any,
    color_scale_selector: Any,
    palette_selector: Any,
    shape_selector: Optional[Any] = None,
    custom_width_input: Optional[Any] = None,
    custom_height_input: Optional[Any] = None,
    scale_input: Optional[Any] = None,
    min_size_input: Optional[Any] = None,
    max_size_input: Optional[Any] = None,
) -> None:
    """
    Synchronize all UI widgets from plot state.
    
    Args:
        plot: BasePlot instance
        min_input: Range minimum input widget
        max_input: Range maximum input widget
        color_scale_selector: Color scale selector widget
        palette_selector: Palette selector widget
        shape_selector: Optional shape mode selector
        custom_width_input: Optional custom width input
        custom_height_input: Optional custom height input
        scale_input: Optional scale input
        min_size_input: Optional minimum size input
        max_size_input: Optional maximum size input
    """
    sync_plot_to_range_inputs(plot, min_input, max_input)
    sync_plot_to_color_scale_selector(plot, color_scale_selector)
    sync_plot_to_palette_selector(plot, palette_selector)
    
    if shape_selector is not None:
        sync_plot_to_shape_controls(
            plot,
            shape_selector,
            custom_width_input or create_text_input("", ""),
            custom_height_input or create_text_input("", ""),
            scale_input or create_text_input("", ""),
            min_size_input or create_text_input("", ""),
            max_size_input or create_text_input("", ""),
        )

