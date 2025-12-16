"""
Layout Builder Utilities

This module provides helper functions for building common dashboard layouts
and organizing UI components into consistent structures.
"""

from typing import List, Optional, Any, Dict, Tuple
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
    Create a tools/controls column with an outline border and 10px left padding.
    
    Args:
        items: List of widgets/components to include
        width: Column width in pixels
        sizing_mode: Sizing mode for the column
        max_height: Optional maximum height in pixels (enables scrolling)
        
    Returns:
        Column layout wrapped in a bordered container with left padding
    """
    from bokeh.layouts import column as bokeh_column, row as bokeh_row
    
    # Create the inner tools column
    # Account for: 2px border on each side (4px total) + 10px left padding = 14px
    inner_width = width - 14
    inner_col = column(*items, width=inner_width, sizing_mode=sizing_mode)
    if max_height:
        inner_col.height = max_height
        inner_col.sizing_mode = "fixed"
    
    # Create a left padding spacer (10px)
    left_padding = create_spacer(width=10, height=1)
    
    # Create a row with left padding and the tools column
    content_row = bokeh_row(left_padding, inner_col, sizing_mode="fixed")
    content_row.width = width - 4  # Account for 2px border on each side
    
    # Create the final bordered wrapper column
    # The content_row already has 10px left padding
    # Now we need to add a border around it
    wrapper_col = bokeh_column(content_row, sizing_mode="fixed", width=width)
    
    # Add border by using CSS classes
    # Bokeh columns can have CSS classes applied
    wrapper_col.css_classes = ["bordered-tools-wrapper"]
    
    # Create a style div that will inject CSS for the border
    # This CSS will style the column with the border class
    style_div = create_div(
        text=f"""
        <style>
        .bordered-tools-wrapper {{
            border: 2px solid #ccc !important;
            border-radius: 4px !important;
            padding-left: 0 !important;  /* Padding already in content_row */
            box-sizing: border-box !important;
        }}
        </style>
        """,
        width=1,
        height=1,
        styles={"display": "none"}  # Hide the style div
    )
    
    # Create final wrapper with style and content
    final_wrapper = bokeh_column(style_div, wrapper_col, sizing_mode="fixed", width=width)
    
    return final_wrapper


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
    return column(*items, sizing_mode=sizing_mode, spacing=0)  # Minimal spacing between widgets


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
    #items = [create_label_div(label, width=width)]
    items = []

    if toggle:
        items.append(toggle)
    
    min_input, max_input = range_inputs
    items.append(row(min_input, max_input, spacing=0))  # Minimal spacing between min and max inputs
    
    return column(*items, sizing_mode="stretch_width", spacing=0)  # Minimal spacing between widgets


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


def create_plot_with_controls_side_by_side(
    plot: Any,
    controls_column: column,
    controls_width: int = 200,
    sizing_mode: str = "stretch_both",
    plot_label: Optional[str] = None,
) -> column:
    """
    Create a plot with controls on the left and plot on the right, with optional label above.
    
    Args:
        plot: Plot widget
        controls_column: Column of control widgets (Min, Max, dynamic/userselected, Linear/Log)
        controls_width: Width of the controls column
        sizing_mode: Sizing mode for the row
        plot_label: Optional label text to display above the entire row (controls + plot)
        
    Returns:
        Column layout with label (if provided), then row with controls on left, plot on right
    """
    # Set width for controls column - keep it fixed width
    controls_column.width = controls_width
    controls_column.sizing_mode = "fixed"
    
    # Create the row with controls and plot
    plot_row = row(controls_column, plot, sizing_mode="scale_width")
    
    # If label is provided, add it above the entire row (spanning controls + plot)
    if plot_label:
        label_div = create_div(
            text=f"<div style='font-weight: bold; font-size: 14px; padding: 5px 0; text-align: left;'>{plot_label}</div>"
        )
        # Create column with label and plot row
        result_column = column(label_div, plot_row, sizing_mode="stretch_width")
        return result_column
    else:
        return column(plot_row, sizing_mode="stretch_width")


def create_collapsible_tools_column(
    items: List[Any],
    width: int = 260, #was 400
    collapsed_width: int = 50,
    initial_collapsed: bool = False,
) -> Tuple[column, Any]:
    """
    Create a collapsible tools/controls column.
    
    Args:
        items: List of widgets/components to include
        width: Column width when expanded
        collapsed_width: Column width when collapsed
        initial_collapsed: Whether column starts collapsed
        
    Returns:
        Tuple of (column layout with toggle, toggle button)
    """
    from bokeh.models import Button
    
    # Create the tools column
    tools_col = column(*items, width=width if not initial_collapsed else collapsed_width, sizing_mode="fixed")
    
    # Create toggle button
    toggle_button = Button(label="◀" if not initial_collapsed else "▶", width=30, height=30)
    
    # Store state in a mutable container to work with closures
    state = {"is_collapsed": initial_collapsed}
    
    def toggle_callback():
        state["is_collapsed"] = not state["is_collapsed"]
        if state["is_collapsed"]:
            tools_col.width = collapsed_width
            toggle_button.label = "▶"
            # Hide all items except the button
            for item in items:
                if hasattr(item, 'visible'):
                    item.visible = False
        else:
            tools_col.width = width
            toggle_button.label = "◀"
            # Show all items
            for item in items:
                if hasattr(item, 'visible'):
                    item.visible = True
    
    toggle_button.on_click(toggle_callback)
    
    # Add toggle button at the top of the column
    tools_col_with_toggle = column(toggle_button, tools_col, sizing_mode="fixed")
    
    return tools_col_with_toggle, toggle_button


def create_optimized_dashboard_layout(
    tools_column: column,
    plot1a_controls: column,
    plot1a_plot: Any,
    plot2a_controls: column,
    plot2a_plot: Any,
    plot3_controls: column,
    plot3_plot: Any,
    plot2b_controls: Optional[column] = None,
    plot2b_plot: Optional[Any] = None,
    x_slider: Optional[Any] = None,
    y_slider: Optional[Any] = None,
    sliders_column: Optional[Any] = None,
    status_display: Optional[Div] = None,
    tools_width: int = 260, #was 400
    controls_width: int = 200,
    sizing_mode: str = "stretch_both",
) -> column:
    """
    Create the optimized dashboard layout with two columns:
    - Tools column (collapsible) on the left
    - Plot column on the right with specific layout:
      - x,y sliders (empty/placeholder)
      - Plot1a | Plot2a (side by side)
      - Plot3 | Plot2b (side by side)
    
    Each plot has controls on the left and plot on the right.
    
    Args:
        tools_column: Tools/controls column (will be made collapsible)
        plot1a_controls: Controls column for Plot1a
        plot1a_plot: Plot widget for Plot1a
        plot2a_controls: Controls column for Plot2a
        plot2a_plot: Plot widget for Plot2a
        plot3_controls: Controls column for Plot3
        plot3_plot: Plot widget for Plot3
        plot2b_controls: Optional controls column for Plot2b
        plot2b_plot: Optional plot widget for Plot2b
        x_slider: Optional X slider widget
        y_slider: Optional Y slider widget
        status_display: Optional status display widget
        tools_width: Width of tools column when expanded
        controls_width: Width of controls column for each plot
        sizing_mode: Sizing mode for the main layout
        
    Returns:
        Main dashboard column layout
    """
    from bokeh.models import Button
    
    # Make tools column collapsible
    # Store the original width
    original_width = tools_column.width if hasattr(tools_column, 'width') else tools_width
    collapsed_width = 0  # Collapse to 0 width so plot column takes full space
    button_width = 30  # Width for the toggle button
    tools_column.width = original_width
    tools_column.sizing_mode = "fixed"
    
    # Create toggle button - positioned on left edge like the example
    toggle_button = Button(
        label="◀",
        width=30,
        height=30,
        button_type="default",
        css_classes=["collapse-btn", "left"]
    )
    
    # Create header div for the tools panel
    header_div = create_div(
        text="""<div style='padding: 3px; background-color: #f0f0f0; border-bottom: 1px solid #ccc;  .collapse-btn {
            position: relative;
            z-index: 1000;
            border-radius: 0 4px 4px 0;
            margin: 5px 0;
        }
        .collapse-btn.left {
            margin-left: 0;
        }'><b>Tools Panel</b></div>""",
        width=original_width
    )
    #   # Add CSS styling for the collapse button (similar to the example)
    # css_style = create_div(text="""
    #     <style>
    #     .collapse-btn {
    #         position: relative;
    #         z-index: 1000;
    #         border-radius: 0 4px 4px 0;
    #         margin: 5px 0;
    #     }
    #     .collapse-btn.left {
    #         margin-left: 0;
    #     }
    #     </style>
    # """)
    # Create toggle container - when collapsed, this will be narrow with just the button
    toggle_container = column(
        row(toggle_button,  
        header_div),
        sizing_mode="fixed",
        width=original_width,
        margin=(0, 0, 0, 0)  # No margin so button is flush with left edge
    )
    
    # Store state
    state = {"is_collapsed": False}
    
    def toggle_callback():
        state["is_collapsed"] = not state["is_collapsed"]
        if state["is_collapsed"]:
            # Collapse: hide tools column content, keep only button visible
            tools_column.visible = False  # Hide the entire tools column content
            header_div.visible = False  # Hide header when collapsed
            toggle_button.label = "▶"
            toggle_button.width = button_width
            # Set container widths to button width so plot column expands
            toggle_container.width = button_width
            tools_col_with_toggle.width = button_width
            # Make sure toggle container only shows button
            toggle_container.visible = True
        else:
            # Expand: restore original width
            tools_column.visible = True  # Show the tools column content
            header_div.visible = True  # Show header when expanded
            toggle_button.label = "◀"
            toggle_button.width = button_width
            # Restore full width
            toggle_container.width = original_width
            tools_col_with_toggle.width = original_width
            tools_column.width = original_width
            # Show all children
            for child in toggle_container.children:
                if hasattr(child, 'visible'):
                    child.visible = True
            for child in tools_column.children:
                if hasattr(child, 'visible'):
                    child.visible = True
    
    toggle_button.on_click(toggle_callback)
    
    # Create column with toggle button and tools
    # When collapsed, this will be just the button width
    tools_col_with_toggle = column( tools_column, sizing_mode="fixed", width=original_width)
    
    # Position the toggle button to be visible on the left edge when collapsed
    # We'll use CSS to position it absolutely when needed
    
    # Create plot with controls for each plot
    # Use stretch_both for proper layout
    # Add labels above each plot
    # For Plot1a, add sliders above it if provided
    plot1a_with_controls = create_plot_with_controls_side_by_side(
        plot1a_plot,
        plot1a_controls,
        controls_width=controls_width,
        sizing_mode="stretch_both",
        plot_label="Projection -- file"
    )
    
    # Add sliders above Plot1a if provided
    # Calculate spacer height to match sliders (slider height is typically ~50px)
    slider_spacer_height = 50  # Approximate height of slider row
    if sliders_column is not None:
        plot1a_row = column(sliders_column, plot1a_with_controls, sizing_mode="stretch_width")
        # Try to get actual height from sliders_column if available
        if hasattr(sliders_column, 'height') and sliders_column.height:
            slider_spacer_height = sliders_column.height
        elif hasattr(sliders_column, 'children') and len(sliders_column.children) > 0:
            # Check if first child (sliders_row) has a height
            first_child = sliders_column.children[0]
            if hasattr(first_child, 'height') and first_child.height:
                slider_spacer_height = first_child.height
    else:
        # Fallback to individual sliders if sliders_column not provided
        slider_row_items = []
        if x_slider:
            slider_row_items.append(x_slider)
        if y_slider:
            slider_row_items.append(y_slider)
        if slider_row_items:
            slider_row = row(*slider_row_items, sizing_mode="stretch_width")
            plot1a_row = column(slider_row, plot1a_with_controls, sizing_mode="stretch_width")
            # Try to get height from slider
            if x_slider and hasattr(x_slider, 'height') and x_slider.height:
                slider_spacer_height = x_slider.height
        else:
            plot1a_row = plot1a_with_controls
            slider_spacer_height = 0  # No sliders, no spacer needed
    
    plot2a_with_controls = create_plot_with_controls_side_by_side(
        plot2a_plot,
        plot2a_controls,
        controls_width=controls_width,
        sizing_mode="stretch_both",
        plot_label="Probe 1"
    )
    
    # Add spacer above Plot2a to align with sliders above Plot1a
    if slider_spacer_height > 0:
        plot2a_spacer = create_spacer(height=slider_spacer_height)
        plot2a_row = column(plot2a_spacer, plot2a_with_controls, sizing_mode="stretch_width")
    else:
        plot2a_row = plot2a_with_controls
    
    plot3_row = create_plot_with_controls_side_by_side(
        plot3_plot,
        plot3_controls,
        controls_width=controls_width,
        sizing_mode="stretch_both",
        plot_label="Projection -- generated"
    )
    
    # Create Plot1a | Plot2a row
    # Use stretch_width for horizontal expansion, but maintain aspect ratio
    plots_row_1 = row(plot1a_row, plot2a_row, sizing_mode="stretch_width")
    
    # Create Plot3 | Plot2b row
    plot2b_row = None
    if plot2b_controls and plot2b_plot:
        plot2b_with_controls = create_plot_with_controls_side_by_side(
            plot2b_plot,
            plot2b_controls,
            controls_width=controls_width,
            sizing_mode="stretch_both",
            plot_label="Probe 2"
        )
        # Add spacer above Plot2b to align with sliders above Plot1a
        if slider_spacer_height > 0:
            plot2b_spacer = create_spacer(height=slider_spacer_height)
            plot2b_row = column(plot2b_spacer, plot2b_with_controls, sizing_mode="stretch_width")
        else:
            plot2b_row = plot2b_with_controls
        plots_row_2 = row(plot3_row, plot2b_row, sizing_mode="stretch_width")
    else:
        # If Plot2b doesn't exist, just show Plot3
        plots_row_2 = row(plot3_row, sizing_mode="stretch_width")
    
    # Create plot column - use stretch_width for horizontal expansion, but maintain vertical space
    plot_column = column(
        plots_row_1,
        plots_row_2,
        sizing_mode="stretch_width"  # Only stretch horizontally, maintain vertical space
    )
    # Create a simple vertical line divider between tools and plot columns
    divider_line = create_div(
        text="",
        width=2,
        styles={
            "background-color": "#ccc",
            "width": "2px",
            "min-height": "100%",
            "margin-right": "10px",
        }
    )
    
    # Create main layout: Tools column | Divider line | Plot column
    # Use scale_width so plot column expands horizontally when tools column collapses
    # But don't affect vertical sizing - plots should maintain their height
    main_row = row(tools_col_with_toggle, divider_line, plot_column, sizing_mode="scale_width")
    
    # Add status display if provided
    items = [main_row]
    if status_display:
        items.append(status_display)
    
    # Create main container with CSS for the collapse button
    main_container = column(*items, sizing_mode="stretch_width")
    

    
    return column(toggle_container, main_container, sizing_mode="stretch_width")

