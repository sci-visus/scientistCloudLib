# SCDashUI - Dashboard UI Component Library

This library provides reusable UI components extracted from the `4d_dashboard.py` file, enabling the creation of dashboard interfaces with consistent styling and behavior.

## Overview

The SCDashUI library is organized into several modules:

1. **SCDashUI_base_components.py** - Basic UI widget factories
2. **SCDashUI_plot_controls.py** - Plot-specific controls (range, color, shape)
3. **SCDashUI_dataset_selectors.py** - Dataset selection UI components
4. **SCDashUI_layout_builders.py** - Layout construction helpers
5. **SCDashUI_sync.py** - State synchronization utilities

## Basic Components

### Creating Basic Widgets

```python
from SCLib_Dashboards import (
    create_select,
    create_slider,
    create_button,
    create_toggle,
    create_text_input,
    create_radio_button_group,
    create_div,
)

# Create a dropdown selector
dataset_selector = create_select(
    title="Dataset:",
    value="dataset1",
    options=["dataset1", "dataset2", "dataset3"],
    width=300
)

# Create a slider
x_slider = create_slider(
    title="X Position",
    start=0.0,
    end=10.0,
    value=5.0,
    step=0.01,
    width=200
)

# Create a button
init_button = create_button(
    label="Initialize",
    button_type="primary",
    width=200,
    callback=initialize_callback
)
```

## Plot Controls

### Range Inputs

```python
from SCLib_Dashboards import create_range_section

# Create a range input section
range_section = create_range_section(
    label="Map Range:",
    min_title="Map Range Min:",
    max_title="Range Max:",
    min_value=0.0,
    max_value=100.0,
    width=120
)
```

### Color Scale and Palette

```python
from SCLib_Dashboards import (
    create_color_scale_section,
    create_palette_section,
)

# Create color scale selector
color_scale_section = create_color_scale_section(
    label="Color Scale:",
    active=0,  # 0=Linear, 1=Log
    callback=on_color_scale_change
)

# Create palette selector
palette_section = create_palette_section(
    label="Color Palette:",
    value="Viridis256",
    callback=on_palette_change
)
```

### Plot Shape Controls

```python
from SCLib_Dashboards import create_plot_shape_controls

# Create plot shape controls
(
    shape_selector,
    custom_width_input,
    custom_height_input,
    scale_input,
    min_size_input,
    max_size_input,
    custom_controls,
    aspect_controls,
    size_limits_controls
) = create_plot_shape_controls(
    active=0,  # 0=Square, 1=Custom, 2=Aspect Ratio
    shape_callback=on_shape_change,
    custom_width_callback=on_width_change,
    custom_height_callback=on_height_change
)
```

## Dataset Selectors

### Dataset Selection Group

```python
from SCLib_Dashboards import create_dataset_selection_group

# Create a complete dataset selection group
mode_selector, single_selector, numerator_selector, denominator_selector = \
    create_dataset_selection_group(
        plot_label="Plot1",
        dataset_choices=["dataset1 (100, 200)", "dataset2 (150, 250)"],
        default_mode=1,  # Ratio mode
        mode_callback=on_mode_change,
        dataset_callback=on_dataset_change,
        numerator_callback=on_numerator_change,
        denominator_callback=on_denominator_change
    )
```

### Coordinate Selectors

```python
from SCLib_Dashboards import create_coordinate_selection_group

# Create coordinate selectors
map_x, map_y, probe_x, probe_y = create_coordinate_selection_group(
    coord_choices=["coord1 (100)", "coord2 (200)"],
    default_map_x="Use Default",
    map_x_callback=on_map_x_change
)
```

## Layout Builders

### Creating Dashboard Layouts

```python
from SCLib_Dashboards import (
    create_tools_column,
    create_plot_column,
    create_plots_row,
    create_dashboard_layout,
)

# Create tools column
tools = create_tools_column([
    x_slider,
    y_slider,
    color_scale_section,
    palette_section
], width=400)

# Create plot columns
plot1_col = create_plot_column([range_section, plot1])
plot2_col = create_plot_column([plot2])

# Create plots row
plots = create_plots_row([plot1_col, plot2_col])

# Create main dashboard layout
dashboard = create_dashboard_layout(
    tools_column=tools,
    plots_row=plots,
    status_display=status_div
)
```

## State Synchronization

### Syncing UI with Plot Objects

```python
from SCLib_Dashboards import (
    sync_plot_to_range_inputs,
    sync_range_inputs_to_plot,
    sync_all_plot_ui,
)

# Sync plot state to UI widgets
sync_plot_to_range_inputs(plot, min_input, max_input)

# Sync UI widgets to plot state
sync_range_inputs_to_plot(plot, min_input, max_input)

# Sync all UI widgets at once
sync_all_plot_ui(
    plot,
    min_input,
    max_input,
    color_scale_selector,
    palette_selector,
    shape_selector,
    custom_width_input,
    custom_height_input
)
```

### Creating Sync Callbacks

```python
from SCLib_Dashboards import create_sync_callbacks

# Create callbacks that automatically sync UI to plot
callbacks = create_sync_callbacks(
    plot,
    min_input,
    max_input,
    color_scale_selector,
    palette_selector
)

# Attach callbacks to widgets
min_input.on_change("value", callbacks["range"])
max_input.on_change("value", callbacks["range"])
color_scale_selector.on_change("active", callbacks["color_scale"])
palette_selector.on_change("value", callbacks["palette"])
```

## Complete Example

```python
from SCLib_Dashboards import (
    MAP_2DPlot,
    create_range_section,
    create_color_scale_section,
    create_palette_section,
    create_tools_column,
    create_plot_column,
    create_dashboard_layout,
    sync_all_plot_ui,
)

# Create a plot
plot = MAP_2DPlot(
    title="Sample Map",
    data=my_data,
    x_coords=x_coords,
    y_coords=y_coords
)

# Create UI controls
range_section = create_range_section(
    label="Range:",
    min_value=0.0,
    max_value=100.0
)

color_scale = create_color_scale_section(
    label="Color Scale:",
    callback=lambda attr, old, new: plot.set_color_scale(
        ColorScale.LOG if new == 1 else ColorScale.LINEAR
    )
)

palette = create_palette_section(
    label="Palette:",
    callback=lambda attr, old, new: plot.set_palette(new)
)

# Create layout
tools = create_tools_column([range_section, color_scale, palette])
plot_col = create_plot_column([plot_widget])  # plot_widget is the Bokeh figure
dashboard = create_dashboard_layout(tools, create_plots_row([plot_col]))

# Sync initial state
sync_all_plot_ui(plot, min_input, max_input, color_scale_selector, palette_selector)
```

## Integration with Existing Dashboard

These UI components are designed to replace the inline widget creation in `4d_dashboard.py`. Instead of:

```python
# Old way
range1_min_input = TextInput(title="Map Range Min:", value="0", width=120)
range1_max_input = TextInput(title="Map Range Max:", value="100", width=120)
```

Use:

```python
# New way
from SCLib_Dashboards import create_range_inputs
min_input, max_input = create_range_inputs(
    min_title="Map Range Min:",
    max_title="Map Range Max:",
    min_value=0.0,
    max_value=100.0,
    width=120
)
```

This provides:
- Consistent styling
- Reusable components
- Better state management
- Easier testing and maintenance

