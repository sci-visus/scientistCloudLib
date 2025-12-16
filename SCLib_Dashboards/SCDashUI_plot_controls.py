"""
Plot Control UI Components

This module provides UI components for controlling plot properties:
- Range inputs (min/max)
- Color scale selectors (Linear/Log)
- Palette selectors
- Plot shape controls (Square/Custom/Aspect Ratio)
- Range mode toggles
"""

from typing import Optional, Callable, Tuple, List
from bokeh.models import TextInput, RadioButtonGroup, Select, Toggle, Div
from bokeh.layouts import column, row

from .SCDashUI_base_components import (
    create_text_input,
    create_radio_button_group,
    create_select,
    create_toggle,
    create_label_div,
    create_div,
)


# Color palettes
DEFAULT_PALETTES = [
    "Viridis256", "Plasma256", "Inferno256", "Magma256",
    "Cividis256", "Turbo256", "Greys256", "Blues256"
]


def create_range_inputs(
    min_title: str = "Range Min:",
    max_title: str = "Range Max:",
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
    width: int = 120,
    min_callback: Optional[Callable] = None,
    max_callback: Optional[Callable] = None,
) -> Tuple[TextInput, TextInput]:
    """
    Create a pair of range input widgets (min and max).
    
    Args:
        min_title: Title for minimum input
        max_title: Title for maximum input
        min_value: Default minimum value
        max_value: Default maximum value
        width: Widget width in pixels
        min_callback: Optional callback for min input
        max_callback: Optional callback for max input
        
    Returns:
        Tuple of (min_input, max_input) widgets
    """
    min_input = create_text_input(
        title=min_title,
        value=str(min_value) if min_value is not None else "",
        width=width,
        callback=min_callback
    )
    
    max_input = create_text_input(
        title=max_title,
        value=str(max_value) if max_value is not None else "",
        width=width,
        callback=max_callback
    )
    
    return min_input, max_input


def create_range_section(
    label: str,
    min_title: str = "Range Min:",
    max_title: str = "Range Max:",
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
    width: int = 100,  # Changed from 120 to 100 (as small as possible)
    min_callback: Optional[Callable] = None,
    max_callback: Optional[Callable] = None,
) -> column:
    """
    Create a complete range input section with label.
    
    Args:
        label: Section label
        min_title: Title for minimum input
        max_title: Title for maximum input
        min_value: Default minimum value
        max_value: Default maximum value
        width: Widget width in pixels
        min_callback: Optional callback for min input
        max_callback: Optional callback for max input
        
    Returns:
        Column layout with label and range inputs
    """
    min_input, max_input = create_range_inputs(
        min_title=min_title,
        max_title=max_title,
        min_value=min_value,
        max_value=max_value,
        width=width,
        min_callback=min_callback,
        max_callback=max_callback
    )
    
    return column(
        #create_label_div(label, width=200),
        row(min_input, max_input, spacing=0),  # Minimal spacing between min and max inputs
        sizing_mode="stretch_width",
        spacing=0  # Minimal spacing between widgets
    )


def create_color_scale_selector(
    labels: List[str] = None,
    active: int = 0,
    width: int = 100,  # Changed from 200 to 100 to match other widgets (as small as possible)
    callback: Optional[Callable] = None,
) -> RadioButtonGroup:
    """
    Create a color scale selector (Linear/Log).
    
    Args:
        labels: List of labels (default: ["Linear", "Log"])
        active: Initially active index
        width: Widget width in pixels
        callback: Optional callback function
        
    Returns:
        RadioButtonGroup widget
    """
    if labels is None:
        labels = ["Linear", "Log"]
    
    return create_radio_button_group(
        labels=labels,
        active=active,
        width=width,
        callback=callback
    )


def create_color_scale_section(
    label: str = "Color Scale:",
    active: int = 0,
    width: int = 200,
    callback: Optional[Callable] = None,
) -> column:
    """
    Create a complete color scale section with label.
    
    Args:
        label: Section label
        active: Initially active index
        width: Widget width in pixels
        callback: Optional callback function
        
    Returns:
        Column layout with label and color scale selector
    """
    selector = create_color_scale_selector(
        active=active,
        width=width,
        callback=callback
    )
    
    return column(
        create_label_div(label, width=width),
        selector
    )


