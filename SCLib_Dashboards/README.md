# SCLib_Dashboards - Dashboard Plot Library

A generic plot class system for dashboard visualizations with comprehensive state management, change tracking, and session persistence.

## Features

- **Generic Base Plot Class**: Extensible base class with all common plot functionality
- **Specialized Plot Types**: Pre-configured classes for MAP_2DPlot, PROBE_2DPlot, and PROBE_1DPlot
- **State Management**: Save and load plot states as JSON (with or without data)
- **Change Tracking**: Automatic logging of all state changes for user experience analysis
- **Session Management**: Manage multiple plots together with session-level state persistence
- **Range Management**: Dynamic or user-specified color/data ranges
- **Plot Configuration**: Flexible plot shape (square, custom, aspect ratio)
- **Interactive Features**: Crosshairs, selection regions, and coordinate systems

## Installation

The library is part of the `scientistCloudLib` package. Import it as:

```python
from SCLib_Dashboards import (
    MAP_2DPlot,
    PROBE_2DPlot,
    PROBE_1DPlot,
    PlotSession,
    ColorScale,
    PlotShapeMode,
    RangeMode,
)
```

## Quick Start

### Creating a 2D Map Plot

```python
import numpy as np
from SCLib_Dashboards import MAP_2DPlot, ColorScale, RangeMode

# Create sample data
x_coords = np.linspace(0, 10, 100)
y_coords = np.linspace(0, 10, 100)
data = np.random.rand(100, 100) * 100

# Create the plot
map_plot = MAP_2DPlot(
    title="My Map View",
    data=data,
    x_coords=x_coords,
    y_coords=y_coords,
    palette="Viridis256",
    color_scale=ColorScale.LINEAR,
    range_mode=RangeMode.DYNAMIC,
    crosshairs_enabled=True,
    crosshair_x=5.0,
    crosshair_y=5.0,
)

# Get state
state = map_plot.get_state(include_data=False)
print(state)
```

### Creating a 1D Probe Plot

```python
from SCLib_Dashboards import PROBE_1DPlot

# Create sample 1D data
x_coords = np.linspace(0, 100, 1000)
data = np.sin(x_coords / 10) * np.exp(-x_coords / 50)

# Create the plot
probe_plot = PROBE_1DPlot(
    title="Probe View",
    data=data,
    x_coords=x_coords,
    x_axis_label="Energy (keV)",
    y_axis_label="Intensity",
    select_region_enabled=True,
    select_region_min_x=20.0,
    select_region_max_x=80.0,
)

# Get selection range
select_range = probe_plot.get_select_range()
print(f"Selection: {select_range}")
```

### Managing a Session

```python
from SCLib_Dashboards import PlotSession

# Create a session
session = PlotSession(
    session_id="my_session",
    metadata={
        "user_id": "user123",
        "dataset_id": "dataset456"
    }
)

# Add plots
session.add_plot("map1", map_plot)
session.add_plot("probe1", probe_plot)

# Save session
session.save_session("my_session.json", include_data=False)

# Export change log
session.export_change_log("my_session_changes.json", format="json")
```

## Core Classes

### BasePlot

The base class for all plots. Provides:

- **Range Management**: `set_range()`, `reset_range()`, dynamic calculation
- **Color Configuration**: `set_palette()`, `set_color_scale()`
- **Crosshairs**: `set_crosshair()` with x, y coordinates
- **Selection Region**: `set_select_region()` for rectangle selection
- **State Management**: `get_state()`, `load_state()`, `reset_state()`
- **Change Tracking**: Automatic logging of all property changes

### MAP_2DPlot

Specialized for 2D map visualizations:
- Validates 2D data
- Default crosshairs enabled
- Coordinate system support
- Methods: `get_data_shape()`, `get_coordinate_ranges()`

### PROBE_2DPlot

Specialized for 2D probe data (e.g., from 4D volumes):
- Validates 2D data
- Supports z/u dimension coordinates
- Methods: `get_data_shape()`

### PROBE_1DPlot

Specialized for 1D line plots:
- Validates 1D data
- Selection range support (min_x, max_x)
- Methods: `get_data_length()`, `get_x_range()`, `get_y_range()`, `set_select_range()`

### PlotSession

Manages multiple plots together:
- Add/remove plots: `add_plot()`, `remove_plot()`
- Session state: `get_session_state()`, `save_session()`, `load_session()`
- Change logging: `get_change_log()`, `export_change_log()`

## State Management

### Saving State

