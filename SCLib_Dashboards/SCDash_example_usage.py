"""
Example Usage of SCLib_Dashboards

This module demonstrates how to use the plot library for creating,
configuring, and managing plots with state persistence.
"""

import numpy as np
from SCLib_Dashboards import (
    MAP_2DPlot,
    PROBE_2DPlot,
    PROBE_1DPlot,
    PlotSession,
    ColorScale,
    PlotShapeMode,
    RangeMode,
)


def example_map_plot():
    """Example: Create and configure a 2D map plot."""
    print("=" * 80)
    print("Example 1: Creating a MAP_2DPlot")
    print("=" * 80)
    
    # Create sample 2D data
    x_coords = np.linspace(0, 10, 100)
    y_coords = np.linspace(0, 10, 100)
    data = np.random.rand(100, 100) * 100
    
    # Create the plot
    map_plot = MAP_2DPlot(
        title="Sample Map View",
        data=data,
        x_coords=x_coords,
        y_coords=y_coords,
        palette="Viridis256",
        color_scale=ColorScale.LINEAR,
        range_mode=RangeMode.DYNAMIC,
        crosshairs_enabled=True,
        crosshair_x=5.0,
        crosshair_y=5.0,
        x_axis_label="X Position (mm)",
        y_axis_label="Y Position (mm)",
    )
    
    # Get state (without data for compactness)
    state = map_plot.get_state(include_data=False)
    print(f"\nPlot state (without data):")
    print(f"  Title: {state['title']}")
    print(f"  Palette: {state['palette']}")
    print(f"  Range: [{state['range_min']:.2f}, {state['range_max']:.2f}]")
    print(f"  Crosshair: ({state['crosshair_x']}, {state['crosshair_y']})")
    
    # Change some properties
    map_plot.set_palette("Plasma256")
    map_plot.set_color_scale(ColorScale.LOG)
    map_plot.set_crosshair(x=7.5, y=7.5)
    
    # Get change history
    changes = map_plot.get_change_history()
    print(f"\nNumber of changes tracked: {len(changes)}")
    for change in changes:
        print(f"  [{change['timestamp']}] {change['action']}: {change['details']}")
    
    # Save state to JSON
    state_json = map_plot.get_state_json(include_data=False)
    print(f"\nState JSON length: {len(state_json)} characters")
    
    return map_plot


