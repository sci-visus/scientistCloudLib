"""
Dashboard Builder Class for 4D Dashboard

This module provides a DashboardBuilder class that encapsulates the dashboard
creation logic, breaking down the massive create_dashboard function into
manageable, testable methods.

The builder uses the specialized plot classes from SCLib_Dashboards:
- MAP_2DPlot for Plot1 (map view)
- PROBE_1DPlot or PROBE_2DPlot for Plot2 (probe view)
- MAP_2DPlot or PROBE_2DPlot for Plot3 (projection view)
"""

import numpy as np
import time
from typing import Optional, Dict, Any, Tuple
from datetime import datetime

# Import specialized plot classes
from SCLib_Dashboards import (
    MAP_2DPlot,
    PROBE_2DPlot,
    PROBE_1DPlot,
    PlotSession,
    SessionStateHistory,
    ColorScale,
    RangeMode,
    PlotShapeMode,
)


class DashboardBuilder:
    """
    Builder class for creating the 4D dashboard.
    
    This class breaks down the massive create_dashboard function into
    smaller, manageable methods that are easier to maintain and test.
    """
    
    def __init__(self, process_4dnexus):
        """
        Initialize the dashboard builder.
        
        Args:
            process_4dnexus: Process4dNexus instance for data loading
        """
        self.process_4dnexus = process_4dnexus
        self.volume = None
        self.presample = None
        self.postsample = None
        self.x_coords = None
        self.y_coords = None
        self.preview = None
        self.is_3d_volume = False
        
        # Plot instances (will be created by specialized plot classes)
        self.plot1_map = None
        self.plot2_probe = None
        self.plot3_projection = None
        
        # Bokeh components (will be created)
        self.plot1_figure = None
        self.plot2_figure = None
        self.plot3_figure = None
        self.source1 = None
        self.source2 = None
        self.source3 = None
        
        # Session management
        self.session = None
        self.session_history = None
        
        # Timing
        self.t0 = None
    
    def load_data(self) -> bool:
        """
        Load data from the nexus file.
        
        Returns:
            True if data loaded successfully, False otherwise
        """
        try:
            self.t0 = time.time()
            print("[TIMING] DashboardBuilder.load_data(): start")
            
            # Load the data
            (self.volume, self.presample, self.postsample, 
             self.x_coords, self.y_coords, self.preview) = \
                self.process_4dnexus.load_nexus_data()
            
            print(f"[TIMING] after load_nexus_data: {time.time()-self.t0:.3f}s")
            
            print(f"Successfully loaded data:")
            print(f"  Volume shape: {self.volume.shape}")
            print(f"  X coords shape: {self.x_coords.shape}")
            print(f"  Y coords shape: {self.y_coords.shape}")
            
            # Check if volume is 3D or 4D
            self.is_3d_volume = len(self.volume.shape) == 3
            print(f"  Volume dimensionality: {'3D (1D probe plot)' if self.is_3d_volume else '4D (2D probe plot)'}")
            
            return True
        except Exception as e:
            print(f"❌ Error loading data: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def create_session(self) -> None:
        """
        Create the plot session and state history for undo/redo.
        """
        from datetime import datetime
        
        # Create PlotSession for state management
        self.session = PlotSession(
            session_id=f"dashboard_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            metadata={
                "dataset_path": getattr(self.process_4dnexus, 'volume_picked', 'unknown'),
                "volume_picked": getattr(self.process_4dnexus, 'volume_picked', None),
                "plot1_single_dataset_picked": getattr(self.process_4dnexus, 'plot1_single_dataset_picked', None),
                "presample_picked": getattr(self.process_4dnexus, 'presample_picked', None),
                "postsample_picked": getattr(self.process_4dnexus, 'postsample_picked', None),
                "x_coords_picked": getattr(self.process_4dnexus, 'x_coords_picked', None),
                "y_coords_picked": getattr(self.process_4dnexus, 'y_coords_picked', None),
                "probe_x_coords_picked": getattr(self.process_4dnexus, 'probe_x_coords_picked', None),
                "probe_y_coords_picked": getattr(self.process_4dnexus, 'probe_y_coords_picked', None),
                "volume_picked_b": getattr(self.process_4dnexus, 'volume_picked_b', None),
                "plot1b_single_dataset_picked": getattr(self.process_4dnexus, 'plot1b_single_dataset_picked', None),
                "presample_picked_b": getattr(self.process_4dnexus, 'presample_picked_b', None),
                "postsample_picked_b": getattr(self.process_4dnexus, 'postsample_picked_b', None),
                "probe_x_coords_picked_b": getattr(self.process_4dnexus, 'probe_x_coords_picked_b', None),
                "probe_y_coords_picked_b": getattr(self.process_4dnexus, 'probe_y_coords_picked_b', None),
                "plot1_mode": "single" if getattr(self.process_4dnexus, 'plot1_single_dataset_picked', None) else "ratio",
                "plot1b_mode": "single" if getattr(self.process_4dnexus, 'plot1b_single_dataset_picked', None) else "ratio",
                "plot1b_enabled": bool(getattr(self.process_4dnexus, 'plot1b_single_dataset_picked', None) or getattr(self.process_4dnexus, 'presample_picked_b', None)),
                "plot2b_enabled": bool(getattr(self.process_4dnexus, 'volume_picked_b', None)),
                "user_email": globals().get('user_email', None),
            }
        )
        
        # Create SessionStateHistory for undo/redo
        self.session_history = SessionStateHistory(self.session, max_history=20)
    
    def create_plot1(self) -> bool:
        """
        Create Plot1 (Map view) using MAP_2DPlot.
        
        Returns:
            True if plot created successfully, False otherwise
        """
        try:
            print("[TIMING] DashboardBuilder.create_plot1(): start")
            
            # Determine if plot needs flipping
            plot1_needs_flip = getattr(self.process_4dnexus, 'plot1_needs_flip', False)
            
            # Create MAP_2DPlot instance
            self.plot1_map = MAP_2DPlot(
                title="Plot1 - Map View",
                data=self.preview,
                x_coords=self.x_coords,
                y_coords=self.y_coords,
                palette="Viridis256",
                color_scale=ColorScale.LINEAR,
                range_mode=RangeMode.DYNAMIC,
                plot_shape_mode=PlotShapeMode.SQUARE,
                plot_width=400,
                plot_height=400,
                crosshairs_enabled=True,
                needs_flip=plot1_needs_flip,
                track_changes=True,
            )
            
            # TODO: Convert MAP_2DPlot to Bokeh figure
            # This will need to be implemented based on how BasePlot creates Bokeh figures
            # For now, this is a placeholder structure
            
            print(f"[TIMING] plot1 created: {time.time()-self.t0:.3f}s")
            return True
        except Exception as e:
            print(f"❌ Error creating Plot1: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def create_plot2(self) -> bool:
        """
        Create Plot2 (Probe view) using PROBE_1DPlot or PROBE_2DPlot.
        
        Returns:
            True if plot created successfully, False otherwise
        """
        try:
            print("[TIMING] DashboardBuilder.create_plot2(): start")
            
            if self.is_3d_volume:
                # Use PROBE_1DPlot for 3D volumes
                # Get initial slice
                initial_slice = self.volume[self.volume.shape[0]//2, self.volume.shape[1]//2, :]
                
                # Try to get probe coordinates
                x_coords_1d = None
                if hasattr(self.process_4dnexus, 'probe_x_coords_picked') and self.process_4dnexus.probe_x_coords_picked:
                    try:
                        probe_coords = self.process_4dnexus.load_probe_coordinates()
                        if probe_coords is not None and len(probe_coords) == len(initial_slice):
                            x_coords_1d = probe_coords
                    except:
                        pass
                
                if x_coords_1d is None:
                    x_coords_1d = np.arange(len(initial_slice))
                
                self.plot2_probe = PROBE_1DPlot(
                    title="Plot2 - Probe View (1D)",
                    data=initial_slice,
                    x_coords=x_coords_1d,
                    palette="Viridis256",
                    color_scale=ColorScale.LINEAR,
                    range_mode=RangeMode.DYNAMIC,
                    plot_width=400,
                    plot_height=300,
                    crosshairs_enabled=False,
                    select_region_enabled=True,
                    track_changes=True,
                )
            else:
                # Use PROBE_2DPlot for 4D volumes
                # Get initial slice (center of Z and U dimensions)
                initial_slice = self.volume[:, :, self.volume.shape[2]//2, self.volume.shape[3]//2]
                
                self.plot2_probe = PROBE_2DPlot(
                    title="Plot2 - Probe View (2D)",
                    data=initial_slice,
                    x_coords=None,  # Will be set based on probe coordinates
                    y_coords=None,  # Will be set based on probe coordinates
                    palette="Viridis256",
                    color_scale=ColorScale.LINEAR,
                    range_mode=RangeMode.DYNAMIC,
                    plot_shape_mode=PlotShapeMode.SQUARE,
                    plot_width=400,
                    plot_height=400,
                    crosshairs_enabled=False,
                    needs_flip=False,
                    track_changes=True,
                )
            
            print(f"[TIMING] plot2 created: {time.time()-self.t0:.3f}s")
            return True
        except Exception as e:
            print(f"❌ Error creating Plot2: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def create_plot3(self) -> bool:
        """
        Create Plot3 (Projection view) using MAP_2DPlot or PROBE_2DPlot.
        
        Returns:
            True if plot created successfully, False otherwise
        """
        try:
            print("[TIMING] DashboardBuilder.create_plot3(): start")
            
            # Plot3 shows a 2D projection (sum over selected Z,U range from Plot2)
            # Start with empty/placeholder data
            initial_data = np.zeros((100, 100))  # Placeholder
            
            self.plot3_projection = MAP_2DPlot(
                title="Plot3 - Projection View",
                data=initial_data,
                x_coords=None,
                y_coords=None,
                palette="Viridis256",
                color_scale=ColorScale.LINEAR,
                range_mode=RangeMode.DYNAMIC,
                plot_shape_mode=PlotShapeMode.SQUARE,
                plot_width=400,
                plot_height=400,
                crosshairs_enabled=False,
                needs_flip=False,
                track_changes=True,
            )
            
            print(f"[TIMING] plot3 created: {time.time()-self.t0:.3f}s")
            return True
        except Exception as e:
            print(f"❌ Error creating Plot3: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def setup_callbacks(self) -> bool:
        """
        Setup all callback functions for inter-plot interactions.
        
        This is where the complex callback logic goes, but broken into
        smaller methods for each interaction type.
        
        Returns:
            True if callbacks setup successfully, False otherwise
        """
        try:
            print("[TIMING] DashboardBuilder.setup_callbacks(): start")
            
            # TODO: Setup callbacks
            # - Plot1 click -> update Plot2
            # - Plot2 selection -> update Plot3
            # - Plot3 selection -> update Plot2
            # - Slider changes -> update plots
            # - Range input changes -> update plots
            
            print(f"[TIMING] callbacks setup: {time.time()-self.t0:.3f}s")
            return True
        except Exception as e:
            print(f"❌ Error setting up callbacks: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def create_controls(self) -> Dict[str, Any]:
        """
        Create all control widgets (sliders, inputs, buttons).
        
        Returns:
            Dictionary of control widgets
        """
        try:
            print("[TIMING] DashboardBuilder.create_controls(): start")
            
            controls = {}
            
            # TODO: Create controls
            # - Sliders for navigation
            # - Range inputs for each plot
            # - Color scale selectors
            # - Palette selectors
            # - Buttons for actions
            
            print(f"[TIMING] controls created: {time.time()-self.t0:.3f}s")
            return controls
        except Exception as e:
            print(f"❌ Error creating controls: {e}")
            import traceback
            traceback.print_exc()
            return {}
    
    def create_layout(self, controls: Dict[str, Any]):
        """
        Create the final dashboard layout.
        
        Args:
            controls: Dictionary of control widgets
            
        Returns:
            Bokeh layout object
        """
        try:
            from bokeh.layouts import column, row
            
            print("[TIMING] DashboardBuilder.create_layout(): start")
            
            # TODO: Create layout
            # - Arrange plots and controls
            # - Add session management UI
            # - Add undo/redo buttons
            
            layout = column()  # Placeholder
            
            print(f"[TIMING] layout created: {time.time()-self.t0:.3f}s")
            return layout
        except Exception as e:
            print(f"❌ Error creating layout: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def build(self):
        """
        Build the complete dashboard.
        
        This is the main entry point that orchestrates all the steps.
        Currently calls the full implementation method which contains
        the complete dashboard creation logic. This will be gradually
        refactored into smaller methods.
        
        Returns:
            Bokeh layout object with the complete dashboard
        """
        return self._build_full_implementation()
    
    def _build_full_implementation(self):
        """
        Full dashboard implementation.
        
        This method contains the complete dashboard creation logic,
        embedded directly to make 4d_dashboardLiteImprove.py independent
        of 4d_dashboardLite.py.
        
        The implementation is loaded from 4d_dashboard_implementation.py
        (located in VisusDataPortalPrivate/Docker/bokeh/) which is generated
        from 4d_dashboardLite.py but adapted for use within this class
        (process_4dnexus -> self.process_4dnexus).
        
        TODO: Break this down into:
        - _setup_data_and_session()
        - _create_plot1_implementation()
        - _create_plot2_implementation()
        - _create_plot3_implementation()
        - _setup_all_callbacks()
        - _create_all_controls()
        - _assemble_layout()
        """
        # Load the embedded implementation from the extracted file
        # This file is generated from 4d_dashboardLite.py and contains
        # the full implementation adapted for use in this class
        import os
        import sys
        
        # Find the implementation file - both files are now in SCLib_Dashboards
        # (scientistCloudLib/SCLib_Dashboards/4d_dashboard_implementation.py)
        # This works both in development and Docker containers where files are copied in
        current_file = os.path.abspath(__file__)
        current_dir = os.path.dirname(current_file)
        
        # Try multiple possible paths:
        # 1. Same directory as this file (both files are in SCLib_Dashboards)
        # 2. Try to find via Python module path (Docker/installed)
        # 3. Old location/name (fallback for backwards compatibility)
        possible_paths = []
        
        # Path 1: Same directory (both files are in SCLib_Dashboards)
        possible_paths.append(os.path.join(current_dir, '4d_dashboard_implementation.py'))
        
        # Path 2: Try to find via Python module path (for Docker/installed packages)
        try:
            import SCLib_Dashboards
            if hasattr(SCLib_Dashboards, '__file__'):
                sc_lib_dir = os.path.dirname(SCLib_Dashboards.__file__)
                possible_paths.append(os.path.join(sc_lib_dir, '4d_dashboard_implementation.py'))
        except ImportError:
            pass
        
        # Path 3: Old location/name (fallback for backwards compatibility)
        # Try old location in dashboards directory
        possible_paths.append(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(current_dir))), 'scientistcloud', 'SC_Dashboards', 'dashboards', '_extracted_implementation.py'))
        
        extracted_file = None
        for path in possible_paths:
            if os.path.exists(path):
                extracted_file = path
                print(f"✅ Found implementation file at: {extracted_file}")
                break
        
        if extracted_file is None:
            extracted_file = possible_paths[0]  # Use first path for error message
        
        if not os.path.exists(extracted_file):
            # Fallback: try to generate it on the fly
            print(f"⚠️ 4d_dashboard_implementation.py not found, attempting to generate...")
            try:
                # Try to extract from 4d_dashboardLite.py if it exists
                original_file = os.path.join(dashboard_dir, '4d_dashboardLite.py')
                if os.path.exists(original_file):
                    import re
                    with open(original_file, 'r') as f:
                        content = f.read()
                    pattern = r'def create_dashboard\(process_4dnexus\):(.*?)(?=\n\ndef |\n\n# Main execution|\Z)'
                    match = re.search(pattern, content, re.DOTALL)
                    if match:
                        function_body = match.group(1)
                        lines = function_body.split('\n')
                        base_indent = None
                        for line in lines:
                            if line.strip() and not line.strip().startswith('#'):
                                base_indent = len(line) - len(line.lstrip())
                                break
                        if base_indent:
                            adapted_lines = []
                            for line in lines:
                                if line.strip():
                                    current_indent = len(line) - len(line.lstrip())
                                    if current_indent >= base_indent:
                                        adapted_lines.append(' ' * 8 + line[base_indent:])
                                    else:
                                        adapted_lines.append(' ' * 8 + line.lstrip())
                                else:
                                    adapted_lines.append('')
                            implementation_code = '\n'.join(adapted_lines)
                            implementation_code = re.sub(r'\bprocess_4dnexus\b', 'self.process_4dnexus', implementation_code)
                        else:
                            raise Exception("Could not determine base indentation")
                    else:
                        raise Exception("Could not find create_dashboard function")
                else:
                    raise Exception(f"Neither 4d_dashboard_implementation.py nor 4d_dashboardLite.py found")
            except Exception as e:
                print(f"❌ Could not generate implementation: {e}")
                return None
        else:
            # Read from the extracted file
            with open(extracted_file, 'r') as f:
                implementation_code = f.read()
        
        # Execute the implementation code
        try:
            # Create a namespace with all necessary imports and self
            namespace = {
                'self': self,
                'np': np,
                'time': time,
            }
            
            # Import all necessary modules into namespace
            from datetime import datetime
            from bokeh.io import curdoc
            from bokeh.layouts import column, row
            from bokeh.models import (
                ColumnDataSource, Div, Slider, Toggle, TapTool, CustomJS, HoverTool,
                ColorBar, LinearColorMapper, LogColorMapper, TextInput,
                LogScale, LinearScale, FileInput, BoxSelectTool, BoxEditTool, BoxAnnotation
            )
            from bokeh.plotting import figure
            from bokeh.transform import linear_cmap
            import matplotlib.colors as colors
            
            namespace.update({
                'datetime': datetime,
                'curdoc': curdoc,
                'column': column,
                'row': row,
                'ColumnDataSource': ColumnDataSource,
                'Div': Div,
                'Slider': Slider,
                'Toggle': Toggle,
                'TapTool': TapTool,
                'CustomJS': CustomJS,
                'HoverTool': HoverTool,
                'ColorBar': ColorBar,
                'LinearColorMapper': LinearColorMapper,
                'LogColorMapper': LogColorMapper,
                'TextInput': TextInput,
                'LogScale': LogScale,
                'LinearScale': LinearScale,
                'FileInput': FileInput,
                'BoxSelectTool': BoxSelectTool,
                'BoxEditTool': BoxEditTool,
                'BoxAnnotation': BoxAnnotation,
                'figure': figure,
                'linear_cmap': linear_cmap,
                'colors': colors,
            })
            
            # Import SCLib components
            from SCLib_Dashboards import (
                PlotSession, SessionStateHistory, PlotStateHistory,
                ColorScale, RangeMode, PlotShapeMode,
                MAP_2DPlot, PROBE_2DPlot, PROBE_1DPlot,
                create_select, create_slider, create_button, create_toggle,
                create_text_input, create_radio_button_group, create_div,
                create_label_div, create_range_inputs, create_range_section,
                create_range_section_with_toggle, create_color_scale_selector,
                create_color_scale_section, create_palette_selector,
                create_palette_section, create_plot_shape_controls,
                create_range_mode_toggle, create_dataset_selection_group,
                create_coordinate_selection_group, create_optional_plot_toggle,
                extract_dataset_path, extract_shape, create_tools_column,
                create_plot_column, create_plots_row, create_dashboard_layout,
                create_status_display, create_initialization_layout,
                sync_all_plot_ui, sync_plot_to_range_inputs,
                sync_range_inputs_to_plot, sync_plot_to_color_scale_selector,
                sync_color_scale_selector_to_plot, sync_plot_to_palette_selector,
                sync_palette_selector_to_plot, create_undo_redo_callbacks,
                update_range_inputs_safely,
            )
            
            namespace.update({
                'PlotSession': PlotSession,
                'SessionStateHistory': SessionStateHistory,
                'PlotStateHistory': PlotStateHistory,
                'ColorScale': ColorScale,
                'RangeMode': RangeMode,
                'PlotShapeMode': PlotShapeMode,
                'MAP_2DPlot': MAP_2DPlot,
                'PROBE_2DPlot': PROBE_2DPlot,
                'PROBE_1DPlot': PROBE_1DPlot,
                'create_select': create_select,
                'create_slider': create_slider,
                'create_button': create_button,
                'create_toggle': create_toggle,
                'create_text_input': create_text_input,
                'create_radio_button_group': create_radio_button_group,
                'create_div': create_div,
                'create_label_div': create_label_div,
                'create_range_inputs': create_range_inputs,
                'create_range_section': create_range_section,
                'create_range_section_with_toggle': create_range_section_with_toggle,
                'create_color_scale_selector': create_color_scale_selector,
                'create_color_scale_section': create_color_scale_section,
                'create_palette_selector': create_palette_selector,
                'create_palette_section': create_palette_section,
                'create_plot_shape_controls': create_plot_shape_controls,
                'create_range_mode_toggle': create_range_mode_toggle,
                'create_dataset_selection_group': create_dataset_selection_group,
                'create_coordinate_selection_group': create_coordinate_selection_group,
                'create_optional_plot_toggle': create_optional_plot_toggle,
                'extract_dataset_path': extract_dataset_path,
                'extract_shape': extract_shape,
                'create_tools_column': create_tools_column,
                'create_plot_column': create_plot_column,
                'create_plots_row': create_plots_row,
                'create_dashboard_layout': create_dashboard_layout,
                'create_status_display': create_status_display,
                'create_initialization_layout': create_initialization_layout,
                'sync_all_plot_ui': sync_all_plot_ui,
                'sync_plot_to_range_inputs': sync_plot_to_range_inputs,
                'sync_range_inputs_to_plot': sync_range_inputs_to_plot,
                'sync_plot_to_color_scale_selector': sync_plot_to_color_scale_selector,
                'sync_color_scale_selector_to_plot': sync_color_scale_selector_to_plot,
                'sync_plot_to_palette_selector': sync_plot_to_palette_selector,
                'sync_palette_selector_to_plot': sync_palette_selector_to_plot,
                'create_undo_redo_callbacks': create_undo_redo_callbacks,
                'update_range_inputs_safely': update_range_inputs_safely,
            })
            
            # Add globals that might be needed
            try:
                namespace['user_email'] = globals().get('user_email', None)
            except:
                namespace['user_email'] = None
            
            # Import create_tmp_dashboard from the main dashboard file
            # This is needed for the back button functionality
            try:
                import importlib.util
                import os
                import sys
                import inspect
                
                # Try to find 4d_dashboardLite.py by looking at the call stack
                # The dashboard builder is called from 4d_dashboardLite.py, so we can find it
                dashboard_file = None
                possible_paths = []
                
                # Method 1: Look in the call stack for the file that called us
                try:
                    frame = inspect.currentframe()
                    # Go up the stack to find the calling file
                    while frame:
                        frame = frame.f_back
                        if frame is None:
                            break
                        filename = frame.f_code.co_filename
                        if '4d_dashboardLite.py' in filename:
                            dashboard_file = filename
                            print(f"✅ Found dashboard file from call stack: {dashboard_file}")
                            break
                except:
                    pass
                
                # Method 2: Try relative paths from current file location
                if dashboard_file is None or not os.path.exists(dashboard_file):
                    current_file = os.path.abspath(__file__)
                    current_dir = os.path.dirname(current_file)
                    
                    # From SCLib_Dashboards to dashboards: 
                    # .../scientistCloudLib/SCLib_Dashboards/ -> .../scientistcloud/SC_Dashboards/dashboards/
                    base_dir = os.path.dirname(os.path.dirname(current_dir))  # Go up to scientistCloudLib
                    possible_paths = [
                        os.path.join(base_dir, 'scientistcloud', 'SC_Dashboards', 'dashboards', '4d_dashboardLite.py'),
                        os.path.join(os.path.dirname(base_dir), 'scientistcloud', 'SC_Dashboards', 'dashboards', '4d_dashboardLite.py'),
                    ]
                    
                    # Method 3: Try current working directory
                    try:
                        cwd = os.getcwd()
                        possible_paths.extend([
                            os.path.join(cwd, 'scientistcloud', 'SC_Dashboards', 'dashboards', '4d_dashboardLite.py'),
                            os.path.join(cwd, 'SC_Dashboards', 'dashboards', '4d_dashboardLite.py'),
                            os.path.join(cwd, 'dashboards', '4d_dashboardLite.py'),
                            os.path.join(cwd, '4d_dashboardLite.py'),
                        ])
                    except:
                        pass
                    
                    # Method 4: Try sys.path
                    for path_dir in sys.path:
                        if path_dir and os.path.isdir(path_dir):
                            test_path = os.path.join(path_dir, '4d_dashboardLite.py')
                            if test_path not in possible_paths:
                                possible_paths.append(test_path)
                    
                    # Try each path
                    for path in possible_paths:
                        if os.path.exists(path):
                            dashboard_file = path
                            print(f"✅ Found dashboard file at: {dashboard_file}")
                            break
                
                if dashboard_file is None or not os.path.exists(dashboard_file):
                    raise FileNotFoundError(f"Dashboard file not found. Tried paths: {possible_paths}")
                
                spec = importlib.util.spec_from_file_location("dashboard_module", dashboard_file)
                dashboard_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(dashboard_module)
                if hasattr(dashboard_module, 'create_tmp_dashboard'):
                    namespace['create_tmp_dashboard'] = dashboard_module.create_tmp_dashboard
                    print("✅ Successfully imported create_tmp_dashboard for back button")
                else:
                    print("⚠️ WARNING: create_tmp_dashboard not found in 4d_dashboardLite module")
                    raise AttributeError("create_tmp_dashboard not found")
            except Exception as e:
                error_message = str(e)  # Capture error message as string to avoid scoping issues
                print(f"⚠️ WARNING: Could not import create_tmp_dashboard: {error_message}")
                import traceback
                traceback.print_exc()
                # Create a dummy function that shows an error
                def create_tmp_dashboard(process_4dnexus):
                    from bokeh.layouts import column
                    from SCLib_Dashboards import create_div
                    return column(create_div(text=f"<h3 style='color: red;'>Error: Could not load dataset selection dashboard</h3><p>{error_message}</p>"))
                namespace['create_tmp_dashboard'] = create_tmp_dashboard
            
            # Execute the implementation code
            exec(implementation_code, namespace)
            
            # The code should set a 'dashboard' variable
            if 'dashboard' in namespace:
                return namespace['dashboard']
            else:
                print("⚠️ WARNING: Implementation did not set 'dashboard' variable")
                return None
                
        except Exception as e:
            print(f"❌ Error executing embedded implementation: {e}")
            import traceback
            traceback.print_exc()
            return None