```python
# Save state without data (compact)
state_json = plot.get_state_json(include_data=False)

# Save state with data (complete)
state_json = plot.get_state_json(include_data=True)

# Save to file
with open("plot_state.json", "w") as f:
    f.write(state_json)
```

### Loading State

```python
# Load from JSON string
plot.load_state(state_json, restore_data=False)

# Load from file
with open("plot_state.json", "r") as f:
    state_json = f.read()
plot.load_state(state_json, restore_data=True)
```

### Session State

```python
# Save entire session
session.save_session("session.json", include_data=False)

# Load session
new_session = PlotSession()
new_session.load_session("session.json", restore_data=False)
```

## Change Tracking

All plots automatically track state changes when `track_changes=True`:

```python
# Get change history
changes = plot.get_change_history()
for change in changes:
    print(f"{change['timestamp']}: {change['action']} - {change['details']}")

# Export change log
session.export_change_log("changes.json", format="json")
session.export_change_log("changes.txt", format="txt")
```

## Configuration Options

### Color Scale

```python
from SCLib_Dashboards import ColorScale

plot.set_color_scale(ColorScale.LINEAR)  # or ColorScale.LOG
```

### Plot Shape

```python
from SCLib_Dashboards import PlotShapeMode

# Square mode
plot.plot_shape_mode = PlotShapeMode.SQUARE

# Custom dimensions
plot.plot_shape_mode = PlotShapeMode.CUSTOM
plot.plot_width = 600
plot.plot_height = 400

# Aspect ratio mode
plot.plot_shape_mode = PlotShapeMode.ASPECT_RATIO
plot.plot_scale = 80.0  # 80% of max size

# Calculate dimensions
width, height = plot.calculate_plot_dimensions()
```

### Range Mode

```python
from SCLib_Dashboards import RangeMode

# Dynamic (auto-calculated from data)
plot.range_mode = RangeMode.DYNAMIC
plot.reset_range()

# User specified
plot.set_range(min_val=10.0, max_val=90.0, mode=RangeMode.USER_SPECIFIED)
```

## API Reference

### BasePlot Methods

- `get_state(include_data=False)` - Get current state as dictionary
- `get_state_json(include_data=False)` - Get current state as JSON string
- `load_state(state, restore_data=False)` - Load state from dict/JSON
- `reset_state()` - Reset to initial state
- `reset_range()` - Reset range to dynamic calculation
- `set_range(min_val, max_val, mode)` - Set color range
- `set_palette(palette)` - Set color palette
- `set_color_scale(scale)` - Set color scale (LINEAR/LOG)
- `set_crosshair(x, y, enabled)` - Set crosshair position
- `set_select_region(min_x, min_y, max_x, max_y, enabled)` - Set selection region
- `update_data(data)` - Update plot data
- `calculate_plot_dimensions()` - Calculate plot size based on shape mode
- `get_change_history()` - Get list of state changes
- `clear_change_history()` - Clear change history

### PlotSession Methods

- `add_plot(plot_id, plot)` - Add a plot to the session
- `get_plot(plot_id)` - Get a plot by ID
- `remove_plot(plot_id)` - Remove a plot from the session
- `get_session_state(include_data=False)` - Get complete session state
- `save_session(filepath, include_data=False)` - Save session to file
- `load_session(filepath, restore_data=False)` - Load session from file
- `get_change_log()` - Get combined change log from all plots
- `export_change_log(filepath, format="json")` - Export change log to file
- `clear_change_logs()` - Clear all change logs
- `reset_session()` - Reset all plots to initial states

## Examples

See `example_usage.py` for comprehensive examples of:
- Creating different plot types
- Configuring plot properties
- Managing sessions
- Saving and loading states
- Tracking changes

## Design Notes

### Axis Flipping

The `needs_flip` property is included in the base class but the actual flipping logic is left to the GUI implementation layer. This allows the plot class to track the flip state without being tied to a specific visualization library (Bokeh, Matplotlib, etc.).

### Data Storage

Data arrays are stored as NumPy arrays. When serializing to JSON:
- With `include_data=True`: Data is converted to lists (can be large)
- With `include_data=False`: Only metadata is saved (compact)

### Change Tracking

Change tracking is optional (`track_changes` parameter) to allow for performance optimization when tracking is not needed. Each change record includes:
- Timestamp
- Action name
- Change details (old/new values)
- State snapshot (without data)

## Future Enhancements

- Integration with Bokeh/Matplotlib for actual rendering
- Plot factory functions for common configurations
- Validation helpers for data/coordinate compatibility
- Performance optimizations for large datasets
- Additional specialized plot types

## License

Part of the ScientistCloud2.0 project.

