"""
Dataset Selection UI Components

This module provides UI components for selecting datasets and coordinates,
including mode selectors (single dataset vs ratio) and coordinate selectors.
"""

from typing import Optional, List, Callable, Tuple, Dict, Any
from bokeh.models import Select, RadioButtonGroup, Toggle
from bokeh.layouts import column, row

from .SCDashUI_base_components import (
    create_select,
    create_radio_button_group,
    create_toggle,
    create_label_div,
)


def create_dataset_selector(
    title: str,
    choices: List[str],
    default_value: Optional[str] = None,
    width: int = 300,
    callback: Optional[Callable] = None,
) -> Select:
    """
    Create a dataset selector dropdown.
    
    Args:
        title: Selector title
        choices: List of dataset choices (with shape info)
        default_value: Default selected value
        width: Widget width in pixels
        callback: Optional callback function
        
    Returns:
        Select widget
    """
    if not choices:
        choices = ["No datasets available"]
    
    value = default_value if default_value is not None else choices[0]
    
    return create_select(
        title=title,
        value=value,
        options=choices,
        width=width,
        callback=callback
    )


def create_mode_selector(
    labels: List[str] = None,
    active: int = 0,
    width: int = 400,
    callback: Optional[Callable] = None,
) -> RadioButtonGroup:
    """
    Create a mode selector (e.g., Single Dataset vs Ratio).
    
    Args:
        labels: List of mode labels (default: ["Single Dataset", "Ratio (Numerator/Denominator)"])
        active: Initially active mode index
        width: Widget width in pixels
        callback: Optional callback function
        
    Returns:
        RadioButtonGroup widget
    """
    if labels is None:
        labels = ["Single Dataset", "Ratio (Numerator/Denominator)"]
    
    return create_radio_button_group(
        labels=labels,
        active=active,
        width=width,
        callback=callback
    )


def create_coordinate_selector(
    title: str,
    choices: List[str],
    default_value: str = "Use Default",
    width: int = 300,
    callback: Optional[Callable] = None,
) -> Select:
    """
    Create a coordinate selector dropdown.
    
    Args:
        title: Selector title
        choices: List of coordinate dataset choices
        default_value: Default selected value
        width: Widget width in pixels
        callback: Optional callback function
        
    Returns:
        Select widget
    """
    options = [default_value] + choices if choices else [default_value]
    
    return create_select(
        title=title,
        value=default_value,
        options=options,
        width=width,
        callback=callback
    )


def create_dataset_selection_group(
    plot_label: str,
    dataset_choices: List[str],
    default_dataset: Optional[str] = None,
    mode_labels: Optional[List[str]] = None,
    default_mode: int = 0,
    width: int = 300,
    mode_callback: Optional[Callable] = None,
    dataset_callback: Optional[Callable] = None,
    numerator_callback: Optional[Callable] = None,
    denominator_callback: Optional[Callable] = None,
) -> Tuple[RadioButtonGroup, Select, Select, Select]:
    """
    Create a complete dataset selection group with mode selector and dataset selectors.
    
    Args:
        plot_label: Label for this plot (e.g., "Plot1")
        dataset_choices: List of dataset choices
        default_dataset: Default selected dataset
        mode_labels: Mode labels (default: ["Single Dataset", "Ratio (Numerator/Denominator)"])
        default_mode: Default mode index
        width: Widget width in pixels
        mode_callback: Callback for mode change
        dataset_callback: Callback for single dataset change
        numerator_callback: Callback for numerator change
        denominator_callback: Callback for denominator change
        
    Returns:
        Tuple of (mode_selector, single_dataset_selector, numerator_selector, denominator_selector)
    """
    # Mode selector
    mode_selector = create_mode_selector(
        labels=mode_labels,
        active=default_mode,
        width=width + 100,
        callback=mode_callback
    )
    
    # Single dataset selector
    single_dataset_selector = create_dataset_selector(
        title=f"{plot_label} Dataset (2D):",
        choices=dataset_choices,
        default_value=default_dataset,
        width=width,
        callback=dataset_callback
    )
    
    # Ratio selectors
    numerator_selector = create_dataset_selector(
        title=f"{plot_label} Numerator (2D):",
        choices=dataset_choices,
        default_value=default_dataset,
        width=width,
        callback=numerator_callback
    )
    
    denominator_selector = create_dataset_selector(
        title=f"{plot_label} Denominator (2D):",
        choices=dataset_choices,
        default_value=default_dataset,
        width=width,
        callback=denominator_callback
    )
    
    return mode_selector, single_dataset_selector, numerator_selector, denominator_selector