def example_probe_1d_plot():
    """Example: Create and configure a 1D probe plot."""
    print("\n" + "=" * 80)
    print("Example 2: Creating a PROBE_1DPlot")
    print("=" * 80)
    
    # Create sample 1D data
    x_coords = np.linspace(0, 100, 1000)  # Probe coordinates
    data = np.sin(x_coords / 10) * np.exp(-x_coords / 50) + np.random.randn(1000) * 0.1
    
    # Create the plot
    probe_plot = PROBE_1DPlot(
        title="Sample Probe (1D)",
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
    print(f"\nSelection range: {select_range}")
    
    # Update selection
    probe_plot.set_select_range(min_x=30.0, max_x=70.0)
    print(f"Updated selection range: {probe_plot.get_select_range()}")
    
    # Get data ranges
    x_range = probe_plot.get_x_range()
    y_range = probe_plot.get_y_range()
    print(f"X range: {x_range}")
    print(f"Y range: {y_range}")
    
    return probe_plot


def example_probe_2d_plot():
    """Example: Create and configure a 2D probe plot."""
    print("\n" + "=" * 80)
    print("Example 3: Creating a PROBE_2DPlot")
    print("=" * 80)
    
    # Create sample 2D probe data
    z_coords = np.linspace(0, 50, 100)  # Z dimension
    u_coords = np.linspace(0, 100, 200)  # U dimension
    data = np.random.rand(100, 200) * 100
    
    # Create the plot
    probe_2d_plot = PROBE_2DPlot(
        title="Sample Probe (2D)",
        data=data,
        x_coords=z_coords,
        y_coords=u_coords,
        x_axis_label="Z",
        y_axis_label="U",
        palette="Inferno256",
        plot_shape_mode=PlotShapeMode.ASPECT_RATIO,
        plot_scale=80.0,
    )
    
    # Calculate plot dimensions
    width, height = probe_2d_plot.calculate_plot_dimensions()
    print(f"\nCalculated plot dimensions: {width}x{height} pixels")
    
    # Set a selection region
    probe_2d_plot.set_select_region(
        min_x=10.0,
        min_y=20.0,
        max_x=40.0,
        max_y=80.0,
        enabled=True
    )
    
    region = {
        "min_x": probe_2d_plot.select_region_min_x,
        "min_y": probe_2d_plot.select_region_min_y,
        "max_x": probe_2d_plot.select_region_max_x,
        "max_y": probe_2d_plot.select_region_max_y,
    }
    print(f"Selection region: {region}")
    
    return probe_2d_plot


def example_session_management():
    """Example: Create and manage a session with multiple plots."""
    print("\n" + "=" * 80)
    print("Example 4: Session Management")
    print("=" * 80)
    
    # Create a session
    session = PlotSession(
        session_id="example_session_001",
        metadata={
            "user_id": "user123",
            "dataset_id": "dataset456",
            "description": "Example session with multiple plots"
        }
    )
    
    # Create and add multiple plots
    map_plot = example_map_plot()
    probe_1d = example_probe_1d_plot()
    probe_2d = example_probe_2d_plot()
    
    session.add_plot("map1", map_plot)
    session.add_plot("probe1d", probe_1d)
    session.add_plot("probe2d", probe_2d)
    
    # Get session state
    session_state = session.get_session_state(include_data=False)
    print(f"\nSession ID: {session_state['session_id']}")
    print(f"Number of plots: {len(session_state['plots'])}")
    print(f"Metadata: {session_state['metadata']}")
    
    # Save session to file
    session.save_session("example_session.json", include_data=False)
    print("\nSession saved to 'example_session.json'")
    
    # Get change log
    change_log = session.get_change_log()
    print(f"\nTotal changes tracked: {len(change_log)}")
    
    # Export change log
    session.export_change_log("example_session_changes.json", format="json")
    session.export_change_log("example_session_changes.txt", format="txt")
    print("Change logs exported to:")
    print("  - example_session_changes.json")
    print("  - example_session_changes.txt")
    
    # Load session (demonstration - would need plot reconstruction)
    loaded_session = PlotSession()
    loaded_session.load_session("example_session.json", restore_data=False)
    print(f"\nLoaded session ID: {loaded_session.session_id}")
    print(f"Loaded plots (states): {len(loaded_session._loaded_plot_states)}")
    
    return session


def example_state_persistence():
    """Example: Save and load plot state."""
    print("\n" + "=" * 80)
    print("Example 5: State Persistence")
    print("=" * 80)
    
    # Create a plot with some configuration
    x_coords = np.linspace(0, 10, 50)
    y_coords = np.linspace(0, 10, 50)
    data = np.random.rand(50, 50) * 100
    
    plot = MAP_2DPlot(
        title="Persistent Plot",
        data=data,
        x_coords=x_coords,
        y_coords=y_coords,
        palette="Cividis256",
        crosshair_x=5.0,
        crosshair_y=5.0,
    )
    
    # Make some changes
    plot.set_palette("Turbo256")
    plot.set_crosshair(x=7.0, y=3.0)
    plot.set_range(10.0, 90.0, RangeMode.USER_SPECIFIED)
    
    # Save state (without data)
    state_json = plot.get_state_json(include_data=False)
    print(f"\nState JSON (without data): {len(state_json)} characters")
    
    # Save state (with data)
    state_json_with_data = plot.get_state_json(include_data=True)
    print(f"State JSON (with data): {len(state_json_with_data)} characters")
    
    # Create a new plot and load state
    new_plot = MAP_2DPlot(title="New Plot")
    new_plot.load_state(state_json, restore_data=False)
    
    print(f"\nLoaded plot configuration:")
    print(f"  Title: {new_plot.title}")
    print(f"  Palette: {new_plot.palette}")
    print(f"  Range: [{new_plot.range_min}, {new_plot.range_max}]")
    print(f"  Crosshair: ({new_plot.crosshair_x}, {new_plot.crosshair_y})")
    
    # Reset to initial state
    plot.reset_state()
    print(f"\nAfter reset:")
    print(f"  Palette: {plot.palette}")
    print(f"  Crosshair: ({plot.crosshair_x}, {plot.crosshair_y})")


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("SCLib_Dashboards - Example Usage")
    print("=" * 80)
    
    # Run examples
    example_map_plot()
    example_probe_1d_plot()
    example_probe_2d_plot()
    example_session_management()
    example_state_persistence()
    
    print("\n" + "=" * 80)
    print("Examples completed!")
    print("=" * 80)

