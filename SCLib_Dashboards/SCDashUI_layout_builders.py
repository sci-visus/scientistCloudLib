"""
Layout Builder Utilities

This module provides helper functions for building common dashboard layouts
and organizing UI components into consistent structures.
"""

from typing import List, Optional, Any, Dict
from bokeh.models import Div
from bokeh.layouts import column, row

from .SCDashUI_base_components import create_div, create_label_div, create_spacer


def create_tools_column(
    items: List[Any],
    width: int = 400,
    sizing_mode: str = "fixed",
    max_height: Optional[int] = None,
) -> column:
    """
    Create a tools/controls column.
    
    Args:
        items: List of widgets/components to include
        width: Column width in pixels
        sizing_mode: Sizing mode for the column
        max_height: Optional maximum height in pixels (enables scrolling)
        
    Returns:
        Column layout
    """
    col = column(*items, width=width, sizing_mode=sizing_mode)
    if max_height:
        col.height = max_height
        col.sizing_mode = "fixed"
    return col


def create_plot_column(
    items: List[Any],
    sizing_mode: str = "scale_width",
) -> column:
    """
    Create a plot column layout.
    
    Args:
        items: List of widgets/components to include
        sizing_mode: Sizing mode for the column
        
    Returns:
        Column layout
    """
    return column(*items, sizing_mode=sizing_mode)


def create_plots_row(
    plot_columns: List[column],
    sizing_mode: str = "stretch_both",
) -> row:
    """
    Create a row of plot columns.
    
    Args:
        plot_columns: List of plot column layouts
        sizing_mode: Sizing mode for the row
        
    Returns:
        Row layout
    """
    return row(*plot_columns, sizing_mode=sizing_mode)


def create_dashboard_layout(
    tools_column: column,
    plots_row: row,
    status_display: Optional[Div] = None,
    sizing_mode: str = "stretch_width",
) -> column:
    """
    Create the main dashboard layout.
    
    Args:
        tools_column: Tools/controls column
        plots_row: Row of plot columns
        status_display: Optional status display widget
        sizing_mode: Sizing mode for the main layout
        
    Returns:
        Main dashboard column layout
    """
    items = [
        row(tools_column, plots_row, sizing_mode=sizing_mode)
    ]
    
    if status_display:
        items.append(status_display)
    
    return column(*items)


def create_section(
    title: str,
    items: List[Any],
    width: Optional[int] = None,
) -> column:
    """
    Create a titled section with items.
    
    Args:
        title: Section title
        items: List of widgets/components
        width: Optional section width
        
    Returns:
        Column layout with title and items
    """
    section_items = [create_label_div(title, width=width)]
    section_items.extend(items)
    return column(*section_items)


def create_button_row(
    buttons: List[Any],
    status_div: Optional[Div] = None,
    sizing_mode: str = "stretch_width",
) -> row:
    """
    Create a row of buttons with optional status display.
    
    Args:
        buttons: List of button widgets
        status_div: Optional status display widget
        sizing_mode: Sizing mode for the row
        
    Returns:
        Row layout
    """
    items = list(buttons)
    if status_div:
        items.append(status_div)
    return row(*items, sizing_mode=sizing_mode)


def create_range_section_layout(
    label: str,
    range_inputs: tuple,  # (min_input, max_input)
    toggle: Optional[Any] = None,
    width: int = 200,
) -> column:
    """
    Create a range input section layout.
    
    Args:
        label: Section label
        range_inputs: Tuple of (min_input, max_input) widgets
        toggle: Optional toggle widget
        width: Section width
        
    Returns:
        Column layout
    """
    items = [create_label_div(label, width=width)]
    
    if toggle:
        items.append(toggle)
    
    min_input, max_input = range_inputs
    items.append(row(min_input, max_input))
    
    return column(*items, sizing_mode="stretch_width")