def create_coordinate_selection_group(
    map_x_title: str = "Map X Coordinates (1D):",
    map_y_title: str = "Map Y Coordinates (1D):",
    probe_x_title: str = "Probe X Coordinates (1D):",
    probe_y_title: str = "Probe Y Coordinates (1D):",
    coord_choices: Optional[List[str]] = None,
    default_map_x: str = "Use Default",
    default_map_y: str = "Use Default",
    default_probe_x: str = "Use Default",
    default_probe_y: str = "Use Default",
    width: int = 300,
    map_x_callback: Optional[Callable] = None,
    map_y_callback: Optional[Callable] = None,
    probe_x_callback: Optional[Callable] = None,
    probe_y_callback: Optional[Callable] = None,
) -> Tuple[Select, Select, Select, Select]:
    """
    Create coordinate selectors for map and probe coordinates.
    
    Args:
        map_x_title: Title for map X coordinate selector
        map_y_title: Title for map Y coordinate selector
        probe_x_title: Title for probe X coordinate selector
        probe_y_title: Title for probe Y coordinate selector
        coord_choices: List of coordinate dataset choices
        default_map_x: Default map X coordinate
        default_map_y: Default map Y coordinate
        default_probe_x: Default probe X coordinate
        default_probe_y: Default probe Y coordinate
        width: Widget width in pixels
        map_x_callback: Callback for map X change
        map_y_callback: Callback for map Y change
        probe_x_callback: Callback for probe X change
        probe_y_callback: Callback for probe Y change
        
    Returns:
        Tuple of (map_x_selector, map_y_selector, probe_x_selector, probe_y_selector)
    """
    map_x_selector = create_coordinate_selector(
        title=map_x_title,
        choices=coord_choices or [],
        default_value=default_map_x,
        width=width,
        callback=map_x_callback
    )
    
    map_y_selector = create_coordinate_selector(
        title=map_y_title,
        choices=coord_choices or [],
        default_value=default_map_y,
        width=width,
        callback=map_y_callback
    )
    
    probe_x_selector = create_coordinate_selector(
        title=probe_x_title,
        choices=coord_choices or [],
        default_value=default_probe_x,
        width=width,
        callback=probe_x_callback
    )
    
    probe_y_selector = create_coordinate_selector(
        title=probe_y_title,
        choices=coord_choices or [],
        default_value=default_probe_y,
        width=width,
        callback=probe_y_callback
    )
    
    return map_x_selector, map_y_selector, probe_x_selector, probe_y_selector


def create_optional_plot_toggle(
    label: str,
    active: bool = False,
    width: int = 250,
    callback: Optional[Callable] = None,
) -> Toggle:
    """
    Create a toggle for enabling/disabling an optional plot (e.g., Plot1B, Plot2B).
    
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


def extract_dataset_path(selection_with_shape: str) -> str:
    """
    Extract just the dataset path from 'path (shape)' format.
    
    Args:
        selection_with_shape: Selection string with shape info
        
    Returns:
        Dataset path without shape info
    """
    if selection_with_shape in ["No 2D datasets", "No 3D/4D datasets", "Use Default", "No datasets available"]:
        return selection_with_shape
    
    # Find the last occurrence of ' (' to separate path from shape
    last_paren = selection_with_shape.rfind(' (')
    if last_paren != -1:
        return selection_with_shape[:last_paren]
    else:
        # Fallback: if no shape found, return as-is
        return selection_with_shape


def extract_shape(selection_with_shape: str) -> Optional[tuple]:
    """
    Extract shape tuple from 'path (shape1, shape2, ...)' format.
    
    Args:
        selection_with_shape: Selection string with shape info
        
    Returns:
        Shape tuple or None if not found
    """
    if not selection_with_shape or selection_with_shape in ["No 2D datasets", "No 3D/4D datasets", "Use Default", "No datasets available"]:
        return None
    
    last_paren = selection_with_shape.rfind(' (')
    if last_paren != -1:
        shape_str = selection_with_shape[last_paren+2:-1]  # Remove ' (' and ')'
        try:
            # Parse shape like "(100, 200)" or "(100, 200, 300)"
            shape = tuple(int(x.strip()) for x in shape_str.split(','))
            return shape
        except Exception:
            return None
    return None