def create_palette_selector(
    palettes: List[str] = None,
    value: str = "Viridis256",
    width: int = 200,
    callback: Optional[Callable] = None,
) -> Select:
    """
    Create a color palette selector.
    
    Args:
        palettes: List of palette names (default: DEFAULT_PALETTES)
        value: Default selected palette
        width: Widget width in pixels
        callback: Optional callback function
        
    Returns:
        Select widget
    """
    if palettes is None:
        palettes = DEFAULT_PALETTES
    
    return create_select(
        title="Color Palette:",
        value=value,
        options=palettes,
        width=width,
        callback=callback
    )


def create_palette_section(
    label: str = "Color Palette:",
    value: str = "Viridis256",
    width: int = 200,
    callback: Optional[Callable] = None,
) -> column:
    """
    Create a complete palette selector section with label.
    
    Args:
        label: Section label
        value: Default selected palette
        width: Widget width in pixels
        callback: Optional callback function
        
    Returns:
        Column layout with label and palette selector
    """
    selector = create_palette_selector(
        value=value,
        width=width,
        callback=callback
    )
    
    return column(
        create_label_div(label, width=width),
        selector
    )


def create_plot_shape_controls(
    active: int = 0,  # 0=Square, 1=Custom, 2=Aspect Ratio
    width: int = 200,
    shape_callback: Optional[Callable] = None,
    custom_width: int = 400,
    custom_height: int = 400,
    custom_width_callback: Optional[Callable] = None,
    custom_height_callback: Optional[Callable] = None,
    scale: float = 100.0,
    scale_callback: Optional[Callable] = None,
    min_size: int = 200,
    max_size: int = 400,
    min_size_callback: Optional[Callable] = None,
    max_size_callback: Optional[Callable] = None,
) -> Tuple[RadioButtonGroup, TextInput, TextInput, TextInput, TextInput, TextInput, column, column, column]:
    """
    Create plot shape control widgets.
    
    Args:
        active: Initial shape mode (0=Square, 1=Custom, 2=Aspect Ratio)
        width: Widget width in pixels
        shape_callback: Callback for shape mode change
        custom_width: Default custom width
        custom_height: Default custom height
        custom_width_callback: Callback for custom width change
        custom_height_callback: Callback for custom height change
        scale: Default scale percentage
        scale_callback: Callback for scale change
        min_size: Default minimum size
        max_size: Default maximum size
        min_size_callback: Callback for min size change
        max_size_callback: Callback for max size change
        
    Returns:
        Tuple of (shape_selector, custom_width_input, custom_height_input, scale_input,
                 min_size_input, max_size_input, custom_controls, aspect_controls, size_limits_controls)
    """
    # Shape mode selector
    shape_selector = create_radio_button_group(
        labels=["Square", "Custom", "Aspect Ratio"],
        active=active,
        width=width,
        callback=shape_callback
    )
    
    # Custom dimensions inputs
    custom_width_input = create_text_input(
        title="Custom Width:",
        value=str(custom_width),
        width=100,
        callback=custom_width_callback
    )
    
    custom_height_input = create_text_input(
        title="Custom Height:",
        value=str(custom_height),
        width=100,
        callback=custom_height_callback
    )
    
    # Scale input for aspect ratio mode
    scale_input = create_text_input(
        title="Map Scale (%):",
        value=str(scale),
        width=100,
        callback=scale_callback
    )
    
    # Size limit inputs
    min_size_input = create_text_input(
        title="Min Map Size (px):",
        value=str(min_size),
        width=100,
        callback=min_size_callback
    )
    
    max_size_input = create_text_input(
        title="Max Map Size (px):",
        value=str(max_size),
        width=100,
        callback=max_size_callback
    )
    
    # Control containers
    custom_controls = column(
        create_label_div("Custom Map Size:", width=200),
        row(custom_width_input, custom_height_input),
    )
    
    aspect_controls = column(
        create_label_div("Map Scale:", width=200),
        scale_input,
    )
    
    size_limits_controls = column(
        create_label_div("Map Size Limits:", width=200),
        row(min_size_input, max_size_input),
    )
    
    return (
        shape_selector,
        custom_width_input,
        custom_height_input,
        scale_input,
        min_size_input,
        max_size_input,
        custom_controls,
        aspect_controls,
        size_limits_controls
    )