def create_plot_with_controls(
    plot: Any,
    controls: List[Any],
    sizing_mode: str = "scale_width",
) -> column:
    """
    Create a plot with associated controls above it.
    
    Args:
        plot: Plot widget
        controls: List of control widgets
        sizing_mode: Sizing mode
        
    Returns:
        Column layout with controls and plot
    """
    items = list(controls)
    items.append(plot)
    return column(*items, sizing_mode=sizing_mode)


def create_plot_with_controls_and_buttons(
    plot: Any,
    controls: List[Any],
    buttons: List[Any],
    status_div: Optional[Div] = None,
    sizing_mode: str = "scale_width",
) -> column:
    """
    Create a plot with controls above and buttons below.
    
    Args:
        plot: Plot widget
        controls: List of control widgets (above plot)
        buttons: List of button widgets (below plot)
        status_div: Optional status display widget
        sizing_mode: Sizing mode
        
    Returns:
        Column layout
    """
    items = list(controls)
    items.append(plot)
    
    button_row = create_button_row(buttons, status_div)
    items.append(button_row)
    
    return column(*items, sizing_mode=sizing_mode)


def create_aligned_plot_columns(
    plot1_column: column,
    plot2_column: column,
    plot3_column: Optional[column] = None,
    spacer_height: int = 70,
) -> List[column]:
    """
    Create aligned plot columns with spacers for consistent alignment.
    
    Args:
        plot1_column: First plot column
        plot2_column: Second plot column
        plot3_column: Optional third plot column
        spacer_height: Height for alignment spacers
        
    Returns:
        List of aligned plot columns
    """
    columns = [plot1_column]
    
    if plot3_column:
        columns.append(plot2_column)
        columns.append(plot3_column)
    else:
        columns.append(plot2_column)
    
    return columns


def create_status_display(
    title: str,
    content: str = "",
    width: int = 800,
    datasets_info: Optional[List[str]] = None,
    instructions: Optional[str] = None,
) -> Div:
    """
    Create a status display widget.
    
    Args:
        title: Display title
        content: Additional content
        width: Widget width
        datasets_info: Optional list of dataset information strings
        instructions: Optional instructions text
        
    Returns:
        Div widget with formatted status display
    """
    html_parts = [f"<h3>{title}</h3>"]
    
    if datasets_info:
        html_parts.append("<p><b>Selected Datasets:</b></p><ul>")
        for info in datasets_info:
            html_parts.append(f"<li>{info}</li>")
        html_parts.append("</ul>")
    
    if instructions:
        html_parts.append(f"<p><b>Instructions:</b></p>{instructions}")
    
    if content:
        html_parts.append(f"<p>{content}</p>")
    
    return create_div(text="".join(html_parts), width=width)


def create_initialization_layout(
    title: str,
    plot1_section: column,
    plot2_section: column,
    initialize_button: Any,
    status_display: Optional[Div] = None,
) -> column:
    """
    Create the initial dataset selection layout.
    
    Args:
        title: Layout title
        plot1_section: Plot1 configuration section
        plot2_section: Plot2 configuration section
        initialize_button: Initialize button widget
        status_display: Optional status display
        
    Returns:
        Column layout for initialization
    """
    # Create main content row - constrain it to prevent taking all vertical space
    main_content = row(plot1_section, plot2_section, sizing_mode="stretch_width")
    
    # Build items list - ensure proper vertical stacking
    items = [
        create_div(text=f"<h2>{title}</h2>"),
        main_content
    ]
    
    # Add status display at the bottom, outside the main content row
    # This ensures it doesn't overlap with plot sections
    if status_display:
        items.append(create_div(text="<hr>", width=800))  # Separator
        # Add status display directly - don't wrap in extra container
        # Set explicit height to prevent it from expanding
        if hasattr(status_display, 'height') and status_display.height:
            pass  # Already has height
        else:
            status_display.height = 200  # Set a reasonable height
        items.append(status_display)
    
    # Use "fixed" sizing mode to ensure items stack vertically without overlap
    # This prevents items from trying to fill all available space
    return column(*items, sizing_mode="fixed")

