"""
SCLib_Dashboards - Dashboard Plot Library

This library provides a generic plot class system that can be specialized
for different plot types (MAP_2DPlot, PROBE_2DPlot, PROBE_1DPlot).

Features:
- Comprehensive state management (save/load JSON)
- Change tracking for user experience logging
- Range management (dynamic/user specified)
- Color palette and colorbar configuration
- Plot shape configuration (square, custom, aspect ratio)
- Crosshairs and selection regions
- Session management for multiple plots

Example usage:
    from SCLib_Dashboards import MAP_2DPlot, PROBE_1DPlot, PlotSession
    
    # Create a 2D map plot
    map_plot = MAP_2DPlot(
        title="Sample Map",
        data=my_2d_data,
        x_coords=x_coordinates,
        y_coords=y_coordinates
    )
    
    # Create a session and add plots
    session = PlotSession(session_id="my_session")
    session.add_plot("map1", map_plot)
    
    # Save session state
    session.save_session("my_session.json")
"""

from .SCDash_base_plot import (
    BasePlot,
    DataMode,
    ColorScale,
    PlotShapeMode,
    RangeMode,
)

from .SCDash_specialized_plots import (
    MAP_2DPlot,
    PROBE_2DPlot,
    PROBE_1DPlot,
)

from .SCDash_state_manager import (
    PlotSession,
    create_session_from_state,
)

from .SCDash_data_session import (
    DataPlotSession,
    create_data_plot_session_from_state,
)

from .SCDash_4d_session import (
    FourDDashboardSession,
    create_4d_session_from_process_4dnexus,
)

from .SCData_base_processor import (
    BaseDataProcessor,
    DatasetCategory,
)

from .SCData_process_nexus import (
    ProcessNexus,
    Process4dNexus,  # Alias for backward compatibility
)

from .SCData_process_zarr import (
    ProcessZarr,
)

# Undo/Redo components (don't depend on bokeh, so import separately)
from .SCDashUI_undo_redo import (
    StateHistory,
    PlotStateHistory,
    SessionStateHistory,
    create_undo_redo_callbacks,
)

# UI Components (required - bokeh must be available)
from .SCDashUI_base_components import (
    create_select,
    create_slider,
    create_button,
    create_toggle,
    create_text_input,
    create_radio_button_group,
    create_div,
    create_label_div,
    create_spacer,
    create_separator,
)

from .SCDashUI_plot_controls import (
    create_range_inputs,
    create_range_section,
    create_color_scale_selector,
    create_color_scale_section,
    create_palette_selector,
    create_palette_section,
    create_plot_shape_controls,
    create_range_mode_toggle,
    create_range_section_with_toggle,
    update_range_inputs_safely,
    DEFAULT_PALETTES,
)

from .SCDashUI_dataset_selectors import (
    create_dataset_selector,
    create_mode_selector,
    create_coordinate_selector,
    create_dataset_selection_group,
    create_coordinate_selection_group,
    create_optional_plot_toggle,
    extract_dataset_path,
    extract_shape,
)

from .SCDashUI_layout_builders import (
    create_tools_column,
    create_plot_column,
    create_plots_row,
    create_dashboard_layout,
    create_section,
    create_button_row,
    create_range_section_layout,
    create_plot_with_controls,
    create_plot_with_controls_and_buttons,
    create_aligned_plot_columns,
    create_status_display,
    create_initialization_layout,
    create_plot_with_controls_side_by_side,
    create_collapsible_tools_column,
    create_optimized_dashboard_layout,
)

from .SCDashUI_sync import (
    sync_plot_to_range_inputs,
    sync_range_inputs_to_plot,
    sync_plot_to_color_scale_selector,
    sync_color_scale_selector_to_plot,
    sync_plot_to_palette_selector,
    sync_palette_selector_to_plot,
    sync_plot_to_shape_controls,
    sync_shape_controls_to_plot,
    sync_plot_to_crosshair_display,
    sync_plot_to_selection_display,
    create_sync_callbacks,
    sync_all_plot_ui,
)

__all__ = [
    # Base classes and enums
    "BasePlot",
    "DataMode",
    "ColorScale",
    "PlotShapeMode",
    "RangeMode",
    # Specialized plot classes
    "MAP_2DPlot",
    "PROBE_2DPlot",
    "PROBE_1DPlot",
    # Session management
    "PlotSession",
    "create_session_from_state",
    "DataPlotSession",
    "create_data_plot_session_from_state",
    "FourDDashboardSession",
    "create_4d_session_from_process_4dnexus",
    # Data processors
    "BaseDataProcessor",
    "DatasetCategory",
    "ProcessNexus",
    "Process4dNexus",
    "ProcessZarr",
    # Undo/Redo (core functionality, doesn't depend on bokeh)
    "StateHistory",
    "PlotStateHistory",
    "SessionStateHistory",
    "create_undo_redo_callbacks",
]

# Add UI components to __all__
__all__.extend([
    # Base components
    "create_select",
    "create_slider",
    "create_button",
    "create_toggle",
    "create_text_input",
    "create_radio_button_group",
    "create_div",
    "create_label_div",
    "create_spacer",
    "create_separator",
    # Plot controls
    "create_range_inputs",
    "create_range_section",
    "create_color_scale_selector",
    "create_color_scale_section",
    "create_palette_selector",
    "create_palette_section",
    "create_plot_shape_controls",
    "create_range_mode_toggle",
    "create_range_section_with_toggle",
    "DEFAULT_PALETTES",
    # Dataset selectors
    "create_dataset_selector",
    "create_mode_selector",
    "create_coordinate_selector",
    "create_dataset_selection_group",
    "create_coordinate_selection_group",
    "create_optional_plot_toggle",
    "extract_dataset_path",
    "extract_shape",
    # Layout builders
    "create_tools_column",
    "create_plot_column",
    "create_plots_row",
    "create_dashboard_layout",
    "create_section",
    "create_button_row",
    "create_range_section_layout",
    "create_plot_with_controls",
    "create_plot_with_controls_and_buttons",
    "create_aligned_plot_columns",
    "create_status_display",
    "create_initialization_layout",
    "create_plot_with_controls_side_by_side",
    "create_collapsible_tools_column",
    "create_optimized_dashboard_layout",
    # State synchronization
    "sync_plot_to_range_inputs",
    "sync_range_inputs_to_plot",
    "sync_plot_to_color_scale_selector",
    "sync_color_scale_selector_to_plot",
    "sync_plot_to_palette_selector",
    "sync_palette_selector_to_plot",
    "sync_plot_to_shape_controls",
    "sync_shape_controls_to_plot",
    "sync_plot_to_crosshair_display",
    "sync_plot_to_selection_display",
    "create_sync_callbacks",
    "sync_all_plot_ui",
])

__version__ = "0.1.0"