def create_range_mode_toggle(
    label: str = "User Specified",
    active: bool = False,
    width: int = 100,  # Changed from 150 to 100 to match other widgets (as small as possible)
    callback: Optional[Callable] = None,
) -> Toggle:
    """
    Create a toggle for range mode (User Specified vs Dynamic).
    
    Args:
        label: Toggle label
        active: Initial active state
        width: Widget width in pixels
        callback: Optional callback function
        
    Returns:
        Toggle widget
    """
    return create_toggle(
        label=label,
        active=active,
        width=width,
        callback=callback
    )


def create_range_section_with_toggle(
    label: str,
    min_title: str = "Range Min:",
    max_title: str = "Range Max:",
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
    width: int = 100,  # Changed from 120 to 100 (as small as possible)
    toggle_label: str = "User Specified",
    toggle_active: bool = False,
    toggle_callback: Optional[Callable] = None,
    min_callback: Optional[Callable] = None,
    max_callback: Optional[Callable] = None,
) -> Tuple[column, Toggle]:
    """
    Create a range input section with a toggle for dynamic/user-specified mode.
    
    Args:
        label: Section label
        min_title: Title for minimum input
        max_title: Title for maximum input
        min_value: Default minimum value
        max_value: Default maximum value
        width: Widget width in pixels
        toggle_label: Toggle label
        toggle_active: Initial toggle state
        toggle_callback: Callback for toggle change
        min_callback: Optional callback for min input
        max_callback: Optional callback for max input
        
    Returns:
        Tuple of (range_section, toggle_widget)
    """
    range_section = create_range_section(
        label=label,
        min_title=min_title,
        max_title=max_title,
        min_value=min_value,
        max_value=max_value,
        width=width,
        min_callback=min_callback,
        max_callback=max_callback
    )
    
    toggle = create_range_mode_toggle(
        label=toggle_label,
        active=toggle_active,
        width=width,  # Use same width as inputs for consistency
        callback=toggle_callback
    )
    
    return range_section, toggle


def update_range_inputs_safely(
    min_input: Optional[TextInput],
    max_input: Optional[TextInput],
    min_value: float,
    max_value: float,
    use_callback: bool = True
) -> Optional[Callable]:
    """
    Safely update range input widgets while preserving their disabled state.
    
    This function handles the common pattern of:
    1. Temporarily enabling disabled inputs
    2. Updating the values
    3. Restoring the disabled state
    
    Args:
        min_input: Minimum range input widget (can be None)
        max_input: Maximum range input widget (can be None)
        min_value: New minimum value to set
        max_value: New maximum value to set
        use_callback: If True, returns a callback function that can be used with
                     curdoc().add_next_tick_callback(). If False, updates immediately.
    
    Returns:
        If use_callback=True, returns a callable function that performs the update.
        If use_callback=False, returns None and updates immediately.
    
    Example:
        # Using with callback (recommended for Bokeh):
        from bokeh.io import curdoc
        update_func = update_range_inputs_safely(
            range1_min_input, range1_max_input, new_min, new_max, use_callback=True
        )
        curdoc().add_next_tick_callback(update_func)
        
        # Immediate update (not recommended for Bokeh):
        update_range_inputs_safely(
            range1_min_input, range1_max_input, new_min, new_max, use_callback=False
        )
    """
    def _update():
        try:
            if min_input is not None:
                was_disabled = min_input.disabled
                if was_disabled:
                    min_input.disabled = False
                min_input.value = str(min_value)
                if was_disabled:
                    min_input.disabled = True
            
            if max_input is not None:
                was_disabled = max_input.disabled
                if was_disabled:
                    max_input.disabled = False
                max_input.value = str(max_value)
                if was_disabled:
                    max_input.disabled = True
        except Exception as e:
            print(f"⚠️ WARNING: Failed to update range inputs: {e}")
            import traceback
            traceback.print_exc()
    
    if use_callback:
        return _update
    else:
        _update()
        return None

