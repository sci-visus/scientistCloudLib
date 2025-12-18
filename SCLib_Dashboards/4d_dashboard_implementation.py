# Create the full dashboard using SCLib components with session management and undo/redo.
try:
    t0 = time.time()
    print("[TIMING] create_dashboard(): start")
    
    # Helper function to get save directory path
    def get_save_dir_path():
        """Get the save directory path based on nexus file location or UUID from URL parameters."""
        import os
        import re
        from pathlib import Path
        try:
            # Use the nexus file directory as the base directory
            nexus_filename = self.process_4dnexus.nexus_filename
            nexus_dir = Path(os.path.dirname(nexus_filename))
            
            # Check if this is a dataset directory (contains UUID pattern in path)
            # Pattern: /mnt/visus_datasets/upload/{uuid} or /mnt/visus_datasets/converted/{uuid}
            path_str = str(nexus_dir)
            if '/mnt/visus_datasets/upload/' in path_str:
                # Extract UUID from path: /mnt/visus_datasets/upload/{uuid}/...
                match = re.search(r'/mnt/visus_datasets/upload/([a-f0-9-]{36})', path_str)
                if match:
                    uuid = match.group(1)
                    # Return the upload directory for this UUID (where sessions should be saved)
                    return Path(f'/mnt/visus_datasets/upload/{uuid}')
            elif '/mnt/visus_datasets/converted/' in path_str:
                # Extract UUID from path: /mnt/visus_datasets/converted/{uuid}/...
                match = re.search(r'/mnt/visus_datasets/converted/([a-f0-9-]{36})', path_str)
                if match:
                    uuid = match.group(1)
                    # Return the upload directory for this UUID (where sessions should be saved)
                    return Path(f'/mnt/visus_datasets/upload/{uuid}')
            
            # If no UUID pattern found, return the nexus file directory
            return nexus_dir
        except Exception as e:
            print(f"⚠️ Error getting save dir from nexus_filename: {e}")
            # Fallback: try environment variable or default
            try:
                DOMAIN_NAME = os.getenv('DOMAIN_NAME', '')
                DATA_IS_LOCAL = (DOMAIN_NAME == 'localhost' or DOMAIN_NAME == '' or DOMAIN_NAME is None)
                if DATA_IS_LOCAL:
                    local_base_dir = "/Users/amygooch/GIT/SCI/DATA/waxs/pil11/"
                    return Path(local_base_dir)
                else:
                    # Try to get from nexus_filename again
                    try:
                        nexus_filename = self.process_4dnexus.nexus_filename
                        nexus_dir = Path(os.path.dirname(nexus_filename))
                        # Check for UUID pattern
                        path_str = str(nexus_dir)
                        if '/mnt/visus_datasets/upload/' in path_str:
                            match = re.search(r'/mnt/visus_datasets/upload/([a-f0-9-]{36})', path_str)
                            if match:
                                uuid = match.group(1)
                                return Path(f'/mnt/visus_datasets/upload/{uuid}')
                        elif '/mnt/visus_datasets/converted/' in path_str:
                            match = re.search(r'/mnt/visus_datasets/converted/([a-f0-9-]{36})', path_str)
                            if match:
                                uuid = match.group(1)
                                return Path(f'/mnt/visus_datasets/upload/{uuid}')
                        return nexus_dir
                    except:
                        return Path(os.getcwd())
            except:
                return Path(os.getcwd())
    
    # Helper function to get a writable sessions directory with fallback
    def get_writable_sessions_dir(preferred_path=None):
        """Get a writable sessions directory, with fallback options if preferred path is not writable.
        
        Args:
            preferred_path: Preferred directory path (usually dataset directory). If None, uses get_save_dir_path().
        
        Returns:
            Path to a writable sessions directory
        """
        import os
        from pathlib import Path
        
        # Try preferred path first (dataset directory)
        if preferred_path is None:
            preferred_path = get_save_dir_path()
        
        preferred_sessions_dir = Path(preferred_path) / "sessions"
        
        # Check if we can write to preferred location
        try:
            # Try to create the directory
            preferred_sessions_dir.mkdir(parents=True, exist_ok=True)
            # Try to set permissions if we can (may not work if we're not owner)
            try:
                os.chmod(preferred_sessions_dir, 0o755)
            except (PermissionError, OSError):
                pass  # Can't change permissions, but might still be able to write
            
            # Test write permissions by trying to create a test file
            test_file = preferred_sessions_dir / ".write_test"
            try:
                test_file.write_text("test")
                test_file.unlink()  # Delete test file
                # Success! Return preferred location
                print(f"✅ Using preferred sessions directory: {preferred_sessions_dir}")
                return preferred_sessions_dir
            except (PermissionError, OSError) as e:
                # Can't write here, try fallback
                print(f"⚠️ Cannot write to preferred sessions directory {preferred_sessions_dir}: {e}")
                print(f"   Directory exists: {preferred_sessions_dir.exists()}, is_dir: {preferred_sessions_dir.is_dir()}")
                pass
        except (PermissionError, OSError) as e:
            # Can't create directory, try fallback
            print(f"⚠️ Cannot create preferred sessions directory {preferred_sessions_dir}: {e}")
            pass
        
        # Fallback 1: Try server-wide sessions directory
        # Use environment variable if set, otherwise use /tmp/scientistcloud_sessions
        server_sessions_base = os.getenv('SC_SESSIONS_DIR', '/tmp/scientistcloud_sessions')
        try:
            server_sessions_dir = Path(server_sessions_base)
            server_sessions_dir.mkdir(parents=True, exist_ok=True)
            # Test write
            test_file = server_sessions_dir / ".write_test"
            test_file.write_text("test")
            test_file.unlink()
            # Create dataset-specific subdirectory
            dataset_id = preferred_path.name if preferred_path else "default"
            dataset_sessions_dir = server_sessions_dir / dataset_id
            dataset_sessions_dir.mkdir(parents=True, exist_ok=True)
            print(f"⚠️ Using fallback sessions directory: {dataset_sessions_dir}")
            return dataset_sessions_dir
        except (PermissionError, OSError) as e:
            print(f"⚠️ Could not use server sessions directory: {e}")
        
        # Fallback 2: Try user's home directory
        try:
            home_dir = Path.home()
            user_sessions_dir = home_dir / ".scientistcloud_sessions"
            user_sessions_dir.mkdir(parents=True, exist_ok=True)
            # Test write
            test_file = user_sessions_dir / ".write_test"
            test_file.write_text("test")
            test_file.unlink()
            # Create dataset-specific subdirectory
            dataset_id = preferred_path.name if preferred_path else "default"
            dataset_sessions_dir = user_sessions_dir / dataset_id
            dataset_sessions_dir.mkdir(parents=True, exist_ok=True)
            print(f"⚠️ Using user home sessions directory: {dataset_sessions_dir}")
            return dataset_sessions_dir
        except (PermissionError, OSError) as e:
            print(f"⚠️ Could not use user home sessions directory: {e}")
        
        # Fallback 3: Use current working directory
        try:
            cwd_sessions_dir = Path(os.getcwd()) / "sessions"
            cwd_sessions_dir.mkdir(parents=True, exist_ok=True)
            print(f"⚠️ Using current directory for sessions: {cwd_sessions_dir}")
            return cwd_sessions_dir
        except (PermissionError, OSError) as e:
            print(f"⚠️ Could not use current directory: {e}")
            # Last resort: raise error
            raise PermissionError(f"Could not find a writable location for sessions. Tried: {preferred_sessions_dir}, {server_sessions_base}, {home_dir}/.scientistcloud_sessions, {os.getcwd()}/sessions")
    
    DATA_IS_LOCAL = False  # Will be determined dynamically if needed

    # Check if we're loading from tmp_dashboard and set flag early to prevent range callbacks from firing
    # Use a mutable container so nested functions can modify it
    _session_loading_state = {"is_loading": False}
    if hasattr(self.process_4dnexus, '_session_filepath_to_load') or hasattr(self.process_4dnexus, '_session_filepath_to_load_from_main'):
        _session_loading_state["is_loading"] = True
        print("🔍 DEBUG: Session loading detected - setting flag to prevent range callbacks")

    # Load the data
    volume, presample, postsample, x_coords, y_coords, preview = self.process_4dnexus.load_nexus_data()
    print(f"[TIMING] after load_nexus_data: {time.time()-t0:.3f}s")

    print(f"Successfully loaded data:")
    print(f"  Volume shape: {volume.shape}")
    print(f"  X coords shape: {x_coords.shape}")
    print(f"  Y coords shape: {y_coords.shape if y_coords is not None else 'None (Plot1 is 1D)'}")

    # Check if Plot1 is 1D
    plot1_is_1d = getattr(self.process_4dnexus, 'plot1_is_1d', False)
    
    # Check if volume is 3D or 4D
    # When Plot1 is 1D, a 3D volume should be treated as 2D for Plot2 (showing z,u slice)
    # When Plot1 is 1D, a 2D volume should be treated as 1D for Plot2 (showing z)
    if plot1_is_1d:
        if len(volume.shape) == 3:
            # 3D volume (x,z,u) -> Plot2 should be 2D showing (z,u)
            is_3d_volume = False  # Force 2D plot
            print(f"  Plot1 is 1D mode: Volume is 3D (x,z,u), Plot2 will be 2D showing (z,u)")
        elif len(volume.shape) == 2:
            # 2D volume (x,z) -> Plot2 should be 1D showing z
            is_3d_volume = True  # Force 1D plot
            print(f"  Plot1 is 1D mode: Volume is 2D (x,z), Plot2 will be 1D showing z")
        else:
            is_3d_volume = len(volume.shape) == 3
    else:
        is_3d_volume = len(volume.shape) == 3
    
    print(f"  Volume dimensionality: {'3D (1D probe plot)' if is_3d_volume else '4D (2D probe plot)'}")

    # Helper variables for dimension indices (for Plot2 z and u dimensions)
    # When Plot1 is 1D and volume is 3D: z is at index 1, u is at index 2
    # When volume is 4D: z is at index 2, u is at index 3
    if plot1_is_1d and len(volume.shape) == 3:
        z_dim_idx = 1  # z dimension index in volume
        u_dim_idx = 2  # u dimension index in volume
        z_size = volume.shape[1]  # size of z dimension
        u_size = volume.shape[2]  # size of u dimension
    else:
        z_dim_idx = 2  # z dimension index in volume (for 4D)
        u_dim_idx = 3  # u dimension index in volume (for 4D)
        z_size = volume.shape[2] if len(volume.shape) > 2 else 0  # size of z dimension
        u_size = volume.shape[3] if len(volume.shape) > 3 else 0  # size of u dimension

    # Import datetime
    from datetime import datetime

    # Import SCLib session classes first (needed before creating session)
    from SCLib_Dashboards.SCDash_4d_session import (
        FourDDashboardSession,
        create_4d_session_from_process_4dnexus,
    )
    from SCLib_Dashboards.SCDashUI_undo_redo import SessionStateHistory

    # Create FourDDashboardSession for state management
    # This specialized session includes all 4D-specific dataset selections
    session = create_4d_session_from_process_4dnexus(
        self.process_4dnexus,
        user_email=user_email if 'user_email' in globals() else None,
    )

    # Create SessionStateHistory for undo/redo
    # NOTE: State history saves with include_data=False, so it only stores UI settings,
    # not data arrays. This keeps undo/redo fast and memory-efficient.
    # Reduced max_history from 100 to 20 for better performance (fewer deep copies)
    session_history = SessionStateHistory(session, max_history=20)

    # Import Bokeh components
    from bokeh.models import (
        Slider, Toggle, TapTool, HoverTool,
        ColorBar, LinearColorMapper, LogColorMapper, TextInput,
        LogScale, LinearScale, FileInput, BoxSelectTool, BoxEditTool, BoxAnnotation
    )
    from bokeh.layouts import row
    from bokeh.transform import linear_cmap
    import matplotlib.colors as colors
    
    # Import SCLib helper functions
    from SCLib_Dashboards import update_range_inputs_safely
    from SCLib_Dashboards.SCDash_volume_utils import (
        compute_2d_plot_from_3d_section,
        compute_3d_source_from_2d_section,
        calculate_percentile_range,
    )
    from SCLib_Dashboards.SCDash_bokeh_utils import (
        get_box_select_selection,
        setup_selection_geometry_handler,
        reset_plot_to_original_data,
    )
    from SCLib_Dashboards.SCDash_specialized_plots import (
        draw_crosshairs_from_indices,
        set_axis_labels,
        set_ticks_from_coords,
        set_ticks_from_coords_both_axes,
    )
    from SCLib_Dashboards.SCDashUI_plot_controls import (
        create_color_scale_selector,
    )
    from SCLib_Dashboards.SCDashUI_sync import (
        sync_plot_to_color_scale_selector,
    )

    # Rectangle class for selection areas and crosshairs
    class Rectangle:
        """Helper class to manage selection rectangles and crosshairs."""
        def __init__(self, min_x=0, min_y=0, max_x=0, max_y=0):
            self.min_x = min_x
            self.min_y = min_y
            self.max_x = max_x
            self.max_y = max_y
            self.h1line = None  # Horizontal line 1 (for crosshairs)
            self.h2line = None  # Horizontal line 2 (for crosshairs)
            self.v1line = None  # Vertical line 1 (for crosshairs)
            self.v2line = None  # Vertical line 2 (for crosshairs)

        def swap_if_needed(self):
            """Swap min/max if needed (for 4D volumes with proper rectangle selection)."""
            if not is_3d_volume:
                if self.min_x > self.max_x:
                        self.min_x, self.max_x = self.max_x, self.min_x
                if self.min_y > self.max_y:
                        self.min_y, self.max_y = self.max_y, self.min_y

        def set(self, min_x=None, min_y=None, max_x=None, max_y=None):
            """Set rectangle coordinates."""
            if min_x is not None:
                self.min_x = min_x
            if min_y is not None:
                self.min_y = min_y
            if max_x is not None:
                self.max_x = max_x
            if max_y is not None:
                self.max_y = max_y
            self.swap_if_needed()

    # Initialize rectangles for selection areas
    # rect1: For Plot1 crosshairs (X, Y indices)
    rect1 = Rectangle(0, 0, volume.shape[0] - 1, volume.shape[1] - 1)
    rect1.h1line = None  # Initialize crosshair line attributes
    rect1.v1line = None
    rect1b = None  # Will be initialized if Plot1B exists

    # rect2: For Plot2A selection (Z, U dimensions for 4D or Z for 3D)
    if is_3d_volume:
        rect2 = Rectangle(0, 0, volume.shape[2] - 1, volume.shape[2] - 1)  # 1D probe
    else:
        # For 4D volume OR 3D volume when Plot1 is 1D
        if plot1_is_1d and len(volume.shape) == 3:
            # When Plot1 is 1D and volume is 3D (x,z,u), use z and u dimensions
            rect2 = Rectangle(0, 0, volume.shape[1] - 1, volume.shape[2] - 1)  # Z, U from 3D volume
        elif len(volume.shape) == 4:
            # Normal 4D volume case
            rect2 = Rectangle(0, 0, volume.shape[2] - 1, volume.shape[3] - 1)  # Z, U
        else:
            # Fallback for other cases (shouldn't normally happen)
            rect2 = Rectangle(0, 0, z_size - 1, u_size - 1)  # Use computed z_size and u_size

    rect2b = None  # Will be initialized if Plot2B exists

    # rect3: For Plot3 selection (X, Y dimensions)
    rect3 = Rectangle(0, 0, volume.shape[0] - 1, volume.shape[1] - 1)
    # rect3_crosshair: For Plot3 crosshairs (synchronized with Plot1)
    rect3_crosshair = Rectangle(0, 0, volume.shape[0] - 1, volume.shape[1] - 1)
    rect3_crosshair.h1line = None  # Initialize crosshair line attributes
    rect3_crosshair.v1line = None

    # Set initial probe positions to middle of the data range
    x_index = volume.shape[0] // 2
    y_index = volume.shape[1] // 2

    # Detect if map coordinates need flipping
    print("=" * 80)
    print("🔍 DEBUG: Map Flip Detection for Plot1:")
    print(f"  preview.shape: {preview.shape if preview is not None else 'None'}")
    map_x_coord_size = None
    map_y_coord_size = None
    if hasattr(self.process_4dnexus, 'x_coords_picked') and self.process_4dnexus.x_coords_picked:
        map_x_coord_size = self.process_4dnexus.get_dataset_size_from_path(self.process_4dnexus.x_coords_picked)
        print(f"  x_coords_picked: {self.process_4dnexus.x_coords_picked}")
        print(f"  map_x_coord_size: {map_x_coord_size}")
    if hasattr(self.process_4dnexus, 'y_coords_picked') and self.process_4dnexus.y_coords_picked:
        map_y_coord_size = self.process_4dnexus.get_dataset_size_from_path(self.process_4dnexus.y_coords_picked)
        print(f"  y_coords_picked: {self.process_4dnexus.y_coords_picked}")
        print(f"  map_y_coord_size: {map_y_coord_size}")

    plot1_needs_flip = False
    if preview is not None and len(preview.shape) == 2:
        plot1_needs_flip = self.process_4dnexus.detect_map_flip_needed(
            preview.shape,
            map_x_coord_size,
            map_y_coord_size
        )
        print(f"  plot1_needs_flip: {plot1_needs_flip}")
    print("=" * 80)

    # Helper function to extract last component of a path (for axis labels)
    def get_last_path_component(path_str):
        """Extract the last component from a path string (e.g., '/entry/instrument/detector/x' -> 'x')."""
        if not path_str:
            return None
        # Split by '/' and get the last non-empty component
        parts = [p for p in path_str.split('/') if p]
        return parts[-1] if parts else None
    
    # Store original coordinate paths for axis labels
    # Extract just the last component for axis labels
    map_x_path = getattr(self.process_4dnexus, 'x_coords_picked', None)
    map_y_path = getattr(self.process_4dnexus, 'y_coords_picked', None)
    original_map_x_label = get_last_path_component(map_x_path) or 'X Position'
    original_map_y_label = get_last_path_component(map_y_path) or 'Y Position'
    
    # Get Plot1 title from dataset source (use x_coords_picked or y_coords_picked, or preview if available)
    plot1_title = "Projection -- file"
    if map_x_path:
        plot1_title = map_x_path
    elif map_y_path:
        plot1_title = map_y_path
    elif hasattr(self.process_4dnexus, 'preview_picked') and self.process_4dnexus.preview_picked:
        plot1_title = self.process_4dnexus.preview_picked

    # Create Plot1 - either 1D line plot or 2D map plot
    map_plot = None
    plot1_1d_plot = None
    plot1_1d_data = None
    plot1_1d_x_coords = None
    
    if plot1_is_1d:
        # Create Plot1 as 1D line plot
        print("🔍 DEBUG: Creating Plot1 as 1D line plot")
        plot1_1d_data = None
        
        # Check if it's Ratio (1D) mode - compute ratio from presample and postsample
        if (hasattr(self.process_4dnexus, 'presample_picked') and self.process_4dnexus.presample_picked and
            hasattr(self.process_4dnexus, 'postsample_picked') and self.process_4dnexus.postsample_picked and
            not (hasattr(self.process_4dnexus, 'plot1_single_dataset_picked') and self.process_4dnexus.plot1_single_dataset_picked)):
            # Ratio (1D) mode: compute ratio from presample and postsample
            print("🔍 DEBUG: Ratio (1D) mode - computing ratio from presample and postsample")
            try:
                if hasattr(self.process_4dnexus, 'presample_conditioned') and hasattr(self.process_4dnexus, 'postsample_conditioned'):
                    # Use already computed conditioned datasets if available
                    presample_1d = self.process_4dnexus.presample_conditioned
                    postsample_1d = self.process_4dnexus.postsample_conditioned
                else:
                    # Load and compute from raw datasets
                    presample_data = self.process_4dnexus.load_dataset_by_path(self.process_4dnexus.presample_picked)
                    postsample_data = self.process_4dnexus.load_dataset_by_path(self.process_4dnexus.postsample_picked)
                    
                    if presample_data is not None and postsample_data is not None:
                        # Convert to numpy arrays if needed
                        if not isinstance(presample_data, np.ndarray):
                            try:
                                presample_data = presample_data[()]
                            except:
                                presample_data = np.array(presample_data, dtype=np.float64)
                        if not isinstance(postsample_data, np.ndarray):
                            try:
                                postsample_data = postsample_data[()]
                            except:
                                postsample_data = np.array(postsample_data, dtype=np.float64)
                        
                        # Flatten to 1D
                        presample_1d = presample_data.flatten()
                        postsample_1d = postsample_data.flatten()
                        
                        # Condition (replace zeros with epsilon)
                        epsilon = 1e-10
                        presample_1d = np.where(presample_1d == 0, epsilon, presample_1d)
                        postsample_1d = np.where(postsample_1d == 0, epsilon, postsample_1d)
                    else:
                        presample_1d = None
                        postsample_1d = None
                
                if presample_1d is not None and postsample_1d is not None:
                    # Compute 1D ratio
                    plot1_1d_data = presample_1d / postsample_1d
                    plot1_1d_data = np.nan_to_num(plot1_1d_data, nan=0.0, posinf=1.0, neginf=0.0)
                    # Ensure it's a numeric type
                    if not np.issubdtype(plot1_1d_data.dtype, np.number):
                        plot1_1d_data = plot1_1d_data.astype(np.float64)
                    print(f"✅ Computed 1D ratio for Plot1: shape={plot1_1d_data.shape}, dtype={plot1_1d_data.dtype}")
                else:
                    print("⚠️ WARNING: Could not load presample/postsample datasets for Ratio (1D), falling back to preview")
            except Exception as e:
                print(f"⚠️ ERROR computing Ratio (1D) for Plot1: {e}")
                import traceback
                traceback.print_exc()
        
        # If not Ratio mode, try loading single dataset
        if plot1_1d_data is None and hasattr(self.process_4dnexus, 'plot1_single_dataset_picked') and self.process_4dnexus.plot1_single_dataset_picked:
            try:
                plot1_1d_data = self.process_4dnexus.load_dataset_by_path(self.process_4dnexus.plot1_single_dataset_picked)
                if plot1_1d_data is not None:
                    # Convert to numpy array if it's an HDF5 dataset reference or not already a numpy array
                    # np should be available in namespace from builder
                    if not isinstance(plot1_1d_data, np.ndarray):
                        # It's likely an HDF5 dataset reference (h5py Dataset), convert to numpy array
                        # Try multiple methods to read the data safely
                        try:
                            # Method 1: Use [()] indexing (most reliable for h5py datasets)
                            plot1_1d_data = plot1_1d_data[()]
                        except:
                            try:
                                # Method 2: Use read() method if available
                                if hasattr(plot1_1d_data, 'read'):
                                    plot1_1d_data = plot1_1d_data.read()
                                else:
                                    # Method 3: Use np.array conversion
                                    plot1_1d_data = np.array(plot1_1d_data, dtype=np.float64)
                            except:
                                try:
                                    # Method 4: Try slicing to force read
                                    plot1_1d_data = plot1_1d_data[:]
                                except Exception as e2:
                                    print(f"⚠️ WARNING: Could not convert HDF5 dataset to numpy array: {e2}")
                                    plot1_1d_data = None
                    # Ensure it's 1D
                    if plot1_1d_data.ndim > 1:
                        plot1_1d_data = plot1_1d_data.flatten()
                    # Ensure it's a numeric type that supports isnan (convert to float64 if needed)
                    if not np.issubdtype(plot1_1d_data.dtype, np.number):
                        plot1_1d_data = plot1_1d_data.astype(np.float64)
                    elif plot1_1d_data.dtype == np.object_ or plot1_1d_data.dtype.kind not in ['f', 'i', 'u', 'c']:
                        # If it's object dtype or not a numeric kind, convert to float64
                        plot1_1d_data = plot1_1d_data.astype(np.float64)
                    print(f"✅ Loaded 1D dataset for Plot1: shape={plot1_1d_data.shape}, dtype={plot1_1d_data.dtype}")
                else:
                    print("⚠️ WARNING: Could not load 1D dataset for Plot1, falling back to preview")
                    plot1_1d_data = None
            except Exception as e:
                print(f"⚠️ ERROR loading 1D dataset for Plot1: {e}")
                import traceback
                traceback.print_exc()
                plot1_1d_data = None
        
        # Use x_coords for the 1D plot
        if plot1_1d_data is not None and x_coords is not None:
            plot1_1d_x_coords = x_coords
            # Create PROBE_1DPlot for Plot1
            plot1_1d_plot = PROBE_1DPlot(
                title=plot1_title,
                data=plot1_1d_data,
                x_coords=plot1_1d_x_coords,
                palette="Viridis256",
                color_scale=ColorScale.LINEAR,
                range_mode=RangeMode.DYNAMIC,
                track_changes=True,
            )
            # Add to session
            session.add_plot("plot1", plot1_1d_plot)
            print("✅ Created Plot1 as 1D line plot")
        else:
            print("⚠️ WARNING: Could not create 1D plot for Plot1, falling back to 2D preview")
            plot1_is_1d = False  # Fall back to 2D mode
    
    if not plot1_is_1d:
        # Create Plot1 as 2D map plot (original behavior)
        map_plot = MAP_2DPlot(
            title=plot1_title,
            data=preview,
            x_coords=x_coords,
            y_coords=y_coords,
            palette="Viridis256",
            color_scale=ColorScale.LINEAR,
            range_mode=RangeMode.DYNAMIC,
            crosshairs_enabled=True,
            x_axis_label=original_map_x_label,  # Original label - will be swapped by get_flipped_x_axis_label() if needed
            y_axis_label=original_map_y_label,  # Original label - will be swapped by get_flipped_y_axis_label() if needed
            needs_flip=plot1_needs_flip,
            track_changes=True,
        )

    # Add plot to session and create history
    if plot1_is_1d and plot1_1d_plot is not None:
        # Already added to session above
        plot1_history = PlotStateHistory(plot1_1d_plot, max_history=20)
        # For 1D plot, use the 1D data and coordinates
        plot1_data = None  # Not used for 1D line plot
        plot1_x_coords = plot1_1d_x_coords
        plot1_y_coords = None
    else:
        # Add 2D map plot to session
        session.add_plot("plot1", map_plot)
        # Create plot history for undo/redo
        # Reduced max_history from 50 to 20 for better performance
        plot1_history = PlotStateHistory(map_plot, max_history=20)
        # Get flipped data and coordinates for Bokeh plot - ALWAYS use flipped methods
        # This ensures consistency - if needs_flip is True, these return flipped versions
        plot1_data = map_plot.get_flipped_data()
        plot1_x_coords = map_plot.get_flipped_x_coords()
        plot1_y_coords = map_plot.get_flipped_y_coords()

    print("🔍 DEBUG: Plot1 Data and Coordinates:")
    if plot1_is_1d and plot1_1d_plot is not None:
        print(f"  Plot1 is 1D line plot")
        print(f"  plot1_1d_data.shape: {plot1_1d_data.shape if plot1_1d_data is not None else 'None'}")
        print(f"  plot1_x_coords length: {len(plot1_x_coords) if plot1_x_coords is not None else 'None'}")
        print(f"  plot1_x_coords range: [{np.min(plot1_x_coords):.2f}, {np.max(plot1_x_coords):.2f}]" if plot1_x_coords is not None else "  plot1_x_coords: None")
        print(f"  X axis label: {original_map_x_label}")
        print(f"  Y axis label: Intensity")
    else:
        print(f"  map_plot.needs_flip: {map_plot.needs_flip if map_plot is not None else 'N/A'}")
        print(f"  Original preview.shape: {preview.shape if preview is not None else 'None'}")
        print(f"  plot1_data.shape: {plot1_data.shape if plot1_data is not None else 'None'}")
        print(f"  Original x_coords length: {len(x_coords) if x_coords is not None else 'None'}")
        print(f"  Original y_coords length: {len(y_coords) if y_coords is not None else 'None'}")
        print(f"  plot1_x_coords length: {len(plot1_x_coords) if plot1_x_coords is not None else 'None'}")
        print(f"  plot1_y_coords length: {len(plot1_y_coords) if plot1_y_coords is not None else 'None'}")
        print(f"  plot1_x_coords range: [{np.min(plot1_x_coords):.2f}, {np.max(plot1_x_coords):.2f}]" if plot1_x_coords is not None else "  plot1_x_coords: None")
        print(f"  plot1_y_coords range: [{np.min(plot1_y_coords):.2f}, {np.max(plot1_y_coords):.2f}]" if plot1_y_coords is not None else "  plot1_y_coords: None")
        print(f"  X axis label: {map_plot.get_flipped_x_axis_label() if map_plot is not None else 'N/A'}")
        print(f"  Y axis label: {map_plot.get_flipped_y_axis_label() if map_plot is not None else 'N/A'}")
    if not plot1_is_1d or plot1_1d_plot is None:
        print(f"  Data shape matches coords: data.shape[1]={plot1_data.shape[1] if plot1_data is not None else 'N/A'} == len(plot1_x_coords)={len(plot1_x_coords) if plot1_x_coords is not None else 'N/A'}, data.shape[0]={plot1_data.shape[0] if plot1_data is not None else 'N/A'} == len(plot1_y_coords)={len(plot1_y_coords) if plot1_y_coords is not None else 'N/A'}")
        if plot1_data is not None and plot1_x_coords is not None and plot1_y_coords is not None:
            # Bokeh image() interprets data as (rows, cols) = (height, width)
            # So data.shape[1] (columns) should match x_coords (width)
            # And data.shape[0] (rows) should match y_coords (height)
            if plot1_data.shape[1] != len(plot1_x_coords) or plot1_data.shape[0] != len(plot1_y_coords):
                print(f"  ⚠️ WARNING: Data shape {plot1_data.shape} does NOT match coordinate lengths!")
                print(f"     Expected: data.shape[1]={plot1_data.shape[1]} == len(x_coords)={len(plot1_x_coords)}")
                print(f"     Expected: data.shape[0]={plot1_data.shape[0]} == len(y_coords)={len(plot1_y_coords)}")
            else:
                print(f"  ✅ Data shape matches coordinate lengths")
                print(f"     data.shape[1]={plot1_data.shape[1]} == len(x_coords)={len(plot1_x_coords)} (columns/width)")
                print(f"     data.shape[0]={plot1_data.shape[0]} == len(y_coords)={len(plot1_y_coords)} (rows/height)")
        print(f"  X axis label (from get_flipped_x_axis_label): {map_plot.get_flipped_x_axis_label() if map_plot is not None else 'N/A'}")
        print(f"  Y axis label (from get_flipped_y_axis_label): {map_plot.get_flipped_y_axis_label() if map_plot is not None else 'N/A'}")
        print(f"  X ticks will show values from: plot1_x_coords (first few: {plot1_x_coords[:3] if plot1_x_coords is not None and len(plot1_x_coords) >= 3 else plot1_x_coords if plot1_x_coords is not None else 'None'})")
        print(f"  Y ticks will show values from: plot1_y_coords (first few: {plot1_y_coords[:3] if plot1_y_coords is not None and len(plot1_y_coords) >= 3 else plot1_y_coords if plot1_y_coords is not None else 'None (Plot1 is 1D)'})")
        # Check if data orientation matches what we expect
        if plot1_data is not None and preview is not None and map_plot is not None and map_plot.needs_flip:
            print(f"  🔄 FLIPPED: Checking data orientation...")
            print(f"     Original data.shape: {preview.shape}")
            print(f"     Transposed data.shape: {plot1_data.shape}")
            print(f"     Original data[0,0]={preview[0,0]}, Transposed data[0,0]={plot1_data[0,0]} (should be original[0,0] if no transpose)")
            print(f"     Original data[-1,-1]={preview[-1,-1]}, Transposed data[-1,-1]={plot1_data[-1,-1]} (should be original[-1,-1] if no transpose)")
            print(f"     Original data[0,-1]={preview[0,-1]}, Transposed data[0,-1]={plot1_data[0,-1]} (should be original[-1,0] if transposed)")
            print(f"     Original data[-1,0]={preview[-1,0]}, Transposed data[-1,0]={plot1_data[-1,0]} (should be original[0,-1] if transposed)")
            # Verify transpose: transposed[i,j] should equal original[j,i]
            if plot1_data[0,0] == preview[0,0] and plot1_data[-1,-1] == preview[-1,-1]:
                print(f"     ⚠️ WARNING: Data might not be transposed! Corner values match original.")
            if plot1_data[0,-1] == preview[-1,0] and plot1_data[-1,0] == preview[0,-1]:
                print(f"     ✅ Data appears to be correctly transposed")
            # Check coordinate mapping
            print(f"     Original x_coords (px, length {len(x_coords) if x_coords is not None else 0}): first={x_coords[0]:.2f}, last={x_coords[-1]:.2f}" if x_coords is not None else "     Original x_coords: None")
            print(f"     Original y_coords (py, length {len(y_coords) if y_coords is not None else 0}): first={y_coords[0]:.2f}, last={y_coords[-1]:.2f}" if y_coords is not None else "     Original y_coords: None (Plot1 is 1D)")
            print(f"     Flipped x_coords (length {len(plot1_x_coords) if plot1_x_coords is not None else 0}): first={plot1_x_coords[0]:.2f}, last={plot1_x_coords[-1]:.2f} (ALWAYS px, goes on x-axis)" if plot1_x_coords is not None else "     Flipped x_coords: None")
            print(f"     Flipped y_coords (length {len(plot1_y_coords) if plot1_y_coords is not None else 0}): first={plot1_y_coords[0]:.2f}, last={plot1_y_coords[-1]:.2f} (ALWAYS py, goes on y-axis)" if plot1_y_coords is not None else "     Flipped y_coords: None (Plot1 is 1D)")
            print(f"     X axis label: {map_plot.get_flipped_x_axis_label()} (swapped if data transposed)")
            print(f"     Y axis label: {map_plot.get_flipped_y_axis_label()} (swapped if data transposed)")
            # Verify coordinate-to-data mapping
            # IMPORTANT: px (x_coords) ALWAYS goes on x-axis, py (y_coords) ALWAYS goes on y-axis
            # We only transpose the DATA if dimensions don't match, but coordinates never swap
            if plot1_y_coords is not None:
                print(f"     🔍 Coordinate-to-Data Mapping Verification:")
                print(f"        Logic: px (x_coords) ALWAYS on x-axis, py (y_coords) ALWAYS on y-axis")
                print(f"        Data.shape[1]={plot1_data.shape[1]} (x-axis/width) should match len(plot1_x_coords)={len(plot1_x_coords) if plot1_x_coords is not None else 0} (px)")
                print(f"        Data.shape[0]={plot1_data.shape[0]} (y-axis/height) should match len(plot1_y_coords)={len(plot1_y_coords)} (py)")
                if plot1_data.shape[1] == len(plot1_x_coords) and plot1_data.shape[0] == len(plot1_y_coords):
                    print(f"        ✅ Coordinate lengths match data dimensions")
                else:
                    print(f"        ⚠️ WARNING: Coordinate lengths DO NOT match data dimensions!")
                    print(f"           This will cause misalignment between data and axes!")
            else:
                print(f"     ⚠️ Skipping coordinate mapping verification (Plot1 is 1D, no y_coords)")

    # Calculate initial range values and create color mapper
    # Initialize color mapper and renderer variables (needed for nonlocal in callbacks)
    color_mapper1 = None
    image_renderer1 = None
    color_mapper1b = None
    image_renderer1b = None
    color_mapper2 = None
    image_renderer2 = None
    color_mapper2b = None
    image_renderer2b = None
    color_mapper3 = None
    image_renderer3 = None
    
    if plot1_is_1d and plot1_1d_plot is not None:
        # For 1D plot, calculate range from 1D data
        map_min_val = float(np.percentile(plot1_1d_data[~np.isnan(plot1_1d_data)], 1))
        map_max_val = float(np.percentile(plot1_1d_data[~np.isnan(plot1_1d_data)], 99))
        # Set initial range values in plot1_1d_plot
        plot1_1d_plot.range_min = map_min_val
        plot1_1d_plot.range_max = map_max_val
        # No color mapper for 1D line plots
        color_mapper1 = None
    else:
        # Calculate initial range values from 1st and 99th percentiles for 2D plot
        map_min_val = float(np.percentile(plot1_data[~np.isnan(plot1_data)], 1))
        map_max_val = float(np.percentile(plot1_data[~np.isnan(plot1_data)], 99))
        # Set initial range values in map_plot
        if map_plot is not None:
            map_plot.range_min = map_min_val
            map_plot.range_max = map_max_val
        # Create color mapper (store in variable for later updates)
        color_mapper1 = LinearColorMapper(palette=map_plot.palette if map_plot is not None else "Viridis256", low=map_min_val, high=map_max_val)

    # Calculate initial plot dimensions
    if plot1_is_1d and plot1_1d_plot is not None:
        # For 1D plots, use default dimensions (no colorbar needed)
        initial_width = 400
        initial_height = 400
        colorbar_width = 0  # No colorbar for 1D line plots
        plot_width_with_colorbar = initial_width
        plot_height = initial_height
    else:
        # Calculate initial plot dimensions from map_plot (respects user settings: Square, Custom, Aspect ratio)
        initial_width, initial_height = map_plot.calculate_plot_dimensions() if map_plot is not None else (400, 400)
        # Add extra width to account for vertical colorbar on the right (typically ~60 pixels)
        colorbar_width = 60
        plot_width_with_colorbar = initial_width + colorbar_width
        plot_height = initial_height
    
    # For Plot1, we use match_aspect=True to maintain 1:1 aspect ratio based on coordinate ranges
    # The map_plot.calculate_plot_dimensions() already respects user settings, so we just add colorbar width
    # Create Bokeh figure for Plot1 - either 1D line plot or 2D image plot
    if plot1_is_1d and plot1_1d_plot is not None:
        # Create 1D line plot
        print(f"🔍 DEBUG: Creating Plot1 as 1D line plot")
        plot1 = figure(
            title=plot1_title,
            x_range=(float(np.min(plot1_x_coords)), float(np.max(plot1_x_coords))),
            y_range=(float(np.min(plot1_1d_data)), float(np.max(plot1_1d_data))),
            tools="pan,wheel_zoom,box_zoom,reset,tap",
            width=plot_width_with_colorbar,
            height=plot_height,
        )
        # Set axis labels
        plot1.xaxis.axis_label = original_map_x_label
        plot1.yaxis.axis_label = "Intensity"
        # Set ticks from x coordinates
        if plot1_x_coords is not None:
            set_ticks_from_coords(plot1, plot1_x_coords, axis='x', num_ticks=10)
    else:
        # Create 2D image plot (original behavior)
        print(f"🔍 DEBUG: Plot1 dimensions from map_plot: {initial_width}x{initial_height}, with colorbar={plot_width_with_colorbar}x{plot_height}")
        # Use match_aspect=True to maintain 1:1 aspect ratio based on coordinate ranges
        # When Plot1 is 1D, plot1_y_coords is None, so derive y_range from data shape
        if plot1_y_coords is not None:
            plot1_y_range = (float(np.min(plot1_y_coords)), float(np.max(plot1_y_coords)))
            use_match_aspect = True  # Maintain 1:1 aspect ratio based on coordinate ranges
        else:
            # When Plot1 is 1D, use data shape for y_range (y-axis is just index-based)
            # Use plot1_1d_data if available, otherwise fallback
            if plot1_is_1d and plot1_1d_data is not None:
                data_shape_0 = plot1_1d_data.shape[0]
            elif plot1_data is not None:
                data_shape_0 = plot1_data.shape[0]
            else:
                data_shape_0 = len(plot1_x_coords) if plot1_x_coords is not None else 1
            plot1_y_range = (0, float(data_shape_0 - 1))
            use_match_aspect = False  # Don't match aspect when y-axis is index-based
        
        plot1 = figure(
            title=plot1_title,
            x_range=(float(np.min(plot1_x_coords)), float(np.max(plot1_x_coords))),
            y_range=plot1_y_range,
            tools="pan,wheel_zoom,box_zoom,reset,tap",
            match_aspect=use_match_aspect,  # Maintain 1:1 aspect ratio based on coordinate ranges (only when y_coords exist)
            width=plot_width_with_colorbar,
            height=plot_height,
        )

        # Set axis labels (already swapped in map_plot if needed)
        if map_plot is not None:
            plot1.xaxis.axis_label = map_plot.get_flipped_x_axis_label()
            plot1.yaxis.axis_label = map_plot.get_flipped_y_axis_label()

    # Set ticks on Plot1 from flipped coordinate arrays (only for 2D plots)
    # The coordinates are already in the correct order from get_flipped_x_coords/y_coords
    if not plot1_is_1d or plot1_1d_plot is None:
        set_ticks_from_coords_both_axes(
            plot1,
            x_coords=plot1_x_coords,
            y_coords=plot1_y_coords,
            x_sample_interval=15,
            y_sample_interval=15,
        )

    # VERIFICATION: Bokeh expectations for Plot1
    if plot1_is_1d and plot1_1d_plot is not None:
        print("🔍 VERIFICATION: Plot1 is 1D line plot")
        print(f"   Our data.shape: {plot1_1d_data.shape if plot1_1d_data is not None else 'None'}")
        print(f"   Our x_coords length: {len(plot1_x_coords) if plot1_x_coords is not None else 'None'} (should match data length)")
        if plot1_1d_data is not None and plot1_x_coords is not None:
            if len(plot1_1d_data) == len(plot1_x_coords):
                print(f"   ✅ VERIFIED: 1D data format matches expectations!")
                print(f"      data length={len(plot1_1d_data)} == len(x_coords)={len(plot1_x_coords)}")
            else:
                print(f"   ❌ ERROR: 1D data format does NOT match expectations!")
                print(f"      data length={len(plot1_1d_data)} != len(x_coords)={len(plot1_x_coords)}")
    else:
        # VERIFICATION: Bokeh image() expects data as (rows, cols) = (height, width)
        # Standard NumPy convention: array[row, col] where:
        # - shape[0] = number of rows = vertical dimension = y-axis (height) → should match y_coords length
        # - shape[1] = number of columns = horizontal dimension = x-axis (width) → should match x_coords length
        # This is why data.shape[1] maps to x-axis (width) and data.shape[0] maps to y-axis (height)
        print("🔍 VERIFICATION: Bokeh image() data format expectations:")
        print(f"   NumPy convention: array[row, col] → shape[0]=rows (y-axis/height), shape[1]=cols (x-axis/width)")
        print(f"   Bokeh interprets: data.shape[0] = rows = y-axis (height)")
        print(f"   Bokeh interprets: data.shape[1] = cols = x-axis (width)")
        print(f"   Our data.shape: {plot1_data.shape if plot1_data is not None else 'None'}")
        print(f"   Our x_coords length: {len(plot1_x_coords) if plot1_x_coords is not None else 'None'} (should match data.shape[1])")
        print(f"   Our y_coords length: {len(plot1_y_coords) if plot1_y_coords is not None else 'None'} (should match data.shape[0])")
        if plot1_data is not None and plot1_x_coords is not None and plot1_y_coords is not None:
            if plot1_data.shape[1] == len(plot1_x_coords) and plot1_data.shape[0] == len(plot1_y_coords):
                print(f"   ✅ VERIFIED: Data format matches Bokeh expectations!")
                print(f"      data.shape[1]={plot1_data.shape[1]} == len(x_coords)={len(plot1_x_coords)} (x-axis/width)")
                print(f"      data.shape[0]={plot1_data.shape[0]} == len(y_coords)={len(plot1_y_coords)} (y-axis/height)")
            else:
                print(f"   ❌ ERROR: Data format does NOT match Bokeh expectations!")
                print(f"      data.shape[1]={plot1_data.shape[1]} != len(x_coords)={len(plot1_x_coords)}")
                print(f"      data.shape[0]={plot1_data.shape[0]} != len(y_coords)={len(plot1_y_coords)}")
                print(f"      This will cause misalignment between data and axes!")

    # Symlog transformation function for handling negative values in log scale
    def symlog_transform(y, linthresh=1e-10):
        """
        Symmetric log transformation: sign(y) * log(|y|) for |y| >= linthresh, linear otherwise.
        
        Args:
            y: Input array (can contain negative, zero, or positive values)
            linthresh: Linear threshold - values with |y| < linthresh are treated linearly
        
        Returns:
            Transformed array
        """
        y = np.asarray(y, dtype=float)
        result = np.zeros_like(y)
        
        # Handle values above threshold
        mask_above = np.abs(y) >= linthresh
        result[mask_above] = np.sign(y[mask_above]) * np.log(np.abs(y[mask_above]) / linthresh) + linthresh
        
        # Handle values below threshold (linear region)
        mask_below = ~mask_above
        result[mask_below] = y[mask_below]
        
        return result
    
    # Store original 1D data for log scale transformation
    plot1_1d_data_original = None
    if plot1_is_1d and plot1_1d_data is not None:
        plot1_1d_data_original = plot1_1d_data.copy()
    
    # Create data source and renderer for Plot1 - either 1D line or 2D image
    if plot1_is_1d and plot1_1d_plot is not None:
        # Create 1D line plot
        source1 = ColumnDataSource(data={"x": plot1_x_coords, "y": plot1_1d_data})
        line_renderer1 = plot1.line("x", "y", source=source1, line_width=2, line_color="blue")
        print("✅ Plot1 line renderer created successfully")
        # No colorbar for 1D line plots
        colorbar1 = None
    else:
        # Create 2D image plot (original behavior)
        # When Plot1 is 1D, plot1_y_coords is None, so use data shape for y position and height
        if plot1_y_coords is not None:
            plot1_y_pos = float(np.min(plot1_y_coords))
            plot1_y_height = float(np.max(plot1_y_coords) - np.min(plot1_y_coords))
        else:
            # When Plot1 is 1D, y-axis is just index-based (0 to shape[0]-1)
            # Use plot1_1d_data if available, otherwise fallback
            if plot1_is_1d and plot1_1d_data is not None:
                data_shape_0 = plot1_1d_data.shape[0]
            elif plot1_data is not None:
                data_shape_0 = plot1_data.shape[0]
            else:
                data_shape_0 = len(plot1_x_coords) if plot1_x_coords is not None else 1
            plot1_y_pos = 0.0
            plot1_y_height = float(data_shape_0 - 1)
        
        source1 = ColumnDataSource(
            data={
                "image": [plot1_data],
                "x": [float(np.min(plot1_x_coords))],
                "y": [plot1_y_pos],
                "dw": [float(np.max(plot1_x_coords) - np.min(plot1_x_coords))],
                "dh": [plot1_y_height],
            }
        )

        # Add image renderer
        try:
            image_renderer1 = plot1.image(
                "image", source=source1, x="x", y="y", dw="dw", dh="dh", color_mapper=color_mapper1
            )
            print("✅ Plot1 image renderer created successfully")
        except Exception as e:
            print(f"⚠️ ERROR creating Plot1 image renderer: {e}")
            import traceback
            traceback.print_exc()

        # Create colorbar
        try:
            colorbar1 = ColorBar(color_mapper=color_mapper1, title="", location=(1, 0))
            plot1.add_layout(colorbar1, "right")
            print("✅ Plot1 colorbar added successfully")
        except Exception as e:
            print(f"⚠️ ERROR adding Plot1 colorbar: {e}")
            import traceback
            traceback.print_exc()

    # Add TapTool to Plot1 for crosshair positioning
    try:
        tap_tool1 = TapTool()
        plot1.add_tools(tap_tool1)
        print("✅ Plot1 TapTool added successfully")
    except Exception as e:
        print(f"⚠️ ERROR adding Plot1 TapTool: {e}")
        import traceback
        traceback.print_exc()

    # Function to draw crosshairs on Plot1
    def draw_cross1():
        """Draw crosshairs on Plot1 based on current slider values."""
        try:
            if plot1_is_1d and plot1_1d_plot is not None:
                # For 1D plots, only draw a vertical line at the x position
                # First, clear any old crosshair renderers
                if hasattr(rect1, 'v1line') and rect1.v1line is not None:
                    try:
                        if rect1.v1line in plot1.renderers:
                            plot1.renderers.remove(rect1.v1line)
                    except (ValueError, AttributeError):
                        pass
                    rect1.v1line = None
                
                x_index = get_x_index()
                if plot1_x_coords is not None and x_index < len(plot1_x_coords):
                    x_coord = plot1_x_coords[x_index]
                    # Draw vertical line
                    rect1.v1line = plot1.line(
                        [x_coord, x_coord],
                        [plot1.y_range.start, plot1.y_range.end],
                        line_color='red',
                        line_width=2,
                        line_dash='dashed'
                    )
            else:
                # For 2D plots, draw both horizontal and vertical crosshairs
                # First, clear any old crosshair renderers from Plot1 using stored references
                if hasattr(rect1, 'h1line') and rect1.h1line is not None:
                    try:
                        if rect1.h1line in plot1.renderers:
                            plot1.renderers.remove(rect1.h1line)
                    except (ValueError, AttributeError):
                        pass
                    rect1.h1line = None
                
                if hasattr(rect1, 'v1line') and rect1.v1line is not None:
                    try:
                        if rect1.v1line in plot1.renderers:
                            plot1.renderers.remove(rect1.v1line)
                    except (ValueError, AttributeError):
                        pass
                    rect1.v1line = None
                
                # Also clear map_plot's stored renderers if they're on Plot1
                if map_plot is not None:
                    if hasattr(map_plot, '_crosshair_h_line') and map_plot._crosshair_h_line is not None:
                        try:
                            if map_plot._crosshair_h_line in plot1.renderers:
                                plot1.renderers.remove(map_plot._crosshair_h_line)
                        except (ValueError, AttributeError):
                            pass
                        map_plot._crosshair_h_line = None
                    
                    if hasattr(map_plot, '_crosshair_v_line') and map_plot._crosshair_v_line is not None:
                        try:
                            if map_plot._crosshair_v_line in plot1.renderers:
                                plot1.renderers.remove(map_plot._crosshair_v_line)
                        except (ValueError, AttributeError):
                            pass
                        map_plot._crosshair_v_line = None
                
                x_index = get_x_index()
                y_index = get_y_index()

                # Get coordinates using flipped coordinate arrays
                # These are already in the correct order for the plot
                if plot1_x_coords is None or plot1_y_coords is None:
                    print("⚠️ WARNING: plot1_x_coords or plot1_y_coords is None in draw_cross1()")
                    return

                # Use the utility function from the plot library
                draw_crosshairs_from_indices(
                    map_plot=map_plot,
                    bokeh_figure=plot1,
                    x_index=x_index,
                    y_index=y_index,
                    x_coords=plot1_x_coords,
                    y_coords=plot1_y_coords,
                    rect_storage=rect1,
                )
        except Exception as e:
            print(f"⚠️ ERROR in draw_cross1(): {e}")
            import traceback
            traceback.print_exc()
            return

        # Also update Plot1B crosshairs if it exists
        try:
            if plot1b is not None and map_plot_b is not None:
                draw_cross1b()
        except (NameError, AttributeError):
            pass  # Plot1B not created yet
        
        # Also update Plot3 crosshairs (synchronized with Plot1)
        try:
            draw_cross3()
        except (NameError, AttributeError):
            pass  # Plot3 not created yet

    # Function to draw crosshairs on Plot3 (synchronized with Plot1)
    def draw_cross3():
        """Draw crosshairs on Plot3 using the same coordinates as Plot1."""
        try:
            # Check if plot3 exists (it's defined in the outer scope)
            try:
                if plot3 is None:
                    return
            except NameError:
                return  # Plot3 not created yet

            # First, clear any existing crosshair renderers from Plot3 using stored references
            if hasattr(rect3_crosshair, 'h1line') and rect3_crosshair.h1line is not None:
                try:
                    if rect3_crosshair.h1line in plot3.renderers:
                        plot3.renderers.remove(rect3_crosshair.h1line)
                except (ValueError, AttributeError):
                    pass
                rect3_crosshair.h1line = None
            
            if hasattr(rect3_crosshair, 'v1line') and rect3_crosshair.v1line is not None:
                try:
                    if rect3_crosshair.v1line in plot3.renderers:
                        plot3.renderers.remove(rect3_crosshair.v1line)
                except (ValueError, AttributeError):
                    pass
                rect3_crosshair.v1line = None

            x_index = get_x_index()
            
            # Handle 1D plots (when Plot1 is 1D, Plot3 is also 1D)
            if plot1_is_1d and plot3_x_coords is not None:
                # For 1D plots, only draw a vertical line at the x position
                if x_index < len(plot3_x_coords):
                    x_coord = plot3_x_coords[x_index]
                    # Draw vertical line
                    rect3_crosshair.v1line = plot3.line(
                        [x_coord, x_coord],
                        [plot3.y_range.start, plot3.y_range.end],
                        line_color='red',
                        line_width=2,
                        line_dash='dashed'
                    )
                return
            
            # For 2D plots, need both x and y coordinates
            if plot3_x_coords is None or plot3_y_coords is None:
                print("⚠️ WARNING: plot3_x_coords or plot3_y_coords is None in draw_cross3()")
                return
            
            y_index = get_y_index()

            # Temporarily store Plot1's crosshair renderers so we don't overwrite them
            # Save current Plot1 crosshair renderers
            plot1_h_line_backup = None
            plot1_v_line_backup = None
            if hasattr(map_plot, '_crosshair_h_line'):
                plot1_h_line_backup = map_plot._crosshair_h_line
            if hasattr(map_plot, '_crosshair_v_line'):
                plot1_v_line_backup = map_plot._crosshair_v_line
            
            # Clear map_plot's crosshair renderer references so it creates new ones for Plot3
            map_plot._crosshair_h_line = None
            map_plot._crosshair_v_line = None

            # Use the utility function from the plot library
            # Plot3 uses the same coordinate system as Plot1, so we can use map_plot
            draw_crosshairs_from_indices(
                map_plot=map_plot,
                bokeh_figure=plot3,
                x_index=x_index,
                y_index=y_index,
                x_coords=plot3_x_coords,
                y_coords=plot3_y_coords,
                rect_storage=rect3_crosshair,
            )
            
            # Restore Plot1's crosshair renderer references
            map_plot._crosshair_h_line = plot1_h_line_backup
            map_plot._crosshair_v_line = plot1_v_line_backup
            
        except NameError:
            # Plot3 not created yet, silently return
            return
        except Exception as e:
            print(f"⚠️ ERROR in draw_cross3(): {e}")
            import traceback
            traceback.print_exc()
            return

    # Function to draw crosshairs on Plot1B (synchronized with Plot1)
    def draw_cross1b():
        """Draw crosshairs on Plot1B using the same coordinates as Plot1."""
        if 'plot1b' not in locals() or plot1b is None or map_plot_b is None:
            return

        try:
            x_index = get_x_index()
            y_index = get_y_index()

            # Use the utility function from the plot library
            # It will automatically get coordinates from map_plot_b if not provided
            draw_crosshairs_from_indices(
                map_plot=map_plot_b,
                bokeh_figure=plot1b,
                x_index=x_index,
                y_index=y_index,
                x_coords=None,  # Will use map_plot_b.get_flipped_x_coords()
                y_coords=None,  # Will use map_plot_b.get_flipped_y_coords()
                rect_storage=rect1b,
            )
        except Exception as e:
            print(f"⚠️ ERROR in draw_cross1b(): {e}")
            import traceback
            traceback.print_exc()
            return

    # Note: Tap handler for Plot1 will be defined after sliders are created
    # Note: UI update function and undo/redo callbacks will be set up after all UI elements are created

    # Create Plot2 (Probe view) using SCLib plot classes
    # Initialize plot2 to None in case creation fails
    plot2 = None
    source2 = None
    color_mapper2 = None
    image_renderer2 = None
    colorbar2 = None
    probe_1d_plot = None
    probe_2d_plot = None
    plot2_history = None
    initial_slice_1d = None
    initial_slice = None
    box_annotation_2 = None  # Only created for 2D plots (4D volumes)

    if is_3d_volume:
        # 1D plot for 3D volume OR 2D volume when Plot1 is 1D
        if plot1_is_1d and len(volume.shape) == 2:
            # When Plot1 is 1D and volume is 2D (x,z), take slice at x_index to get z
            initial_slice_1d = volume[volume.shape[0]//2, :]
            print(f"  Plot1 is 1D: Extracting 1D slice (z) from 2D volume at x_index={volume.shape[0]//2}")
        else:
            # Normal 3D volume case
            initial_slice_1d = volume[volume.shape[0]//2, volume.shape[1]//2, :]

        # Try to load probe coordinates for Plot2 1D
        plot2_x_coords_1d = None
        plot2_x_label = "Probe Index"
        if hasattr(self.process_4dnexus, 'probe_x_coords_picked') and self.process_4dnexus.probe_x_coords_picked:
            try:
                probe_coords = self.process_4dnexus.load_probe_coordinates(use_b=False)
                if probe_coords is not None and len(probe_coords) == len(initial_slice_1d):
                    plot2_x_coords_1d = probe_coords
                    plot2_x_label = self.process_4dnexus.probe_x_coords_picked
                else:
                    plot2_x_coords_1d = np.arange(len(initial_slice_1d))
            except:
                plot2_x_coords_1d = np.arange(len(initial_slice_1d))
        else:
            plot2_x_coords_1d = np.arange(len(initial_slice_1d))

        # Get Plot2 title from dataset source (volume_picked)
        plot2_title_1d = getattr(self.process_4dnexus, 'volume_picked', None) or "Plot2 - 1D Probe View"
        
        # Create PROBE_1DPlot
        probe_1d_plot = PROBE_1DPlot(
            title=plot2_title_1d,
            data=initial_slice_1d,
            x_coords=plot2_x_coords_1d,
            palette="Viridis256",
            color_scale=ColorScale.LINEAR,
            range_mode=RangeMode.DYNAMIC,
            track_changes=True,
        )

        # Add to session
        session.add_plot("plot2", probe_1d_plot)
        # Reduced max_history from 50 to 20 for better performance
        plot2_history = PlotStateHistory(probe_1d_plot, max_history=20)

        # Create Bokeh figure (smaller size: 300x300)
        # For 1D plots, add BoxSelectTool configured for x-range selection only (bar selection)
        box_select_1d = BoxSelectTool(dimensions="width")  # Only select x-range (width dimension)

        # Get Plot2 title from dataset source (volume_picked)
        plot2_title = getattr(self.process_4dnexus, 'volume_picked', None) or "Plot2 - 1D Probe View"

        plot2 = figure(
            title=plot2_title,
            tools="pan,wheel_zoom,box_zoom,reset,tap",
            x_range=(float(np.min(plot2_x_coords_1d)), float(np.max(plot2_x_coords_1d))),
            y_range=(float(np.min(initial_slice_1d)), float(np.max(initial_slice_1d))),
            width=plot_width_with_colorbar,
            height=initial_height,
        )
        # Store base dimensions for Probe Scale control (1D plot)
        plot2_base_area_width = plot_width_with_colorbar - colorbar_width
        plot2_base_area_height = initial_height
        plot2_data_aspect_ratio = None
        plot2.add_tools(box_select_1d)

        # Set axis labels and ticks for Plot2 1D (use last component of path)
        plot2_x_label_last = get_last_path_component(plot2_x_label) if plot2_x_label and plot2_x_label != "Probe Index" else plot2_x_label
        set_axis_labels(plot2, x_label=plot2_x_label_last, y_label="Intensity")

        # Set ticks from probe coordinates if available
        if hasattr(self.process_4dnexus, 'probe_x_coords_picked') and self.process_4dnexus.probe_x_coords_picked and plot2_x_coords_1d is not None and len(plot2_x_coords_1d) == len(initial_slice_1d):
            set_ticks_from_coords(plot2, plot2_x_coords_1d, axis='x', num_ticks=10)

        source2 = ColumnDataSource(data={"x": plot2_x_coords_1d, "y": initial_slice_1d})
        plot2.line("x", "y", source=source2, line_width=2, line_color="blue")
    else:
        # 2D plot for 4D volume OR 3D volume when Plot1 is 1D
        if len(volume.shape) == 3:
            # Volume is 3D (x,z,u) - this happens when Plot1 is 1D or when we have a 3D volume
            # Take slice at x_index to get (z,u)
            initial_slice = volume[volume.shape[0]//2, :, :]
            print(f"  Volume is 3D: Extracting 2D slice (z,u) from 3D volume at x_index={volume.shape[0]//2}")
        elif len(volume.shape) == 4:
            # Normal 4D volume case (x,y,z,u)
            initial_slice = volume[volume.shape[0]//2, volume.shape[1]//2, :, :]
            print(f"  Volume is 4D: Extracting 2D slice (z,u) from 4D volume at x_index={volume.shape[0]//2}, y_index={volume.shape[1]//2}")
        else:
            raise ValueError(f"Unexpected volume shape: {volume.shape}, expected 3D or 4D")

        # Detect if probe coordinates need flipping
        print("=" * 80)
        print("🔍 DEBUG: Probe Flip Detection for Plot2:")
        print(f"  volume.shape: {volume.shape}")
        probe_x_coord_size = None
        probe_y_coord_size = None
        if hasattr(self.process_4dnexus, 'probe_x_coords_picked') and self.process_4dnexus.probe_x_coords_picked:
            probe_x_coord_size = self.process_4dnexus.get_dataset_size_from_path(self.process_4dnexus.probe_x_coords_picked)
            print(f"  probe_x_coords_picked: {self.process_4dnexus.probe_x_coords_picked}")
            print(f"  probe_x_coord_size: {probe_x_coord_size}")
        if hasattr(self.process_4dnexus, 'probe_y_coords_picked') and self.process_4dnexus.probe_y_coords_picked:
            probe_y_coord_size = self.process_4dnexus.get_dataset_size_from_path(self.process_4dnexus.probe_y_coords_picked)
            print(f"  probe_y_coords_picked: {self.process_4dnexus.probe_y_coords_picked}")
            print(f"  probe_y_coord_size: {probe_y_coord_size}")

        plot2_needs_flip = self.process_4dnexus.detect_probe_flip_needed(
            volume.shape,
            probe_x_coord_size,
            probe_y_coord_size
        )
        print(f"  plot2_needs_flip: {plot2_needs_flip}")
        print("=" * 80)

        # Store original coordinate paths for axis labels
        # NOTE: Pass ORIGINAL labels to PROBE_2DPlot - it will handle swapping via get_flipped_x_axis_label()
        # Extract just the last component for axis labels
        probe_x_path = getattr(self.process_4dnexus, 'probe_x_coords_picked', None)
        probe_y_path = getattr(self.process_4dnexus, 'probe_y_coords_picked', None)
        original_probe_x_label = get_last_path_component(probe_x_path) or 'Probe X'
        original_probe_y_label = get_last_path_component(probe_y_path) or 'Probe Y'

        # Labels are already extracted to last component above

        # Load actual probe coordinate arrays (cache them for future use)
        # Check if cached coordinates match current path - if not, clear cache and reload
        cached_x_path = getattr(self.process_4dnexus, '_cached_probe_x_coords_path', None)
        cached_y_path = getattr(self.process_4dnexus, '_cached_probe_y_coords_path', None)
        current_x_path = getattr(self.process_4dnexus, 'probe_x_coords_picked', None)
        current_y_path = getattr(self.process_4dnexus, 'probe_y_coords_picked', None)

        # Clear cache if path has changed
        if cached_x_path != current_x_path:
            self.process_4dnexus._cached_probe_x_coords = None
            self.process_4dnexus._cached_probe_x_coords_path = None
        if cached_y_path != current_y_path:
            self.process_4dnexus._cached_probe_y_coords = None
            self.process_4dnexus._cached_probe_y_coords_path = None

        probe_x_coords_array = getattr(self.process_4dnexus, '_cached_probe_x_coords', None)
        probe_y_coords_array = getattr(self.process_4dnexus, '_cached_probe_y_coords', None)

        if probe_x_coords_array is None and hasattr(self.process_4dnexus, 'probe_x_coords_picked') and self.process_4dnexus.probe_x_coords_picked:
            try:
                probe_x_coords_array = self.process_4dnexus.load_dataset_by_path(self.process_4dnexus.probe_x_coords_picked)
                if probe_x_coords_array is not None and probe_x_coords_array.ndim == 1:
                    probe_x_coords_array = np.array(probe_x_coords_array)
                    self.process_4dnexus._cached_probe_x_coords = probe_x_coords_array  # Cache for future use
                    self.process_4dnexus._cached_probe_x_coords_path = self.process_4dnexus.probe_x_coords_picked  # Cache path
            except:
                probe_x_coords_array = None
        if probe_y_coords_array is None and hasattr(self.process_4dnexus, 'probe_y_coords_picked') and self.process_4dnexus.probe_y_coords_picked:
            try:
                probe_y_coords_array = self.process_4dnexus.load_dataset_by_path(self.process_4dnexus.probe_y_coords_picked)
                if probe_y_coords_array is not None and probe_y_coords_array.ndim == 1:
                    probe_y_coords_array = np.array(probe_y_coords_array)
                    self.process_4dnexus._cached_probe_y_coords = probe_y_coords_array  # Cache for future use
                    self.process_4dnexus._cached_probe_y_coords_path = self.process_4dnexus.probe_y_coords_picked  # Cache path
            except:
                probe_y_coords_array = None

        # Map probe coordinates to slice dimensions
        # initial_slice has shape (z_size, u_size) from volume[x, y, :, :]
        # - initial_slice.shape[0] = z (from volume.shape[2])
        # - initial_slice.shape[1] = u (from volume.shape[3])
        # 
        # IMPORTANT: px (x_coords) ALWAYS goes on x-axis, py (y_coords) ALWAYS goes on y-axis
        # We only transpose the DATA if dimensions don't match, but coordinates never swap
        # 
        # The detect_probe_flip_needed() function determines if we need to transpose:
        # - If px matches z and py matches u: no transpose (data stays (z, u))
        # - If px matches u and py matches z: transpose needed (data becomes (u, z))
        # 
        # So we simply pass px and py directly - the flip logic will handle transposing the data
        if probe_x_coords_array is not None and probe_y_coords_array is not None:
            # px always goes on x-axis, py always goes on y-axis
            plot2_x_coords_for_plot = probe_x_coords_array  # px → x-axis
            plot2_y_coords_for_plot = probe_y_coords_array  # py → y-axis
        else:
            # Fallback to indices if coordinate arrays not available
            plot2_x_coords_for_plot = np.arange(initial_slice.shape[1])  # u dimension
            plot2_y_coords_for_plot = np.arange(initial_slice.shape[0])  # z dimension

        # Get Plot2 title from dataset source (volume_picked)
        plot2_title_2d = getattr(self.process_4dnexus, 'volume_picked', None) or "Plot2 - 2D Probe View"
        
        # Create PROBE_2DPlot (data will be transposed for display)
        # Pass original labels - the plot object will handle flipping via its methods
        probe_2d_plot = PROBE_2DPlot(
            title=plot2_title_2d,
            data=initial_slice,
            x_coords=plot2_x_coords_for_plot,
            y_coords=plot2_y_coords_for_plot,
            palette="Viridis256",
            color_scale=ColorScale.LINEAR,
            range_mode=RangeMode.DYNAMIC,
            x_axis_label=original_probe_x_label,  # Original label - will be swapped by get_flipped_x_axis_label() if needed
            y_axis_label=original_probe_y_label,  # Original label - will be swapped by get_flipped_y_axis_label() if needed
            needs_flip=plot2_needs_flip,
            track_changes=True,
        )

        # Add to session
        session.add_plot("plot2", probe_2d_plot)
        # Reduced max_history from 50 to 20 for better performance
        plot2_history = PlotStateHistory(probe_2d_plot, max_history=20)

        # Prepare data and coordinates for Bokeh plot using PROBE_2DPlot flipped methods
        # The probe_2d_plot object handles all flipping logic internally
        plot2_data = probe_2d_plot.get_flipped_data()
        plot2_x_coords = probe_2d_plot.get_flipped_x_coords()
        plot2_y_coords = probe_2d_plot.get_flipped_y_coords()

        # If flipped methods return None, fall back to manual calculation
        if plot2_data is None:
            plot2_data = initial_slice  # Use original data if get_flipped_data() returns None
        if plot2_x_coords is None:
            plot2_x_coords = np.arange(plot2_data.shape[1])
        if plot2_y_coords is None:
            plot2_y_coords = np.arange(plot2_data.shape[0])

        # CRITICAL: Validate that coordinates match flipped data shape
        # Bokeh expects: data.shape[1] == len(x_coords), data.shape[0] == len(y_coords)
        if plot2_data is not None and plot2_x_coords is not None and plot2_y_coords is not None:
            if plot2_data.shape[1] != len(plot2_x_coords) or plot2_data.shape[0] != len(plot2_y_coords):
                print(f"⚠️ WARNING in Plot2 initial setup: Coordinate mismatch detected!")
                print(f"   plot2_data.shape={plot2_data.shape}")
                print(f"   len(plot2_x_coords)={len(plot2_x_coords)}, len(plot2_y_coords)={len(plot2_y_coords)}")
                print(f"   Recomputing coordinates to match data shape...")
                # Recompute coordinates to match flipped data shape
                plot2_x_coords = np.arange(plot2_data.shape[1])
                plot2_y_coords = np.arange(plot2_data.shape[0])

        # Create Bokeh figure (smaller size: 300x300)
        # Add BoxSelectTool for rectangle region selection with persistent=True to keep box visible
        box_select_2d = BoxSelectTool(dimensions="both", persistent=True)  # Select both x and y ranges, keep box visible

        # Get Plot2 title from dataset source (volume_picked)
        plot2_title = getattr(self.process_4dnexus, 'volume_picked', None) or "Plot2 - 2D Probe View"

        # Calculate aspect ratio from Plot2 data shape for 1:1 display
        # Data shape is (height, width) in numpy: shape[0]=rows (y-axis/height), shape[1]=cols (x-axis/width)
        if plot2_data is not None and len(plot2_data.shape) == 2:
            plot2_data_width = plot2_data.shape[1]  # Number of columns (x dimension) - e.g., 487
            plot2_data_height = plot2_data.shape[0]  # Number of rows (y dimension) - e.g., 407
            plot2_data_aspect_ratio = plot2_data_width / plot2_data_height  # e.g., 487/407 ≈ 1.197
            print(f"🔍 DEBUG: Plot2 data aspect ratio from shape: {plot2_data_aspect_ratio:.3f} (width={plot2_data_width}, height={plot2_data_height})")
            
            # Calculate plot dimensions to maintain 1:1 aspect ratio based on data shape
            # Use height as base, then calculate width to maintain aspect ratio
            base_height = initial_height
            plot2_area_height = base_height
            plot2_area_width = int(base_height * plot2_data_aspect_ratio)  # Make width proportional to aspect ratio
            
            # Add extra width to account for vertical colorbar on the right
            plot2_width_with_colorbar = plot2_area_width + colorbar_width
            plot2_height = plot2_area_height
            
            print(f"🔍 DEBUG: Plot2 dimensions: plot_area={plot2_area_width}x{plot2_area_height}, with colorbar={plot2_width_with_colorbar}x{plot2_height}")
            # Store base dimensions for Probe Scale control
            plot2_base_area_width = plot2_area_width
            plot2_base_area_height = plot2_area_height
        else:
            # Fallback to original calculation if data shape not available
            plot2_width_with_colorbar = plot_width_with_colorbar
            plot2_height = initial_height
            plot2_data_aspect_ratio = None
            # Store base dimensions for Probe Scale control (1D plot)
            plot2_base_area_width = plot_width_with_colorbar - colorbar_width
            plot2_base_area_height = initial_height
        
        plot2 = figure(
            title=plot2_title,
            tools="pan,wheel_zoom,box_zoom,reset,tap",
            x_range=(float(np.min(plot2_x_coords)), float(np.max(plot2_x_coords))),
            y_range=(float(np.min(plot2_y_coords)), float(np.max(plot2_y_coords))),
            match_aspect=False,  # We maintain aspect ratio manually via dimensions
            width=plot2_width_with_colorbar,
            height=plot2_height,
        )
        plot2.add_tools(box_select_2d)

        # Create BoxAnnotation for persistent selection rectangle on Plot2
        box_annotation_2 = BoxAnnotation(
            left=None, right=None, top=None, bottom=None,
            fill_alpha=0.1, fill_color='blue',
            line_color='blue', line_width=2, line_dash='dashed'
        )
        plot2.add_layout(box_annotation_2)

        # Set axis labels using flipped methods from probe_2d_plot
        plot2.xaxis.axis_label = probe_2d_plot.get_flipped_x_axis_label() or original_probe_x_label
        plot2.yaxis.axis_label = probe_2d_plot.get_flipped_y_axis_label() or original_probe_y_label

        # VERIFICATION: For 4D volume (x, y, z, u) OR 3D volume when Plot1 is 1D, Plot2 shows slice (z, u)
        # - For 4D: initial_slice = volume[:, :, :, :] gives shape (z, u) = (volume.shape[2], volume.shape[3])
        # - For 3D when Plot1 is 1D: initial_slice = volume[x, :, :] gives shape (z, u) = (volume.shape[1], volume.shape[2])
        # - Bokeh interprets: data.shape[0] = rows = y-axis (height), data.shape[1] = cols = x-axis (width)
        # - After flipping (if needed): data.shape[1] should match x_coords, data.shape[0] should match y_coords
        print("🔍 VERIFICATION: Plot2 data and coordinate mapping:")
        if plot1_is_1d and len(volume.shape) == 3:
            print(f"   For 3D volume (x, z, u) with Plot1 1D: slice has shape (z, u) = (volume.shape[1], volume.shape[2])")
            print(f"   Volume dimensions: z={volume.shape[1]}, u={volume.shape[2]}")
        elif len(volume.shape) == 4:
            print(f"   For 4D volume (x, y, z, u): slice has shape (z, u) = (volume.shape[2], volume.shape[3])")
            print(f"   Volume dimensions: z={volume.shape[2]}, u={volume.shape[3]}")
        else:
            print(f"   For volume with shape {volume.shape}: slice dimensions depend on volume structure")
            if len(volume.shape) >= 2:
                print(f"   Volume dimensions available: {volume.shape}")
        print(f"   Our data.shape: {plot2_data.shape if plot2_data is not None else 'None'} (after flip if needed)")
        print(f"   px (x_coords) length: {len(plot2_x_coords) if plot2_x_coords is not None else 'None'} (should map to x-axis/width)")
        print(f"   py (y_coords) length: {len(plot2_y_coords) if plot2_y_coords is not None else 'None'} (should map to y-axis/height)")
        print(f"   Bokeh interprets: data.shape[0] = rows = y-axis (height), data.shape[1] = cols = x-axis (width)")
        if plot2_data is not None and plot2_x_coords is not None and plot2_y_coords is not None:
            # Bokeh convention: data.shape[1] (cols/x-axis/width) should match x_coords
            # Bokeh convention: data.shape[0] (rows/y-axis/height) should match y_coords
            shape1_matches_x = plot2_data.shape[1] == len(plot2_x_coords)
            shape0_matches_y = plot2_data.shape[0] == len(plot2_y_coords)

            if shape1_matches_x and shape0_matches_y:
                print(f"   ✅ VERIFIED: Plot2 data format matches Bokeh expectations!")
                print(f"      data.shape[1]={plot2_data.shape[1]} == len(x_coords)={len(plot2_x_coords)} (x-axis/width)")
                print(f"      data.shape[0]={plot2_data.shape[0]} == len(y_coords)={len(plot2_y_coords)} (y-axis/height)")
            else:
                print(f"   ❌ ERROR: Data and coordinates do NOT match Bokeh expectations!")
                print(f"      data.shape[0]={plot2_data.shape[0]}, data.shape[1]={plot2_data.shape[1]}")
                print(f"      len(px)={len(plot2_x_coords)}, len(py)={len(plot2_y_coords)}")
                if not shape1_matches_x:
                    print(f"      data.shape[1]={plot2_data.shape[1]} != len(x_coords)={len(plot2_x_coords)} (x-axis/width should match)")
                if not shape0_matches_y:
                        print(f"      data.shape[0]={plot2_data.shape[0]} != len(y_coords)={len(plot2_y_coords)} (y-axis/height should match)")
                print(f"      This will cause misalignment between data and axes!")

        source2 = ColumnDataSource(
            data={
                "image": [plot2_data],
                "x": [float(np.min(plot2_x_coords))],
                "y": [float(np.min(plot2_y_coords))],
                "dw": [float(np.max(plot2_x_coords) - np.min(plot2_x_coords))],
                "dh": [float(np.max(plot2_y_coords) - np.min(plot2_y_coords))],
            }
        )
        
        # Calculate data range for color mapper
        valid_data = plot2_data[~np.isnan(plot2_data)]
        if valid_data.size > 0:
            probe_min_val = float(np.percentile(valid_data, 1))
            probe_max_val = float(np.percentile(valid_data, 99))
            print(f"🔍 DEBUG: Plot2 data range: min={probe_min_val:.3f}, max={probe_max_val:.3f}, valid_points={valid_data.size}")
        else:
            # Fallback if all data is NaN
            probe_min_val = 0.0
            probe_max_val = 1.0
            print(f"⚠️ WARNING: Plot2 data is all NaN, using default range [0, 1]")
        
        color_mapper2 = LinearColorMapper(palette="Viridis256", low=probe_min_val, high=probe_max_val)
        print(f"✅ Created color_mapper2: low={color_mapper2.low:.3f}, high={color_mapper2.high:.3f}, palette={color_mapper2.palette}")
        
        image_renderer2 = plot2.image(
            "image", source=source2, x="x", y="y", dw="dw", dh="dh", color_mapper=color_mapper2
        )
        colorbar2 = ColorBar(color_mapper=color_mapper2, title="", location=(1, 0))
        plot2.add_layout(colorbar2, "right")
        print(f"✅ Plot2 image renderer and colorbar created successfully")
        
        # Store original Plot2 slice data for reset functionality
        plot2_original_data = {
            "image": [plot2_data.copy()],
            "x": [float(np.min(plot2_x_coords))],
            "y": [float(np.min(plot2_y_coords))],
            "dw": [float(np.max(plot2_x_coords) - np.min(plot2_x_coords))],
            "dh": [float(np.max(plot2_y_coords) - np.min(plot2_y_coords))],
        }
        plot2_original_min = probe_min_val
        plot2_original_max = probe_max_val

    # Helper functions for coordinate/index conversion (needed before Plot2B creation)
    # Note: These functions will be redefined after sliders are created to use slider values
    def get_x_index(coord=None):
        """Get X index from coordinate or slider value."""
        if coord is None:
            # Try to get from slider if it exists, otherwise use middle value
            try:
                coord = x_slider.value
            except (NameError, AttributeError):
                coord = float(np.min(x_coords) + (np.max(x_coords) - np.min(x_coords)) / 2)
        # Find closest index
        idx = np.argmin(np.abs(x_coords - coord))
        return max(0, min(idx, len(x_coords) - 1))

    def get_y_index(coord=None):
        """Get Y index from coordinate or slider value."""
        # When Plot1 is 1D, y_coords is None - return middle index of volume's second dimension
        if y_coords is None:
            if len(volume.shape) >= 2:
                return volume.shape[1] // 2  # Return middle of second dimension
            else:
                return 0
        
        if coord is None:
            # Try to get from slider if it exists, otherwise use middle value
            try:
                # Check if y_slider exists in the enclosing scope
                if y_slider is not None:
                    try:
                        coord = y_slider.value
                    except (AttributeError, TypeError):
                        coord = float(np.min(y_coords) + (np.max(y_coords) - np.min(y_coords)) / 2)
                else:
                    coord = float(np.min(y_coords) + (np.max(y_coords) - np.min(y_coords)) / 2)
            except NameError:
                # y_slider doesn't exist in scope, use middle value
                coord = float(np.min(y_coords) + (np.max(y_coords) - np.min(y_coords)) / 2)
        # Find closest index
        idx = np.argmin(np.abs(y_coords - coord))
        return max(0, min(idx, len(y_coords) - 1))

    # Create Plot2B if enabled
    plot2b = None
    source2b = None
    color_mapper2b = None
    image_renderer2b = None
    colorbar2b = None
    probe_2d_plot_b = None
    plot2b_is_2d = False
    probe2b_min_val = None
    probe2b_max_val = None
    initial_slice_1d_b = None

    if hasattr(self.process_4dnexus, 'volume_picked_b') and self.process_4dnexus.volume_picked_b:
        try:
            # Load Plot2B volume - check cache first, but always validate
            cached_path = getattr(self.process_4dnexus, '_cached_volume_b_path', None)
            if (hasattr(self.process_4dnexus, '_cached_volume_b') and 
                cached_path == self.process_4dnexus.volume_picked_b and
                self.process_4dnexus._cached_volume_b is not None):
                # Validate cached volume still has correct shape
                volume_b = self.process_4dnexus._cached_volume_b
                # Double-check by verifying it's the right dataset
                try:
                    # Quick validation: check if it's a valid array
                    if hasattr(volume_b, 'shape') and len(volume_b.shape) >= 2:
                        print(f"✅ Using cached volume_b for {self.process_4dnexus.volume_picked_b} (shape: {volume_b.shape})")
                    else:
                        print(f"⚠️ Cached volume_b invalid, reloading...")
                        volume_b = None
                except:
                    print(f"⚠️ Error validating cached volume_b, reloading...")
                    volume_b = None
            else:
                volume_b = None

            if volume_b is None:
                # Clear cache if path changed
                if cached_path != self.process_4dnexus.volume_picked_b:
                    self.process_4dnexus._cached_volume_b = None
                    self.process_4dnexus._cached_volume_b_path = None

                # Load and cache volume_b
                volume_b = self.process_4dnexus.load_dataset_by_path(self.process_4dnexus.volume_picked_b)
                if volume_b is not None:
                    # Validate the loaded data
                    if hasattr(volume_b, 'shape') and len(volume_b.shape) >= 2:
                        self.process_4dnexus._cached_volume_b = volume_b
                        self.process_4dnexus._cached_volume_b_path = self.process_4dnexus.volume_picked_b
                        print(f"✅ Loaded and cached volume_b for {self.process_4dnexus.volume_picked_b} (type: {type(volume_b).__name__}, shape: {volume_b.shape})")
                    else:
                        print(f"⚠️ WARNING: Loaded volume_b has invalid shape: {volume_b.shape if hasattr(volume_b, 'shape') else 'N/A'}")
                        volume_b = None
                else:
                        print(f"⚠️ WARNING: Failed to load volume_b for {self.process_4dnexus.volume_picked_b}")

            if volume_b is not None:
                # Check if Plot2B should be 2D or 1D
                # When Plot1 is 1D, a 3D volume should be treated as 2D for Plot2B (showing z,u slice)
                # When Plot1 is 1D, a 2D volume should be treated as 1D for Plot2B (showing z)
                if plot1_is_1d:
                    if len(volume_b.shape) == 3:
                        # 3D volume (x,z,u) -> Plot2B should be 2D showing (z,u)
                        plot2b_is_2d = True  # Force 2D plot
                        print(f"  Plot1 is 1D mode: Volume B is 3D (x,z,u), Plot2B will be 2D showing (z,u)")
                    elif len(volume_b.shape) == 2:
                        # 2D volume (x,z) -> Plot2B should be 1D showing z
                        plot2b_is_2d = False  # Force 1D plot
                        print(f"  Plot1 is 1D mode: Volume B is 2D (x,z), Plot2B will be 1D showing z")
                    else:
                        plot2b_is_2d = len(volume_b.shape) == 4
                else:
                    plot2b_is_2d = len(volume_b.shape) == 4

                # Get initial slice
                x_idx = get_x_index()
                y_idx = get_y_index()

                if plot2b_is_2d:
                    # 2D probe plot - can be from 4D volume OR 3D volume when Plot1 is 1D
                    if plot1_is_1d and len(volume_b.shape) == 3:
                        # Volume B is 3D (x,z,u) - when Plot1 is 1D, extract 2D slice (z,u) at x_idx
                        initial_slice_b = volume_b[x_idx, :, :]
                        print(f"  Volume B is 3D: Extracting 2D slice (z,u) from 3D volume B at x_index={x_idx}")
                    elif len(volume_b.shape) == 4:
                        # Normal 4D volume case (x,y,z,u)
                        initial_slice_b = volume_b[x_idx, y_idx, :, :]
                        print(f"  Volume B is 4D: Extracting 2D slice (z,u) from 4D volume B at x_index={x_idx}, y_index={y_idx}")
                    else:
                        raise ValueError(f"Unexpected volume_b shape: {volume_b.shape}, expected 3D or 4D")

                    # Detect flip for Plot2B
                    plot2b_probe_x_coord_size = None
                    plot2b_probe_y_coord_size = None
                    if hasattr(self.process_4dnexus, 'probe_x_coords_picked_b') and self.process_4dnexus.probe_x_coords_picked_b:
                        plot2b_probe_x_coord_size = self.process_4dnexus.get_dataset_size_from_path(self.process_4dnexus.probe_x_coords_picked_b)
                    if hasattr(self.process_4dnexus, 'probe_y_coords_picked_b') and self.process_4dnexus.probe_y_coords_picked_b:
                        plot2b_probe_y_coord_size = self.process_4dnexus.get_dataset_size_from_path(self.process_4dnexus.probe_y_coords_picked_b)

                    plot2b_needs_flip = self.process_4dnexus.detect_probe_flip_needed(
                        volume_b.shape,
                        plot2b_probe_x_coord_size,
                        plot2b_probe_y_coord_size
                    )

                    # Get axis labels for Plot2B
                    # NOTE: Pass ORIGINAL labels to PROBE_2DPlot - it will handle swapping via get_flipped_x_axis_label()
                    # Extract just the last component for axis labels
                    plot2b_x_path = getattr(self.process_4dnexus, 'probe_x_coords_picked_b', None)
                    plot2b_y_path = getattr(self.process_4dnexus, 'probe_y_coords_picked_b', None)
                    original_plot2b_x_label = get_last_path_component(plot2b_x_path) or "Probe X"
                    original_plot2b_y_label = get_last_path_component(plot2b_y_path) or "Probe Y"

                    # Load actual probe coordinate arrays for Plot2B (cache them for future use)
                    # Check if cached coordinates match current path - if not, clear cache and reload
                    cached_x_path_b = getattr(self.process_4dnexus, '_cached_probe_x_coords_path_b', None)
                    cached_y_path_b = getattr(self.process_4dnexus, '_cached_probe_y_coords_path_b', None)
                    current_x_path_b = getattr(self.process_4dnexus, 'probe_x_coords_picked_b', None)
                    current_y_path_b = getattr(self.process_4dnexus, 'probe_y_coords_picked_b', None)

                    # Clear cache if path has changed
                    if cached_x_path_b != current_x_path_b:
                        self.process_4dnexus._cached_probe_x_coords_b = None
                        self.process_4dnexus._cached_probe_x_coords_path_b = None
                    if cached_y_path_b != current_y_path_b:
                        self.process_4dnexus._cached_probe_y_coords_b = None
                        self.process_4dnexus._cached_probe_y_coords_path_b = None

                    plot2b_probe_x_coords_array = getattr(self.process_4dnexus, '_cached_probe_x_coords_b', None)
                    plot2b_probe_y_coords_array = getattr(self.process_4dnexus, '_cached_probe_y_coords_b', None)

                    if plot2b_probe_x_coords_array is None and hasattr(self.process_4dnexus, 'probe_x_coords_picked_b') and self.process_4dnexus.probe_x_coords_picked_b:
                        try:
                            plot2b_probe_x_coords_array = self.process_4dnexus.load_dataset_by_path(self.process_4dnexus.probe_x_coords_picked_b)
                            if plot2b_probe_x_coords_array is not None and plot2b_probe_x_coords_array.ndim == 1:
                                plot2b_probe_x_coords_array = np.array(plot2b_probe_x_coords_array)
                                self.process_4dnexus._cached_probe_x_coords_b = plot2b_probe_x_coords_array  # Cache for future use
                                self.process_4dnexus._cached_probe_x_coords_path_b = self.process_4dnexus.probe_x_coords_picked_b  # Cache path
                        except:
                            plot2b_probe_x_coords_array = None
                    if plot2b_probe_y_coords_array is None and hasattr(self.process_4dnexus, 'probe_y_coords_picked_b') and self.process_4dnexus.probe_y_coords_picked_b:
                        try:
                            plot2b_probe_y_coords_array = self.process_4dnexus.load_dataset_by_path(self.process_4dnexus.probe_y_coords_picked_b)
                            if plot2b_probe_y_coords_array is not None and plot2b_probe_y_coords_array.ndim == 1:
                                plot2b_probe_y_coords_array = np.array(plot2b_probe_y_coords_array)
                                self.process_4dnexus._cached_probe_y_coords_b = plot2b_probe_y_coords_array  # Cache for future use
                                self.process_4dnexus._cached_probe_y_coords_path_b = self.process_4dnexus.probe_y_coords_picked_b  # Cache path
                        except:
                            plot2b_probe_y_coords_array = None

                    # Map probe coordinates to slice dimensions for Plot2B
                    # initial_slice_b has shape (z_size, u_size) 
                    # When Plot1 is 1D and volume_b is 3D: from volume_b[x, :, :] -> (z, u)
                    # When volume_b is 4D: from volume_b[x, y, :, :] -> (z, u)
                    # Dimension 0 (rows, z) = z_size, Dimension 1 (cols, u) = u_size
                    # For PROBE_2DPlot: x_coords maps to columns (dimension 1), y_coords maps to rows (dimension 0)
                    if plot2b_probe_x_coords_array is not None and plot2b_probe_y_coords_array is not None:
                        # IMPORTANT: px (x_coords) ALWAYS goes on x-axis, py (y_coords) ALWAYS goes on y-axis
                        # We only transpose the DATA if dimensions don't match, but coordinates never swap
                        # The detect_probe_flip_needed() function determines if we need to transpose the data
                        # px always goes on x-axis, py always goes on y-axis
                        plot2b_x_coords_for_plot = plot2b_probe_x_coords_array  # px → x-axis
                        plot2b_y_coords_for_plot = plot2b_probe_y_coords_array  # py → y-axis
                    else:
                        # Fallback to indices if coordinate arrays not available
                        plot2b_x_coords_for_plot = np.arange(initial_slice_b.shape[1])
                        plot2b_y_coords_for_plot = np.arange(initial_slice_b.shape[0])

                    # Get Plot2B title from dataset source (volume_picked_b)
                    plot2b_title_2d = getattr(self.process_4dnexus, 'volume_picked_b', None) or "Plot2B - 2D Probe View"
                    
                    # Create PROBE_2DPlot for Plot2B
                    # Pass original labels - the plot object will handle flipping via its methods
                    probe_2d_plot_b = PROBE_2DPlot(
                        title=plot2b_title_2d,
                        data=initial_slice_b,
                        x_coords=plot2b_x_coords_for_plot,
                        y_coords=plot2b_y_coords_for_plot,
                        palette="Viridis256",
                        color_scale=ColorScale.LINEAR,
                        range_mode=RangeMode.DYNAMIC,
                        x_axis_label=original_plot2b_x_label,  # Original label - px label always goes on x-axis
                        y_axis_label=original_plot2b_y_label,  # Original label - py label always goes on y-axis
                        needs_flip=plot2b_needs_flip,
                        track_changes=True,
                    )

                    # Prepare data and coordinates for Bokeh plot using PROBE_2DPlot flipped methods
                    plot2b_data = probe_2d_plot_b.get_flipped_data()
                    plot2b_x_coords = probe_2d_plot_b.get_flipped_x_coords()
                    plot2b_y_coords = probe_2d_plot_b.get_flipped_y_coords()

                    # If flipped methods return None, fall back to manual calculation
                    if plot2b_data is None:
                        plot2b_data = initial_slice_b  # Use original data if get_flipped_data() returns None
                    if plot2b_x_coords is None:
                        plot2b_x_coords = np.arange(plot2b_data.shape[1])
                    if plot2b_y_coords is None:
                        plot2b_y_coords = np.arange(plot2b_data.shape[0])

                    # Create Bokeh figure (smaller size: 300x300)
                    # Add BoxSelectTool for rectangle region selection with persistent=True to keep box visible
                    box_select_2db = BoxSelectTool(dimensions="both", persistent=True)  # Select both x and y ranges, keep box visible
                    # Calculate aspect ratio from Plot2B data shape for 1:1 display
                    if plot2b_data is not None and len(plot2b_data.shape) == 2:
                        plot2b_data_width = plot2b_data.shape[1]  # Number of columns (x dimension)
                        plot2b_data_height = plot2b_data.shape[0]  # Number of rows (y dimension)
                        plot2b_data_aspect_ratio = plot2b_data_width / plot2b_data_height
                        print(f"🔍 DEBUG: Plot2B data aspect ratio from shape: {plot2b_data_aspect_ratio:.3f} (width={plot2b_data_width}, height={plot2b_data_height})")
                        
                        # Calculate plot dimensions to maintain 1:1 aspect ratio based on data shape
                        base_height = initial_height
                        plot2b_area_height = base_height
                        plot2b_area_width = int(base_height * plot2b_data_aspect_ratio)
                        
                        # Add extra width to account for vertical colorbar on the right
                        plot2b_width_with_colorbar = plot2b_area_width + colorbar_width
                        plot2b_height = plot2b_area_height
                        
                        print(f"🔍 DEBUG: Plot2B dimensions: plot_area={plot2b_area_width}x{plot2b_area_height}, with colorbar={plot2b_width_with_colorbar}x{plot2b_height}")
                        # Store base dimensions for Probe Scale control
                        plot2b_base_area_width = plot2b_area_width
                        plot2b_base_area_height = plot2b_area_height
                    else:
                        # Fallback to original calculation if data shape not available
                        plot2b_width_with_colorbar = plot_width_with_colorbar
                        plot2b_height = initial_height
                        # Store base dimensions for Probe Scale control (1D plot)
                        plot2b_base_area_width = plot_width_with_colorbar - colorbar_width
                        plot2b_base_area_height = initial_height
                    
                    plot2b = figure(
                        title=plot2b_title_2d,
                        tools="pan,wheel_zoom,box_zoom,reset,tap",
                        x_range=(float(np.min(plot2b_x_coords)), float(np.max(plot2b_x_coords))),
                        y_range=(float(np.min(plot2b_y_coords)), float(np.max(plot2b_y_coords))),
                        match_aspect=False,  # We maintain aspect ratio manually via dimensions
                        width=plot2b_width_with_colorbar,
                        height=plot2b_height,
                    )
                    plot2b.add_tools(box_select_2db)

                    # Create BoxAnnotation for persistent selection rectangle on Plot2B
                    box_annotation_2b = BoxAnnotation(
                        left=None, right=None, top=None, bottom=None,
                        fill_alpha=0.1, fill_color='green',
                        line_color='green', line_width=2, line_dash='dashed'
                    )
                    plot2b.add_layout(box_annotation_2b)

                    # Set axis labels using flipped methods from probe_2d_plot_b
                    plot2b.xaxis.axis_label = probe_2d_plot_b.get_flipped_x_axis_label() or original_plot2b_x_label
                    plot2b.yaxis.axis_label = probe_2d_plot_b.get_flipped_y_axis_label() or original_plot2b_y_label

                    # Plot2B uses Bokeh's default auto-ticker (same as Plot2)
                    # This provides intelligent tick spacing based on plot size and data range
                    # No manual tick settings needed - Bokeh will automatically choose appropriate spacing

                    # VERIFICATION: For 4D volume (x, y, z, u), Plot2B shows slice (z, u)
                    # - initial_slice_b shape depends on volume_b dimensions
                    # - We CANNOT assume data.shape[0] = y-axis and data.shape[1] = x-axis
                    # - Bokeh image() interprets: data.shape[0] = rows = y-axis (height), data.shape[1] = cols = x-axis (width)
                    # - So we need to ensure z and u are correctly mapped to y and x axes based on coordinate arrays
                    print("🔍 VERIFICATION: Plot2B Bokeh image() data format expectations:")
                    if plot1_is_1d and len(volume_b.shape) == 3:
                        print(f"   For 3D volume (x, z, u) with Plot1 1D: slice has shape (z, u) = (volume_b.shape[1], volume_b.shape[2])")
                        print(f"   Volume dimensions: z={volume_b.shape[1]}, u={volume_b.shape[2]}")
                    else:
                        print(f"   For 4D volume (x, y, z, u): slice has shape (z, u) = (volume_b.shape[2], volume_b.shape[3])")
                        if 'volume_b' in locals() or 'volume_b' in globals():
                            print(f"   Volume dimensions: z={volume_b.shape[2]}, u={volume_b.shape[3]}")
                    print(f"   Bokeh interprets: data.shape[0] = rows = y-axis (height)")
                    print(f"   Bokeh interprets: data.shape[1] = cols = x-axis (width)")
                    print(f"   Our data.shape: {plot2b_data.shape if plot2b_data is not None else 'None'} (after flip if needed)")
                    print(f"   Our x_coords (px) length: {len(plot2b_x_coords) if plot2b_x_coords is not None else 'None'} (should match data.shape[1])")
                    print(f"   Our y_coords (py) length: {len(plot2b_y_coords) if plot2b_y_coords is not None else 'None'} (should match data.shape[0])")
                    if plot2b_data is not None and plot2b_x_coords is not None and plot2b_y_coords is not None:
                        if plot2b_data.shape[1] == len(plot2b_x_coords) and plot2b_data.shape[0] == len(plot2b_y_coords):
                            print(f"   ✅ VERIFIED: Plot2B data format matches Bokeh expectations!")
                            print(f"      data.shape[1]={plot2b_data.shape[1]} == len(x_coords)={len(plot2b_x_coords)} (x-axis/width)")
                            print(f"      data.shape[0]={plot2b_data.shape[0]} == len(y_coords)={len(plot2b_y_coords)} (y-axis/height)")
                        else:
                            print(f"   ❌ ERROR: Plot2B data format does NOT match Bokeh expectations!")
                            print(f"      data.shape[1]={plot2b_data.shape[1]} != len(x_coords)={len(plot2b_x_coords)}")
                            print(f"      data.shape[0]={plot2b_data.shape[0]} != len(y_coords)={len(plot2b_y_coords)}")
                            print(f"      This will cause misalignment between data and axes!")

                    # Debug: Check if data is valid
                    print(f"🔍 DEBUG: Plot2B initial data check:")
                    print(f"   initial_slice_b.shape: {initial_slice_b.shape}")
                    print(f"   initial_slice_b min: {np.nanmin(initial_slice_b)}, max: {np.nanmax(initial_slice_b)}")
                    print(f"   initial_slice_b sum: {np.nansum(initial_slice_b)}")
                    print(f"   plot2b_data.shape: {plot2b_data.shape if plot2b_data is not None else 'None'}")
                    if plot2b_data is not None:
                        print(f"   plot2b_data min: {np.nanmin(plot2b_data)}, max: {np.nanmax(plot2b_data)}")
                        print(f"   plot2b_data sum: {np.nansum(plot2b_data)}")

                    source2b = ColumnDataSource(
                        data={
                            "image": [plot2b_data],
                            "x": [float(np.min(plot2b_x_coords))],
                            "y": [float(np.min(plot2b_y_coords))],
                            "dw": [float(np.max(plot2b_x_coords) - np.min(plot2b_x_coords))],
                            "dh": [float(np.max(plot2b_y_coords) - np.min(plot2b_y_coords))],
                        }
                    )
                    # Check if data has valid values before computing percentiles
                    valid_data = plot2b_data[~np.isnan(plot2b_data)]
                    if len(valid_data) > 0:
                        probe2b_min_val = float(np.percentile(valid_data, 1))
                        probe2b_max_val = float(np.percentile(valid_data, 99))
                    else:
                        print(f"⚠️ WARNING: Plot2B data is all NaN or empty!")
                        probe2b_min_val = 0.0
                        probe2b_max_val = 1.0
                    # Store for later use in range controls
                    color_mapper2b = LinearColorMapper(palette="Viridis256", low=probe2b_min_val, high=probe2b_max_val)
                    image_renderer2b = plot2b.image(
                        "image", source=source2b, x="x", y="y", dw="dw", dh="dh", color_mapper=color_mapper2b
                    )
                    colorbar2b = ColorBar(color_mapper=color_mapper2b, title="", location=(1, 0))
                    plot2b.add_layout(colorbar2b, "right")
                    
                    # Store original Plot2B slice data for reset functionality
                    plot2b_original_data = {
                        "image": [plot2b_data.copy()],
                        "x": [float(np.min(plot2b_x_coords))],
                        "y": [float(np.min(plot2b_y_coords))],
                        "dw": [float(np.max(plot2b_x_coords) - np.min(plot2b_x_coords))],
                        "dh": [float(np.max(plot2b_y_coords) - np.min(plot2b_y_coords))],
                    }
                    plot2b_original_min = probe2b_min_val
                    plot2b_original_max = probe2b_max_val

                    # Initialize rect2b for Plot2B selection
                    # Handle both 3D and 4D volumes
                    if plot1_is_1d and len(volume_b.shape) == 3:
                        # Volume B is 3D (x,z,u) - use z and u dimensions
                        rect2b = Rectangle(0, 0, volume_b.shape[1] - 1, volume_b.shape[2] - 1)  # Z, U from 3D volume
                    else:
                        # Normal 4D volume case
                        rect2b = Rectangle(0, 0, volume_b.shape[2] - 1, volume_b.shape[3] - 1)  # Z, U
                else:
                    # 1D probe plot - can be from 3D volume OR 2D volume when Plot1 is 1D
                    if plot1_is_1d and len(volume_b.shape) == 2:
                        # Volume B is 2D (x,z) - when Plot1 is 1D, extract 1D slice z at x_idx
                        initial_slice_1d_b = volume_b[x_idx, :]
                        print(f"  Volume B is 2D: Extracting 1D slice z from 2D volume B at x_index={x_idx}")
                    elif len(volume_b.shape) == 3:
                        # Normal 3D volume case (x,y,z)
                        initial_slice_1d_b = volume_b[x_idx, y_idx, :]
                        print(f"  Volume B is 3D: Extracting 1D slice z from 3D volume B at x_index={x_idx}, y_index={y_idx}")
                    else:
                        raise ValueError(f"Unexpected volume_b shape for 1D Plot2B: {volume_b.shape}, expected 2D or 3D")
                    # Store for later use in range controls
                    probe2b_min_val = float(np.percentile(initial_slice_1d_b[~np.isnan(initial_slice_1d_b)], 1))
                    probe2b_max_val = float(np.percentile(initial_slice_1d_b[~np.isnan(initial_slice_1d_b)], 99))
                    plot2b_title_1d = getattr(self.process_4dnexus, 'volume_picked_b', None) or "Plot2B - 1D Probe View"
                    probe_1d_plot_b = PROBE_1DPlot(
                        title=plot2b_title_1d,
                        data=initial_slice_1d_b,
                        x_coords=np.arange(len(initial_slice_1d_b)),
                        palette="Viridis256",
                        color_scale=ColorScale.LINEAR,
                        range_mode=RangeMode.DYNAMIC,
                        track_changes=True,
                    )

                    # Create Bokeh figure for 1D plot (smaller size: 300x300)
                    # For 1D plots, add BoxSelectTool configured for x-range selection only (bar selection)
                    box_select_1db = BoxSelectTool(dimensions="width")  # Only select x-range (width dimension)
                    plot2b_title_1d = getattr(self.process_4dnexus, 'volume_picked_b', None) or "Plot2B - 1D Probe View"
                    plot2b = figure(
                        title=plot2b_title_1d,
                        tools="pan,wheel_zoom,box_zoom,reset,tap",
                        x_range=(0, len(initial_slice_1d_b)),
                        y_range=(float(np.min(initial_slice_1d_b)), float(np.max(initial_slice_1d_b))),
                        width=plot_width_with_colorbar,
                        height=initial_height,
                    )
                    # Store base dimensions for Probe Scale control (1D plot)
                    plot2b_base_area_width = plot_width_with_colorbar - colorbar_width
                    plot2b_base_area_height = initial_height
                    plot2b_data_aspect_ratio = None
                    plot2b.add_tools(box_select_1db)

                    # Set axis labels and ticks for 1D Plot2B
                    plot2b_x_coords_1d = None
                    if hasattr(self.process_4dnexus, 'probe_x_coords_picked_b') and self.process_4dnexus.probe_x_coords_picked_b:
                        try:
                            probe_coords_b = self.process_4dnexus.load_probe_coordinates(use_b=True)
                            if probe_coords_b is not None and len(probe_coords_b) == len(initial_slice_1d_b):
                                plot2b_x_coords_1d = probe_coords_b
                                plot2b.xaxis.axis_label = get_last_path_component(self.process_4dnexus.probe_x_coords_picked_b) or "Probe X"
                                # Update x_range to use probe coordinates
                                plot2b.x_range.start = float(np.min(plot2b_x_coords_1d))
                                plot2b.x_range.end = float(np.max(plot2b_x_coords_1d))

                                # Set ticks from probe coordinates
                                set_ticks_from_coords(plot2b, plot2b_x_coords_1d, axis='x', num_ticks=10)
                            else:
                                plot2b_x_coords_1d = np.arange(len(initial_slice_1d_b))
                                plot2b.xaxis.axis_label = "Probe Index"
                        except:
                            plot2b_x_coords_1d = np.arange(len(initial_slice_1d_b))
                            plot2b.xaxis.axis_label = "Probe Index"
                    else:
                        plot2b_x_coords_1d = np.arange(len(initial_slice_1d_b))
                        plot2b.xaxis.axis_label = "Probe Index"
                    plot2b.yaxis.axis_label = "Intensity"

                    source2b = ColumnDataSource(data={"x": plot2b_x_coords_1d, "y": initial_slice_1d_b})
                    plot2b.line("x", "y", source=source2b, line_width=2)

                    # Initialize rect2b for Plot2B selection (1D)
                    # Handle both 2D and 3D volumes
                    if plot1_is_1d and len(volume_b.shape) == 2:
                        # Volume B is 2D (x,z) - use z dimension
                        rect2b = Rectangle(0, 0, volume_b.shape[1] - 1, volume_b.shape[1] - 1)
                    elif len(volume_b.shape) == 3:
                        # Normal 3D volume case (x,y,z)
                        rect2b = Rectangle(0, 0, volume_b.shape[2] - 1, volume_b.shape[2] - 1)
                    else:
                        # Fallback
                        rect2b = Rectangle(0, 0, 0, 0)
        except Exception as e:
            import traceback
            print(f"Failed to create Plot2B: {e}")
            traceback.print_exc()

    # Create Plot3 (Additional view) - empty initially, populated from Plot2 selections
    # Plot3 should match Plot1's orientation (respects flip) (smaller size: 300x300)
    # Use flipped coordinates from map_plot to ensure consistency, or use plot1 coordinates if Plot1 is 1D
    if plot1_is_1d and plot1_1d_plot is not None:
        # When Plot1 is 1D, use the same coordinates as Plot1
        plot3_x_coords = plot1_x_coords
        plot3_y_coords = None  # Plot1 is 1D, so no y_coords
    elif map_plot is not None:
        # Use flipped coordinates from map_plot
        plot3_x_coords = map_plot.get_flipped_x_coords()
        plot3_y_coords = map_plot.get_flipped_y_coords()
    else:
        # Fallback: use plot1 coordinates directly
        plot3_x_coords = plot1_x_coords
        plot3_y_coords = plot1_y_coords

    # Add BoxSelectTool for rectangle region selection on Plot3 with persistent=True to keep box visible
    box_select_3 = BoxSelectTool(dimensions="both", persistent=True)  # Select both x and y ranges, keep box visible
    # Get Plot3 title from dataset source (volume_picked)
    plot3_title = getattr(self.process_4dnexus, 'volume_picked', None) or "Projection -- generated"
    
    # Plot3 should use the exact same dimensions as Plot1 since they show the same type of data
    # When Plot1 is 1D, plot3_y_coords is None, so derive y_range from data shape (same as Plot1)
    if plot3_y_coords is not None:
        plot3_y_range = (float(np.min(plot3_y_coords)), float(np.max(plot3_y_coords)))
        use_match_aspect_3 = True  # Maintain 1:1 aspect ratio based on coordinate ranges
    else:
        # When Plot1 is 1D, use data shape for y_range (y-axis is just index-based)
        if plot1_is_1d and plot1_1d_data is not None:
            # Use plot1_1d_data for 1D case
            plot3_y_range = (float(np.min(plot1_1d_data)), float(np.max(plot1_1d_data)))
        elif plot1_data is not None:
            # Use plot1_data for 2D case (fallback)
            plot3_y_range = (0, float(plot1_data.shape[0] - 1))
        else:
            # Ultimate fallback
            plot3_y_range = (0, 100)
        use_match_aspect_3 = False  # Don't match aspect when y-axis is index-based or 1D
    
    # Use the same dimensions calculated for Plot1 (respects user settings and includes colorbar width)
    plot3 = figure(
        title=plot3_title,
        tools="pan,wheel_zoom,box_zoom,reset,tap",
        x_range=(float(np.min(plot3_x_coords)), float(np.max(plot3_x_coords))),
        y_range=plot3_y_range,
        match_aspect=use_match_aspect_3,  # Maintain 1:1 aspect ratio based on coordinate ranges (only when y_coords exist)
        width=plot_width_with_colorbar,  # Same width as Plot1 (includes colorbar)
        height=plot_height,  # Same height as Plot1
    )
    plot3.add_tools(box_select_3)

    # Create BoxAnnotation for persistent selection rectangle on Plot3
    box_annotation_3 = BoxAnnotation(
        left=None, right=None, top=None, bottom=None,
        fill_alpha=0.1, fill_color='red',
        line_color='red', line_width=2, line_dash='dashed'
    )
    plot3.add_layout(box_annotation_3)

    # Set axis labels for Plot3
    if plot1_is_1d and plot1_1d_plot is not None:
        # When Plot1 is 1D, use the same axis labels as Plot1
        plot3.xaxis.axis_label = original_map_x_label if 'original_map_x_label' in locals() else "X"
        plot3.yaxis.axis_label = "Intensity"
    elif map_plot is not None:
        # Use flipped axis labels from map_plot
        plot3.xaxis.axis_label = map_plot.get_flipped_x_axis_label()
        plot3.yaxis.axis_label = map_plot.get_flipped_y_axis_label()
    else:
        # Fallback
        plot3.xaxis.axis_label = "X"
        plot3.yaxis.axis_label = "Y"

    # Create Plot3 renderer based on Plot1 type (1D line plot or 2D image)
    image_renderer3 = None
    line_renderer3 = None
    source3 = None
    source3_1d = None
    color_mapper3 = None
    colorbar3 = None
    # Use a mutable container to avoid nonlocal issues when code is executed via exec()
    plot3_1d_data_original = [None]  # Store original Plot3 1D data for log scale transformation
    
    if plot1_is_1d and plot1_1d_plot is not None:
        # Plot3 should be a 1D line plot when Plot1 is 1D
        source3_1d = ColumnDataSource(
            data={
                "x": [],
                "y": [],
            }
        )
        # Create line renderer for 1D plot
        line_renderer3 = plot3.line("x", "y", source=source3_1d, line_width=2, line_color="blue")
    else:
        # Plot3 should be a 2D image when Plot1 is 2D
        source3 = ColumnDataSource(
            data={
                "image": [],
                "x": [],
                "y": [],
                "dw": [],
                "dh": [],
            }
        )
        # Create color mapper for Plot3
        color_mapper3 = LinearColorMapper(palette="Viridis256", low=0.0, high=1.0)
        image_renderer3 = plot3.image(
            "image", source=source3, x="x", y="y", dw="dw", dh="dh", color_mapper=color_mapper3
        )
        colorbar3 = ColorBar(color_mapper=color_mapper3, title="", location=(1, 0))
        plot3.add_layout(colorbar3, "right")

    # Create sliders using SCLib UI (compact with inline labels)
    x_slider = create_slider(
        title="",  # No title, we'll add label inline
        start=float(np.min(x_coords)),
        end=float(np.max(x_coords)),
        value=float(np.min(x_coords) + (np.max(x_coords) - np.min(x_coords)) / 2),
        step=0.01,
        width=200
    )

    # Only create y_slider when y_coords exists (not when Plot1 is 1D)
    y_slider = None
    if y_coords is not None:
        y_slider = create_slider(
            title="",  # No title, we'll add label inline
            start=float(np.min(y_coords)),
            end=float(np.max(y_coords)),
            value=float(np.min(y_coords) + (np.max(y_coords) - np.min(y_coords)) / 2),
            step=0.01,
            width=200
        )
    
    # Create compact slider layout with inline labels (all on one line)
    # When Plot1 is 1D, only show x_slider
    if y_slider is not None:
        sliders_row = row(
            create_label_div("X:", width=30), x_slider,
            create_label_div("Y:", width=30), y_slider,
            sizing_mode="stretch_width"
        )
    else:
        sliders_row = row(
            create_label_div("X:", width=30), x_slider,
            sizing_mode="stretch_width"
        )
    sliders_column = column(sliders_row, sizing_mode="stretch_width")

    # Function to update Plot2 based on crosshair position
    def show_slice():
        """Update Plot2 based on current crosshair position (x_index, y_index)."""
        x_idx = get_x_index()
        
        # When Plot1 is 1D, there's no y_idx - use x_idx to select volume slice
        if plot1_is_1d:
            y_idx = None  # Not used when Plot1 is 1D
        else:
            y_idx = get_y_index()

        if is_3d_volume:
            # For 3D: update 1D line plot
            if plot1_is_1d and len(volume.shape) == 2:
                # When Plot1 is 1D and volume is 2D (x,z), take slice at x_idx to get z
                slice_1d = volume[x_idx, :]
            else:
                # Normal 3D volume case
                slice_1d = volume[x_idx, y_idx, :]
            # Try to use probe coordinates if available
            if hasattr(self.process_4dnexus, 'probe_x_coords_picked') and self.process_4dnexus.probe_x_coords_picked:
                try:
                    probe_coords = self.process_4dnexus.load_probe_coordinates()
                    if probe_coords is not None and len(probe_coords) == len(slice_1d):
                        x_coords_1d = probe_coords
                    else:
                        x_coords_1d = np.arange(len(slice_1d))
                except:
                    x_coords_1d = np.arange(len(slice_1d))
            else:
                x_coords_1d = np.arange(len(slice_1d))

            source2.data = {"x": x_coords_1d, "y": slice_1d}
            
            # Preserve zoom state: only update x_range if coordinates have changed
            coords_min = float(np.min(x_coords_1d))
            coords_max = float(np.max(x_coords_1d))
            if (_plot2_zoom_state["x_range"]["coords_min"] is None or 
                _plot2_zoom_state["x_range"]["coords_max"] is None or
                abs(_plot2_zoom_state["x_range"]["coords_min"] - coords_min) > 1e-6 or
                abs(_plot2_zoom_state["x_range"]["coords_max"] - coords_max) > 1e-6):
                # Coordinates changed - update range
                plot2.x_range.start = coords_min
                plot2.x_range.end = coords_max
                _plot2_zoom_state["x_range"]["coords_min"] = coords_min
                _plot2_zoom_state["x_range"]["coords_max"] = coords_max
                _plot2_zoom_state["x_range"]["min"] = coords_min
                _plot2_zoom_state["x_range"]["max"] = coords_max
                _plot2_zoom_state["is_manual_zoom"] = False
            # else: preserve current zoom state (user has zoomed)

            # Update ticks from probe coordinates if available
            if hasattr(self.process_4dnexus, 'probe_x_coords_picked') and self.process_4dnexus.probe_x_coords_picked:
                set_ticks_from_coords(plot2, x_coords_1d, axis='x', num_ticks=10)

            # Update y-range based on mode
            # Check if range inputs exist and are enabled (User Specified mode) or disabled (Dynamic mode)
            try:
                if range2_min_input is not None and not range2_min_input.disabled:
                    # User Specified mode - preserve zoom state, only use input values if they're set
                    try:
                        if range2_min_input.value and range2_max_input.value:
                            min_val = float(range2_min_input.value)
                            max_val = float(range2_max_input.value)
                            plot2.y_range.start = min_val
                            plot2.y_range.end = max_val
                            _plot2_zoom_state["y_range"]["min"] = min_val
                            _plot2_zoom_state["y_range"]["max"] = max_val
                        # else: preserve current zoom state
                    except:
                        # Fallback: preserve current zoom if possible, otherwise use data range
                        if _plot2_zoom_state["y_range"]["min"] is None:
                            plot2.y_range.start = float(np.min(slice_1d))
                            plot2.y_range.end = float(np.max(slice_1d))
                        # else: preserve current zoom state
                else:
                    # Dynamic mode - recompute from current slice
                    probe_min = float(np.percentile(slice_1d[~np.isnan(slice_1d)], 1))
                    probe_max = float(np.percentile(slice_1d[~np.isnan(slice_1d)], 99))
                    plot2.y_range.start = probe_min
                    plot2.y_range.end = probe_max
                    _plot2_zoom_state["y_range"]["min"] = probe_min
                    _plot2_zoom_state["y_range"]["max"] = probe_max
                    # Update range inputs so user can see the computed values
                    # Use add_next_tick_callback to ensure updates happen in next Bokeh tick
                    from bokeh.io import curdoc
                    update_func = update_range_inputs_safely(
                        range2_min_input, range2_max_input, probe_min, probe_max, use_callback=True
                    )
                    curdoc().add_next_tick_callback(update_func)
            except NameError:
                # Range inputs not defined yet - use Dynamic mode as default
                probe_min = float(np.percentile(slice_1d[~np.isnan(slice_1d)], 1))
                probe_max = float(np.percentile(slice_1d[~np.isnan(slice_1d)], 99))
                plot2.y_range.start = probe_min
                plot2.y_range.end = probe_max
                _plot2_zoom_state["y_range"]["min"] = probe_min
                _plot2_zoom_state["y_range"]["max"] = probe_max
        else:
            # For 4D: update 2D image plot OR 3D volume when Plot1 is 1D
            if len(volume.shape) == 3:
                # Volume is 3D (x,z,u) - take slice at x_idx to get (z,u)
                slice_2d = volume[x_idx, :, :]  # This is (z, u)
            elif len(volume.shape) == 4:
                # Normal 4D volume case (x,y,z,u)
                slice_2d = volume[x_idx, y_idx, :, :]  # This is (z, u)
            else:
                raise ValueError(f"Unexpected volume shape: {volume.shape}, expected 3D or 4D")

            # Update probe_2d_plot's data and use its flipped methods
            probe_2d_plot.data = slice_2d

            # Get flipped data and coordinates from probe_2d_plot
            flipped_slice = probe_2d_plot.get_flipped_data()
            x_coords = probe_2d_plot.get_flipped_x_coords()
            y_coords = probe_2d_plot.get_flipped_y_coords()

            # Fallback if flipped methods return None
            if flipped_slice is None:
                flipped_slice = slice_2d  # Use original data if get_flipped_data() returns None
            if x_coords is None:
                x_coords = np.arange(flipped_slice.shape[1])
            if y_coords is None:
                y_coords = np.arange(flipped_slice.shape[0])

            # CRITICAL: Validate that coordinates match flipped data shape
            # Bokeh expects: data.shape[1] == len(x_coords), data.shape[0] == len(y_coords)
            if flipped_slice is not None and x_coords is not None and y_coords is not None:
                if flipped_slice.shape[1] != len(x_coords) or flipped_slice.shape[0] != len(y_coords):
                    print(f"⚠️ WARNING in show_slice(): Coordinate mismatch detected!")
                    print(f"   flipped_slice.shape={flipped_slice.shape}")
                    print(f"   len(x_coords)={len(x_coords)}, len(y_coords)={len(y_coords)}")
                    print(f"   Recomputing coordinates to match data shape...")
                    # Recompute coordinates to match flipped data shape
                    x_coords = np.arange(flipped_slice.shape[1])
                    y_coords = np.arange(flipped_slice.shape[0])

            # Calculate dimensions
            dw = float(np.max(x_coords) - np.min(x_coords)) if len(x_coords) > 0 else float(flipped_slice.shape[1])
            dh = float(np.max(y_coords) - np.min(y_coords)) if len(y_coords) > 0 else float(flipped_slice.shape[0])

            source2.data = {
                "image": [flipped_slice],
                "x": [float(np.min(x_coords))],
                "y": [float(np.min(y_coords))],
                "dw": [dw],
                "dh": [dh],
            }

            # Update plot ranges to match coordinate arrays
            # Preserve zoom state: only update if coordinates have changed
            coords_x_min = float(np.min(x_coords))
            coords_x_max = float(np.max(x_coords))
            coords_y_min = float(np.min(y_coords))
            coords_y_max = float(np.max(y_coords))
            
            # Check if x coordinates have changed
            if (_plot2_zoom_state["x_range"]["coords_min"] is None or 
                _plot2_zoom_state["x_range"]["coords_max"] is None or
                abs(_plot2_zoom_state["x_range"]["coords_min"] - coords_x_min) > 1e-6 or
                abs(_plot2_zoom_state["x_range"]["coords_max"] - coords_x_max) > 1e-6):
                # Coordinates changed - update range
                plot2.x_range.start = coords_x_min
                plot2.x_range.end = coords_x_max
                _plot2_zoom_state["x_range"]["coords_min"] = coords_x_min
                _plot2_zoom_state["x_range"]["coords_max"] = coords_x_max
                _plot2_zoom_state["x_range"]["min"] = coords_x_min
                _plot2_zoom_state["x_range"]["max"] = coords_x_max
                _plot2_zoom_state["is_manual_zoom"] = False
            # else: preserve current x zoom state
            
            # Check if y coordinates have changed
            if (_plot2_zoom_state["y_range"]["coords_min"] is None or 
                _plot2_zoom_state["y_range"]["coords_max"] is None or
                abs(_plot2_zoom_state["y_range"]["coords_min"] - coords_y_min) > 1e-6 or
                abs(_plot2_zoom_state["y_range"]["coords_max"] - coords_y_max) > 1e-6):
                # Coordinates changed - update range
                plot2.y_range.start = coords_y_min
                plot2.y_range.end = coords_y_max
                _plot2_zoom_state["y_range"]["coords_min"] = coords_y_min
                _plot2_zoom_state["y_range"]["coords_max"] = coords_y_max
                _plot2_zoom_state["y_range"]["min"] = coords_y_min
                _plot2_zoom_state["y_range"]["max"] = coords_y_max
                _plot2_zoom_state["is_manual_zoom"] = False
            # else: preserve current y zoom state
            # Update color mapper range based on mode
            # Check if range inputs exist and are enabled (User Specified mode) or disabled (Dynamic mode)
            try:
                if range2_min_input is not None and not range2_min_input.disabled:
                    # User Specified mode - use input values
                    try:
                        min_val = float(range2_min_input.value) if range2_min_input.value else probe_min
                        max_val = float(range2_max_input.value) if range2_max_input.value else probe_max
                        color_mapper2.low = min_val
                        color_mapper2.high = max_val
                    except:
                        # Fallback to percentile if input is invalid
                        probe_min = float(np.percentile(flipped_slice[~np.isnan(flipped_slice)], 1))
                        probe_max = float(np.percentile(flipped_slice[~np.isnan(flipped_slice)], 99))
                        color_mapper2.low = probe_min
                        color_mapper2.high = probe_max
                else:
                    # Dynamic mode - recompute from current slice
                    probe_min = float(np.percentile(flipped_slice[~np.isnan(flipped_slice)], 1))
                    probe_max = float(np.percentile(flipped_slice[~np.isnan(flipped_slice)], 99))
                    color_mapper2.low = probe_min
                    color_mapper2.high = probe_max
                    # CRITICAL: Always update range inputs in Dynamic mode so user can see the computed values
                    # Use add_next_tick_callback to ensure updates happen in next Bokeh tick
                    from bokeh.io import curdoc
                    update_func = update_range_inputs_safely(
                        range2_min_input, range2_max_input, probe_min, probe_max, use_callback=True
                    )
                    curdoc().add_next_tick_callback(update_func)
            except NameError:
                # Range inputs not defined yet - use Dynamic mode as default
                probe_min = float(np.percentile(flipped_slice[~np.isnan(flipped_slice)], 1))
                probe_max = float(np.percentile(flipped_slice[~np.isnan(flipped_slice)], 99))
                color_mapper2.low = probe_min
                color_mapper2.high = probe_max

    # Function to update Plot2B based on crosshair position
    def show_slice_b():
        """Update Plot2B based on current crosshair position (x_index, y_index)."""
        if plot2b is None:
            return

        x_idx = get_x_index()
        # When Plot1 is 1D, there's no y_idx - use x_idx to select volume slice
        if plot1_is_1d:
            y_idx = None  # Not used when Plot1 is 1D
        else:
            y_idx = get_y_index()

        if plot2b_is_2d:
            # 4D volume: update 2D image plot
            if hasattr(self.process_4dnexus, 'volume_picked_b') and self.process_4dnexus.volume_picked_b and probe_2d_plot_b is not None:
                try:
                    # Use cached volume_b if available, but validate
                    cached_path = getattr(self.process_4dnexus, '_cached_volume_b_path', None)
                    if (hasattr(self.process_4dnexus, '_cached_volume_b') and 
                        cached_path == self.process_4dnexus.volume_picked_b and
                        self.process_4dnexus._cached_volume_b is not None):
                        volume_b = self.process_4dnexus._cached_volume_b
                        # Quick validation
                        if not (hasattr(volume_b, 'shape') and len(volume_b.shape) >= 2):
                            print(f"⚠️ Cached volume_b invalid in show_slice_b(), reloading...")
                            volume_b = None
                    else:
                        volume_b = None

                    if volume_b is None:
                        # Clear cache if path changed
                        if cached_path != self.process_4dnexus.volume_picked_b:
                            self.process_4dnexus._cached_volume_b = None
                            self.process_4dnexus._cached_volume_b_path = None

                        # Load and cache volume_b
                        volume_b = self.process_4dnexus.load_dataset_by_path(self.process_4dnexus.volume_picked_b)
                        if volume_b is not None:
                            self.process_4dnexus._cached_volume_b = volume_b
                            self.process_4dnexus._cached_volume_b_path = self.process_4dnexus.volume_picked_b

                    if volume_b is not None:
                        # Extract 2D slice - handle both 3D and 4D volumes
                        if plot1_is_1d and len(volume_b.shape) == 3:
                            # Volume B is 3D (x,z,u) - when Plot1 is 1D, extract 2D slice (z,u) at x_idx
                            new_slice_b = volume_b[x_idx, :, :]
                        elif len(volume_b.shape) == 4:
                            # Normal 4D volume case (x,y,z,u)
                            new_slice_b = volume_b[x_idx, y_idx, :, :]
                        else:
                            raise ValueError(f"Unexpected volume_b shape: {volume_b.shape}, expected 3D or 4D")

                        # Update probe_2d_plot_b's data and use its flipped methods
                        probe_2d_plot_b.data = new_slice_b

                        # Get flipped data and coordinates from probe_2d_plot_b
                        flipped_slice_b = probe_2d_plot_b.get_flipped_data()
                        x_coords_b = probe_2d_plot_b.get_flipped_x_coords()
                        y_coords_b = probe_2d_plot_b.get_flipped_y_coords()

                        # Fallback if flipped methods return None
                        if flipped_slice_b is None:
                            flipped_slice_b = new_slice_b  # Use original data if get_flipped_data() returns None
                        if x_coords_b is None:
                            x_coords_b = np.arange(flipped_slice_b.shape[1])
                        if y_coords_b is None:
                            y_coords_b = np.arange(flipped_slice_b.shape[0])

                        # CRITICAL: Validate that coordinates match flipped data shape
                        # Bokeh expects: data.shape[1] == len(x_coords), data.shape[0] == len(y_coords)
                        if flipped_slice_b is not None and x_coords_b is not None and y_coords_b is not None:
                            if flipped_slice_b.shape[1] != len(x_coords_b) or flipped_slice_b.shape[0] != len(y_coords_b):
                                print(f"⚠️ WARNING in show_slice_b(): Coordinate mismatch detected!")
                                print(f"   flipped_slice_b.shape={flipped_slice_b.shape}")
                                print(f"   len(x_coords_b)={len(x_coords_b)}, len(y_coords_b)={len(y_coords_b)}")
                                print(f"   Recomputing coordinates to match data shape...")
                                # Recompute coordinates to match flipped data shape
                                x_coords_b = np.arange(flipped_slice_b.shape[1])
                            y_coords_b = np.arange(flipped_slice_b.shape[0])

                        # Calculate dimensions
                        dw_b = float(np.max(x_coords_b) - np.min(x_coords_b)) if len(x_coords_b) > 0 else float(flipped_slice_b.shape[1])
                        dh_b = float(np.max(y_coords_b) - np.min(y_coords_b)) if len(y_coords_b) > 0 else float(flipped_slice_b.shape[0])

                        source2b.data = {
                            "image": [flipped_slice_b],
                            "x": [float(np.min(x_coords_b))],
                            "y": [float(np.min(y_coords_b))],
                            "dw": [dw_b],
                            "dh": [dh_b],
                        }

                        # Update plot ranges to match coordinate arrays
                        # Preserve zoom state: only update if coordinates have changed
                        coords_x_min_b = float(np.min(x_coords_b))
                        coords_x_max_b = float(np.max(x_coords_b))
                        coords_y_min_b = float(np.min(y_coords_b))
                        coords_y_max_b = float(np.max(y_coords_b))
                        
                        # Check if x coordinates have changed
                        if (_plot2b_zoom_state["x_range"]["coords_min"] is None or 
                            _plot2b_zoom_state["x_range"]["coords_max"] is None or
                            abs(_plot2b_zoom_state["x_range"]["coords_min"] - coords_x_min_b) > 1e-6 or
                            abs(_plot2b_zoom_state["x_range"]["coords_max"] - coords_x_max_b) > 1e-6):
                            # Coordinates changed - update range
                            plot2b.x_range.start = coords_x_min_b
                            plot2b.x_range.end = coords_x_max_b
                            _plot2b_zoom_state["x_range"]["coords_min"] = coords_x_min_b
                            _plot2b_zoom_state["x_range"]["coords_max"] = coords_x_max_b
                            _plot2b_zoom_state["x_range"]["min"] = coords_x_min_b
                            _plot2b_zoom_state["x_range"]["max"] = coords_x_max_b
                            _plot2b_zoom_state["is_manual_zoom"] = False
                        # else: preserve current x zoom state
                        
                        # Check if y coordinates have changed
                        if (_plot2b_zoom_state["y_range"]["coords_min"] is None or 
                            _plot2b_zoom_state["y_range"]["coords_max"] is None or
                            abs(_plot2b_zoom_state["y_range"]["coords_min"] - coords_y_min_b) > 1e-6 or
                            abs(_plot2b_zoom_state["y_range"]["coords_max"] - coords_y_max_b) > 1e-6):
                            # Coordinates changed - update range
                            plot2b.y_range.start = coords_y_min_b
                            plot2b.y_range.end = coords_y_max_b
                            _plot2b_zoom_state["y_range"]["coords_min"] = coords_y_min_b
                            _plot2b_zoom_state["y_range"]["coords_max"] = coords_y_max_b
                            _plot2b_zoom_state["y_range"]["min"] = coords_y_min_b
                            _plot2b_zoom_state["y_range"]["max"] = coords_y_max_b
                            _plot2b_zoom_state["is_manual_zoom"] = False
                        # else: preserve current y zoom state

                        # Plot2B uses Bokeh's default auto-ticker (same as Plot2)
                        # No manual tick updates needed - Bokeh will automatically adjust ticks when data changes

                        # Update range based on mode
                        try:
                            if range2b_min_input is not None and range2b_min_input.disabled:
                                # Dynamic mode - recompute from current slice
                                probe2b_min = float(np.percentile(flipped_slice_b[~np.isnan(flipped_slice_b)], 1))
                                probe2b_max = float(np.percentile(flipped_slice_b[~np.isnan(flipped_slice_b)], 99))
                                color_mapper2b.low = probe2b_min
                                color_mapper2b.high = probe2b_max
                                # Update range inputs so user can see the computed values
                                # Use add_next_tick_callback to ensure updates happen in next Bokeh tick
                                from bokeh.io import curdoc
                                update_func = update_range_inputs_safely(
                                    range2b_min_input, range2b_max_input, probe2b_min, probe2b_max, use_callback=True
                                )
                                curdoc().add_next_tick_callback(update_func)
                            elif range2b_min_input is not None:
                                # User Specified mode - use input values
                                try:
                                    min_val = float(range2b_min_input.value) if range2b_min_input.value else probe2b_min
                                    max_val = float(range2b_max_input.value) if range2b_max_input.value else probe2b_max
                                    color_mapper2b.low = min_val
                                    color_mapper2b.high = max_val
                                except:
                                    pass
                        except NameError:
                            # Range inputs not defined yet - use Dynamic mode as default
                            probe2b_min = float(np.percentile(flipped_slice_b[~np.isnan(flipped_slice_b)], 1))
                            probe2b_max = float(np.percentile(flipped_slice_b[~np.isnan(flipped_slice_b)], 99))
                            color_mapper2b.low = probe2b_min
                            color_mapper2b.high = probe2b_max
                except Exception as e:
                        print(f"Error updating Plot2B: {e}")
        else:
            # 3D volume: update 1D line plot
            if hasattr(self.process_4dnexus, 'volume_picked_b') and self.process_4dnexus.volume_picked_b:
                try:
                    # Use cached volume_b if available
                    if (hasattr(self.process_4dnexus, '_cached_volume_b') and 
                        hasattr(self.process_4dnexus, '_cached_volume_b_path') and
                        self.process_4dnexus._cached_volume_b_path == self.process_4dnexus.volume_picked_b):
                            volume_b = self.process_4dnexus._cached_volume_b
                    else:
                        # Load and cache volume_b
                        volume_b = self.process_4dnexus.load_dataset_by_path(self.process_4dnexus.volume_picked_b)
                        if volume_b is not None:
                            self.process_4dnexus._cached_volume_b = volume_b
                            self.process_4dnexus._cached_volume_b_path = self.process_4dnexus.volume_picked_b

                    if volume_b is not None:
                        # Extract 1D slice - handle both 2D and 3D volumes
                        if plot1_is_1d and len(volume_b.shape) == 2:
                            # Volume B is 2D (x,z) - when Plot1 is 1D, extract 1D slice z at x_idx
                            slice_1d_b = volume_b[x_idx, :]
                        elif len(volume_b.shape) == 3:
                            # Normal 3D volume case (x,y,z)
                            slice_1d_b = volume_b[x_idx, y_idx, :]
                        else:
                            raise ValueError(f"Unexpected volume_b shape for 1D Plot2B: {volume_b.shape}, expected 2D or 3D")

                        # Try to use probe coordinates if available
                        if hasattr(self.process_4dnexus, 'probe_x_coords_picked_b') and self.process_4dnexus.probe_x_coords_picked_b:
                            try:
                                probe_coords_b = self.process_4dnexus.load_probe_coordinates(use_b=True)
                                if probe_coords_b is not None and len(probe_coords_b) == len(slice_1d_b):
                                    x_coords_1d_b = probe_coords_b
                                else:
                                    x_coords_1d_b = np.arange(len(slice_1d_b))
                            except:
                                x_coords_1d_b = np.arange(len(slice_1d_b))
                        else:
                            x_coords_1d_b = np.arange(len(slice_1d_b))

                        source2b.data = {"x": x_coords_1d_b, "y": slice_1d_b}
                        
                        # Preserve zoom state: only update x_range if coordinates have changed
                        coords_min_b = float(np.min(x_coords_1d_b))
                        coords_max_b = float(np.max(x_coords_1d_b))
                        if (_plot2b_zoom_state["x_range"]["coords_min"] is None or 
                            _plot2b_zoom_state["x_range"]["coords_max"] is None or
                            abs(_plot2b_zoom_state["x_range"]["coords_min"] - coords_min_b) > 1e-6 or
                            abs(_plot2b_zoom_state["x_range"]["coords_max"] - coords_max_b) > 1e-6):
                            # Coordinates changed - update range
                            plot2b.x_range.start = coords_min_b
                            plot2b.x_range.end = coords_max_b
                            _plot2b_zoom_state["x_range"]["coords_min"] = coords_min_b
                            _plot2b_zoom_state["x_range"]["coords_max"] = coords_max_b
                            _plot2b_zoom_state["x_range"]["min"] = coords_min_b
                            _plot2b_zoom_state["x_range"]["max"] = coords_max_b
                            _plot2b_zoom_state["is_manual_zoom"] = False
                        # else: preserve current zoom state (user has zoomed)

                        # Update ticks from probe coordinates if available
                        if hasattr(self.process_4dnexus, 'probe_x_coords_picked_b') and self.process_4dnexus.probe_x_coords_picked_b:
                            set_ticks_from_coords(plot2b, x_coords_1d_b, axis='x', num_ticks=10)

                        # Update range dynamically if in Dynamic mode
                        try:
                            if range2b_min_input is not None and range2b_min_input.disabled:
                                # Dynamic mode - recompute from current slice
                                probe2b_min = float(np.percentile(slice_1d_b[~np.isnan(slice_1d_b)], 1))
                                probe2b_max = float(np.percentile(slice_1d_b[~np.isnan(slice_1d_b)], 99))
                                plot2b.y_range.start = probe2b_min
                                plot2b.y_range.end = probe2b_max
                                _plot2b_zoom_state["y_range"]["min"] = probe2b_min
                                _plot2b_zoom_state["y_range"]["max"] = probe2b_max
                                # Update range inputs so user can see the computed values
                                # Use add_next_tick_callback to ensure updates happen in next Bokeh tick
                                from bokeh.io import curdoc
                                update_func = update_range_inputs_safely(
                                    range2b_min_input, range2b_max_input, probe2b_min, probe2b_max, use_callback=True
                                )
                                curdoc().add_next_tick_callback(update_func)
                            elif range2b_min_input is not None:
                                # User Specified mode - preserve zoom state, only use input values if they're set
                                try:
                                    if range2b_min_input.value and range2b_max_input.value:
                                        min_val = float(range2b_min_input.value)
                                        max_val = float(range2b_max_input.value)
                                        plot2b.y_range.start = min_val
                                        plot2b.y_range.end = max_val
                                        _plot2b_zoom_state["y_range"]["min"] = min_val
                                        _plot2b_zoom_state["y_range"]["max"] = max_val
                                    # else: preserve current zoom state
                                except:
                                    # Fallback: preserve current zoom if possible, otherwise use data range
                                    if _plot2b_zoom_state["y_range"]["min"] is None:
                                        plot2b.y_range.start = float(np.min(slice_1d_b))
                                        plot2b.y_range.end = float(np.max(slice_1d_b))
                                    # else: preserve current zoom state
                        except NameError:
                            # Range inputs not defined yet - use Dynamic mode as default
                            probe2b_min = float(np.percentile(slice_1d_b[~np.isnan(slice_1d_b)], 1))
                            probe2b_max = float(np.percentile(slice_1d_b[~np.isnan(slice_1d_b)], 99))
                            plot2b.y_range.start = probe2b_min
                            plot2b.y_range.end = probe2b_max
                            _plot2b_zoom_state["y_range"]["min"] = probe2b_min
                            _plot2b_zoom_state["y_range"]["max"] = probe2b_max
                except Exception as e:
                        print(f"Error updating Plot2B: {e}")

    # Slider callbacks to update crosshairs and Plot2
    def on_x_slider_change(attr, old, new):
        try:
            # Immediately save slider value to session metadata (for undo/redo)
            try:
                session.metadata['x_slider_value'] = new
            except (NameError, AttributeError):
                pass  # session not available in this scope
            
            draw_cross1()
            show_slice()  # This already handles Plot2 Dynamic/User Specified range mode
            # Note: Plot1's range should NOT update when slider moves - it uses static map data
            # Plot1's dynamic range is computed once at initialization or when mode changes
            # Update Plot2B if it exists
            show_slice_b()  # This already handles Plot2B Dynamic/User Specified range mode
            
            # Track slider drag state - only save initial and final positions to undo/redo
            # Skip if we're restoring state (undo/redo) or during programmatic changes (plot clicks)
            if not _skip_slider_state_save["value"]:
                from bokeh.io import curdoc
                
                # If this is the first change (not currently dragging), save initial value
                if not _slider_drag_state["x"]["is_dragging"]:
                    _slider_drag_state["x"]["is_dragging"] = True
                    _slider_drag_state["x"]["initial_value"] = old
                    print(f"🔍 DEBUG: X slider drag started from {old}")
                
                # Cancel any pending save for this slider
                if _slider_drag_state["x"]["timer"] is not None:
                    try:
                        curdoc().remove_timeout_callback(_slider_drag_state["x"]["timer"])
                    except:
                        pass
                
                # Set up a timer to save state when dragging ends (after 1 second of no changes)
                def save_slider_final_state():
                    if _slider_drag_state["x"]["is_dragging"]:
                        initial_val = _slider_drag_state["x"]["initial_value"]
                        final_val = x_slider.value
                        _slider_drag_state["x"]["is_dragging"] = False
                        _slider_drag_state["x"]["initial_value"] = None
                        print(f"🔍 DEBUG: X slider drag ended from {initial_val} to {final_val}")
                        debounced_save_state(f"X slider changed ({initial_val:.3f} → {final_val:.3f})", update_undo_redo=True)
                
                _slider_drag_state["x"]["timer"] = curdoc().add_timeout_callback(save_slider_final_state, 1000)  # 1 second delay
            else:
                # Reset drag state when skipping saves (e.g., during plot clicks or undo/redo)
                from bokeh.io import curdoc
                if _slider_drag_state["x"]["is_dragging"]:
                    # Cancel any pending timer
                    if _slider_drag_state["x"]["timer"] is not None:
                        try:
                            curdoc().remove_timeout_callback(_slider_drag_state["x"]["timer"])
                        except:
                            pass
                    # Reset drag state
                    _slider_drag_state["x"]["is_dragging"] = False
                    _slider_drag_state["x"]["initial_value"] = None
        except Exception as e:
            print(f"⚠️ ERROR in on_x_slider_change(): {e}")
            import traceback
            traceback.print_exc()

    def on_y_slider_change(attr, old, new):
        try:
            # Immediately save slider value to session metadata (for undo/redo)
            try:
                session.metadata['y_slider_value'] = new
            except (NameError, AttributeError):
                pass  # session not available in this scope
            
            draw_cross1()
            show_slice()  # This already handles Plot2 Dynamic/User Specified range mode
            # Note: Plot1's range should NOT update when slider moves - it uses static map data
            # Plot1's dynamic range is computed once at initialization or when mode changes
            # Update Plot2B if it exists
            show_slice_b()  # This already handles Plot2B Dynamic/User Specified range mode
            
            # Track slider drag state - only save initial and final positions to undo/redo
            # Skip if we're restoring state (undo/redo) or during programmatic changes (plot clicks)
            if not _skip_slider_state_save["value"]:
                from bokeh.io import curdoc
                
                # If this is the first change (not currently dragging), save initial value
                if not _slider_drag_state["y"]["is_dragging"]:
                    _slider_drag_state["y"]["is_dragging"] = True
                    _slider_drag_state["y"]["initial_value"] = old
                    print(f"🔍 DEBUG: Y slider drag started from {old}")
                
                # Cancel any pending save for this slider
                if _slider_drag_state["y"]["timer"] is not None:
                    try:
                        curdoc().remove_timeout_callback(_slider_drag_state["y"]["timer"])
                    except:
                        pass
                
                # Set up a timer to save state when dragging ends (after 1 second of no changes)
                def save_slider_final_state():
                    if _slider_drag_state["y"]["is_dragging"]:
                        initial_val = _slider_drag_state["y"]["initial_value"]
                        final_val = y_slider.value
                        _slider_drag_state["y"]["is_dragging"] = False
                        _slider_drag_state["y"]["initial_value"] = None
                        print(f"🔍 DEBUG: Y slider drag ended from {initial_val} to {final_val}")
                        debounced_save_state(f"Y slider changed ({initial_val:.3f} → {final_val:.3f})", update_undo_redo=True)
                
                _slider_drag_state["y"]["timer"] = curdoc().add_timeout_callback(save_slider_final_state, 1000)  # 1 second delay
            else:
                # Reset drag state when skipping saves (e.g., during plot clicks or undo/redo)
                from bokeh.io import curdoc
                if _slider_drag_state["y"]["is_dragging"]:
                    # Cancel any pending timer
                    if _slider_drag_state["y"]["timer"] is not None:
                        try:
                            curdoc().remove_timeout_callback(_slider_drag_state["y"]["timer"])
                        except:
                            pass
                    # Reset drag state
                    _slider_drag_state["y"]["is_dragging"] = False
                    _slider_drag_state["y"]["initial_value"] = None
        except Exception as e:
            print(f"⚠️ ERROR in on_y_slider_change(): {e}")
            import traceback
            traceback.print_exc()

    # Connect slider callbacks
    try:
        x_slider.on_change("value", on_x_slider_change)
        if y_slider is not None:
            y_slider.on_change("value", on_y_slider_change)
        print("✅ Sliders connected successfully")
    except Exception as e:
        print(f"⚠️ ERROR connecting sliders: {e}")
        import traceback
        traceback.print_exc()

    # Tap handler for Plot1 to update crosshairs (defined after sliders are created)
    def on_plot1_tap(event):
        """Handle tap events on Plot1 to update crosshair position."""
        # Bokeh tap events have x and y attributes
        # The plot axes are already in flipped order, so we need to convert back to original indices
        if hasattr(event, 'x') and hasattr(event, 'y'):
            # Find closest indices in the flipped coordinate arrays
            x_idx = np.argmin(np.abs(plot1_x_coords - event.x))
            # When Plot1 is 1D, plot1_y_coords is None, so use index-based y_idx
            if plot1_y_coords is not None:
                y_idx = np.argmin(np.abs(plot1_y_coords - event.y))
            else:
                # When Plot1 is 1D, y-axis is index-based (0 to shape[0]-1)
                # Use plot1_1d_data if available, otherwise fallback
                if plot1_is_1d and plot1_1d_data is not None:
                    data_shape_0 = plot1_1d_data.shape[0]
                elif plot1_data is not None:
                    data_shape_0 = plot1_data.shape[0]
                else:
                    data_shape_0 = len(plot1_x_coords) if plot1_x_coords is not None else 1
                y_idx = max(0, min(int(round(event.y)), data_shape_0 - 1))

            # Convert back to original coordinate space for sliders
            # Sliders use original x_coords and y_coords (not flipped)
            # Temporarily disable state saves to prevent multiple saves
            _skip_slider_state_save["value"] = True
            
            try:
                # Update sliders (handlers will update plots but won't save state)
                # When Plot1 is 1D, y_coords is None, so only update x_slider
                if y_coords is None:
                    # Plot1 is 1D - only update x_slider
                    x_slider.value = x_coords[x_idx] if x_idx < len(x_coords) else x_coords[-1]
                elif map_plot.needs_flip:
                    # When flipped: plot1_x_coords is actually y_coords, plot1_y_coords is actually x_coords
                    x_slider.value = y_coords[y_idx] if y_idx < len(y_coords) else y_coords[-1]
                    if y_slider is not None:
                        y_slider.value = x_coords[x_idx] if x_idx < len(x_coords) else x_coords[-1]
                else:
                    # Not flipped: plot1_x_coords is x_coords, plot1_y_coords is y_coords
                    x_slider.value = x_coords[x_idx] if x_idx < len(x_coords) else x_coords[-1]
                    if y_slider is not None:
                        y_slider.value = y_coords[y_idx] if y_idx < len(y_coords) else y_coords[-1]
                
                # Slider change handlers will automatically call draw_cross1() (which also calls draw_cross3()) and show_slice()
                # Save state once for both slider changes (after both are updated)
                debounced_save_state("Plot1 clicked (both sliders changed)", update_undo_redo=True)
            finally:
                _skip_slider_state_save["value"] = False

    # Draw initial crosshairs (skip if loading session - will be drawn by auto_load_session)
    # Note: draw_cross1() will also call draw_cross3() to synchronize Plot3 crosshairs
    if not _session_loading_state["is_loading"]:
        try:
            draw_cross1()  # This will also draw crosshairs on Plot3
            print("✅ Initial crosshairs drawn successfully (Plot1 and Plot3)")
        except Exception as e:
            print(f"⚠️ ERROR drawing initial crosshairs: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("⏭️ Skipping initial crosshairs (session loading will draw them)")

    # CRITICAL: Add callbacks to redraw crosshairs whenever plot ranges change
    # This ensures crosshairs persist even when ranges are updated during session loading
    # The _session_loading_state["is_loading"] flag is set at the start of create_dashboard() if a session is pending

    def on_plot1_range_change(attr, old, new):
        """Redraw crosshairs when Plot1 range changes."""
        # Don't redraw during session loading - it will be handled by auto_load_session
        if _session_loading_state["is_loading"]:
            return
        try:
            draw_cross1()
        except:
            pass  # Silently fail if crosshairs can't be drawn yet

    plot1.x_range.on_change("start", on_plot1_range_change)
    plot1.x_range.on_change("end", on_plot1_range_change)
    plot1.y_range.on_change("start", on_plot1_range_change)
    plot1.y_range.on_change("end", on_plot1_range_change)

    # Create Plot1B if enabled
    plot1b = None
    source1b = None
    color_mapper1b = None
    image_renderer1b = None
    colorbar1b = None
    map_plot_b = None
    map1b_min_val = None
    map1b_max_val = None

    if hasattr(self.process_4dnexus, 'plot1b_single_dataset_picked') and self.process_4dnexus.plot1b_single_dataset_picked:
        try:
            # Load Plot1B dataset
            single_dataset_b = self.process_4dnexus.load_dataset_by_path(self.process_4dnexus.plot1b_single_dataset_picked)
            if single_dataset_b is not None:
                # Convert h5py.Dataset to numpy array if needed (h5py.Dataset doesn't have .flatten())
                import h5py
                if isinstance(single_dataset_b, h5py.Dataset):
                    single_dataset_b = np.array(single_dataset_b)
                
                # Flatten if needed and reshape
                if single_dataset_b.ndim > 1:
                    single_dataset_b_flat = single_dataset_b.flatten()
                else:
                    single_dataset_b_flat = single_dataset_b

                if single_dataset_b_flat.size == len(x_coords) * len(y_coords):
                    preview_b_rect = np.reshape(single_dataset_b_flat, (len(x_coords), len(y_coords)))
                    # Clean and normalize
                    preview_b = np.nan_to_num(preview_b_rect, nan=0.0, posinf=0.0, neginf=0.0)
                    if np.max(preview_b) > np.min(preview_b):
                        preview_b = (preview_b - np.min(preview_b)) / (np.max(preview_b) - np.min(preview_b))
                    preview_b = preview_b.astype(np.float32)

                    # Detect flip for Plot1B
                    plot1b_needs_flip = self.process_4dnexus.detect_map_flip_needed(
                        preview_b.shape,
                        self.process_4dnexus.get_dataset_size_from_path(self.process_4dnexus.x_coords_picked) if self.process_4dnexus.x_coords_picked else None,
                        self.process_4dnexus.get_dataset_size_from_path(self.process_4dnexus.y_coords_picked) if self.process_4dnexus.y_coords_picked else None
                    )

                    # Create Plot1B using MAP_2DPlot
                    # Use original_map_x_label and original_map_y_label (same as Plot1)
                    # The plot object will handle flipping via its methods
                    map_plot_b = MAP_2DPlot(
                        title="Plot1B - Map View (Duplicate)",
                        data=preview_b,
                        x_coords=x_coords,
                        y_coords=y_coords,
                        palette="Viridis256",
                        color_scale=ColorScale.LINEAR,
                        range_mode=RangeMode.DYNAMIC,
                        crosshairs_enabled=True,
                        x_axis_label=original_map_x_label,  # Original label - will be swapped by get_flipped_x_axis_label() if needed
                        y_axis_label=original_map_y_label,  # Original label - will be swapped by get_flipped_y_axis_label() if needed
                        needs_flip=plot1b_needs_flip,
                        track_changes=True,
                    )

                    # Get flipped data and coordinates
                    plot1b_data = map_plot_b.get_flipped_data() if map_plot_b.needs_flip else preview_b
                    plot1b_x_coords = map_plot_b.get_flipped_x_coords() if map_plot_b.needs_flip else x_coords
                    plot1b_y_coords = map_plot_b.get_flipped_y_coords() if map_plot_b.needs_flip else y_coords

                    # Calculate initial plot dimensions from map_plot_b
                    initial_width_b, initial_height_b = map_plot_b.calculate_plot_dimensions()
                    
                    # Add extra width to account for vertical colorbar on the right (typically ~60 pixels)
                    plot_width_b_with_colorbar = initial_width_b + colorbar_width

                    # Create Bokeh figure for Plot1B (use calculated dimensions)
                    plot1b = figure(
                        title="Plot1B - Map View (Duplicate)",
                        x_range=(float(np.min(plot1b_x_coords)), float(np.max(plot1b_x_coords))),
                        y_range=(float(np.min(plot1b_y_coords)), float(np.max(plot1b_y_coords))),
                        tools="pan,wheel_zoom,box_zoom,reset,tap",
                        match_aspect=True,
                        width=plot_width_b_with_colorbar,
                        height=initial_height_b,
                    )

                    plot1b.xaxis.axis_label = map_plot_b.get_flipped_x_axis_label()
                    plot1b.yaxis.axis_label = map_plot_b.get_flipped_y_axis_label()

                    source1b = ColumnDataSource(
                        data={
                            "image": [plot1b_data],
                            "x": [float(np.min(plot1b_x_coords))],
                            "y": [float(np.min(plot1b_y_coords))],
                            "dw": [float(np.max(plot1b_x_coords) - np.min(plot1b_x_coords))],
                            "dh": [float(np.max(plot1b_y_coords) - np.min(plot1b_y_coords))],
                        }
                    )

                    map1b_min_val = float(np.percentile(plot1b_data[~np.isnan(plot1b_data)], 1))
                    map1b_max_val = float(np.percentile(plot1b_data[~np.isnan(plot1b_data)], 99))
                    # Store for later use in range controls
                    color_mapper1b = LinearColorMapper(palette="Viridis256", low=map1b_min_val, high=map1b_max_val)
                    image_renderer1b = plot1b.image(
                        "image", source=source1b, x="x", y="y", dw="dw", dh="dh", color_mapper=color_mapper1b
                    )
                    colorbar1b = ColorBar(color_mapper=color_mapper1b, title="", location=(1, 0))
                    plot1b.add_layout(colorbar1b, "right")

                    # Initialize rect1b for Plot1B crosshairs
                    rect1b = Rectangle(0, 0, volume.shape[0] - 1, volume.shape[1] - 1)

                    # Tap handler for Plot1B (updates sliders, which updates both Plot1 and Plot1B crosshairs)
                    def on_plot1b_tap(event):
                        """Handle tap events on Plot1B to update crosshair position."""
                        if hasattr(event, 'x') and hasattr(event, 'y'):
                            # Find closest indices in Plot1B's flipped coordinate arrays
                            plot1b_x_coords = map_plot_b.get_flipped_x_coords()
                            plot1b_y_coords = map_plot_b.get_flipped_y_coords()
                            x_idx = np.argmin(np.abs(plot1b_x_coords - event.x))
                            y_idx = np.argmin(np.abs(plot1b_y_coords - event.y))

                            # Convert back to original coordinate space for sliders
                            if map_plot_b.needs_flip:
                                x_slider.value = y_coords[y_idx] if y_idx < len(y_coords) else y_coords[-1]
                                y_slider.value = x_coords[x_idx] if x_idx < len(x_coords) else x_coords[-1]
                            else:
                                x_slider.value = x_coords[x_idx] if x_idx < len(x_coords) else x_coords[-1]
                                y_slider.value = y_coords[y_idx] if y_idx < len(y_coords) else y_coords[-1]
                            draw_cross1()  # This will also update Plot1B crosshairs
                            show_slice()

                    # Add TapTool to Plot1B and connect handler
                    tap_tool1b = TapTool()
                    plot1b.add_tools(tap_tool1b)
                    plot1b.on_event("tap", on_plot1b_tap)

                    # Draw initial crosshairs on Plot1B (skip if loading session - will be drawn by auto_load_session)
                    if not _session_loading_state["is_loading"]:
                        draw_cross1b()

                    # CRITICAL: Add callbacks to redraw crosshairs whenever Plot1B ranges change
                    def on_plot1b_range_change(attr, old, new):
                        """Redraw crosshairs when Plot1B range changes."""
                        # Don't redraw during session loading - it will be handled by auto_load_session
                        if _session_loading_state["is_loading"]:
                            return
                        try:
                            draw_cross1b()
                        except:
                            pass  # Silently fail if crosshairs can't be drawn yet

                    plot1b.x_range.on_change("start", on_plot1b_range_change)
                    plot1b.x_range.on_change("end", on_plot1b_range_change)
                    plot1b.y_range.on_change("start", on_plot1b_range_change)
                    plot1b.y_range.on_change("end", on_plot1b_range_change)
        except Exception as e:
            import traceback
            print(f"Failed to create Plot1B: {e}")
            traceback.print_exc()
    elif hasattr(self.process_4dnexus, 'presample_picked_b') and hasattr(self.process_4dnexus, 'postsample_picked_b') and \
        self.process_4dnexus.presample_picked_b and self.process_4dnexus.postsample_picked_b:
        try:
            # Ratio mode for Plot1B
            presample_b = self.process_4dnexus.load_dataset_by_path(self.process_4dnexus.presample_picked_b)
            postsample_b = self.process_4dnexus.load_dataset_by_path(self.process_4dnexus.postsample_picked_b)
            if presample_b is not None and postsample_b is not None:
                epsilon = 1e-10
                presample_b = np.where(presample_b == 0, epsilon, presample_b)
                postsample_b = np.where(postsample_b == 0, epsilon, postsample_b)
                presample_b = presample_b.reshape(len(x_coords), len(y_coords))
                postsample_b = postsample_b.reshape(len(x_coords), len(y_coords))
                preview_b = presample_b / postsample_b
                preview_b = np.nan_to_num(preview_b, nan=0.0, posinf=1.0, neginf=0.0).astype(np.float32)
                if np.max(preview_b) > np.min(preview_b):
                    preview_b = (preview_b - np.min(preview_b)) / (np.max(preview_b) - np.min(preview_b))

                # Detect flip for Plot1B
                plot1b_needs_flip = self.process_4dnexus.detect_map_flip_needed(
                    preview_b.shape,
                    self.process_4dnexus.get_dataset_size_from_path(self.process_4dnexus.x_coords_picked) if self.process_4dnexus.x_coords_picked else None,
                    self.process_4dnexus.get_dataset_size_from_path(self.process_4dnexus.y_coords_picked) if self.process_4dnexus.y_coords_picked else None
                )

                # Create Plot1B using MAP_2DPlot
                # Use original_map_x_label and original_map_y_label (same as Plot1)
                # The plot object will handle flipping via its methods
                map_plot_b = MAP_2DPlot(
                    title="Plot1B - Map View (Duplicate)",
                    data=preview_b,
                    x_coords=x_coords,
                    y_coords=y_coords,
                    palette="Viridis256",
                    color_scale=ColorScale.LINEAR,
                    range_mode=RangeMode.DYNAMIC,
                    crosshairs_enabled=True,
                    x_axis_label=original_map_x_label,  # Original label - will be swapped by get_flipped_x_axis_label() if needed
                    y_axis_label=original_map_y_label,  # Original label - will be swapped by get_flipped_y_axis_label() if needed
                    needs_flip=plot1b_needs_flip,
                    track_changes=True,
                )

                # Get flipped data and coordinates
                plot1b_data = map_plot_b.get_flipped_data() if map_plot_b.needs_flip else preview_b
                plot1b_x_coords = map_plot_b.get_flipped_x_coords() if map_plot_b.needs_flip else x_coords
                plot1b_y_coords = map_plot_b.get_flipped_y_coords() if map_plot_b.needs_flip else y_coords

                # Calculate initial plot dimensions from map_plot_b
                initial_width_b, initial_height_b = map_plot_b.calculate_plot_dimensions()
                
                # Add extra width to account for vertical colorbar on the right (typically ~60 pixels)
                plot_width_b_with_colorbar = initial_width_b + colorbar_width

                # Create Bokeh figure for Plot1B (use calculated dimensions)
                plot1b = figure(
                    title="Plot1B - Map View (Duplicate)",
                    x_range=(float(np.min(plot1b_x_coords)), float(np.max(plot1b_x_coords))),
                    y_range=(float(np.min(plot1b_y_coords)), float(np.max(plot1b_y_coords))),
                    tools="pan,wheel_zoom,box_zoom,reset,tap",
                    match_aspect=True,
                    width=plot_width_b_with_colorbar,
                    height=initial_height_b,
                )

                plot1b.xaxis.axis_label = map_plot_b.get_flipped_x_axis_label()
                plot1b.yaxis.axis_label = map_plot_b.get_flipped_y_axis_label()

                source1b = ColumnDataSource(
                    data={
                        "image": [plot1b_data],
                        "x": [float(np.min(plot1b_x_coords))],
                        "y": [float(np.min(plot1b_y_coords))],
                        "dw": [float(np.max(plot1b_x_coords) - np.min(plot1b_x_coords))],
                        "dh": [float(np.max(plot1b_y_coords) - np.min(plot1b_y_coords))],
                    }
                )

                map1b_min_val = float(np.percentile(plot1b_data[~np.isnan(plot1b_data)], 1))
                map1b_max_val = float(np.percentile(plot1b_data[~np.isnan(plot1b_data)], 99))
                color_mapper1b = LinearColorMapper(palette="Viridis256", low=map1b_min_val, high=map1b_max_val)
                image_renderer1b = plot1b.image(
                    "image", source=source1b, x="x", y="y", dw="dw", dh="dh", color_mapper=color_mapper1b
                )
                colorbar1b = ColorBar(color_mapper=color_mapper1b, title="", location=(1, 0))
                plot1b.add_layout(colorbar1b, "right")

                # Initialize rect1b for Plot1B crosshairs
                rect1b = Rectangle(0, 0, volume.shape[0] - 1, volume.shape[1] - 1)

                # Tap handler for Plot1B
                def on_plot1b_tap(event):
                    """Handle tap events on Plot1B to update crosshair position."""
                    if hasattr(event, 'x') and hasattr(event, 'y'):
                        # Find closest indices in Plot1B's flipped coordinate arrays
                        plot1b_x_coords = map_plot_b.get_flipped_x_coords()
                        plot1b_y_coords = map_plot_b.get_flipped_y_coords()
                        x_idx = np.argmin(np.abs(plot1b_x_coords - event.x))
                        y_idx = np.argmin(np.abs(plot1b_y_coords - event.y))

                        # Convert back to original coordinate space for sliders
                        if map_plot_b.needs_flip:
                            x_slider.value = y_coords[y_idx] if y_idx < len(y_coords) else y_coords[-1]
                            y_slider.value = x_coords[x_idx] if x_idx < len(x_coords) else x_coords[-1]
                        else:
                            x_slider.value = x_coords[x_idx] if x_idx < len(x_coords) else x_coords[-1]
                            y_slider.value = y_coords[y_idx] if y_idx < len(y_coords) else y_coords[-1]
                        draw_cross1()  # This will also update Plot1B crosshairs
                        show_slice()

                # Add TapTool to Plot1B and connect handler
                tap_tool1b = TapTool()
                plot1b.add_tools(tap_tool1b)
                plot1b.on_event("tap", on_plot1b_tap)

                # Draw initial crosshairs on Plot1B (skip if loading session - will be drawn by auto_load_session)
                if not _session_loading_state["is_loading"]:
                    draw_cross1b()

                # CRITICAL: Add callbacks to redraw crosshairs whenever Plot1B ranges change
                def on_plot1b_range_change(attr, old, new):
                    """Redraw crosshairs when Plot1B range changes."""
                    # Don't redraw during session loading - it will be handled by auto_load_session
                    if _session_loading_state["is_loading"]:
                        return
                    try:
                        draw_cross1b()
                    except:
                        pass  # Silently fail if crosshairs can't be drawn yet

                plot1b.x_range.on_change("start", on_plot1b_range_change)
                plot1b.x_range.on_change("end", on_plot1b_range_change)
                plot1b.y_range.on_change("start", on_plot1b_range_change)
                plot1b.y_range.on_change("end", on_plot1b_range_change)
        except Exception as e:
            import traceback
            print(f"Failed to create Plot1B (ratio mode): {e}")
            traceback.print_exc()

    # Helper function to draw selection rectangles on plots
    def draw_rect(p, r, x1, x2, y1, y2, line_color="yellow", line_width=2):
        """Draw a rectangle on a plot using lines."""
        # Clear existing rectangle lines
        if r.h1line is not None:
            try:
                p.renderers.remove(r.h1line)
            except:
                pass
        if r.h2line is not None:
            try:
                p.renderers.remove(r.h2line)
            except:
                pass
        if r.v1line is not None:
            try:
                p.renderers.remove(r.v1line)
            except:
                pass
        if r.v2line is not None:
            try:
                p.renderers.remove(r.v2line)
            except:
                pass

        # Draw new rectangle
        r.h1line = p.line(x=[x1, x2], y=[y1, y1], line_color=line_color, line_width=line_width)
        r.h2line = p.line(x=[x1, x2], y=[y2, y2], line_color=line_color, line_width=line_width)
        r.v1line = p.line(x=[x1, x1], y=[y1, y2], line_color=line_color, line_width=line_width)
        r.v2line = p.line(x=[x2, x2], y=[y1, y2], line_color=line_color, line_width=line_width)

    def clear_rect(p, r):
        """Clear rectangle from plot."""
        if r.h1line is not None:
            try:
                p.renderers.remove(r.h1line)
            except:
                pass
            r.h1line = None
        if r.h2line is not None:
            try:
                p.renderers.remove(r.h2line)
            except:
                pass
            r.h2line = None
        if r.v1line is not None:
            try:
                p.renderers.remove(r.v1line)
            except:
                pass
            r.v1line = None
        if r.v2line is not None:
            try:
                p.renderers.remove(r.v2line)
            except:
                pass
            r.v2line = None

    # Add TapTool to Plot2 for region selection (Plot2 should NOT have crosshairs)
    tap_tool2 = TapTool()
    plot2.add_tools(tap_tool2)

    # Tap handler for Plot2 to set selection region
    def on_plot2_tap(event):
        """Handle tap events on Plot2 to set selection region."""
        if is_3d_volume:
            # For 3D: only use x-coordinate
            if hasattr(self.process_4dnexus, 'probe_x_coords_picked') and self.process_4dnexus.probe_x_coords_picked:
                try:
                    probe_coords = self.process_4dnexus.load_probe_coordinates()
                    if probe_coords is not None:
                        z_index = int(np.argmin(np.abs(probe_coords - event.x)))
                    else:
                        z_index = int(event.x)
                except:
                        z_index = int(event.x)
            else:
                z_index = int(event.x)

            if event.modifiers.get("shift", False):
                rect2.set(min_x=z_index, min_y=z_index)
            elif event.modifiers.get("ctrl", False) or event.modifiers.get('meta', False) or event.modifiers.get('cmd', False):
                rect2.set(max_x=z_index, max_y=z_index)
            else:
                # Regular click: set both to same value
                rect2.set(min_x=z_index, min_y=z_index, max_x=z_index, max_y=z_index)
                clear_rect(plot2, rect2)
                draw_rect(plot2, rect2, z_index, z_index, 0, plot2.y_range.end)
        else:
            # For 4D: use both x and y coordinates
            # Plot2 uses flipped coordinates, so we need to convert event coordinates to indices
            # using the flipped coordinate arrays
            plot2_x_coords = probe_2d_plot.get_flipped_x_coords()
            plot2_y_coords = probe_2d_plot.get_flipped_y_coords()

            # Find closest indices in flipped coordinate arrays
            click_u_idx = int(np.argmin(np.abs(plot2_x_coords - event.x))) if plot2_x_coords is not None else int(event.x)
            click_z_idx = int(np.argmin(np.abs(plot2_y_coords - event.y))) if plot2_y_coords is not None else int(event.y)

            # Convert back to original coordinate space (rect2 stores original indices)
            # The flipped coordinates correspond to swapped dimensions
            if probe_2d_plot.needs_flip:
                # When flipped: plot2_x_coords is actually probe_y (u), plot2_y_coords is actually probe_x (z)
                click_z = click_z_idx  # This is actually the z dimension index
                click_u = click_u_idx  # This is actually the u dimension index
            else:
                # Not flipped: plot2_x_coords is probe_x (z), plot2_y_coords is probe_y (u)
                click_z = click_u_idx  # This is the z dimension index
                click_u = click_z_idx  # This is the u dimension index

            if event.modifiers.get("shift", False):
                rect2.set(min_x=click_z, min_y=click_u)
            elif event.modifiers.get("ctrl", False) or event.modifiers.get('meta', False) or event.modifiers.get('cmd', False):
                rect2.set(max_x=click_z, max_y=click_u)
            else:
                # Regular click: set both to same value
                rect2.set(min_x=click_z, min_y=click_u, max_x=click_z, max_y=click_u)
                clear_rect(plot2, rect2)
                draw_rect(plot2, rect2, click_z, click_z, click_u, click_u)

    # Double-tap handler for Plot2 (sets max coordinates)
    def on_plot2_doubletap(event):
        """Handle double-tap events on Plot2 to set max coordinates."""
        if is_3d_volume:
            if hasattr(self.process_4dnexus, 'probe_x_coords_picked') and self.process_4dnexus.probe_x_coords_picked:
                try:
                    probe_coords = self.process_4dnexus.load_probe_coordinates()
                    if probe_coords is not None:
                        z_index = int(np.argmin(np.abs(probe_coords - event.x)))
                    else:
                        z_index = int(event.x)
                except:
                        z_index = int(event.x)
            else:
                z_index = int(event.x)
            rect2.set(max_x=z_index, max_y=z_index)
        else:
            # For 4D: use both x and y coordinates
            # Plot2 uses flipped coordinates, so we need to convert event coordinates to indices
            plot2_x_coords = probe_2d_plot.get_flipped_x_coords()
            plot2_y_coords = probe_2d_plot.get_flipped_y_coords()

            # Find closest indices in flipped coordinate arrays
            click_u_idx = int(np.argmin(np.abs(plot2_x_coords - event.x))) if plot2_x_coords is not None else int(event.x)
            click_z_idx = int(np.argmin(np.abs(plot2_y_coords - event.y))) if plot2_y_coords is not None else int(event.y)

            # Convert back to original coordinate space
            if probe_2d_plot.needs_flip:
                click_z = click_z_idx
                click_u = click_u_idx
            else:
                click_z = click_u_idx
                click_u = click_z_idx
            rect2.set(max_x=click_z, max_y=click_u)

    # Function to draw rect2 on Plot2
    # DISABLED: Using Bokeh's BoxAnnotation instead
    def draw_rect2():
        """Draw selection rectangle on Plot2."""
        # Disabled - using Bokeh's BoxAnnotation instead
        pass
        # if is_3d_volume:
        #     plot_x1 = rect2.min_x
        #     plot_x2 = rect2.max_x
        #     plot_y1 = 0
        #     plot_y2 = plot2.y_range.end
        # else:
        #     plot2_needs_flip = probe_2d_plot.needs_flip if hasattr(probe_2d_plot, 'needs_flip') else False
        #     if plot2_needs_flip:
        #         plot_x1 = rect2.min_y  # u min -> plot x
        #         plot_x2 = rect2.max_y  # u max -> plot x
        #         plot_y1 = rect2.min_x  # z min -> plot y
        #         plot_y2 = rect2.max_x  # z max -> plot y
        #     else:
        #         plot_x1 = rect2.min_x  # z min -> plot x
        #         plot_x2 = rect2.max_x  # z max -> plot x
        #         plot_y1 = rect2.min_y  # u min -> plot y
        #         plot_y2 = rect2.max_y  # u max -> plot y
        # draw_rect(plot2, rect2, plot_x1, plot_x2, plot_y1, plot_y2)

    # Add Plot2B tap handlers if Plot2B exists
    if plot2b is not None:
        tap_tool2b = TapTool()
        plot2b.add_tools(tap_tool2b)

        # Function to draw rect2b on Plot2B
        # DISABLED: Using Bokeh's BoxAnnotation instead
        def draw_rect2b():
            """Draw selection rectangle on Plot2B."""
            # Disabled - using Bokeh's BoxAnnotation instead
            pass
            # if not plot2b_is_2d:
            #     # 1D plot
            #     plot_x1 = rect2b.min_x
            #     plot_x2 = rect2b.max_x
            #     plot_y1 = 0
            #     plot_y2 = plot2b.y_range.end
            # else:
            #     # 2D plot
            #     plot2b_needs_flip = probe_2d_plot_b.needs_flip if hasattr(probe_2d_plot_b, 'needs_flip') else False
            #     if plot2b_needs_flip:
            #         plot_x1 = rect2b.min_y  # u min -> plot x
            #         plot_x2 = rect2b.max_y  # u max -> plot x
            #         plot_y1 = rect2b.min_x  # z min -> plot y
            #         plot_y2 = rect2b.max_x  # z max -> plot y
            #     else:
            #         plot_x1 = rect2b.min_x  # z min -> plot x
            #         plot_x2 = rect2b.max_x  # z max -> plot x
            #         plot_y1 = rect2b.min_y  # u min -> plot y
            #         plot_y2 = rect2b.max_y  # u max -> plot y
            # draw_rect(plot2b, rect2b, plot_x1, plot_x2, plot_y1, plot_y2)

        # Tap handler for Plot2B
        def on_plot2b_tap(event):
            """Handle tap events on Plot2B to set selection region."""
            if not plot2b_is_2d:
                # 1D plot
                if hasattr(self.process_4dnexus, 'probe_x_coords_picked_b') and self.process_4dnexus.probe_x_coords_picked_b:
                    try:
                        probe_coords_b = self.process_4dnexus.load_probe_coordinates(use_b=True)
                        if probe_coords_b is not None:
                            z_index = int(np.argmin(np.abs(probe_coords_b - event.x)))
                        else:
                            z_index = int(event.x)
                    except:
                        z_index = int(event.x)
                else:
                        z_index = int(event.x)

                if hasattr(event, 'modifiers') and event.modifiers.get("shift", False):
                    rect2b.set(min_x=z_index, min_y=z_index)
                elif hasattr(event, 'modifiers') and (event.modifiers.get("ctrl", False) or event.modifiers.get('meta', False) or event.modifiers.get('cmd', False)):
                    rect2b.set(max_x=z_index, max_y=z_index)
                else:
                    rect2b.set(min_x=z_index, min_y=z_index, max_x=z_index, max_y=z_index)
                    clear_rect(plot2b, rect2b)
                    draw_rect(plot2b, rect2b, z_index, z_index, 0, plot2b.y_range.end)
            else:
                # 2D plot
                plot2b_needs_flip = probe_2d_plot_b.needs_flip if hasattr(probe_2d_plot_b, 'needs_flip') else False
                if plot2b_needs_flip:
                    click_z = int(event.y)
                    click_u = int(event.x)
                else:
                    click_z = int(event.x)
                    click_u = int(event.y)

                if hasattr(event, 'modifiers') and event.modifiers.get("shift", False):
                    rect2b.set(min_x=click_z, min_y=click_u)
                    # draw_rect2b()  # Disabled - using Bokeh's BoxAnnotation instead
                elif hasattr(event, 'modifiers') and (event.modifiers.get("ctrl", False) or event.modifiers.get('meta', False) or event.modifiers.get('cmd', False)):
                    rect2b.set(max_x=click_z, max_y=click_u)
                    # draw_rect2b()  # Disabled - using Bokeh's BoxAnnotation instead
                else:
                    clear_rect(plot2b, rect2b)
                    rect2b.set(min_x=click_z, min_y=click_u, max_x=click_z, max_y=click_u)
                    draw_rect(plot2b, rect2b, click_z, click_z, click_u, click_u)

        # Double-tap handler for Plot2B
        def on_plot2b_doubletap(event):
            """Handle double-tap events on Plot2B to set max coordinates."""
            if not plot2b_is_2d:
                if hasattr(self.process_4dnexus, 'probe_x_coords_picked_b') and self.process_4dnexus.probe_x_coords_picked_b:
                    try:
                        probe_coords_b = self.process_4dnexus.load_probe_coordinates(use_b=True)
                        if probe_coords_b is not None:
                            z_index = int(np.argmin(np.abs(probe_coords_b - event.x)))
                        else:
                            z_index = int(event.x)
                    except:
                        z_index = int(event.x)
                else:
                    z_index = int(event.x)
                rect2b.set(max_x=z_index, max_y=z_index)
            else:
                plot2b_needs_flip = probe_2d_plot_b.needs_flip if hasattr(probe_2d_plot_b, 'needs_flip') else False
                if plot2b_needs_flip:
                    click_z = int(event.y)
                    click_u = int(event.x)
                else:
                    click_z = int(event.x)
                    click_u = int(event.y)
                rect2b.set(max_x=click_z, max_y=click_u)
                draw_rect2b()

    # Reset buttons for Plot2 and Plot2b
    # Create buttons for both 3D and 4D volumes (reset reloads from data source)
    reset_plot2_button = None
    reset_plot2b_button = None
    
    if plot2 is not None:
        reset_plot2_button = create_button(
            label="Reset Plot2",
            button_type="warning",
            width=100
        )
    
    if plot2b is not None:
        reset_plot2b_button = create_button(
            label="Reset Plot2b",
            button_type="warning",
            width=100
        )
    
    # Create buttons to compute Plot3 from Plot2 selections
    compute_plot3_button = create_button(
        label="Generate Projection", #Show Plot3 from Plot2a ->",
        button_type="success",
        width=100  # Changed from 200 to 100 to match other widgets (as small as possible)
    )

    compute_plot3_from_plot2b_button = None
    if plot2b is not None:
        compute_plot3_from_plot2b_button = create_button(
            label="Generate Projection", #"Show Plot3 from Plot2b ->",
            button_type="success",
            width=100  # Changed from 200 to 100 to match other widgets (as small as possible)
        )

    # Create undo/redo buttons first (needed for callbacks)
    undo_button = create_button(
        label="Undo",
        button_type="default",
        width=100
    )

    redo_button = create_button(
        label="Redo",
        button_type="default",
        width=100
    )

    # Create undo/redo status display
    undo_redo_status = create_div(text="State 1 of 1", width=200)

    # Set up undo/redo callbacks
    undo_redo_callbacks = create_undo_redo_callbacks(
        session_history,
        undo_button,
        redo_button,
        undo_redo_status
    )

    # Debouncing for state saves - only save after user stops making changes
    # This prevents excessive state saves during rapid UI interactions
    # Use a mutable container so nested functions can modify the values
    _state_save_state = {"timer": None, "pending": False}
    _skip_slider_state_save = {"value": False}  # Flag to skip state saves during undo/redo (mutable container)
    
    # Track slider drag state - only save initial and final positions to undo/redo
    _slider_drag_state = {
        "x": {"is_dragging": False, "initial_value": None, "timer": None},
        "y": {"is_dragging": False, "initial_value": None, "timer": None}
    }
    
    # Track zoom state for Plot2 and Plot2B to preserve user zoom when updating slices
    _plot2_zoom_state = {
        "x_range": {"min": None, "max": None, "coords_min": None, "coords_max": None},
        "y_range": {"min": None, "max": None, "coords_min": None, "coords_max": None},
        "is_manual_zoom": False
    }
    _plot2b_zoom_state = {
        "x_range": {"min": None, "max": None, "coords_min": None, "coords_max": None},
        "y_range": {"min": None, "max": None, "coords_min": None, "coords_max": None},
        "is_manual_zoom": False
    }

    def debounced_save_state(description: str, update_undo_redo: bool = True, delay: float = 0.5):
        """
        Save state with debouncing to avoid excessive saves during rapid changes.

        Args:
            description: Description of the state change
            update_undo_redo: Whether to update undo/redo buttons (can skip for frequent operations)
            delay: Delay in seconds before actually saving (default 0.5s)
        """
        from bokeh.io import curdoc

        def do_save():
            if _state_save_state["pending"]:
                # Save slider positions to session metadata before saving state
                # Access x_slider and y_slider from closure scope (not locals())
                try:
                    # Try to access sliders from closure - they should be available
                    if x_slider is not None:
                        session.metadata['x_slider_value'] = x_slider.value
                        print(f"🔍 DEBUG: do_save() - Saved x_slider.value = {x_slider.value} to session.metadata")
                    if y_slider is not None:
                        session.metadata['y_slider_value'] = y_slider.value
                        print(f"🔍 DEBUG: do_save() - Saved y_slider.value = {y_slider.value} to session.metadata")
                except (NameError, AttributeError) as e:
                    print(f"⚠️ DEBUG: Error saving slider values to metadata: {e}")
                    import traceback
                    traceback.print_exc()
                
                print(f"🔍 DEBUG: do_save() - Saving state with description: {description}")
                print(f"🔍 DEBUG: do_save() - session.metadata keys before save: {list(session.metadata.keys())}")
                plot1_history.save_state(description)
                session_history.save_state(description)
                print(f"✅ DEBUG: do_save() - State saved. History length: {len(session_history.history)}, current_index: {session_history.current_index}")
                if update_undo_redo:
                    undo_redo_callbacks["update"]()
                _state_save_state["pending"] = False

        # Cancel any pending save
        if _state_save_state["timer"] is not None:
            try:
                curdoc().remove_timeout_callback(_state_save_state["timer"])
            except:
                pass

        _state_save_state["pending"] = True
        _state_save_state["timer"] = curdoc().add_timeout_callback(do_save, delay)

    # Create UI update function (defined after color_mapper1 is created)
    def update_ui_after_state_change():
        """Update UI widgets after state change (undo/redo/load)."""
        # Sync Plot1 range inputs
        if plot1_is_1d and plot1_1d_plot is not None:
            sync_plot_to_range_inputs(plot1_1d_plot, range1_min_input, range1_max_input)
        elif map_plot is not None:
            sync_plot_to_range_inputs(map_plot, range1_min_input, range1_max_input)
        # Sync color scale selectors for all plots
        try:
            from SCLib_Dashboards.SCDashUI_sync import sync_plot_to_color_scale_selector
            # Sync Plot1 color scale selector (only for 2D plots)
            if not plot1_is_1d and map_plot is not None:
                sync_plot_to_color_scale_selector(map_plot, plot1_color_scale_selector)
            
            # Sync Plot2 color scale selector if it exists
            try:
                if 'plot2_color_scale_selector' in locals() and plot2_color_scale_selector is not None:
                    if probe_2d_plot is not None:
                        sync_plot_to_color_scale_selector(probe_2d_plot, plot2_color_scale_selector)
                    elif probe_1d_plot is not None:
                        # For 1D plots, check if y_scale is LogScale
                        from bokeh.models import LogScale
                        is_log = isinstance(plot2.y_scale, LogScale) if 'plot2' in locals() and plot2 is not None else False
                        plot2_color_scale_selector.active = 1 if is_log else 0
            except Exception as e:
                print(f"⚠️ DEBUG: Could not sync Plot2 color scale selector: {e}")
            
            # Sync Plot2B color scale selector if it exists
            try:
                if 'plot2b_color_scale_selector' in locals() and plot2b_color_scale_selector is not None:
                    if probe_2d_plot_b is not None:
                        sync_plot_to_color_scale_selector(probe_2d_plot_b, plot2b_color_scale_selector)
                    elif probe_1d_plot_b is not None:
                        # For 1D plots, check if y_scale is LogScale
                        from bokeh.models import LogScale
                        is_log = isinstance(plot2b.y_scale, LogScale) if 'plot2b' in locals() and plot2b is not None else False
                        plot2b_color_scale_selector.active = 1 if is_log else 0
            except Exception as e:
                print(f"⚠️ DEBUG: Could not sync Plot2B color scale selector: {e}")
            
            # Sync Plot3 color scale selector (Plot3 uses map_plot for state, or plot1_1d_plot if Plot1 is 1D)
            try:
                if 'plot3_color_scale_selector' in locals() and plot3_color_scale_selector is not None:
                    # Plot3 doesn't have color scale for 1D plots, so only sync for 2D plots
                    if not plot1_is_1d and map_plot is not None:
                        sync_plot_to_color_scale_selector(map_plot, plot3_color_scale_selector)
            except Exception as e:
                print(f"⚠️ DEBUG: Could not sync Plot3 color scale selector: {e}")
        except Exception as e:
            print(f"⚠️ DEBUG: Error syncing color scale selectors: {e}")
        
        # Sync Plot1 palette and color mapper (only for 2D plots)
        if plot1_is_1d and plot1_1d_plot is not None:
            # For 1D plots, sync to plot1_1d_plot if needed
            if plot1_1d_plot is not None and palette_selector is not None:
                sync_plot_to_palette_selector(plot1_1d_plot, palette_selector)
        else:
            if map_plot is not None:
                sync_plot_to_palette_selector(map_plot, palette_selector)
                # Update Bokeh color mapper if needed
                if color_mapper1 is not None:
                    if hasattr(map_plot, 'range_min') and hasattr(map_plot, 'range_max'):
                        color_mapper1.low = map_plot.range_min
                        color_mapper1.high = map_plot.range_max
                    if map_plot.palette != color_mapper1.palette:
                        color_mapper1.palette = map_plot.palette
        
        # Sync Plot1 range mode toggle label and active state
        try:
            if 'range1_mode_toggle' in locals() and range1_mode_toggle is not None:
                if plot1_is_1d and plot1_1d_plot is not None:
                    # For 1D plots, check plot1_1d_plot range mode
                    if plot1_1d_plot.range_mode == RangeMode.USER_SPECIFIED:
                        range1_mode_toggle.label = "Auto=Off"
                        range1_mode_toggle.active = True
                    else:
                        range1_mode_toggle.label = "Auto=On"
                        range1_mode_toggle.active = False
                elif map_plot is not None:
                    if map_plot.range_mode == RangeMode.USER_SPECIFIED:
                        range1_mode_toggle.label = "Auto=Off"
                        range1_mode_toggle.active = True
                    else:
                        range1_mode_toggle.label = "Auto=On"
                        range1_mode_toggle.active = False
        except:
            pass
        
        # Sync Plot1B range mode toggle if it exists
        try:
            if 'range1b_mode_toggle' in locals() and range1b_mode_toggle is not None and map_plot_b is not None:
                if map_plot_b.range_mode == RangeMode.USER_SPECIFIED:
                    range1b_mode_toggle.label = "Auto=Off"
                    range1b_mode_toggle.active = True
                else:
                    range1b_mode_toggle.label = "Auto=On"
                    range1b_mode_toggle.active = False
        except:
            pass
        
        # Sync Plot2 range mode toggle if it exists
        try:
            if 'range2_mode_toggle' in locals() and range2_mode_toggle is not None:
                # For Plot2, check probe_2d_plot or probe_1d_plot range_mode
                plot2_range_mode = None
                if probe_2d_plot is not None and hasattr(probe_2d_plot, 'range_mode'):
                    plot2_range_mode = probe_2d_plot.range_mode
                elif probe_1d_plot is not None and hasattr(probe_1d_plot, 'range_mode'):
                    plot2_range_mode = probe_1d_plot.range_mode
                
                if plot2_range_mode == RangeMode.USER_SPECIFIED:
                    range2_mode_toggle.label = "Auto=Off"
                    range2_mode_toggle.active = True
                else:
                    range2_mode_toggle.label = "Auto=On"
                    range2_mode_toggle.active = False
        except:
            pass
        
        # Sync Plot2B range mode toggle if it exists
        try:
            if 'range2b_mode_toggle' in locals() and range2b_mode_toggle is not None:
                # For Plot2B, check probe_2d_plot_b or probe_1d_plot_b range_mode
                plot2b_range_mode = None
                if probe_2d_plot_b is not None and hasattr(probe_2d_plot_b, 'range_mode'):
                    plot2b_range_mode = probe_2d_plot_b.range_mode
                elif probe_1d_plot_b is not None and hasattr(probe_1d_plot_b, 'range_mode'):
                    plot2b_range_mode = probe_1d_plot_b.range_mode
                
                if plot2b_range_mode == RangeMode.USER_SPECIFIED:
                    range2b_mode_toggle.label = "Auto=Off"
                    range2b_mode_toggle.active = True
                else:
                    range2b_mode_toggle.label = "Auto=On"
                    range2b_mode_toggle.active = False
        except:
            pass
        
        # Sync Plot3 range mode toggle if it exists (Plot3 uses map_plot for state)
        try:
            if 'range3_mode_toggle' in locals() and range3_mode_toggle is not None:
                if map_plot is not None:
                    if map_plot.range_mode == RangeMode.USER_SPECIFIED:
                        range3_mode_toggle.label = "Auto=Off"
                        range3_mode_toggle.active = True
                    else:
                        range3_mode_toggle.label = "Auto=On"
                        range3_mode_toggle.active = False
        except:
            pass
        
        # Restore slider positions from session metadata
        # Use flag to prevent state saves during restoration
        print(f"🔍 DEBUG: update_ui_after_state_change() called")
        print(f"🔍 DEBUG: session.metadata keys: {list(session.metadata.keys())}")
        
        _skip_slider_state_save["value"] = True
        try:
            # Access sliders from closure scope (not locals())
            if x_slider is not None and y_slider is not None:
                # Restore both slider values (handlers will update plots but won't save state)
                slider_restored = False
                if 'x_slider_value' in session.metadata:
                    print(f"🔍 DEBUG: Restoring x_slider.value from {x_slider.value} to {session.metadata['x_slider_value']}")
                    x_slider.value = session.metadata['x_slider_value']
                    slider_restored = True
                else:
                    # No saved value - restore to initial position (middle of range)
                    initial_x = float(x_slider.start + (x_slider.end - x_slider.start) / 2)
                    print(f"⚠️ DEBUG: 'x_slider_value' not found in session.metadata - restoring to initial position: {initial_x}")
                    x_slider.value = initial_x
                    slider_restored = True
                    
                if 'y_slider_value' in session.metadata:
                    print(f"🔍 DEBUG: Restoring y_slider.value from {y_slider.value} to {session.metadata['y_slider_value']}")
                    y_slider.value = session.metadata['y_slider_value']
                    slider_restored = True
                else:
                    # No saved value - restore to initial position (middle of range)
                    initial_y = float(y_slider.start + (y_slider.end - y_slider.start) / 2)
                    print(f"⚠️ DEBUG: 'y_slider_value' not found in session.metadata - restoring to initial position: {initial_y}")
                    y_slider.value = initial_y
                    slider_restored = True
                
                # Explicitly update crosshairs and slice after restoring slider values
                # This ensures they're updated even if change handlers don't fire
                # Always update crosshairs/slice if at least one slider was restored, or if we're restoring to initial state
                if slider_restored:
                    print(f"✅ DEBUG: Slider values restored, updating crosshairs and slice")
                    try:
                        draw_cross1()  # Update crosshairs on Plot1 and Plot3
                        show_slice()   # Update Plot2 slice
                        try:
                            show_slice_b()  # Update Plot2B slice if it exists
                        except NameError:
                            pass  # show_slice_b not defined
                        print(f"✅ DEBUG: Crosshairs and slice updated successfully")
                    except Exception as e:
                        print(f"⚠️ Warning: Could not update crosshairs/slice after slider restore: {e}")
                        import traceback
                        traceback.print_exc()
                else:
                    print(f"⚠️ DEBUG: No slider values to restore - sliders remain at current positions")
                    # Even if no sliders were restored, update crosshairs/slice to reflect current slider positions
                    try:
                        draw_cross1()  # Update crosshairs based on current slider values
                        show_slice()   # Update Plot2 slice based on current slider values
                        try:
                            show_slice_b()  # Update Plot2B slice if it exists
                        except NameError:
                            pass
                        print(f"✅ DEBUG: Crosshairs and slice updated to reflect current slider positions")
                    except Exception as e:
                        print(f"⚠️ Warning: Could not update crosshairs/slice: {e}")
            else:
                print(f"⚠️ DEBUG: x_slider or y_slider is None or not accessible")
        except (NameError, AttributeError) as e:
            print(f"⚠️ Warning: Could not access sliders for restoration: {e}")
            import traceback
            traceback.print_exc()
        except Exception as e:
            print(f"⚠️ Warning: Could not restore slider positions: {e}")
            import traceback
            traceback.print_exc()
        finally:
            _skip_slider_state_save["value"] = False
        
        # Restore Plot2 and Plot2B custom dimensions and probe scale from session metadata
        try:
            # Restore Plot2 dimensions
            if 'plot2_width' in session.metadata and 'plot2_height' in session.metadata and plot2 is not None:
                plot2_width = session.metadata['plot2_width']
                plot2_height = session.metadata['plot2_height']
                # Add colorbar width if Plot2 has a colorbar (2D plots)
                if not is_3d_volume and color_mapper2 is not None:
                    plot2.width = plot2_width + colorbar_width
                else:
                    plot2.width = plot2_width
                plot2.height = plot2_height
                # Update custom width/height inputs
                if 'plot2_custom_width_input' in locals() and plot2_custom_width_input is not None:
                    plot2_custom_width_input.value = str(int(plot2_width))
                if 'plot2_custom_height_input' in locals() and plot2_custom_height_input is not None:
                    plot2_custom_height_input.value = str(int(plot2_height))
                print(f"✅ Restored Plot2 dimensions: {plot2_width}x{plot2_height}")
            
            # Restore Plot2B dimensions
            if 'plot2b_width' in session.metadata and 'plot2b_height' in session.metadata and plot2b is not None:
                plot2b_width = session.metadata['plot2b_width']
                plot2b_height = session.metadata['plot2b_height']
                # Add colorbar width if Plot2B has a colorbar (2D plots)
                if 'plot2b_is_2d' in locals() and plot2b_is_2d and color_mapper2b is not None:
                    plot2b.width = plot2b_width + colorbar_width
                else:
                    plot2b.width = plot2b_width
                plot2b.height = plot2b_height
                # Update custom width/height inputs
                if 'plot2b_custom_width_input' in locals() and plot2b_custom_width_input is not None:
                    plot2b_custom_width_input.value = str(int(plot2b_width))
                if 'plot2b_custom_height_input' in locals() and plot2b_custom_height_input is not None:
                    plot2b_custom_height_input.value = str(int(plot2b_height))
                print(f"✅ Restored Plot2B dimensions: {plot2b_width}x{plot2b_height}")
            
            # Restore probe scale
            if 'probe_scale' in session.metadata and 'probe_scale_input' in locals() and probe_scale_input is not None:
                probe_scale_value = session.metadata['probe_scale']
                probe_scale_input.value = str(probe_scale_value)
                # Trigger the probe scale change handler to apply the scale
                try:
                    on_probe_scale_change(None, None, str(probe_scale_value))
                except:
                    pass
                print(f"✅ Restored probe scale: {probe_scale_value}%")
        except Exception as e:
            print(f"⚠️ Warning: Could not restore Plot2/Plot2B dimensions or probe scale: {e}")
            import traceback
            traceback.print_exc()

    # Create custom undo/redo callbacks that also update UI
    def on_undo():
        """Undo callback with UI update."""
        print(f"🔍 DEBUG: on_undo() called")
        print(f"🔍 DEBUG: session_history.can_undo() = {session_history.can_undo()}")
        print(f"🔍 DEBUG: session_history.current_index = {session_history.current_index}")
        print(f"🔍 DEBUG: session_history.history length = {len(session_history.history)}")
        
        if session_history.undo():
            print(f"✅ DEBUG: session_history.undo() returned True")
            try:
                print(f"🔍 DEBUG: Current slider values before restore: x={x_slider.value}, y={y_slider.value}")
            except (NameError, AttributeError):
                print(f"🔍 DEBUG: Could not access slider values (not in scope)")
            print(f"🔍 DEBUG: session.metadata keys: {list(session.metadata.keys())}")
            if 'x_slider_value' in session.metadata:
                print(f"🔍 DEBUG: session.metadata['x_slider_value'] = {session.metadata['x_slider_value']}")
            if 'y_slider_value' in session.metadata:
                print(f"🔍 DEBUG: session.metadata['y_slider_value'] = {session.metadata['y_slider_value']}")
            
            update_ui_after_state_change()
            undo_redo_callbacks["update"]()
            try:
                print(f"✅ DEBUG: After update_ui_after_state_change(), slider values: x={x_slider.value}, y={y_slider.value}")
            except (NameError, AttributeError):
                print(f"✅ DEBUG: After update_ui_after_state_change(), could not access slider values")
            
            if 'status_div' in locals():
                status_div.text = "Undo successful"
        else:
            print(f"❌ DEBUG: session_history.undo() returned False")
            if 'status_div' in locals():
                status_div.text = "Cannot undo - already at initial state"

    def on_redo():
        """Redo callback with UI update."""
        if session_history.redo():
            update_ui_after_state_change()
            undo_redo_callbacks["update"]()
            if 'status_div' in locals():
                status_div.text = "Redo successful"
        else:
            if 'status_div' in locals():
                status_div.text = "Cannot redo - already at latest state"

    # Override with custom callbacks that update UI
    undo_button.on_click(on_undo)
    redo_button.on_click(on_redo)

    # Create session management UI components
    # Function to get default save filename
    def get_default_save_filename():
        """Generate default save filename."""
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"session_{timestamp}.json"

    # Create text input for save filename
    save_filename_input = create_text_input(
        title="Save Filename:",
        value=get_default_save_filename(),
        width=200
    )

    # Create text input for save directory (optional, defaults to sessions subdirectory)
    save_dir_input = create_text_input(
        title="Save Directory (optional):",
        value="",
        width=200,
        placeholder="Leave empty for default sessions directory"
    )

    save_session_button = create_button(
        label="Save Session",
        button_type="success",
        width=120
    )

    # Function to refresh session list for loading
    def refresh_session_list():
        """Refresh the list of available sessions from both preferred and fallback locations."""
        try:
            from pathlib import Path
            import os
            from datetime import datetime

            # Determine sessions directory (use nexus file directory)
            save_dir_path = get_save_dir_path()
            print(f"🔍 DEBUG refresh_session_list: save_dir_path = {save_dir_path}")

            # Check BOTH preferred and fallback locations to find all sessions
            preferred_sessions_dir = save_dir_path / "sessions"
            print(f"🔍 DEBUG refresh_session_list: preferred_sessions_dir = {preferred_sessions_dir}")
            all_session_files = []
            
            # Check preferred location first
            if preferred_sessions_dir.exists() and preferred_sessions_dir.is_dir():
                try:
                    # Test if readable
                    list(preferred_sessions_dir.iterdir())
                    # Find session files in preferred location
                    preferred_files = list(preferred_sessions_dir.glob("session_*.json"))
                    all_session_files.extend(preferred_files)
                    print(f"✅ Found {len(preferred_files)} session(s) in preferred location: {preferred_sessions_dir}")
                except (PermissionError, OSError) as e:
                    print(f"⚠️ Cannot read preferred sessions directory: {e}")
            
            # Also check fallback location (where sessions might actually be saved)
            try:
                fallback_sessions_dir = get_writable_sessions_dir(save_dir_path)
                if fallback_sessions_dir.exists() and fallback_sessions_dir.is_dir():
                    # Find session files in fallback location
                    fallback_files = list(fallback_sessions_dir.glob("session_*.json"))
                    # Only add files that aren't already in the list (avoid duplicates)
                    for f in fallback_files:
                        if f not in all_session_files:
                            all_session_files.append(f)
                    if fallback_files:
                        print(f"✅ Found {len(fallback_files)} session(s) in fallback location: {fallback_sessions_dir}")
            except (PermissionError, OSError) as e:
                print(f"⚠️ Cannot access fallback sessions directory: {e}")

            # If no session files found in either location
            if not all_session_files:
                load_session_select.options = ["No session files found"]
                return []

            # Sort all session files by modification time (newest first)
            all_session_files = sorted(all_session_files, key=os.path.getmtime, reverse=True)

            # Create display names with timestamps
            session_choices = []
            session_files_list = []
            for filepath in all_session_files:
                try:
                    mtime = os.path.getmtime(filepath)
                    timestamp_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
                    display_name = f"{filepath.name} ({timestamp_str})"
                    session_choices.append(display_name)
                    session_files_list.append(filepath)
                except Exception as e:
                    print(f"⚠️ Error processing session file {filepath}: {e}")
                    session_choices.append(filepath.name)
                    session_files_list.append(filepath)

            load_session_select.options = session_choices
            print(f"✅ Total sessions found: {len(session_files_list)}")
            return session_files_list
        except Exception as e:
            print(f"Error refreshing session list: {e}")
            load_session_select.options = [f"Error: {str(e)}"]
            return []

    # Create select dropdown for loading sessions
    load_session_select = create_select(
        title="Load Session:",
        value="",
        options=["Click 'Refresh' to load sessions"],
        width=200
    )

    # Store session files list (will be updated by refresh)
    # Use a mutable container so nested functions can modify it
    _session_state = {"files": []}

    # Initialize status_div to None (will be created later)
    # This allows on_refresh_sessions() to reference it as a free variable
    status_div = None

    # Refresh button for session list
    refresh_sessions_button = create_button(
        label="Refresh Sessions",
        button_type="default",
        width=120
    )

    def on_refresh_sessions():
        """Refresh the session list."""
        # Update the mutable container (no nonlocal needed)
        _session_state["files"] = refresh_session_list()
        # Only update status_div if it exists and is not None
        # status_div is accessed from outer scope, no nonlocal needed for reading
        if status_div is not None:
            if _session_state["files"]:
                status_div.text = f"Found {len(_session_state['files'])} session(s)"
            else:
                status_div.text = "No sessions found"

    refresh_sessions_button.on_click(on_refresh_sessions)

    load_session_button = create_button(
        label="Load",
        button_type="primary",
        width=60
    )

    # Create button to go back to dataset selection
    back_to_selection_button = create_button(
        label="Back to Dataset Selection",
        button_type="default",
        width=150
    )

    # Create range inputs using SCLib UI
    def on_range_change(attr, old, new):
        """Handle range input changes."""
        if sync_range_inputs_to_plot(map_plot, range1_min_input, range1_max_input):
            # Update Bokeh color mapper immediately
            color_mapper1.low = map_plot.range_min
            color_mapper1.high = map_plot.range_max
            # Save state with debouncing to avoid excessive saves
            debounced_save_state("Range changed", update_undo_redo=True)

    # Note: range1_min_input and range1_max_input will be extracted from range1_section below
    # We create them here as placeholders that will be overwritten
    range1_min_input = None
    range1_max_input = None

    # Function to update Plot1 range dynamically based on static map data
    def update_plot1_range_dynamic():
        """Update Plot1 range to 1st and 99th percentiles of static map data (Plot1's own data, not slice data)."""
        # Skip for 1D plots (no color mapper to update)
        if plot1_is_1d and plot1_1d_plot is not None:
            return
        
        if map_plot is None:
            return
            
        print(f"🔍 DEBUG: update_plot1_range_dynamic() called, range_mode={map_plot.range_mode}")
        if map_plot.range_mode == RangeMode.DYNAMIC:
            # Update toggle label to show "Dynamic" while recalculating
            try:
                if 'range1_mode_toggle' in locals() and range1_mode_toggle is not None:
                    range1_mode_toggle.label = "Auto=On"
            except:
                pass

            # Get static map data from Plot1 (NOT from Plot2's slice data)
            # Plot1 shows a 2D map projection that doesn't change when slider moves
            current_data = None
            try:
                # Primary source: get data directly from map_plot
                if map_plot is not None:
                    current_data = map_plot.get_flipped_data()
                elif plot1_is_1d and plot1_1d_data is not None:
                    # For 1D plots, use plot1_1d_data
                    current_data = plot1_1d_data
                if current_data is not None and current_data.size == 0:
                    current_data = None
                else:
                        print(f"🔍 DEBUG: Got static map data from map_plot, shape={current_data.shape if current_data is not None else 'None'}")
            except Exception as e:
                print(f"⚠️ WARNING in update_plot1_range_dynamic(): Failed to get data from map_plot: {e}")
                current_data = None

            # Fallback to source1 if map_plot doesn't have data
            if current_data is None or current_data.size == 0:
                try:
                    if 'source1' in locals() and source1 is not None and 'image' in source1.data and len(source1.data['image']) > 0:
                        current_data = np.array(source1.data["image"][0])
                    print(f"🔍 DEBUG: Got static map data from source1, shape={current_data.shape}")
                except Exception as e:
                        print(f"⚠️ WARNING in update_plot1_range_dynamic(): Failed to get data from source1: {e}")

                    # Final fallback to plot1_data
                if (current_data is None or current_data.size == 0) and 'plot1_data' in locals() and plot1_data is not None:
                    current_data = plot1_data
                    print(f"🔍 DEBUG: Using plot1_data as final fallback, shape={current_data.shape if current_data is not None else 'None'}")

            if current_data is not None and current_data.size > 0:
                try:
                    # Filter out NaN and infinite values
                    valid_data = current_data[~np.isnan(current_data) & ~np.isinf(current_data)]
                    if valid_data.size > 0:
                        new_min = float(np.percentile(valid_data, 1))
                        new_max = float(np.percentile(valid_data, 99))

                        print(f"🔍 DEBUG: update_plot1_range_dynamic() computed range: min={new_min:.6f}, max={new_max:.6f}")

                        # Update map_plot range
                        map_plot.range_min = new_min
                        map_plot.range_max = new_max

                        # Update UI inputs - access from closure scope
                        # Use add_next_tick_callback to ensure updates happen in next Bokeh tick
                        from bokeh.io import curdoc
                        def update_inputs():
                            try:
                                was_min_disabled = range1_min_input.disabled if range1_min_input is not None else False
                                was_max_disabled = range1_max_input.disabled if range1_max_input is not None else False

                                # Temporarily enable if disabled (so values update visually)
                                if range1_min_input is not None:
                                    if was_min_disabled:
                                        range1_min_input.disabled = False
                                    range1_min_input.value = str(new_min)
                                    if was_min_disabled:
                                        range1_min_input.disabled = True

                                if range1_max_input is not None:
                                    if was_max_disabled:
                                        range1_max_input.disabled = False
                                    range1_max_input.value = str(new_max)
                                    if was_max_disabled:
                                        range1_max_input.disabled = True

                                print(f"✅ DEBUG: Updated range1_min_input.value = {new_min:.6f}")
                                print(f"✅ DEBUG: Updated range1_max_input.value = {new_max:.6f}")
                            except Exception as e:
                                print(f"⚠️ WARNING in update_plot1_range_dynamic(): Failed to update range inputs: {e}")
                                import traceback
                                traceback.print_exc()

                        curdoc().add_next_tick_callback(update_inputs)

                        # Update color mapper
                        try:
                            if 'color_mapper1' in locals() and color_mapper1 is not None:
                                color_mapper1.low = new_min
                                color_mapper1.high = new_max
                                print(f"✅ DEBUG: Updated color_mapper1: low={new_min:.6f}, high={new_max:.6f}")
                        except Exception as e:
                            print(f"⚠️ WARNING in update_plot1_range_dynamic(): Failed to update color_mapper1: {e}")
                            import traceback
                            traceback.print_exc()
                    else:
                        print(f"⚠️ WARNING in update_plot1_range_dynamic(): No valid data after filtering NaN/Inf")
                except Exception as e:
                    print(f"⚠️ ERROR in update_plot1_range_dynamic(): Failed to compute percentiles: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                print(f"⚠️ WARNING in update_plot1_range_dynamic(): No data available (current_data is None or empty)")
                if current_data is None:
                    print(f"   current_data is None")
                elif current_data.size == 0:
                    print(f"   current_data.size == 0")

    # Create range section with toggle for Plot1
    # Set initial label based on range mode
    if plot1_is_1d and plot1_1d_plot is not None:
        plot1_initial_label = "Auto=Off" if plot1_1d_plot.range_mode == RangeMode.USER_SPECIFIED else "Auto=On"
        plot1_initial_active = (plot1_1d_plot.range_mode == RangeMode.USER_SPECIFIED)
    elif map_plot is not None:
        plot1_initial_label = "Auto=Off" if map_plot.range_mode == RangeMode.USER_SPECIFIED else "Auto=On"
        plot1_initial_active = (map_plot.range_mode == RangeMode.USER_SPECIFIED)
    else:
        plot1_initial_label = "Auto=On"
        plot1_initial_active = False
    range1_section, range1_mode_toggle = create_range_section_with_toggle(
        label="Plot1 Range:",
        min_title="Min:",
        max_title="Max:",
        min_value=map_min_val,
        max_value=map_max_val,
        width=100,  # Changed from 120 to 100 to match other widgets
        toggle_label=plot1_initial_label,
        toggle_active=plot1_initial_active,
        toggle_callback=None,  # Will be set after toggle is created
        min_callback=on_range_change,
        max_callback=on_range_change,
    )
    
    # Define callback after toggle is created so we can reference it
    def on_plot1_range_mode_change(attr, old, new):
        """Handle Plot1 range mode toggle (User Specified vs Dynamic)."""
        # Note: toggle_active=True means User Specified, toggle_active=False means Dynamic
        # The callback receives new=True when toggle is active (User Specified), new=False when inactive (Dynamic)
        if new:  # Toggle is active = User Specified mode
            if plot1_is_1d and plot1_1d_plot is not None:
                plot1_1d_plot.range_mode = RangeMode.USER_SPECIFIED
            elif map_plot is not None:
                map_plot.range_mode = RangeMode.USER_SPECIFIED
            range1_min_input.disabled = False
            range1_max_input.disabled = False
            # Update toggle label to "User selected"
            range1_mode_toggle.label = "Auto=Off"
        else:  # Toggle is inactive = Dynamic mode
            if plot1_is_1d and plot1_1d_plot is not None:
                plot1_1d_plot.range_mode = RangeMode.DYNAMIC
            elif map_plot is not None:
                map_plot.range_mode = RangeMode.DYNAMIC
            range1_min_input.disabled = True
            range1_max_input.disabled = True
            # Update toggle label to "Dynamic"
            range1_mode_toggle.label = "Auto=On"
            # Recompute range from current data (only for 2D plots, 1D plots don't have color mapper)
            if not plot1_is_1d or plot1_1d_plot is None:
                update_plot1_range_dynamic()
        # Save state immediately for mode changes (important state, not frequent)
        from bokeh.io import curdoc
        def save_state_async():
            plot1_history.save_state("Range mode changed")
            session_history.save_state("Range mode changed")
            undo_redo_callbacks["update"]()
        curdoc().add_next_tick_callback(save_state_async)
    
    # Attach callback to toggle after it's created
    range1_mode_toggle.on_change("active", on_plot1_range_mode_change)

    # Extract the actual input widgets from the section (they're in a row inside the column)
    # range1_section.children structure: [label_div, row(min_input, max_input)]
    # We need to find the row and extract the inputs from it
    for child in range1_section.children:
        if hasattr(child, 'children') and len(child.children) == 2:
            # This is the row containing the two inputs
            range1_min_input = child.children[0]  # First input is min
            range1_max_input = child.children[1]  # Second input is max
            print(f"✅ DEBUG: Extracted range1_min_input and range1_max_input from range1_section")
            break

    # Color scale selector will be created after on_color_scale_change is defined

    # Sync initial state from plot to the extracted inputs
    if range1_min_input is not None and range1_max_input is not None:
        if plot1_is_1d and plot1_1d_plot is not None:
            # For 1D plots, sync from plot1_1d_plot
            sync_plot_to_range_inputs(plot1_1d_plot, range1_min_input, range1_max_input)
        elif map_plot is not None:
            # For 2D plots, sync from map_plot
            sync_plot_to_range_inputs(map_plot, range1_min_input, range1_max_input)

    # Initialize dynamic range if in dynamic mode (ensures range is calculated from actual data)
    # Only for 2D plots (1D plots don't have color mapper to update)
    if not plot1_is_1d and map_plot is not None and map_plot.range_mode == RangeMode.DYNAMIC:
        update_plot1_range_dynamic()

    # Create color scale and palette selectors using SCLib UI
    def on_color_scale_change(attr, old, new):
        """Handle color scale change for Plot1 and Plot1B."""
        # Note: Python treats assignments as creating local variables, so we need to read
        # the current values into local variables first before any assignments.
        try:
            # Read current values into local variables first (before any assignments)
            # This prevents UnboundLocalError when Python sees assignments later
            try:
                current_color_mapper1 = color_mapper1
            except NameError:
                current_color_mapper1 = None
            try:
                current_image_renderer1 = image_renderer1
            except NameError:
                current_image_renderer1 = None
            try:
                current_color_mapper1b = color_mapper1b
            except NameError:
                current_color_mapper1b = None
            try:
                current_image_renderer1b = image_renderer1b
            except NameError:
                current_image_renderer1b = None
            
            # Check if plot and source exist before proceeding
            if plot1 is None or source1 is None:
                # Silently return during initialization
                return
            
            # Get current data from source1
            if 'image' not in source1.data or len(source1.data['image']) == 0:
                # Silently return during initialization (source might not be populated yet)
                return

            current_data = np.array(source1.data["image"][0])
            if current_data.size == 0:
                # Silently return during initialization
                return

            # If color_mapper1 is None, try to get it from the image renderer or create a new one
            if current_color_mapper1 is None and current_image_renderer1 is not None:
                try:
                    # Try to get color_mapper from existing image renderer
                    if hasattr(current_image_renderer1, 'glyph') and hasattr(current_image_renderer1.glyph, 'color_mapper'):
                        current_color_mapper1 = current_image_renderer1.glyph.color_mapper
                        color_mapper1 = current_color_mapper1  # Update outer scope variable
                        print(f"🔍 DEBUG: Retrieved color_mapper1 from image_renderer1")
                except:
                    pass
            
            # If still None, try to create one from plot class or source data
            if current_color_mapper1 is None and map_plot is not None and source1 is not None:
                try:
                    from bokeh.models import LinearColorMapper
                    if 'image' in source1.data and len(source1.data['image']) > 0:
                        current_data = np.array(source1.data["image"][0])
                        if current_data.size > 0:
                            data_min = float(np.percentile(current_data[~np.isnan(current_data)], 1))
                            data_max = float(np.percentile(current_data[~np.isnan(current_data)], 99))
                            current_color_mapper1 = LinearColorMapper(palette=map_plot.palette, low=data_min, high=data_max)
                            color_mapper1 = current_color_mapper1  # Update outer scope variable
                            print(f"🔍 DEBUG: Created new color_mapper1 from source data")
                except Exception as e:
                    print(f"⚠️ Could not create color_mapper1: {e}")
            
            # If color_mapper1 is still None, we can't update it, but we should still try Plot1B if it exists
            if current_color_mapper1 is None and (plot1b is None or current_color_mapper1b is None):
                print(f"⚠️ Cannot update color scale - color_mapper1 is None and no alternative plot available")
                return
            
            # Debug: Log when callback is actually called by user interaction
            print(f"🔍 DEBUG: on_color_scale_change called with new={new}, color_mapper1 exists={current_color_mapper1 is not None}")

            # Use the plot class method to update color scale (it handles range computation internally)
            def preserve_crosshairs_1():
                crosshair_renderers = []
                if rect1.h1line is not None and rect1.h1line in plot1.renderers:
                    crosshair_renderers.append(rect1.h1line)
                if rect1.v1line is not None and rect1.v1line in plot1.renderers:
                    crosshair_renderers.append(rect1.v1line)
                return crosshair_renderers
            
            def restore_crosshairs_1(renderers):
                for renderer in renderers:
                    if renderer in plot1.renderers:
                        plot1.renderers.remove(renderer)
                    plot1.renderers.append(renderer)
                try:
                    draw_cross1()
                except:
                    pass
            
            if current_color_mapper1 is not None and map_plot is not None:
                color_mapper1, image_renderer1 = map_plot.update_color_scale(
                    plot1,
                    current_image_renderer1,
                    current_color_mapper1,
                    source1,
                    use_log=(new == 1),
                    colorbar=colorbar1 if 'colorbar1' in locals() else None,
                    preserve_crosshairs=preserve_crosshairs_1,
                    restore_crosshairs=restore_crosshairs_1,
                )

            # Update Plot1B if it exists
            if plot1b is not None and current_image_renderer1b is not None and current_color_mapper1b is not None and map_plot_b is not None:
                def preserve_crosshairs_1b():
                    crosshair_renderers = []
                    if rect1b is not None:
                        if rect1b.h1line is not None and rect1b.h1line in plot1b.renderers:
                            crosshair_renderers.append(rect1b.h1line)
                        if rect1b.v1line is not None and rect1b.v1line in plot1b.renderers:
                            crosshair_renderers.append(rect1b.v1line)
                    return crosshair_renderers
                
                def restore_crosshairs_1b(renderers):
                    for renderer in renderers:
                        if renderer in plot1b.renderers:
                            plot1b.renderers.remove(renderer)
                        plot1b.renderers.append(renderer)
                    try:
                        draw_cross1b()
                    except:
                        pass
                
                color_mapper1b, image_renderer1b = map_plot_b.update_color_scale(
                    plot1b,
                    current_image_renderer1b,
                    current_color_mapper1b,
                    source1b if 'source1b' in locals() else source1,  # Fallback to source1 if source1b doesn't exist
                    use_log=(new == 1),
                    colorbar=colorbar1b if 'colorbar1b' in locals() else None,
                    preserve_crosshairs=preserve_crosshairs_1b,
                    restore_crosshairs=restore_crosshairs_1b,
                )

            # Redraw crosshairs after color scale change (they might have been affected)
            try:
                draw_cross1()
            except:
                pass

            # Color scale state is already updated by update_color_scale method

            # Save state immediately for color scale changes (important state, not frequent)
            from bokeh.io import curdoc
            def save_state_async():
                plot1_history.save_state("Color scale changed")
                session_history.save_state("Color scale changed")
                undo_redo_callbacks["update"]()
            curdoc().add_next_tick_callback(save_state_async)
        except Exception as e:
            print(f"Error in on_color_scale_change: {e}")
            import traceback
            traceback.print_exc()
    
    # Create color scale selector for Plot1 (no label, inline with toggle)
    # Now that on_color_scale_change is defined, we can create the selector
    plot1_color_scale_selector = create_color_scale_selector(
        active=0,
        width=100,  # Changed from 120 to 100 to match other widgets
        callback=on_color_scale_change
    )
    
    # Add log scale toggle for 1D plots
    plot1_log_scale_toggle = None
    if plot1_is_1d and plot1_1d_plot is not None:
        from bokeh.models import Toggle
        plot1_log_scale_toggle = Toggle(
            label="Log Scale",
            active=False,
            button_type="default",
            width=100
        )
        
        def on_plot1_log_scale_change(attr, old, new):
            """Handle log scale toggle for Plot1 1D plots."""
            if plot1_1d_data_original is None or source1 is None:
                return
            
            if new:  # Log scale enabled
                # Apply symlog transformation
                transformed_data = symlog_transform(plot1_1d_data_original)
                source1.data = {"x": plot1_x_coords, "y": transformed_data}
                plot1.yaxis.axis_label = "Intensity (symlog)"
                print("✅ Plot1 log scale enabled (symlog)")
            else:  # Log scale disabled
                # Use original data
                source1.data = {"x": plot1_x_coords, "y": plot1_1d_data_original}
                plot1.yaxis.axis_label = "Intensity"
                print("✅ Plot1 log scale disabled")
            
            # Update y-axis range to fit the data
            y_data = source1.data["y"]
            if len(y_data) > 0:
                y_min = float(np.nanmin(y_data))
                y_max = float(np.nanmax(y_data))
                # Add some padding
                y_range_padding = (y_max - y_min) * 0.05
                plot1.y_range.start = y_min - y_range_padding
                plot1.y_range.end = y_max + y_range_padding
        
        plot1_log_scale_toggle.on_change("active", on_plot1_log_scale_change)
    
    # Add toggle and color scale selector in a row (no label for color scale)
    # For 1D plots, add log scale toggle instead of color scale selector
    if plot1_is_1d and plot1_1d_plot is not None and plot1_log_scale_toggle is not None:
        range1_section.children.append(row(range1_mode_toggle, plot1_log_scale_toggle, spacing=0))
    else:
        range1_section.children.append(row(range1_mode_toggle, plot1_color_scale_selector, spacing=0))
    
    # Sync color scale selector to plot state
    # For 1D plots, color scale doesn't apply (no color mapper), so skip sync
    if plot1_is_1d and plot1_1d_plot is not None:
        # 1D plots don't have color scale, so we can skip syncing or set a default
        # The color scale selector might not be visible/used for 1D plots anyway
        pass
    elif map_plot is not None:
        sync_plot_to_color_scale_selector(map_plot, plot1_color_scale_selector)

    def on_palette_change(attr, old, new):
        """Handle palette change for all plots."""
        # Note: All color_mapper and image_renderer variables are in the same scope (try block).
        # However, Python treats assignments as creating local variables, so we need to read
        # the current values into local variables first before any assignments.
        try:
            # Read current values into local variables first (before any assignments)
            # This prevents UnboundLocalError when Python sees assignments later
            try:
                current_color_mapper1 = color_mapper1
            except NameError:
                current_color_mapper1 = None
            try:
                current_image_renderer1 = image_renderer1
            except NameError:
                current_image_renderer1 = None
            try:
                current_color_mapper1b = color_mapper1b
            except NameError:
                current_color_mapper1b = None
            try:
                current_image_renderer1b = image_renderer1b
            except NameError:
                current_image_renderer1b = None
            try:
                current_color_mapper2 = color_mapper2
            except NameError:
                current_color_mapper2 = None
            try:
                current_image_renderer2 = image_renderer2
            except NameError:
                current_image_renderer2 = None
            try:
                current_color_mapper2b = color_mapper2b
            except NameError:
                current_color_mapper2b = None
            try:
                current_image_renderer2b = image_renderer2b
            except NameError:
                current_image_renderer2b = None
            try:
                current_color_mapper3 = color_mapper3
            except NameError:
                current_color_mapper3 = None
            try:
                current_image_renderer3 = image_renderer3
            except NameError:
                current_image_renderer3 = None
            
            # Use the new palette value directly from the callback parameter
            # 'new' is the palette name string (e.g., "Viridis256", "Plasma256", etc.)
            new_palette = new
            
            # Debug: Log when callback is actually called by user interaction
            print(f"🔍 DEBUG: on_palette_change called with new_palette={new_palette}")
            
            # Check if any plot is ready (don't return early - try to update all available plots)
            try:
                plot1_ready = plot1 is not None and source1 is not None and current_color_mapper1 is not None
            except NameError:
                plot1_ready = False
            
            if not plot1_ready:
                print(f"⚠️ DEBUG: on_palette_change called but plot1 not ready yet (plot1={plot1 is not None if 'plot1' in locals() else 'N/A'}, source1={source1 is not None if 'source1' in locals() else 'N/A'}, color_mapper1={current_color_mapper1 is not None})")
                # Don't return - continue to try updating other plots that might be ready
            else:
                print(f"🔍 DEBUG: on_palette_change proceeding - color_mapper1 exists={current_color_mapper1 is not None}")

            # Update Plot1 using the plot class method
            def preserve_crosshairs_1():
                crosshair_renderers = []
                if rect1.h1line is not None and rect1.h1line in plot1.renderers:
                    crosshair_renderers.append(rect1.h1line)
                if rect1.v1line is not None and rect1.v1line in plot1.renderers:
                    crosshair_renderers.append(rect1.v1line)
                return crosshair_renderers
            
            def restore_crosshairs_1(renderers):
                for renderer in renderers:
                    if renderer in plot1.renderers:
                        plot1.renderers.remove(renderer)
                    plot1.renderers.append(renderer)
                try:
                    draw_cross1()
                except:
                    pass
            
            # Get colorbar1 if it exists
            colorbar1_obj = None
            try:
                for item in plot1.below:
                    if hasattr(item, 'color_mapper'):
                        colorbar1_obj = item
                        break
            except:
                pass
            
            # If color_mapper1 is None, try to get it from the image renderer or create a new one
            if current_color_mapper1 is None and current_image_renderer1 is not None:
                try:
                    # Try to get color_mapper from existing image renderer
                    if hasattr(current_image_renderer1, 'glyph') and hasattr(current_image_renderer1.glyph, 'color_mapper'):
                        current_color_mapper1 = current_image_renderer1.glyph.color_mapper
                        color_mapper1 = current_color_mapper1  # Update outer scope variable
                        print(f"🔍 DEBUG: Retrieved color_mapper1 from image_renderer1 for palette change")
                except:
                    pass
            
            # If still None, try to create one from plot class or source data
            if current_color_mapper1 is None and map_plot is not None and source1 is not None:
                try:
                    from bokeh.models import LinearColorMapper
                    if 'image' in source1.data and len(source1.data['image']) > 0:
                        current_data = np.array(source1.data["image"][0])
                        if current_data.size > 0:
                            data_min = float(np.percentile(current_data[~np.isnan(current_data)], 1))
                            data_max = float(np.percentile(current_data[~np.isnan(current_data)], 99))
                            current_color_mapper1 = LinearColorMapper(palette=new_palette, low=data_min, high=data_max)
                            color_mapper1 = current_color_mapper1  # Update outer scope variable
                            print(f"🔍 DEBUG: Created new color_mapper1 from source data for palette change")
                except Exception as e:
                    print(f"⚠️ Could not create color_mapper1: {e}")
            
            if current_color_mapper1 is not None and source1 is not None and map_plot is not None:
                try:
                    new_color_mapper1, new_image_renderer1 = map_plot.update_palette(
                        plot1,
                        current_image_renderer1,
                        current_color_mapper1,
                        source1,
                        new_palette,
                        colorbar=colorbar1_obj,
                        preserve_crosshairs=preserve_crosshairs_1,
                        restore_crosshairs=restore_crosshairs_1,
                    )
                    # Update outer scope variables
                    import sys
                    frame = sys._getframe(1)
                    frame.f_locals['color_mapper1'] = new_color_mapper1
                    frame.f_locals['image_renderer1'] = new_image_renderer1
                    # Trigger source change to refresh the plot
                    try:
                        source1.change.emit()
                    except:
                        pass
                    print(f"✅ Updated Plot1 palette to {new_palette} (plot class palette now: {map_plot.palette})")
                except Exception as e:
                    print(f"⚠️ Error updating Plot1 palette: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                missing = []
                if current_color_mapper1 is None:
                    missing.append("color_mapper1")
                if source1 is None:
                    missing.append("source1")
                if map_plot is None:
                    missing.append("map_plot")
                print(f"⚠️ Cannot update Plot1 palette - missing: {', '.join(missing)}")

            # Update Plot1B if it exists
            if plot1b is not None and current_color_mapper1b is not None and map_plot_b is not None:
                def preserve_crosshairs_1b():
                    crosshair_renderers = []
                    if rect1b is not None:
                        if rect1b.h1line is not None and rect1b.h1line in plot1b.renderers:
                            crosshair_renderers.append(rect1b.h1line)
                        if rect1b.v1line is not None and rect1b.v1line in plot1b.renderers:
                            crosshair_renderers.append(rect1b.v1line)
                    return crosshair_renderers
                
                def restore_crosshairs_1b(renderers):
                    for renderer in renderers:
                        if renderer in plot1b.renderers:
                            plot1b.renderers.remove(renderer)
                        plot1b.renderers.append(renderer)
                    try:
                        draw_cross1b()
                    except:
                        pass
                
                # Get colorbar1b if it exists
                colorbar1b_obj = None
                try:
                    for item in plot1b.below:
                        if hasattr(item, 'color_mapper'):
                            colorbar1b_obj = item
                            break
                except:
                    pass
                
                new_color_mapper1b, new_image_renderer1b = map_plot_b.update_palette(
                    plot1b,
                    current_image_renderer1b,
                    current_color_mapper1b,
                    source1b if 'source1b' in locals() else source1,
                    new_palette,
                    colorbar=colorbar1b_obj,
                    preserve_crosshairs=preserve_crosshairs_1b,
                    restore_crosshairs=restore_crosshairs_1b,
                )
                # Update outer scope variables
                import sys
                frame = sys._getframe(1)
                frame.f_locals['color_mapper1b'] = new_color_mapper1b
                frame.f_locals['image_renderer1b'] = new_image_renderer1b
                # Trigger source change to refresh the plot
                try:
                    (source1b if 'source1b' in locals() else source1).change.emit()
                except:
                    pass
                print(f"✅ Updated Plot1B palette to {new_palette}")

            # Update Plot2 if it exists (2D plots only)
            # If color_mapper2 is None, try to get it from the image renderer or create a new one
            if current_color_mapper2 is None and current_image_renderer2 is not None:
                try:
                    # Try to get color_mapper from existing image renderer
                    if hasattr(current_image_renderer2, 'glyph') and hasattr(current_image_renderer2.glyph, 'color_mapper'):
                        current_color_mapper2 = current_image_renderer2.glyph.color_mapper
                        color_mapper2 = current_color_mapper2  # Update outer scope variable
                        print(f"🔍 DEBUG: Retrieved color_mapper2 from image_renderer2 for palette change")
                except:
                    pass
            
            # If still None, try to create one from plot class or source data
            if current_color_mapper2 is None and probe_2d_plot is not None and source2 is not None:
                try:
                    from bokeh.models import LinearColorMapper
                    if 'image' in source2.data and len(source2.data['image']) > 0:
                        current_data = np.array(source2.data["image"][0])
                        if current_data.size > 0:
                            data_min = float(np.percentile(current_data[~np.isnan(current_data)], 1))
                            data_max = float(np.percentile(current_data[~np.isnan(current_data)], 99))
                            current_color_mapper2 = LinearColorMapper(palette=new_palette, low=data_min, high=data_max)
                            color_mapper2 = current_color_mapper2  # Update outer scope variable
                            print(f"🔍 DEBUG: Created new color_mapper2 from source data for palette change")
                except Exception as e:
                    print(f"⚠️ Could not create color_mapper2: {e}")
            
            # Check is_3d_volume variable
            try:
                current_is_3d_volume = is_3d_volume
            except NameError:
                current_is_3d_volume = False
            
            print(f"🔍 DEBUG: Checking Plot2 palette update conditions:")
            print(f"   plot2 is not None: {plot2 is not None}")
            print(f"   not is_3d_volume: {not current_is_3d_volume}")
            print(f"   current_color_mapper2 is not None: {current_color_mapper2 is not None}")
            print(f"   probe_2d_plot is not None: {probe_2d_plot is not None}")
            print(f"   source2 is not None: {source2 is not None}")
            
            if plot2 is not None and not current_is_3d_volume and current_color_mapper2 is not None and probe_2d_plot is not None and source2 is not None:
                # Get colorbar2 if it exists
                colorbar2_obj = None
                try:
                    for item in plot2.below:
                        if hasattr(item, 'color_mapper'):
                            colorbar2_obj = item
                            break
                except:
                    pass
                
                try:
                    print(f"🔍 DEBUG: Calling probe_2d_plot.update_palette() for Plot2...")
                    new_color_mapper2, new_image_renderer2 = probe_2d_plot.update_palette(
                        plot2,
                        current_image_renderer2,
                        current_color_mapper2,
                        source2,
                        new_palette,
                        colorbar=colorbar2_obj,
                    )
                    # Update outer scope variables
                    import sys
                    frame = sys._getframe(1)
                    frame.f_locals['color_mapper2'] = new_color_mapper2
                    frame.f_locals['image_renderer2'] = new_image_renderer2
                    # Trigger source change to refresh the plot
                    try:
                        source2.change.emit()
                    except:
                        pass
                    print(f"✅ Updated Plot2 palette to {new_palette} (plot class palette now: {probe_2d_plot.palette})")
                    print(f"🔍 DEBUG: Plot2 color_mapper2.palette = {new_color_mapper2.palette}")
                except Exception as e:
                    print(f"⚠️ Error updating Plot2 palette: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                missing = []
                if plot2 is None:
                    missing.append("plot2")
                if is_3d_volume:
                    missing.append("(is_3d_volume)")
                if current_color_mapper2 is None:
                    missing.append("color_mapper2")
                if probe_2d_plot is None:
                    missing.append("probe_2d_plot")
                if source2 is None:
                    missing.append("source2")
                print(f"⚠️ Cannot update Plot2 palette - missing: {', '.join(missing)}")

            # Check plot2b_is_2d variable
            try:
                current_plot2b_is_2d = plot2b_is_2d
            except NameError:
                current_plot2b_is_2d = False
            
            # Update Plot2B if it exists (2D plots only)
            if plot2b is not None and current_plot2b_is_2d and current_color_mapper2b is not None and probe_2d_plot_b is not None:
                # Get colorbar2b if it exists
                colorbar2b_obj = None
                try:
                    for item in plot2b.below:
                        if hasattr(item, 'color_mapper'):
                            colorbar2b_obj = item
                            break
                except:
                    pass
                
                try:
                    new_color_mapper2b, new_image_renderer2b = probe_2d_plot_b.update_palette(
                        plot2b,
                        current_image_renderer2b,
                        current_color_mapper2b,
                        source2b,
                        new_palette,
                        colorbar=colorbar2b_obj,
                    )
                    # Update outer scope variables
                    import sys
                    frame = sys._getframe(1)
                    frame.f_locals['color_mapper2b'] = new_color_mapper2b
                    frame.f_locals['image_renderer2b'] = new_image_renderer2b
                    # Trigger source change to refresh the plot
                    try:
                        source2b.change.emit()
                    except:
                        pass
                    print(f"✅ Updated Plot2B palette to {new_palette} (plot class palette now: {probe_2d_plot_b.palette})")
                except Exception as e:
                    print(f"⚠️ Error updating Plot2B palette: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                missing = []
                if plot2b is None:
                    missing.append("plot2b")
                if not plot2b_is_2d:
                    missing.append("(not 2D)")
                if current_color_mapper2b is None:
                    missing.append("color_mapper2b")
                if probe_2d_plot_b is None:
                    missing.append("probe_2d_plot_b")
                print(f"⚠️ Cannot update Plot2B palette - missing: {', '.join(missing)}")

            # Update Plot3 if it exists
            try:
                current_plot3 = plot3
            except NameError:
                current_plot3 = None
            try:
                current_source3 = source3
            except NameError:
                current_source3 = None
            
            if current_plot3 is not None and current_color_mapper3 is not None and map_plot is not None:
                # Get colorbar3 if it exists
                colorbar3_obj = None
                try:
                    for item in current_plot3.below:
                        if hasattr(item, 'color_mapper'):
                            colorbar3_obj = item
                            break
                except:
                    pass
                
                try:
                    new_color_mapper3, new_image_renderer3 = map_plot.update_palette(
                        current_plot3,
                        current_image_renderer3,
                        current_color_mapper3,
                        current_source3,
                        new_palette,
                        colorbar=colorbar3_obj,
                    )
                    # Update outer scope variables
                    import sys
                    frame = sys._getframe(1)
                    frame.f_locals['color_mapper3'] = new_color_mapper3
                    frame.f_locals['image_renderer3'] = new_image_renderer3
                    # Trigger source change to refresh the plot
                    try:
                        current_source3.change.emit()
                    except:
                        pass
                    print(f"✅ Updated Plot3 palette to {new_palette}")
                except Exception as e:
                    print(f"⚠️ Error updating Plot3 palette: {e}")
                    import traceback
                    traceback.print_exc()

            # Redraw crosshairs after palette change (they might have been affected)
            try:
                draw_cross1()
            except:
                pass

            # Save state asynchronously
            from bokeh.io import curdoc
            def save_state_async():
                plot1_history.save_state("Palette changed")
                session_history.save_state("Palette changed")
                undo_redo_callbacks["update"]()
            curdoc().add_next_tick_callback(save_state_async)
        except Exception as e:
            print(f"Error in on_palette_change: {e}")
            import traceback
            traceback.print_exc()

    # Create Plot1 color scale section (replaces old "Map Color Scale")
    # Color scale selector is now inline with range toggle, no separate section needed
    # plot1_color_scale_section is created above when adding to range1_section

    palette_section = create_palette_section(
        label="Color Palette:",
        value="Viridis256",
        width=200,
        callback=on_palette_change
    )
    
    # Extract the palette selector from palette_section for syncing
    # palette_section is a column with [label_div, selector] as children
    palette_selector = palette_section.children[1] if len(palette_section.children) > 1 else None
    if palette_selector is not None:
        if plot1_is_1d and plot1_1d_plot is not None:
            # For 1D plots, sync to plot1_1d_plot (though 1D plots may not use palette)
            sync_plot_to_palette_selector(plot1_1d_plot, palette_selector)
        elif map_plot is not None:
            sync_plot_to_palette_selector(map_plot, palette_selector)

    # Create Probe Scale control for Plot2 and Plot2b
    # Initialize base dimensions if not already set (fallback for edge cases)
    try:
        _ = plot2_base_area_width  # Check if variable exists
    except NameError:
        try:
            if plot2 is not None:
                plot2_base_area_width = plot2.width - colorbar_width if hasattr(plot2, 'width') else plot_width_with_colorbar - colorbar_width
                plot2_base_area_height = plot2.height if hasattr(plot2, 'height') else initial_height
            else:
                plot2_base_area_width = plot_width_with_colorbar - colorbar_width
                plot2_base_area_height = initial_height
        except:
            plot2_base_area_width = plot_width_with_colorbar - colorbar_width
            plot2_base_area_height = initial_height
    
    try:
        _ = plot2b_base_area_width  # Check if variable exists
    except NameError:
        try:
            if plot2b is not None:
                plot2b_base_area_width = plot2b.width - colorbar_width if hasattr(plot2b, 'width') else plot_width_with_colorbar - colorbar_width
                plot2b_base_area_height = plot2b.height if hasattr(plot2b, 'height') else initial_height
            else:
                plot2b_base_area_width = plot_width_with_colorbar - colorbar_width
                plot2b_base_area_height = initial_height
        except:
            plot2b_base_area_width = plot_width_with_colorbar - colorbar_width
            plot2b_base_area_height = initial_height
    
    # Default probe scale is 100% (1.0)
    probe_scale_value = 100.0
    
    def on_probe_scale_change(attr, old, new):
        """Handle Probe Scale change - scales Plot2 and Plot2b while preserving aspect ratio."""
        try:
            scale_percent = float(new) if new else 100.0
            scale_factor = scale_percent / 100.0
            
            # Scale Plot2
            if plot2 is not None:
                try:
                    # Get current dimensions from the plot (which may have been customized)
                    # This ensures probe scale works from the current custom size, not just the initial size
                    current_width = plot2.width
                    current_height = plot2.height
                    # Subtract colorbar width if present
                    if not is_3d_volume and color_mapper2 is not None:
                        current_width = current_width - colorbar_width
                    
                    # Use current dimensions as base (they may have been customized)
                    # If probe scale is being used for the first time or after a custom size change,
                    # use the current plot dimensions as the base
                    base_width = current_width
                    base_height = current_height
                    
                    # Check if we should use stored base dimensions (for consistent scaling)
                    # Only use stored base if current dimensions match them (within tolerance)
                    try:
                        if 'plot2_base_area_width' in locals() and 'plot2_base_area_height' in locals():
                            # If current dimensions are close to stored base, use stored base for consistent scaling
                            if abs(plot2_base_area_width - current_width) <= 1 and abs(plot2_base_area_height - current_height) <= 1:
                                base_width = plot2_base_area_width
                                base_height = plot2_base_area_height
                            else:
                                # Current dimensions are different (user customized) - update stored base to current
                                plot2_base_area_width = current_width
                                plot2_base_area_height = current_height
                    except:
                        # If base dimensions don't exist, use current dimensions and store them
                        try:
                            plot2_base_area_width = current_width
                            plot2_base_area_height = current_height
                        except:
                            pass
                    
                    # Calculate new dimensions preserving aspect ratio
                    new_width = int(base_width * scale_factor)
                    new_height = int(base_height * scale_factor)
                    
                    # Update plot dimensions (add colorbar width back)
                    plot2.width = new_width + colorbar_width if not is_3d_volume and color_mapper2 is not None else new_width
                    plot2.height = new_height
                    
                    # Update custom width/height inputs to reflect the new scaled dimensions
                    try:
                        if 'plot2_custom_width_input' in locals() and plot2_custom_width_input is not None:
                            plot2_custom_width_input.value = str(new_width)
                        if 'plot2_custom_height_input' in locals() and plot2_custom_height_input is not None:
                            plot2_custom_height_input.value = str(new_height)
                    except:
                        pass
                    
                    print(f"🔍 DEBUG: Plot2 scaled to {new_width + (colorbar_width if not is_3d_volume and color_mapper2 is not None else 0)}x{new_height} (scale={scale_percent}%)")
                except Exception as e:
                    print(f"⚠️ WARNING: Error scaling Plot2: {e}")
            
            # Scale Plot2b
            if plot2b is not None:
                try:
                    # Get current dimensions from the plot (which may have been customized)
                    current_width = plot2b.width
                    current_height = plot2b.height
                    # Subtract colorbar width if present
                    if plot2b_is_2d and color_mapper2b is not None:
                        current_width = current_width - colorbar_width
                    
                    # Use current dimensions as base (they may have been customized)
                    base_width = current_width
                    base_height = current_height
                    
                    # Check if we should use stored base dimensions (for consistent scaling)
                    try:
                        if 'plot2b_base_area_width' in locals() and 'plot2b_base_area_height' in locals():
                            # If current dimensions are close to stored base, use stored base for consistent scaling
                            if abs(plot2b_base_area_width - current_width) <= 1 and abs(plot2b_base_area_height - current_height) <= 1:
                                base_width = plot2b_base_area_width
                                base_height = plot2b_base_area_height
                            else:
                                # Current dimensions are different (user customized) - update stored base to current
                                plot2b_base_area_width = current_width
                                plot2b_base_area_height = current_height
                    except:
                        # If base dimensions don't exist, use current dimensions and store them
                        try:
                            plot2b_base_area_width = current_width
                            plot2b_base_area_height = current_height
                        except:
                            pass
                    
                    # Calculate new dimensions preserving aspect ratio
                    new_width = int(base_width * scale_factor)
                    new_height = int(base_height * scale_factor)
                    
                    # Update plot dimensions (add colorbar width back)
                    plot2b.width = new_width + colorbar_width if plot2b_is_2d and color_mapper2b is not None else new_width
                    plot2b.height = new_height
                    
                    # Update custom width/height inputs to reflect the new scaled dimensions
                    try:
                        if 'plot2b_custom_width_input' in locals() and plot2b_custom_width_input is not None:
                            plot2b_custom_width_input.value = str(new_width)
                        if 'plot2b_custom_height_input' in locals() and plot2b_custom_height_input is not None:
                            plot2b_custom_height_input.value = str(new_height)
                    except:
                        pass
                    
                    print(f"🔍 DEBUG: Plot2b scaled to {new_width + (colorbar_width if plot2b_is_2d and color_mapper2b is not None else 0)}x{new_height} (scale={scale_percent}%)")
                except Exception as e:
                    print(f"⚠️ WARNING: Error scaling Plot2b: {e}")
            
            # Save probe scale to session metadata immediately (for undo/redo and session save)
            try:
                session.metadata['probe_scale'] = scale_percent
            except:
                pass
            
            # Save state asynchronously
            from bokeh.io import curdoc
            def save_state_async():
                if 'plot2_history' in locals() and plot2_history is not None:
                    plot2_history.save_state("Probe scale changed")
                if 'session_history' in locals() and session_history is not None:
                    session_history.save_state("Probe scale changed")
                if 'undo_redo_callbacks' in locals() and undo_redo_callbacks:
                    undo_redo_callbacks["update"]()
            curdoc().add_next_tick_callback(save_state_async)
        except Exception as e:
            print(f"⚠️ ERROR in on_probe_scale_change(): {e}")
            import traceback
            traceback.print_exc()
    
    # Create Probe Scale text input
    from SCLib_Dashboards.SCDashUI_base_components import create_text_input
    probe_scale_input = create_text_input(
        title="Probe Scale (%):",
        value=str(probe_scale_value),
        width=100,
        callback=on_probe_scale_change
    )
    
    # Create Probe Scale section
    probe_scale_section = column(
        create_label_div("Probe Scale:", width=200),
        probe_scale_input,
    )

    # Create color scale handlers for Plot2, Plot2B, and Plot3
    def on_plot2_color_scale_change(attr, old, new):
        """Handle Plot2 color scale change (Linear vs Log) for 2D and 1D plots."""
        # Read current values into local variables first (before any assignments)
        # This prevents UnboundLocalError when Python sees assignments later
        try:
            print(f"🔍 DEBUG: Plot2 color scale change called: new={new} (0=Linear, 1=Log)")
            try:
                current_color_mapper2 = color_mapper2
            except NameError:
                current_color_mapper2 = None
            try:
                current_image_renderer2 = image_renderer2
            except NameError:
                current_image_renderer2 = None
            try:
                current_probe_2d_plot = probe_2d_plot
            except NameError:
                current_probe_2d_plot = None
            try:
                current_colorbar2 = colorbar2
            except NameError:
                current_colorbar2 = None
            
            # Check if Plot2 is initialized
            try:
                current_plot2 = plot2
            except NameError:
                current_plot2 = None
            try:
                current_is_3d_volume = is_3d_volume
            except NameError:
                current_is_3d_volume = False
            
            if current_plot2 is None or current_color_mapper2 is None:
                print(f"🔍 DEBUG: Plot2 not ready: plot2={current_plot2 is None}, color_mapper2={current_color_mapper2 is None}")
                return

            # Handle Plot2 (2D plots only - 4D volumes)
            if not current_is_3d_volume and current_color_mapper2 is not None and current_probe_2d_plot is not None:
                print(f"🔍 DEBUG: Plot2 color scale change: new={new} (0=Linear, 1=Log), use_log={new == 1}")
                # Use the plot class method to update color scale (it handles range computation internally)
                # Note: Plot2 doesn't have crosshairs like Plot1, so we don't need preserve/restore functions
                def preserve_crosshairs_2():
                    return []  # Plot2 doesn't have crosshairs
                
                def restore_crosshairs_2(renderers):
                    pass  # Plot2 doesn't have crosshairs
                
                try:
                    new_color_mapper2, new_image_renderer2 = current_probe_2d_plot.update_color_scale(
                        current_plot2,
                        current_image_renderer2,
                        current_color_mapper2,
                        source2,
                        use_log=(new == 1),
                        colorbar=current_colorbar2,
                        preserve_crosshairs=preserve_crosshairs_2,
                        restore_crosshairs=restore_crosshairs_2,
                    )
                    # Update outer scope variables using globals() or exec
                    # Since we're in a nested function, we need to update the outer scope
                    import sys
                    frame = sys._getframe(1)
                    frame.f_locals['color_mapper2'] = new_color_mapper2
                    frame.f_locals['image_renderer2'] = new_image_renderer2
                    # Also try to trigger a source change to refresh the plot
                    try:
                        source2.change.emit()
                    except:
                        pass
                    print(f"✅ DEBUG: Plot2 color scale updated successfully")
                except Exception as e:
                    print(f"❌ ERROR: Failed to update Plot2 color scale: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                print(f"🔍 DEBUG: Plot2 color scale update skipped - conditions check:")
                print(f"  is_3d_volume={current_is_3d_volume}")
                print(f"  color_mapper2={current_color_mapper2 is not None}")
                print(f"  probe_2d_plot={current_probe_2d_plot is not None}")
                if current_is_3d_volume:
                    print(f"🔍 DEBUG: Plot2 is 3D volume, skipping 2D color scale update")
                elif current_color_mapper2 is None:
                    print(f"🔍 DEBUG: Plot2 color_mapper2 is None, skipping update")
                elif current_probe_2d_plot is None:
                    print(f"🔍 DEBUG: Plot2 probe_2d_plot is None, skipping update")

            # Handle 1D plots (3D volumes) - apply log scale to y-axis
            if is_3d_volume and plot2 is not None and source2 is not None:
                if new == 1:  # Log scale selected
                    # Set y-axis to log scale
                    plot2.y_scale = LogScale()
                    # Ensure y-axis range is positive for log scale
                    if 'y' in source2.data and len(source2.data['y']) > 0:
                        y_data = np.array(source2.data['y'])
                        positive_y = y_data[y_data > 0]
                        if positive_y.size > 0:
                            y_min = max(np.min(positive_y), 0.001)
                            y_max = np.max(positive_y)
                            plot2.y_range.start = y_min
                            plot2.y_range.end = y_max
                        else:
                            # No positive values, set safe default
                            plot2.y_range.start = 0.001
                            plot2.y_range.end = 1.0
                else:  # Linear scale selected
                    plot2.y_scale = LinearScale()
                    # Reset y-range to include all data (including negatives/zeros)
                    if 'y' in source2.data and len(source2.data['y']) > 0:
                        y_data = np.array(source2.data['y'])
                        plot2.y_range.start = float(np.min(y_data))
                        plot2.y_range.end = float(np.max(y_data))

                # Force plot update for 1D plots by updating data source
                if 'x' in source2.data and 'y' in source2.data:
                    source2.data = {
                        'x': source2.data['x'],
                        'y': source2.data['y']
                    }
            
            # Save state immediately for color scale changes (important state, not frequent)
            from bokeh.io import curdoc
            def save_state_async():
                plot1_history.save_state("Plot2 color scale changed")
                session_history.save_state("Plot2 color scale changed")
                undo_redo_callbacks["update"]()
            curdoc().add_next_tick_callback(save_state_async)
        except Exception as e:
            print(f"Error in on_plot2_color_scale_change: {e}")
            import traceback
            traceback.print_exc()

    def on_plot2b_color_scale_change(attr, old, new):
        """Handle Plot2B color scale change (Linear vs Log) for 2D and 1D plots."""
        # Read current values into local variables first (before any assignments)
        # This prevents UnboundLocalError when Python sees assignments later
        try:
            print(f"🔍 DEBUG: Plot2B color scale change called: new={new} (0=Linear, 1=Log)")
            try:
                current_color_mapper2b = color_mapper2b
            except NameError:
                current_color_mapper2b = None
            try:
                current_image_renderer2b = image_renderer2b
            except NameError:
                current_image_renderer2b = None
            try:
                current_probe_2d_plot_b = probe_2d_plot_b
            except NameError:
                current_probe_2d_plot_b = None
            try:
                current_colorbar2b = colorbar2b
            except NameError:
                current_colorbar2b = None
            try:
                current_plot2b_is_2d = plot2b_is_2d
            except NameError:
                current_plot2b_is_2d = False
            
            # Silently return if Plot2B is not initialized yet
            if plot2b is None or current_color_mapper2b is None:
                return

            # Handle Plot2B (2D plots only)
            if current_plot2b_is_2d and current_color_mapper2b is not None and current_probe_2d_plot_b is not None:
                print(f"🔍 DEBUG: Plot2B color scale change: new={new} (0=Linear, 1=Log), use_log={new == 1}")
                # Use the plot class method to update color scale (it handles range computation internally)
                # Note: Plot2B doesn't have crosshairs like Plot1, so we don't need preserve/restore functions
                def preserve_crosshairs_2b():
                    return []  # Plot2B doesn't have crosshairs
                
                def restore_crosshairs_2b(renderers):
                    pass  # Plot2B doesn't have crosshairs
                
                try:
                    new_color_mapper2b, new_image_renderer2b = current_probe_2d_plot_b.update_color_scale(
                        plot2b,
                        current_image_renderer2b,
                        current_color_mapper2b,
                        source2b,
                        use_log=(new == 1),
                        colorbar=current_colorbar2b,
                        preserve_crosshairs=preserve_crosshairs_2b,
                        restore_crosshairs=restore_crosshairs_2b,
                    )
                    # Update outer scope variables
                    import sys
                    frame = sys._getframe(1)
                    frame.f_locals['color_mapper2b'] = new_color_mapper2b
                    frame.f_locals['image_renderer2b'] = new_image_renderer2b
                    # Trigger source change to refresh the plot
                    try:
                        source2b.change.emit()
                    except:
                        pass
                    print(f"✅ DEBUG: Plot2B color scale updated successfully")
                except Exception as e:
                    print(f"❌ ERROR: Failed to update Plot2B color scale: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                if not current_plot2b_is_2d:
                    print(f"🔍 DEBUG: Plot2B is not 2D, skipping 2D color scale update")
                elif current_color_mapper2b is None:
                    print(f"🔍 DEBUG: Plot2B color_mapper2b is None, skipping update")
                elif current_probe_2d_plot_b is None:
                    print(f"🔍 DEBUG: Plot2B probe_2d_plot_b is None, skipping update")

            # Handle 1D plots (3D volumes) - apply log scale to y-axis
            if plot2b is not None and not plot2b_is_2d:
                if new == 1:  # Log scale
                    plot2b.y_scale = LogScale()
                    if 'y' in source2b.data and len(source2b.data['y']) > 0:
                        y_data_b = np.array(source2b.data['y'])
                        positive_y_b = y_data_b[y_data_b > 0]
                        if positive_y_b.size > 0:
                            y_min_b = max(np.min(positive_y_b), 0.001)
                            y_max_b = np.max(positive_y_b)
                            plot2b.y_range.start = y_min_b
                            plot2b.y_range.end = y_max_b
                        else:
                            plot2b.y_range.start = 0.001
                            plot2b.y_range.end = 1.0
                else:  # Linear scale
                    plot2b.y_scale = LinearScale()
                    if 'y' in source2b.data and len(source2b.data['y']) > 0:
                        y_data_b = np.array(source2b.data['y'])
                        plot2b.y_range.start = float(np.min(y_data_b))
                        plot2b.y_range.end = float(np.max(y_data_b))
                # Force Plot2B update by updating data source
                if 'source2b' in locals() and source2b is not None and 'x' in source2b.data and 'y' in source2b.data:
                    source2b.data = {
                        'x': source2b.data['x'],
                        'y': source2b.data['y']
                    }
            
            # Save state immediately for color scale changes (important state, not frequent)
            from bokeh.io import curdoc
            def save_state_async():
                plot1_history.save_state("Plot2B color scale changed")
                session_history.save_state("Plot2B color scale changed")
                undo_redo_callbacks["update"]()
            curdoc().add_next_tick_callback(save_state_async)
        except Exception as e:
            print(f"Error in on_plot2b_color_scale_change: {e}")
            import traceback
            traceback.print_exc()

    def on_plot3_color_scale_change(attr, old, new):
        """Handle Plot3 color scale change (Linear vs Log)."""
        # Read current values into local variables first (before any assignments)
        # This prevents UnboundLocalError when Python sees assignments later
        try:
            print(f"🔍 DEBUG: Plot3 color scale change called: new={new} (0=Linear, 1=Log)")
            try:
                current_color_mapper3 = color_mapper3
            except NameError:
                current_color_mapper3 = None
            try:
                current_image_renderer3 = image_renderer3
            except NameError:
                current_image_renderer3 = None
            try:
                current_plot3 = plot3
            except NameError:
                current_plot3 = None
            try:
                current_source3 = source3
            except NameError:
                current_source3 = None
            
            # If color_mapper3 is None but image_renderer3 exists, try to get it from the renderer
            if current_color_mapper3 is None and current_image_renderer3 is not None:
                print(f"🔍 DEBUG: Plot3 color_mapper3 is None, trying to recover from image_renderer3...")
                try:
                    if hasattr(current_image_renderer3, 'glyph') and hasattr(current_image_renderer3.glyph, 'color_mapper'):
                        current_color_mapper3 = current_image_renderer3.glyph.color_mapper
                        color_mapper3 = current_color_mapper3  # Update outer scope variable
                        print(f"✅ DEBUG: Retrieved color_mapper3 from image_renderer3: {type(current_color_mapper3).__name__}")
                    else:
                        print(f"🔍 DEBUG: image_renderer3.glyph doesn't have color_mapper attribute")
                except Exception as e:
                    print(f"🔍 DEBUG: Failed to recover color_mapper3 from renderer: {e}")
            
            # Check if Plot3 is initialized
            if current_plot3 is None or current_color_mapper3 is None:
                print(f"🔍 DEBUG: Plot3 not initialized: plot3={current_plot3 is None}, color_mapper3={current_color_mapper3 is None}, image_renderer3={current_image_renderer3 is None}")
                return
            
            # Get current data from source3
            if current_source3 is None or 'image' not in current_source3.data or len(current_source3.data['image']) == 0:
                # Silently return during initialization
                print(f"🔍 DEBUG: Plot3 source3 not ready: source3={current_source3 is None}")
                return

            current_data = np.array(current_source3.data["image"][0])
            if current_data.size == 0:
                # Silently return during initialization
                return

            # For log scale, we need to handle zeros/negatives
            if new == 1:  # Log scale selected
                # Filter out zeros and negatives, use a small epsilon for minimum
                positive_data = current_data[current_data > 0]
                if positive_data.size == 0:
                    print("Warning: No positive values for log scale in Plot3, using linear scale")
                    new_cls = LinearColorMapper
                    # Use current ranges or defaults
                    low3 = current_color_mapper3.low if current_color_mapper3.low > 0 else 0.001
                    high3 = current_color_mapper3.high if current_color_mapper3.high > 0 else 1.0
                else:
                    new_cls = LogColorMapper
                    # Use current ranges if they're positive, otherwise use data-based ranges
                    low3 = current_color_mapper3.low if current_color_mapper3.low > 0 else max(np.min(positive_data), 0.001)
                    high3 = current_color_mapper3.high if current_color_mapper3.high > 0 else np.max(positive_data)
            else:  # Linear scale
                new_cls = LinearColorMapper
                # Preserve current ranges
                low3 = current_color_mapper3.low
                high3 = current_color_mapper3.high

            # Get colorbar3 if it exists
            colorbar3_obj = None
            try:
                for item in current_plot3.below:
                    if hasattr(item, 'color_mapper'):
                        colorbar3_obj = item
                        break
            except:
                pass
            
            # Use map_plot.update_color_scale() method (same as Plot1) to preserve palette
            if map_plot is not None:
                print(f"🔍 DEBUG: Using map_plot.update_color_scale() for Plot3: use_log={new == 1}")
                # Plot3 doesn't have crosshairs, so we don't need preserve/restore functions
                def preserve_crosshairs_3():
                    return []  # Plot3 doesn't have crosshairs
                
                def restore_crosshairs_3(renderers):
                    pass  # Plot3 doesn't have crosshairs
                
                try:
                    new_color_mapper3, new_image_renderer3 = map_plot.update_color_scale(
                        current_plot3,
                        current_image_renderer3,
                        current_color_mapper3,
                        current_source3,
                        use_log=(new == 1),
                        colorbar=colorbar3_obj,
                        preserve_crosshairs=preserve_crosshairs_3,
                        restore_crosshairs=restore_crosshairs_3,
                    )
                    # Update outer scope variables
                    import sys
                    frame = sys._getframe(1)
                    frame.f_locals['color_mapper3'] = new_color_mapper3
                    frame.f_locals['image_renderer3'] = new_image_renderer3
                    # Trigger source change to refresh the plot
                    try:
                        current_source3.change.emit()
                    except:
                        pass
                    print(f"✅ DEBUG: Plot3 color scale updated successfully using map_plot.update_color_scale()")
                except Exception as e:
                    print(f"❌ ERROR: Failed to update Plot3 color scale: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                print(f"⚠️ WARNING: map_plot is None, cannot use update_color_scale() for Plot3")
            
            # Save state immediately for color scale changes (important state, not frequent)
            from bokeh.io import curdoc
            def save_state_async():
                plot1_history.save_state("Plot3 color scale changed")
                session_history.save_state("Plot3 color scale changed")
                undo_redo_callbacks["update"]()
            curdoc().add_next_tick_callback(save_state_async)
        except Exception as e:
            print(f"❌ ERROR: Error in on_plot3_color_scale_change: {e}")
            import traceback
            traceback.print_exc()

    # Create color scale selectors for Plot2, Plot2B, and Plot3
    # Color scale selector is now inline with range toggle, no separate section needed
    # plot2_color_scale_selector is created above when adding to range2_section

    # Color scale selector is now inline with range toggle, no separate section needed
    # plot2b_color_scale_selector is created above when adding to range2b_section
    plot2b_color_scale_section = None

    # Color scale selector is now inline with range toggle, no separate section needed
    # plot3_color_scale_selector is created above when adding to range3_section

    # Create plot shape controls for Plot1
    def on_plot1_shape_change(attr, old, new):
        """Handle Plot1 shape mode change."""
        # For 1D plots, shape mode doesn't apply, so skip
        if plot1_is_1d:
            return
        
        if map_plot is None:
            return
            
        if new == 0:  # Square
            map_plot.plot_shape_mode = PlotShapeMode.SQUARE
        elif new == 1:  # Custom
            map_plot.plot_shape_mode = PlotShapeMode.CUSTOM
        elif new == 2:  # Aspect Ratio
            map_plot.plot_shape_mode = PlotShapeMode.ASPECT_RATIO
        # Update plot dimensions
        width, height = map_plot.calculate_plot_dimensions()
        # Add colorbar width to total width (Plot1 and Plot3 both have colorbars)
        width_with_colorbar = width + colorbar_width
        plot1.width = width_with_colorbar
        plot1.height = height
        # Plot3 should match Plot1 dimensions
        if plot3 is not None:
            plot3.width = width_with_colorbar
            plot3.height = height
        # Also update Plot1B if it exists
        if plot1b is not None and map_plot_b is not None:
            map_plot_b.plot_shape_mode = map_plot.plot_shape_mode
            map_plot_b.plot_width = map_plot.plot_width
            map_plot_b.plot_height = map_plot.plot_height
            map_plot_b.plot_scale = map_plot.plot_scale
            map_plot_b.plot_min_size = map_plot.plot_min_size
            map_plot_b.plot_max_size = map_plot.plot_max_size
            width_b, height_b = map_plot_b.calculate_plot_dimensions()
            plot1b.width = width_b
            plot1b.height = height_b
        # Save state asynchronously
        from bokeh.io import curdoc
        def save_state_async():
            plot1_history.save_state("Plot shape changed")
            session_history.save_state("Plot shape changed")
            undo_redo_callbacks["update"]()
        curdoc().add_next_tick_callback(save_state_async)

    def on_plot1_custom_width_change(attr, old, new):
        """Handle Plot1 custom width change."""
        # For 1D plots, shape controls don't apply
        if plot1_is_1d or map_plot is None:
            return
        try:
            map_plot.plot_width = int(float(new))
            width, height = map_plot.calculate_plot_dimensions()
            # Add colorbar width to total width (Plot1 and Plot3 both have colorbars)
            width_with_colorbar = width + colorbar_width
            plot1.width = width_with_colorbar
            plot1.height = height
            # Plot3 should match Plot1 dimensions
            if plot3 is not None:
                plot3.width = width_with_colorbar
                plot3.height = height
            # Also update Plot1B if it exists
            if plot1b is not None and map_plot_b is not None:
                map_plot_b.plot_width = map_plot.plot_width
                width_b, height_b = map_plot_b.calculate_plot_dimensions()
                plot1b.width = width_b
                plot1b.height = height_b
            # Save state asynchronously
            from bokeh.io import curdoc
            def save_state_async():
                plot1_history.save_state("Plot width changed")
                session_history.save_state("Plot width changed")
                undo_redo_callbacks["update"]()
            curdoc().add_next_tick_callback(save_state_async)
        except:
            pass

    def on_plot1_custom_height_change(attr, old, new):
        """Handle Plot1 custom height change."""
        # For 1D plots, shape controls don't apply
        if plot1_is_1d or map_plot is None:
            return
        try:
            map_plot.plot_height = int(float(new))
            width, height = map_plot.calculate_plot_dimensions()
            # Add colorbar width to total width (Plot1 and Plot3 both have colorbars)
            width_with_colorbar = width + colorbar_width
            plot1.width = width_with_colorbar
            plot1.height = height
            # Plot3 should match Plot1 dimensions
            if plot3 is not None:
                plot3.width = width_with_colorbar
                plot3.height = height
            # Also update Plot1B if it exists
            if plot1b is not None and map_plot_b is not None:
                map_plot_b.plot_height = map_plot.plot_height
                width_b, height_b = map_plot_b.calculate_plot_dimensions()
                plot1b.width = width_b
                plot1b.height = height_b
            # Save state asynchronously
            from bokeh.io import curdoc
            def save_state_async():
                plot1_history.save_state("Plot height changed")
                session_history.save_state("Plot height changed")
                undo_redo_callbacks["update"]()
            curdoc().add_next_tick_callback(save_state_async)
        except:
            pass

    def on_plot1_scale_change(attr, old, new):
        """Handle Plot1 scale change."""
        # For 1D plots, shape controls don't apply
        if plot1_is_1d or map_plot is None:
            return
        try:
            map_plot.plot_scale = float(new)
            width, height = map_plot.calculate_plot_dimensions()
            # Add colorbar width to total width (Plot1 and Plot3 both have colorbars)
            width_with_colorbar = width + colorbar_width
            plot1.width = width_with_colorbar
            plot1.height = height
            # Plot3 should match Plot1 dimensions
            if plot3 is not None:
                plot3.width = width_with_colorbar
                plot3.height = height
            # Also update Plot1B if it exists
            if plot1b is not None and map_plot_b is not None:
                map_plot_b.plot_scale = map_plot.plot_scale
                width_b, height_b = map_plot_b.calculate_plot_dimensions()
                plot1b.width = width_b
                plot1b.height = height_b
            # Save state asynchronously
            from bokeh.io import curdoc
            def save_state_async():
                plot1_history.save_state("Plot scale changed")
                session_history.save_state("Plot scale changed")
                undo_redo_callbacks["update"]()
            curdoc().add_next_tick_callback(save_state_async)
        except:
            pass

    def on_plot1_min_size_change(attr, old, new):
        """Handle Plot1 min size change."""
        # For 1D plots, shape controls don't apply
        if plot1_is_1d or map_plot is None:
            return
        try:
            map_plot.plot_min_size = int(float(new))
            width, height = map_plot.calculate_plot_dimensions()
            # Add colorbar width to total width (Plot1 and Plot3 both have colorbars)
            width_with_colorbar = width + colorbar_width
            plot1.width = width_with_colorbar
            plot1.height = height
            # Plot3 should match Plot1 dimensions
            if plot3 is not None:
                plot3.width = width_with_colorbar
                plot3.height = height
            # Also update Plot1B if it exists
            if plot1b is not None and map_plot_b is not None:
                map_plot_b.plot_min_size = map_plot.plot_min_size
                width_b, height_b = map_plot_b.calculate_plot_dimensions()
                plot1b.width = width_b
                plot1b.height = height_b
            # Save state asynchronously
            from bokeh.io import curdoc
            def save_state_async():
                plot1_history.save_state("Plot min size changed")
                session_history.save_state("Plot min size changed")
                undo_redo_callbacks["update"]()
            curdoc().add_next_tick_callback(save_state_async)
        except:
            pass

    def on_plot1_max_size_change(attr, old, new):
        """Handle Plot1 max size change."""
        # For 1D plots, shape controls don't apply
        if plot1_is_1d or map_plot is None:
            return
        try:
            map_plot.plot_max_size = int(float(new))
            width, height = map_plot.calculate_plot_dimensions()
            # Add colorbar width to total width (Plot1 and Plot3 both have colorbars)
            width_with_colorbar = width + colorbar_width
            plot1.width = width_with_colorbar
            plot1.height = height
            # Plot3 should match Plot1 dimensions
            if plot3 is not None:
                plot3.width = width_with_colorbar
                plot3.height = height
            # Also update Plot1B if it exists
            if plot1b is not None and map_plot_b is not None:
                map_plot_b.plot_max_size = map_plot.plot_max_size
                width_b, height_b = map_plot_b.calculate_plot_dimensions()
                plot1b.width = width_b
                plot1b.height = height_b
            # Save state asynchronously
            from bokeh.io import curdoc
            def save_state_async():
                plot1_history.save_state("Plot max size changed")
                session_history.save_state("Plot max size changed")
                undo_redo_callbacks["update"]()
            curdoc().add_next_tick_callback(save_state_async)
        except:
            pass

    # Get initial shape mode
    initial_shape_mode = 0  # Square
    if plot1_is_1d and plot1_1d_plot is not None:
        # For 1D plots, use defaults (shape mode doesn't really apply, but we'll use square)
        plot_width = 400
        plot_height = 400
        plot_scale = 1.0
        plot_min_size = 100
        plot_max_size = 2000
    elif map_plot is not None:
        if map_plot.plot_shape_mode == PlotShapeMode.CUSTOM:
            initial_shape_mode = 1
        elif map_plot.plot_shape_mode == PlotShapeMode.ASPECT_RATIO:
            initial_shape_mode = 2
        plot_width = map_plot.plot_width
        plot_height = map_plot.plot_height
        plot_scale = map_plot.plot_scale
        plot_min_size = map_plot.plot_min_size
        plot_max_size = map_plot.plot_max_size
    else:
        # Fallback defaults
        plot_width = 400
        plot_height = 400
        plot_scale = 1.0
        plot_min_size = 100
        plot_max_size = 2000

    plot1_shape_selector, plot1_custom_width_input, plot1_custom_height_input, \
    plot1_scale_input, plot1_min_size_input, plot1_max_size_input, \
    plot1_custom_controls, plot1_aspect_controls, plot1_size_limits_controls = create_plot_shape_controls(
        active=initial_shape_mode,
        width=200,
        shape_callback=on_plot1_shape_change,
        custom_width=plot_width,
        custom_height=plot_height,
        custom_width_callback=on_plot1_custom_width_change,
        custom_height_callback=on_plot1_custom_height_change,
        scale=plot_scale,
        scale_callback=on_plot1_scale_change,
        min_size=plot_min_size,
        max_size=plot_max_size,
        min_size_callback=on_plot1_min_size_change,
        max_size_callback=on_plot1_max_size_change,
    )

    # Connect min/max size input callbacks
    plot1_min_size_input.on_change("value", on_plot1_min_size_change)
    plot1_max_size_input.on_change("value", on_plot1_max_size_change)

    # Create plot shape section
    plot1_shape_section = column(
        create_label_div("Plot1 Shape:", width=200),
        plot1_shape_selector,
        plot1_custom_controls,
        # Removed plot1_aspect_controls and plot1_size_limits_controls - not needed with custom map size
    )

    # Plot2 width/height change callbacks
    def on_plot2_custom_width_change(attr, old, new):
        """Handle Plot2 custom width change."""
        try:
            new_width = int(float(new))
            # Account for colorbar if Plot2 has one (2D plots have colorbars)
            if not is_3d_volume and color_mapper2 is not None:
                # Plot2 has a colorbar, so add colorbar width
                plot2.width = new_width + colorbar_width
            else:
                # Plot2 is 1D, no colorbar
                plot2.width = new_width
            # Save to session metadata immediately (for undo/redo and session save)
            try:
                session.metadata['plot2_width'] = new_width
            except:
                pass
            # Update base dimensions so probe scale can work from the new custom size
            # Store the new custom dimensions as the base for future probe scale operations
            # Base dimensions will be updated when probe scale reads current plot size
            # Save state asynchronously
            from bokeh.io import curdoc
            def save_state_async():
                plot1_history.save_state("Plot2 width changed")
                session_history.save_state("Plot2 width changed")
                undo_redo_callbacks["update"]()
            curdoc().add_next_tick_callback(save_state_async)
        except:
            pass

    def on_plot2_custom_height_change(attr, old, new):
        """Handle Plot2 custom height change."""
        try:
            new_height = int(float(new))
            plot2.height = new_height
            # Save to session metadata immediately (for undo/redo and session save)
            try:
                session.metadata['plot2_height'] = new_height
            except:
                pass
            # Update base dimensions so probe scale can work from the new custom size
            # Store the new custom dimensions as the base for future probe scale operations
            # Base dimensions will be updated when probe scale reads current plot size
            # Save state asynchronously
            from bokeh.io import curdoc
            def save_state_async():
                plot1_history.save_state("Plot2 height changed")
                session_history.save_state("Plot2 height changed")
                undo_redo_callbacks["update"]()
            curdoc().add_next_tick_callback(save_state_async)
        except:
            pass

    # Plot2B width/height change callbacks
    def on_plot2b_custom_width_change(attr, old, new):
        """Handle Plot2B custom width change."""
        try:
            if plot2b is None:
                return
            new_width = int(float(new))
            # Account for colorbar if Plot2B has one (2D plots have colorbars)
            if plot2b_is_2d and color_mapper2b is not None:
                # Plot2B has a colorbar, so add colorbar width
                plot2b.width = new_width + colorbar_width
            else:
                # Plot2B is 1D, no colorbar
                plot2b.width = new_width
            # Save to session metadata immediately (for undo/redo and session save)
            try:
                session.metadata['plot2b_width'] = new_width
            except:
                pass
            # Update base dimensions so probe scale can work from the new custom size
            # Store the new custom dimensions as the base for future probe scale operations
            # Base dimensions will be updated when probe scale reads current plot size
            # Save state asynchronously
            from bokeh.io import curdoc
            def save_state_async():
                plot1_history.save_state("Plot2B width changed")
                session_history.save_state("Plot2B width changed")
                undo_redo_callbacks["update"]()
            curdoc().add_next_tick_callback(save_state_async)
        except:
            pass

    def on_plot2b_custom_height_change(attr, old, new):
        """Handle Plot2B custom height change."""
        try:
            if plot2b is None:
                return
            new_height = int(float(new))
            plot2b.height = new_height
            # Save to session metadata immediately (for undo/redo and session save)
            try:
                session.metadata['plot2b_height'] = new_height
            except:
                pass
            # Update base dimensions so probe scale can work from the new custom size
            # Store the new custom dimensions as the base for future probe scale operations
            # Base dimensions will be updated when probe scale reads current plot size
            # Save state asynchronously
            from bokeh.io import curdoc
            def save_state_async():
                plot1_history.save_state("Plot2B height changed")
                session_history.save_state("Plot2B height changed")
                undo_redo_callbacks["update"]()
            curdoc().add_next_tick_callback(save_state_async)
        except:
            pass

    # Get initial Plot2 dimensions (accounting for colorbar if present)
    try:
        plot2_initial_width = plot2.width
        plot2_initial_height = plot2.height
        # Subtract colorbar width if Plot2 has a colorbar (2D plots)
        if not is_3d_volume and 'colorbar_width' in locals():
            plot2_initial_width = plot2_initial_width - colorbar_width
    except (NameError, AttributeError):
        plot2_initial_width = 400
        plot2_initial_height = 400

    # Create Plot2 shape controls (simplified - just width/height inputs, no shape mode selector)
    plot2_custom_width_input = create_text_input(
        title="Width:",
        value=str(plot2_initial_width),
        width=100,
        callback=on_plot2_custom_width_change
    )

    plot2_custom_height_input = create_text_input(
        title="Height:",
        value=str(plot2_initial_height),
        width=100,
        callback=on_plot2_custom_height_change
    )

    plot2_shape_section = column(
        create_label_div("Probe 1 Size:", width=200),
        row(plot2_custom_width_input, plot2_custom_height_input, spacing=5),
    )

    # Get initial Plot2B dimensions (accounting for colorbar if present)
    try:
        if plot2b is not None:
            plot2b_initial_width = plot2b.width
            plot2b_initial_height = plot2b.height
            # Subtract colorbar width if Plot2B has a colorbar (2D plots)
            if 'plot2b_is_2d' in locals() and plot2b_is_2d and 'colorbar_width' in locals():
                plot2b_initial_width = plot2b_initial_width - colorbar_width
        else:
            plot2b_initial_width = 400
            plot2b_initial_height = 400
    except (NameError, AttributeError):
        plot2b_initial_width = 400
        plot2b_initial_height = 400

    # Create Plot2B shape controls (simplified - just width/height inputs, no shape mode selector)
    plot2b_custom_width_input = create_text_input(
        title="Width:",
        value=str(plot2b_initial_width),
        width=100,
        callback=on_plot2b_custom_width_change
    )

    plot2b_custom_height_input = create_text_input(
        title="Height:",
        value=str(plot2b_initial_height),
        width=100,
        callback=on_plot2b_custom_height_change
    )

    plot2b_shape_section = column(
        create_label_div("Probe 2 Size:", width=200),
        row(plot2b_custom_width_input, plot2b_custom_height_input, spacing=5),
    )
    # Hide Plot2B shape section if plot2b doesn't exist
    try:
        if plot2b is None:
            plot2b_shape_section.visible = False
    except NameError:
        plot2b_shape_section.visible = False

    # Create range controls for Plot1B if it exists
    range1b_section = None
    if plot1b is not None and map_plot_b is not None and map1b_min_val is not None and map1b_max_val is not None:
        def on_range1b_change(attr, old, new):
            """Handle Plot1B range input changes."""
            if sync_range_inputs_to_plot(map_plot_b, range1b_min_input, range1b_max_input):
                color_mapper1b.low = map_plot_b.range_min
                color_mapper1b.high = map_plot_b.range_max

        range1b_min_input, range1b_max_input = create_range_inputs(
            min_title="Min:",
            max_title="Max:",
            min_value=map1b_min_val,
            max_value=map1b_max_val,
            width=100,  # Changed from 120 to 100 to match other widgets
            min_callback=on_range1b_change,
            max_callback=on_range1b_change,
        )
        sync_plot_to_range_inputs(map_plot_b, range1b_min_input, range1b_max_input)

        # Set initial label based on range mode
        plot1b_initial_label = "Auto=Off" if map_plot_b.range_mode == RangeMode.USER_SPECIFIED else "Auto=On"
        range1b_section, range1b_mode_toggle = create_range_section_with_toggle(
            label="Plot1B Range:",
            min_title="Min:",
            max_title="Max:",
            min_value=map1b_min_val,
            max_value=map1b_max_val,
            width=100,  # Changed from 120 to 100 to match other widgets
            toggle_label=plot1b_initial_label,
            toggle_active=(map_plot_b.range_mode == RangeMode.USER_SPECIFIED),
            toggle_callback=None,  # Will be set after toggle is created
            min_callback=on_range1b_change,
            max_callback=on_range1b_change,
        )

        # Define callback after toggle is created so we can reference it
        def on_plot1b_range_mode_change(attr, old, new):
            """Handle Plot1B range mode toggle."""
            # Note: toggle_active=True means User Specified, toggle_active=False means Dynamic
            if new:  # Toggle is active = User Specified mode
                map_plot_b.range_mode = RangeMode.USER_SPECIFIED
                range1b_min_input.disabled = False
                range1b_max_input.disabled = False
                # Update toggle label to "User selected"
                range1b_mode_toggle.label = "Auto=Off"
            else:  # Toggle is inactive = Dynamic mode
                map_plot_b.range_mode = RangeMode.DYNAMIC
                range1b_min_input.disabled = True
                range1b_max_input.disabled = True
                # Update toggle label to "Dynamic"
                range1b_mode_toggle.label = "Auto=On"
        
        # Attach callback to toggle after it's created
        range1b_mode_toggle.on_change("active", on_plot1b_range_mode_change)
        
        # Add toggle to the section so it's visible
        if range1b_mode_toggle not in range1b_section.children:
            range1b_section.children.append(range1b_mode_toggle)

    # Create range controls for Plot2
    range2_section = None
    if is_3d_volume:
        # 1D plot
        probe_min_val = float(np.percentile(initial_slice_1d[~np.isnan(initial_slice_1d)], 1))
        probe_max_val = float(np.percentile(initial_slice_1d[~np.isnan(initial_slice_1d)], 99))
    else:
        # 2D plot
        probe_min_val = float(np.percentile(plot2_data[~np.isnan(plot2_data)], 1))
        probe_max_val = float(np.percentile(plot2_data[~np.isnan(plot2_data)], 99))

    # Function to update Plot2 range dynamically
    def update_plot2_range_dynamic():
        """Update Plot2 range to 1st and 99th percentiles of current slice."""
        if is_3d_volume:
            # For 1D plots, get current slice data
            x_idx = get_x_index()
            y_idx = get_y_index()
            current_slice = volume[x_idx, y_idx, :]
            if current_slice is not None and current_slice.size > 0:
                new_min = float(np.percentile(current_slice[~np.isnan(current_slice)], 1))
                new_max = float(np.percentile(current_slice[~np.isnan(current_slice)], 99))
                plot2.y_range.start = new_min
                plot2.y_range.end = new_max
                # Update range inputs using add_next_tick_callback
                from bokeh.io import curdoc
                update_func = update_range_inputs_safely(
                    range2_min_input, range2_max_input, new_min, new_max, use_callback=True
                )
                curdoc().add_next_tick_callback(update_func)
        else:
            # For 2D plots, get current slice data
            x_idx = get_x_index()
            if len(volume.shape) == 3:
                # Volume is 3D (x,z,u) - only need x_idx
                current_slice = volume[x_idx, :, :]
            elif len(volume.shape) == 4:
                # Normal 4D volume case (x,y,z,u) - need both x_idx and y_idx
                y_idx = get_y_index()
                current_slice = volume[x_idx, y_idx, :, :]
            else:
                raise ValueError(f"Unexpected volume shape: {volume.shape}, expected 3D or 4D")
            if plot2_needs_flip:
                current_slice = np.transpose(current_slice)
            if current_slice is not None and current_slice.size > 0:
                new_min = float(np.percentile(current_slice[~np.isnan(current_slice)], 1))
                new_max = float(np.percentile(current_slice[~np.isnan(current_slice)], 99))
                color_mapper2.low = new_min
                color_mapper2.high = new_max
                # Update range inputs using add_next_tick_callback
                from bokeh.io import curdoc
                update_func = update_range_inputs_safely(
                    range2_min_input, range2_max_input, new_min, new_max, use_callback=True
                )
                curdoc().add_next_tick_callback(update_func)

    def on_range2_change(attr, old, new):
        """Handle Plot2 range input changes."""
        try:
            min_val = float(range2_min_input.value) if range2_min_input.value else probe_min_val
            max_val = float(range2_max_input.value) if range2_max_input.value else probe_max_val
            if is_3d_volume:
                plot2.y_range.start = min_val
                plot2.y_range.end = max_val
            else:
                color_mapper2.low = min_val
                color_mapper2.high = max_val
        except:
            pass

    # Note: range2_min_input and range2_max_input will be extracted from range2_section below
    # We create them here as placeholders that will be overwritten
    range2_min_input = None
    range2_max_input = None

    # Determine Plot2 initial range mode and label
    plot2_initial_range_mode = RangeMode.DYNAMIC  # Default
    if probe_2d_plot is not None and hasattr(probe_2d_plot, 'range_mode'):
        plot2_initial_range_mode = probe_2d_plot.range_mode
    elif probe_1d_plot is not None and hasattr(probe_1d_plot, 'range_mode'):
        plot2_initial_range_mode = probe_1d_plot.range_mode
    plot2_initial_label = "Auto=Off" if plot2_initial_range_mode == RangeMode.USER_SPECIFIED else "Auto=On"
    
    range2_section, range2_mode_toggle = create_range_section_with_toggle(
        label="Plot2 Range:",
        min_title="Min:",
        max_title="Max:",
        min_value=probe_min_val,
        max_value=probe_max_val,
        width=100,  # Changed from 120 to 100 to match other widgets
        toggle_label=plot2_initial_label,
        toggle_active=(plot2_initial_range_mode == RangeMode.USER_SPECIFIED),  # True = User Specified, False = Dynamic
        toggle_callback=None,  # Will be set after toggle is created
        min_callback=on_range2_change,
        max_callback=on_range2_change,
    )

    # Extract the actual input widgets from the section (they're in a row inside the column)
    for child in range2_section.children:
        if hasattr(child, 'children') and len(child.children) == 2:
            # This is the row containing the two inputs
            range2_min_input = child.children[0]  # First input is min
            range2_max_input = child.children[1]  # Second input is max
            print(f"✅ DEBUG: Extracted range2_min_input and range2_max_input from range2_section")
            break

    # Define callback after toggle is created so we can reference it
    def on_plot2_range_mode_change(attr, old, new):
        """Handle Plot2 range mode toggle."""
        # Note: toggle_active=False means Dynamic mode, toggle_active=True means User Specified
        # But the callback receives new=True when toggle is active (User Specified), new=False when inactive (Dynamic)
        if new:  # Toggle is active = User Specified mode
            range2_min_input.disabled = False
            range2_max_input.disabled = False
            # Update toggle label to "User selected"
            range2_mode_toggle.label = "Auto=Off"
        else:  # Toggle is inactive = Dynamic mode
            range2_min_input.disabled = True
            range2_max_input.disabled = True
            # Update toggle label to "Dynamic"
            range2_mode_toggle.label = "Auto=On"
            # Recompute range from current data
            update_plot2_range_dynamic()
    
    # Attach callback to toggle after it's created
    range2_mode_toggle.on_change("active", on_plot2_range_mode_change)

    # Add toggle to the section so it's visible
    # Create color scale selector for Plot2 (no label, inline with toggle)
    plot2_color_scale_selector = create_color_scale_selector(
        active=0,
        width=100,  # Changed from 120 to 100 to match other widgets
        callback=on_plot2_color_scale_change
    )
    
    # Add toggle and color scale selector in a row (no label for color scale)
    range2_section.children.append(row(range2_mode_toggle, plot2_color_scale_selector, spacing=0))
    
    # Sync color scale selector to plot state
    if probe_2d_plot is not None:
        sync_plot_to_color_scale_selector(probe_2d_plot, plot2_color_scale_selector)

    # Initialize: Set inputs to disabled (Dynamic mode)
    # Note: Initial dynamic range is already computed when the plot is created
    # The range will update automatically when sliders move via show_slice()
    if range2_min_input is not None and range2_max_input is not None:
        range2_min_input.disabled = True  # Dynamic mode
        range2_max_input.disabled = True  # Dynamic mode

    # Create range controls for Plot2B if it exists
    range2b_section = None
    if plot2b is not None:
        # Get range values based on Plot2B type
        if probe2b_min_val is not None and probe2b_max_val is not None:
            plot2b_min_val = probe2b_min_val
            plot2b_max_val = probe2b_max_val
        else:
            # Fallback values
            plot2b_min_val = 0.0
            plot2b_max_val = 1.0

        def on_range2b_change(attr, old, new):
            """Handle Plot2B range input changes."""
            try:
                min_val = float(range2b_min_input.value) if range2b_min_input.value else plot2b_min_val
                max_val = float(range2b_max_input.value) if range2b_max_input.value else plot2b_max_val
                if plot2b_is_2d:
                    if color_mapper2b is not None:
                        color_mapper2b.low = min_val
                        color_mapper2b.high = max_val
                else:
                    plot2b.y_range.start = min_val
                    plot2b.y_range.end = max_val
            except:
                pass

        # Note: range2b_min_input and range2b_max_input will be extracted from range2b_section below
        # We create them here as placeholders that will be overwritten
        range2b_min_input = None
        range2b_max_input = None

        # Determine Plot2B initial range mode and label
        plot2b_initial_range_mode = RangeMode.DYNAMIC  # Default
        if probe_2d_plot_b is not None and hasattr(probe_2d_plot_b, 'range_mode'):
            plot2b_initial_range_mode = probe_2d_plot_b.range_mode
        elif probe_1d_plot_b is not None and hasattr(probe_1d_plot_b, 'range_mode'):
            plot2b_initial_range_mode = probe_1d_plot_b.range_mode
        plot2b_initial_label = "Auto=Off" if plot2b_initial_range_mode == RangeMode.USER_SPECIFIED else "Auto=On"
        
        range2b_section, range2b_mode_toggle = create_range_section_with_toggle(
            label="Plot2B Range:",
            min_title="Min:",
            max_title="Max:",
            min_value=plot2b_min_val,
            max_value=plot2b_max_val,
            width=100,  # Changed from 120 to 100 to match other widgets
            toggle_label=plot2b_initial_label,
            toggle_active=(plot2b_initial_range_mode == RangeMode.USER_SPECIFIED),  # True = User Specified, False = Dynamic
            toggle_callback=None,  # Will be set after toggle is created
            min_callback=on_range2b_change,
            max_callback=on_range2b_change,
        )

        # Extract the actual input widgets from the section (they're in a row inside the column)
        for child in range2b_section.children:
            if hasattr(child, 'children') and len(child.children) == 2:
                # This is the row containing the two inputs
                range2b_min_input = child.children[0]  # First input is min
                range2b_max_input = child.children[1]  # Second input is max
                print(f"✅ DEBUG: Extracted range2b_min_input and range2b_max_input from range2b_section")
                break

        # Define callback after toggle is created so we can reference it
        def on_plot2b_range_mode_change(attr, old, new):
            """Handle Plot2B range mode toggle."""
            # Note: toggle_active=True means User Specified, toggle_active=False means Dynamic
            if new:  # Toggle is active = User Specified mode
                range2b_min_input.disabled = False
                range2b_max_input.disabled = False
                # Update toggle label to "User selected"
                range2b_mode_toggle.label = "Auto=Off"
            else:  # Toggle is inactive = Dynamic mode
                range2b_min_input.disabled = True
                range2b_max_input.disabled = True
                # Update toggle label to "Dynamic"
                range2b_mode_toggle.label = "Auto=On"
                # Recompute range from current data
                x_idx = get_x_index()
                y_idx = get_y_index()
                if plot2b_is_2d:
                    if hasattr(self.process_4dnexus, 'volume_picked_b') and self.process_4dnexus.volume_picked_b:
                        try:
                            # Use cached volume_b if available
                            if (hasattr(self.process_4dnexus, '_cached_volume_b') and 
                                hasattr(self.process_4dnexus, '_cached_volume_b_path') and
                                self.process_4dnexus._cached_volume_b_path == self.process_4dnexus.volume_picked_b):
                                    volume_b = self.process_4dnexus._cached_volume_b
                            else:
                                # Load and cache volume_b
                                volume_b = self.process_4dnexus.load_dataset_by_path(self.process_4dnexus.volume_picked_b)
                                if volume_b is not None:
                                    self.process_4dnexus._cached_volume_b = volume_b
                                    self.process_4dnexus._cached_volume_b_path = self.process_4dnexus.volume_picked_b

                            if volume_b is not None:
                                # Extract 2D slice - handle both 3D and 4D volumes
                                if plot1_is_1d and len(volume_b.shape) == 3:
                                    # Volume B is 3D (x,z,u) - when Plot1 is 1D, extract 2D slice (z,u) at x_idx
                                    current_slice = volume_b[x_idx, :, :]
                                elif len(volume_b.shape) == 4:
                                    # Normal 4D volume case (x,y,z,u)
                                    current_slice = volume_b[x_idx, y_idx, :, :]
                                else:
                                    raise ValueError(f"Unexpected volume_b shape: {volume_b.shape}, expected 3D or 4D")
                                # Get coordinate sizes for flip detection
                                plot2b_probe_x_coord_size_local = None
                                plot2b_probe_y_coord_size_local = None
                                if hasattr(self.process_4dnexus, 'probe_x_coords_picked_b') and self.process_4dnexus.probe_x_coords_picked_b:
                                    plot2b_probe_x_coord_size_local = self.process_4dnexus.get_dataset_size_from_path(self.process_4dnexus.probe_x_coords_picked_b)
                                if hasattr(self.process_4dnexus, 'probe_y_coords_picked_b') and self.process_4dnexus.probe_y_coords_picked_b:
                                    plot2b_probe_y_coord_size_local = self.process_4dnexus.get_dataset_size_from_path(self.process_4dnexus.probe_y_coords_picked_b)

                                plot2b_needs_flip_local = self.process_4dnexus.detect_probe_flip_needed(
                                    volume_b.shape,
                                    plot2b_probe_x_coord_size_local,
                                    plot2b_probe_y_coord_size_local
                                )
                                if plot2b_needs_flip_local:
                                    current_slice = np.transpose(current_slice)
                                else:
                                    current_slice = np.transpose(current_slice)
                                if current_slice is not None and current_slice.size > 0:
                                    new_min = float(np.percentile(current_slice[~np.isnan(current_slice)], 1))
                                    new_max = float(np.percentile(current_slice[~np.isnan(current_slice)], 99))
                                    color_mapper2b.low = new_min
                                    color_mapper2b.high = new_max
                                    # Update range inputs so user can see the computed values
                                    # Use add_next_tick_callback to ensure updates happen in next Bokeh tick
                                    from bokeh.io import curdoc
                                    update_func = update_range_inputs_safely(
                                        range2b_min_input, range2b_max_input, new_min, new_max, use_callback=True
                                    )
                                    curdoc().add_next_tick_callback(update_func)
                        except:
                            pass
                else:
                    # 1D plot
                    if hasattr(self.process_4dnexus, 'volume_picked_b') and self.process_4dnexus.volume_picked_b:
                        try:
                            # Use cached volume_b if available
                            if (hasattr(self.process_4dnexus, '_cached_volume_b') and 
                                hasattr(self.process_4dnexus, '_cached_volume_b_path') and
                                self.process_4dnexus._cached_volume_b_path == self.process_4dnexus.volume_picked_b):
                                    volume_b = self.process_4dnexus._cached_volume_b
                            else:
                                # Load and cache volume_b
                                volume_b = self.process_4dnexus.load_dataset_by_path(self.process_4dnexus.volume_picked_b)
                                if volume_b is not None:
                                    self.process_4dnexus._cached_volume_b = volume_b
                                    self.process_4dnexus._cached_volume_b_path = self.process_4dnexus.volume_picked_b

                            if volume_b is not None:
                                # Extract 1D slice - handle both 2D and 3D volumes
                                if plot1_is_1d and len(volume_b.shape) == 2:
                                    # Volume B is 2D (x,z) - when Plot1 is 1D, extract 1D slice z at x_idx
                                    current_slice = volume_b[x_idx, :]
                                elif len(volume_b.shape) == 3:
                                    # Normal 3D volume case (x,y,z)
                                    current_slice = volume_b[x_idx, y_idx, :]
                                else:
                                    raise ValueError(f"Unexpected volume_b shape for 1D Plot2B: {volume_b.shape}, expected 2D or 3D")
                                if current_slice is not None and current_slice.size > 0:
                                    new_min = float(np.percentile(current_slice[~np.isnan(current_slice)], 1))
                                    new_max = float(np.percentile(current_slice[~np.isnan(current_slice)], 99))
                                    plot2b.y_range.start = new_min
                                    plot2b.y_range.end = new_max
                                    # Update range inputs so user can see the computed values
                                    # Use add_next_tick_callback to ensure updates happen in next Bokeh tick
                                    from bokeh.io import curdoc
                                    update_func = update_range_inputs_safely(
                                        range2b_min_input, range2b_max_input, new_min, new_max, use_callback=True
                                    )
                                    curdoc().add_next_tick_callback(update_func)
                        except:
                            pass
        
        # Attach callback to toggle after it's created
        range2b_mode_toggle.on_change("active", on_plot2b_range_mode_change)

        # Add toggle to the section so it's visible
        # Create color scale selector for Plot2B (no label, inline with toggle)
        plot2b_color_scale_selector = create_color_scale_selector(
            active=0,
            width=100,  # Changed from 120 to 100 to match other widgets
            callback=on_plot2b_color_scale_change
        )
        
        # Add toggle and color scale selector in a row (no label for color scale)
        if range2b_mode_toggle not in range2b_section.children:
            range2b_section.children.append(row(range2b_mode_toggle, plot2b_color_scale_selector, spacing=0))
        
        # Sync color scale selector to plot state
        if probe_2d_plot_b is not None:
            sync_plot_to_color_scale_selector(probe_2d_plot_b, plot2b_color_scale_selector)

        # Initialize: Set inputs to disabled (Dynamic mode)
        # Note: Initial dynamic range will be computed when show_slice_b() is first called
        # (which happens when sliders are initialized), so we don't need to call it here
        if range2b_min_input is not None and range2b_max_input is not None:
            range2b_min_input.disabled = True  # Dynamic mode
            range2b_max_input.disabled = True  # Dynamic mode

    # Create range controls for Plot3
    range3_section = None
    plot3_min_val = 0.0
    plot3_max_val = 1.0

    def on_range3_change(attr, old, new):
        """Handle Plot3 range input changes."""
        try:
            min_val = float(range3_min_input.value) if range3_min_input.value else plot3_min_val
            max_val = float(range3_max_input.value) if range3_max_input.value else plot3_max_val
            color_mapper3.low = min_val
            color_mapper3.high = max_val
        except:
            pass

    range3_min_input, range3_max_input = create_range_inputs(
        min_title="Min:",
        max_title="Max:",
        min_value=plot3_min_val,
        max_value=plot3_max_val,
        width=100,  # Changed from 120 to 100 to match other widgets
        min_callback=on_range3_change,
        max_callback=on_range3_change,
    )

    # Determine Plot3 initial range mode and label (Plot3 uses map_plot for state)
    plot3_initial_range_mode = map_plot.range_mode if map_plot is not None else RangeMode.DYNAMIC
    plot3_initial_label = "Auto=Off" if plot3_initial_range_mode == RangeMode.USER_SPECIFIED else "Auto=On"
    
    range3_section, range3_mode_toggle = create_range_section_with_toggle(
        label="Plot3 Range:",
        min_title="Min:",
        max_title="Max:",
        min_value=plot3_min_val,
        max_value=plot3_max_val,
        width=100,  # Changed from 120 to 100 to match other widgets
        toggle_label=plot3_initial_label,
        toggle_active=(plot3_initial_range_mode == RangeMode.USER_SPECIFIED),  # True = User Specified, False = Dynamic
        toggle_callback=None,  # Will be set after toggle is created
        min_callback=on_range3_change,
        max_callback=on_range3_change,
    )
    
    # Extract range inputs from the section (they're in a row inside the column)
    for child in range3_section.children:
        if hasattr(child, 'children') and len(child.children) == 2:
            # This is the row containing the two inputs
            range3_min_input = child.children[0]  # First input is min
            range3_max_input = child.children[1]  # Second input is max
            break
    
    # Define callback after toggle is created so we can reference it
    def on_plot3_range_mode_change(attr, old, new):
        """Handle Plot3 range mode toggle."""
        # Note: toggle_active=True means User Specified, toggle_active=False means Dynamic
        # The callback receives new=True when toggle is active (User Specified), new=False when inactive (Dynamic)
        if new:  # Toggle is active = User Specified mode
            range3_min_input.disabled = False
            range3_max_input.disabled = False
            # Update toggle label to "Auto=Off"
            range3_mode_toggle.label = "Auto=Off"
        else:  # Toggle is inactive = Dynamic mode
            range3_min_input.disabled = True
            range3_max_input.disabled = True
            # Update toggle label to "Auto=On"
            range3_mode_toggle.label = "Auto=On"
    
    # Attach callback to toggle after it's created
    range3_mode_toggle.on_change("active", on_plot3_range_mode_change)

    # Create color scale selector for Plot3 (no label, inline with toggle)
    plot3_color_scale_selector = create_color_scale_selector(
        active=0,
        width=100,  # Changed from 120 to 100 to match other widgets
        callback=on_plot3_color_scale_change
    )
    
    # Add log scale toggle for Plot3 1D plots
    plot3_log_scale_toggle = None
    
    if plot1_is_1d and plot1_1d_plot is not None:
        from bokeh.models import Toggle
        plot3_log_scale_toggle = Toggle(
            label="Log Scale",
            active=False,
            button_type="default",
            width=100
        )
        
        def on_plot3_log_scale_change(attr, old, new):
            """Handle log scale toggle for Plot3 1D plots."""
            if plot3_1d_data_original[0] is None or source3_1d is None:
                return
            
            if new:  # Log scale enabled
                # Apply symlog transformation
                transformed_data = symlog_transform(plot3_1d_data_original[0])
                source3_1d.data = {"x": source3_1d.data["x"], "y": transformed_data}
                plot3.yaxis.axis_label = "Intensity (symlog)"
                print("✅ Plot3 log scale enabled (symlog)")
            else:  # Log scale disabled
                # Use original data
                source3_1d.data = {"x": source3_1d.data["x"], "y": plot3_1d_data_original[0]}
                plot3.yaxis.axis_label = "Intensity"
                print("✅ Plot3 log scale disabled")
            
            # Update y-axis range to fit the data
            y_data = source3_1d.data["y"]
            if len(y_data) > 0:
                y_min = float(np.nanmin(y_data))
                y_max = float(np.nanmax(y_data))
                # Add some padding
                y_range_padding = (y_max - y_min) * 0.05
                plot3.y_range.start = y_min - y_range_padding
                plot3.y_range.end = y_max + y_range_padding
        
        plot3_log_scale_toggle.on_change("active", on_plot3_log_scale_change)
    
    # Add toggle and color scale selector in a row (no label for color scale)
    # For 1D plots, add log scale toggle instead of color scale selector
    if plot1_is_1d and plot1_1d_plot is not None and plot3_log_scale_toggle is not None:
        range3_section.children.append(row(range3_mode_toggle, plot3_log_scale_toggle, spacing=0))
    else:
        range3_section.children.append(row(range3_mode_toggle, plot3_color_scale_selector, spacing=0))
    # Note: Plot3 -> Plot2 computation buttons will be added to range3_section after they're created
    
    # Sync color scale selector to plot state (Plot3 uses map_plot for state, or plot1_1d_plot if Plot1 is 1D)
    # Plot3 doesn't have color scale for 1D plots, so only sync for 2D plots
    if not plot1_is_1d and map_plot is not None:
        sync_plot_to_color_scale_selector(map_plot, plot3_color_scale_selector)

    # Save session callback
    def on_save_session():
        """Save current session to file.

        NOTE: This saves ONLY UI settings (ranges, colors, palettes, plot shapes, etc.)
        NOT data arrays. Data is loaded fresh from the dataset files when the session is loaded.
        This keeps session files small and fast to save/load.
        """
        try:
            from pathlib import Path
            import os

            # Get filename from input
            filename = save_filename_input.value.strip()
            if not filename:
                save_status_div.text = "<span style='color: orange;'>Please enter a filename</span>"
                status_div.text = "<span style='color: orange;'>Please enter a filename</span>"
                return

            # Ensure filename ends with .json
            if not filename.endswith('.json'):
                filename += '.json'

            # Get save directory from input or use default
            save_dir_custom = save_dir_input.value.strip()
            if save_dir_custom:
                # User specified a custom directory
                save_dir_path = Path(save_dir_custom)
                if not save_dir_path.is_absolute():
                    # If relative, make it relative to base_dir (nexus file directory)
                    base = get_save_dir_path()
                    save_dir_path = base / save_dir_custom
                save_dir_path.mkdir(parents=True, exist_ok=True)
                filepath = save_dir_path / filename
            else:
                # Use default sessions directory (nexus file directory)
                save_dir_path = get_save_dir_path()

            # Get writable sessions directory (with fallback if needed)
            sessions_dir = get_writable_sessions_dir(save_dir_path)
            filepath = sessions_dir / filename

            # Save Plot2 and Plot2B custom dimensions and probe scale to session metadata before saving
            try:
                # Save Plot2 dimensions (accounting for colorbar if present)
                if plot2 is not None:
                    plot2_width = plot2.width
                    plot2_height = plot2.height
                    # Subtract colorbar width if Plot2 has a colorbar (2D plots)
                    if not is_3d_volume and color_mapper2 is not None:
                        plot2_width = plot2_width - colorbar_width
                    session.metadata['plot2_width'] = plot2_width
                    session.metadata['plot2_height'] = plot2_height
                
                # Save Plot2B dimensions (accounting for colorbar if present)
                if plot2b is not None:
                    plot2b_width = plot2b.width
                    plot2b_height = plot2b.height
                    # Subtract colorbar width if Plot2B has a colorbar (2D plots)
                    if 'plot2b_is_2d' in locals() and plot2b_is_2d and color_mapper2b is not None:
                        plot2b_width = plot2b_width - colorbar_width
                    session.metadata['plot2b_width'] = plot2b_width
                    session.metadata['plot2b_height'] = plot2b_height
                
                # Save probe scale value
                if 'probe_scale_input' in locals() and probe_scale_input is not None:
                    try:
                        probe_scale_value = float(probe_scale_input.value) if probe_scale_input.value else 100.0
                        session.metadata['probe_scale'] = probe_scale_value
                    except:
                        pass
            except Exception as e:
                print(f"⚠️ Warning: Could not save Plot2/Plot2B dimensions or probe scale to metadata: {e}")

            # Save session - include_data=False means NO data arrays, only UI settings
            session.save_session(filepath, include_data=False)

            # Save state to history (but don't create a new history entry for the save action itself)
            # The save action is logged in session_changes, but we don't want to undo/redo the save
            undo_redo_callbacks["update"]()

            # Refresh session list after saving
            on_refresh_sessions()

            # Update compact save status message
            save_status_div.text = f"✅ Saved: {filepath.name}"
            # Also update main status div
            status_div.text = f"Session saved to {filepath}"
            print(f"✅ Session saved to {filepath}")
        except Exception as e:
            import traceback
            error_msg = f"Error saving session: {str(e)}"
            print(error_msg)
            traceback.print_exc()
            save_status_div.text = f"<span style='color: red;'>Error: {str(e)[:50]}</span>"
            status_div.text = f"<span style='color: red;'>{error_msg}</span>"

    # Load session callback
    def on_load_session():
        """Load session from file, restore dataset paths, and recreate dashboard (same approach as tmp_dashboard)."""
        try:
            from pathlib import Path
            import os
            import json
            from datetime import datetime

            # Get selected session from dropdown
            selected_session = load_session_select.value
            if not selected_session or selected_session.startswith("No ") or selected_session.startswith("Error:") or selected_session == "Click 'Refresh' to load sessions":
                status_div.text = "<span style='color: orange;'>Please select a session to load</span>"
                return

            # Refresh session list to ensure we have current files
            _session_state["files"] = refresh_session_list()
            if not _session_state["files"]:
                status_div.text = "<span style='color: orange;'>No sessions available. Please refresh.</span>"
                return

            # Extract filename from selected_session (e.g., "session_xxx.json (2023-10-27 10:30:00)")
            session_filename = selected_session.split(" (")[0] if " (" in selected_session else selected_session

            filepath = None
            # Try to match by filename first
            for fpath in _session_state["files"]:
                if fpath.name == session_filename:
                    filepath = fpath
                    break

            # Fallback to index-based matching if filename match fails
            if filepath is None:
                for i, choice in enumerate(load_session_select.options):
                    if choice == selected_session:
                        if i < len(_session_state["files"]):
                            filepath = _session_state["files"][i]
                            break

            if filepath is None or not filepath.exists():
                status_div.text = f"<span style='color: red;'>Session file not found: {session_filename}</span>"
                return

            print(f"✅ DEBUG: Found session file: {filepath}")

            # Read session file to extract metadata (dataset paths)
            with open(filepath, 'r') as f:
                session_data = json.load(f)

            # Extract metadata which contains dataset paths
            metadata = session_data.get("metadata", {})
            print(f"🔍 DEBUG: Loading session metadata keys: {list(metadata.keys())}")

            # CRITICAL: Restore dataset paths to self.process_4dnexus BEFORE recreating dashboard
            # This ensures the correct data is loaded when the dashboard is recreated
            if metadata:
                # Restore main volume and Plot1 datasets
                if "volume_picked" in metadata and metadata["volume_picked"]:
                    self.process_4dnexus.volume_picked = metadata["volume_picked"]
                    print(f"✅ Restored volume_picked: {metadata['volume_picked']}")

                if "plot1_single_dataset_picked" in metadata:
                    self.process_4dnexus.plot1_single_dataset_picked = metadata["plot1_single_dataset_picked"]
                    print(f"✅ Restored plot1_single_dataset_picked: {metadata.get('plot1_single_dataset_picked')}")

                if "presample_picked" in metadata:
                    self.process_4dnexus.presample_picked = metadata["presample_picked"]
                    print(f"✅ Restored presample_picked: {metadata.get('presample_picked')}")

                if "postsample_picked" in metadata:
                    self.process_4dnexus.postsample_picked = metadata["postsample_picked"]
                    print(f"✅ Restored postsample_picked: {metadata.get('postsample_picked')}")

                # Restore coordinate datasets
                if "x_coords_picked" in metadata:
                    self.process_4dnexus.x_coords_picked = metadata["x_coords_picked"]
                    print(f"✅ Restored x_coords_picked: {metadata.get('x_coords_picked')}")

                if "y_coords_picked" in metadata:
                    self.process_4dnexus.y_coords_picked = metadata["y_coords_picked"]
                    print(f"✅ Restored y_coords_picked: {metadata.get('y_coords_picked')}")

                if "probe_x_coords_picked" in metadata:
                    self.process_4dnexus.probe_x_coords_picked = metadata["probe_x_coords_picked"]
                    print(f"✅ Restored probe_x_coords_picked: {metadata.get('probe_x_coords_picked')}")

                if "probe_y_coords_picked" in metadata:
                    self.process_4dnexus.probe_y_coords_picked = metadata["probe_y_coords_picked"]
                    print(f"✅ Restored probe_y_coords_picked: {metadata.get('probe_y_coords_picked')}")

                # Restore Plot1B and Plot2B datasets
                if "volume_picked_b" in metadata:
                    self.process_4dnexus.volume_picked_b = metadata["volume_picked_b"]
                    print(f"✅ Restored volume_picked_b: {metadata.get('volume_picked_b')}")

                if "plot1b_single_dataset_picked" in metadata:
                    self.process_4dnexus.plot1b_single_dataset_picked = metadata["plot1b_single_dataset_picked"]
                    print(f"✅ Restored plot1b_single_dataset_picked: {metadata.get('plot1b_single_dataset_picked')}")

                if "presample_picked_b" in metadata:
                    self.process_4dnexus.presample_picked_b = metadata["presample_picked_b"]
                    print(f"✅ Restored presample_picked_b: {metadata.get('presample_picked_b')}")

                if "postsample_picked_b" in metadata:
                    self.process_4dnexus.postsample_picked_b = metadata["postsample_picked_b"]
                    print(f"✅ Restored postsample_picked_b: {metadata.get('postsample_picked_b')}")

                if "probe_x_coords_picked_b" in metadata:
                    self.process_4dnexus.probe_x_coords_picked_b = metadata["probe_x_coords_picked_b"]
                    print(f"✅ Restored probe_x_coords_picked_b: {metadata.get('probe_x_coords_picked_b')}")

                if "probe_y_coords_picked_b" in metadata:
                    self.process_4dnexus.probe_y_coords_picked_b = metadata["probe_y_coords_picked_b"]
                    print(f"✅ Restored probe_y_coords_picked_b: {metadata.get('probe_y_coords_picked_b')}")

            # Store the session filepath for the dashboard to load after recreation
            # Use a different attribute name to distinguish from tmp_dashboard loads
            self.process_4dnexus._session_filepath_to_load_from_main = filepath

            # Recreate the dashboard with restored dataset paths (same approach as tmp_dashboard)
            from bokeh.io import curdoc as _curdoc
            import importlib.util
            import os
            import sys
            import inspect
            
            # Import create_dashboard from the main dashboard file
            # Similar to how create_tmp_dashboard is imported in 4d_dashboard_builder.py
            create_dashboard_func = None
            try:
                # Try to find 4d_dashboardLite.py by looking at the call stack or file paths
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
                        if '4d_dashboardopt.py' in filename or '4d_dashboardLite.py' in filename:
                            dashboard_file = filename
                            print(f"✅ Found dashboard file from call stack: {dashboard_file}")
                            break
                except:
                    pass
                
                # Method 2: Try relative paths - don't use __file__ since code is executed via exec()
                if dashboard_file is None or not os.path.exists(dashboard_file):
                    # Try Docker path first (most common in production)
                    possible_paths = [
                        os.path.join('/app', '4d_dashboardopt.py'),  # Docker path
                        os.path.join('/app', '4d_dashboardLite.py'),  # Fallback for old name
                    ]
                    
                    # Try to get current file location if __file__ is available
                    try:
                        current_file = os.path.abspath(__file__)
                        current_dir = os.path.dirname(current_file)
                        # From SCLib_Dashboards to dashboards
                        base_dir = os.path.dirname(os.path.dirname(current_dir))  # Go up to scientistCloudLib
                        possible_paths.extend([
                            os.path.join(base_dir, 'scientistcloud', 'SC_Dashboards', 'dashboards', '4d_dashboardopt.py'),
                            os.path.join(os.path.dirname(base_dir), 'scientistcloud', 'SC_Dashboards', 'dashboards', '4d_dashboardopt.py'),
                            os.path.join(base_dir, 'scientistcloud', 'SC_Dashboards', 'dashboards', '4d_dashboardLite.py'),  # Fallback
                            os.path.join(os.path.dirname(base_dir), 'scientistcloud', 'SC_Dashboards', 'dashboards', '4d_dashboardLite.py'),  # Fallback
                        ])
                    except NameError:
                        # __file__ not available (code executed via exec), skip these paths
                        pass
                    
                    for path in possible_paths:
                        if os.path.exists(path):
                            dashboard_file = path
                            print(f"✅ Found dashboard file at: {dashboard_file}")
                            break
                
                # Method 3: Try current working directory
                if dashboard_file is None or not os.path.exists(dashboard_file):
                    try:
                        cwd = os.getcwd()
                        for filename in ['4d_dashboardopt.py', '4d_dashboardLite.py']:
                            cwd_path = os.path.join(cwd, filename)
                            if os.path.exists(cwd_path):
                                dashboard_file = cwd_path
                                print(f"✅ Found dashboard file in CWD: {dashboard_file}")
                                break
                    except:
                        pass
                
                if dashboard_file and os.path.exists(dashboard_file):
                    spec = importlib.util.spec_from_file_location("dashboard_lite", dashboard_file)
                    dashboard_module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(dashboard_module)
                    create_dashboard_func = getattr(dashboard_module, 'create_dashboard', None)
                    if create_dashboard_func:
                        print(f"✅ Successfully imported create_dashboard from {dashboard_file}")
                    else:
                        print(f"⚠️ create_dashboard function not found in {dashboard_file}")
                else:
                    print(f"⚠️ Could not find 4d_dashboardopt.py. Tried: {possible_paths}")
            except Exception as e:
                import traceback
                print(f"⚠️ Error importing create_dashboard: {e}")
                traceback.print_exc()
            
            if create_dashboard_func is None:
                error_msg = "Could not import create_dashboard function. Cannot recreate dashboard."
                print(f"❌ {error_msg}")
                status_div.text = f"<span style='color: red;'>{error_msg}</span>"
                return
            
            # Store the function and other needed variables that will be captured by the closure
            # Use a list to ensure the variable is mutable and captured correctly
            dashboard_creator_ref = [create_dashboard_func]
            process_instance = self.process_4dnexus
            session_file_name = filepath.name
            
            loading = column(create_div(text="<h3>Loading dashboard with session...</h3>"))
            _curdoc().clear()
            _curdoc().add_root(loading)

            def _build_and_swap():
                """Rebuild the dashboard with the loaded session data."""
                try:
                    # Use the captured variable from outer scope
                    dashboard_creator = dashboard_creator_ref[0]
                    if dashboard_creator is None:
                        # Fallback: try to import it again
                        try:
                            import importlib.util
                            import os
                            # Try Docker path first (most common in production)
                            dashboard_file = '/app/4d_dashboardopt.py'
                            if not os.path.exists(dashboard_file):
                                dashboard_file = '/app/4d_dashboardLite.py'  # Fallback for old name
                            if not os.path.exists(dashboard_file):
                                # Try to get current file location if __file__ is available
                                try:
                                    current_file = os.path.abspath(__file__)
                                    current_dir = os.path.dirname(current_file)
                                    base_dir = os.path.dirname(os.path.dirname(current_dir))
                                    for filename in ['4d_dashboardopt.py', '4d_dashboardLite.py']:
                                        test_path = os.path.join(base_dir, 'scientistcloud', 'SC_Dashboards', 'dashboards', filename)
                                        if os.path.exists(test_path):
                                            dashboard_file = test_path
                                            break
                                except NameError:
                                    # __file__ not available, try sys.path
                                    import sys
                                    for path_dir in sys.path:
                                        if path_dir and os.path.isdir(path_dir):
                                            for filename in ['4d_dashboardopt.py', '4d_dashboardLite.py']:
                                                test_path = os.path.join(path_dir, filename)
                                                if os.path.exists(test_path):
                                                    dashboard_file = test_path
                                                    break
                                            if os.path.exists(dashboard_file):
                                                break
                                    # If still not found, try current working directory
                                    if not os.path.exists(dashboard_file):
                                        cwd = os.getcwd()
                                        for filename in ['4d_dashboardopt.py', '4d_dashboardLite.py']:
                                            cwd_path = os.path.join(cwd, filename)
                                            if os.path.exists(cwd_path):
                                                dashboard_file = cwd_path
                                                break
                            
                            if os.path.exists(dashboard_file):
                                spec = importlib.util.spec_from_file_location("dashboard_lite", dashboard_file)
                                dashboard_module = importlib.util.module_from_spec(spec)
                                spec.loader.exec_module(dashboard_module)
                                dashboard_creator = getattr(dashboard_module, 'create_dashboard', None)
                                if dashboard_creator:
                                    dashboard_creator_ref[0] = dashboard_creator  # Update the reference
                                else:
                                    raise NameError("create_dashboard function not found in module")
                            else:
                                raise FileNotFoundError(f"Dashboard file not found: {dashboard_file}")
                        except Exception as import_error:
                            raise NameError(f"create_dashboard function not available: {import_error}")
                    
                    # Call the dashboard creator function
                    full_dashboard = dashboard_creator(process_instance)
                    _curdoc().clear()
                    _curdoc().add_root(full_dashboard)
                    print(f"✅ Dashboard recreated with session data from {session_file_name}")
                except Exception as e:
                    import traceback
                    error_msg = f"Error recreating dashboard: {str(e)}"
                    print(error_msg)
                    traceback.print_exc()
                    error_div = create_div(
                        text=f"<h3 style='color: red;'>Error Recreating Dashboard</h3><p>{error_msg}</p><pre>{traceback.format_exc()}</pre>",
                        width=800
                    )
                    _curdoc().clear()
                    _curdoc().add_root(error_div)

            _curdoc().add_next_tick_callback(_build_and_swap)

            print(f"✅ Session paths restored, recreating dashboard...")
        except Exception as e:
            import traceback
            error_msg = f"Error loading session: {str(e)}"
            print(error_msg)
            traceback.print_exc()
            status_div.text = f"<span style='color: red;'>{error_msg}</span>"

    save_session_button.on_click(on_save_session)
    load_session_button.on_click(on_load_session)

    # Initial refresh of session list
    on_refresh_sessions()

    # Callback to go back to dataset selection
    def on_back_to_selection():
        """Return to the dataset selection dashboard."""
        from bokeh.io import curdoc as _curdoc
        try:
            # Recreate the tmp_dashboard
            tmp_dashboard = create_tmp_dashboard(self.process_4dnexus)
            _curdoc().clear()
            _curdoc().add_root(tmp_dashboard)
        except Exception as e:
            import traceback
            error_msg = f"Error returning to dataset selection: {str(e)}"
            print(error_msg)
            traceback.print_exc()
            error_div = create_div(
                text=f"<h3 style='color: red;'>Error</h3><p>{error_msg}</p><pre>{traceback.format_exc()}</pre>",
                width=800
            )
            _curdoc().clear()
            _curdoc().add_root(error_div)

    back_to_selection_button.on_click(on_back_to_selection)

    # Create export change log button (needed before session_section)
    export_log_button = create_button(
        label="Export Change Log",
        button_type="default",
        width=120
    )

    def on_export_log():
        """Export change log to file."""
        try:
            from pathlib import Path

            # Determine save directory (use nexus file directory)
            save_dir_path = get_save_dir_path()

            # Get writable sessions directory (with fallback if needed)
            sessions_dir = get_writable_sessions_dir(save_dir_path)

            # Generate filename
            filename = f"changelog_{session.session_id}.json"
            filepath = sessions_dir / filename

            # Export change log
            session.export_change_log(filepath, format="json")

            status_div.text = f"Change log exported to {filepath}"
            print(f"✅ Change log exported to {filepath}")
        except Exception as e:
            import traceback
            error_msg = f"Error exporting change log: {str(e)}"
            print(error_msg)
            traceback.print_exc()
            status_div.text = f"<span style='color: red;'>{error_msg}</span>"

    export_log_button.on_click(on_export_log)

    # Create compact save status message (minimal space)
    save_status_div = create_div(
        text="",
        width=200,
        styles={
            "font-size": "11px",
            "color": "#28a745",
            "min-height": "15px",
            "padding": "2px 0"
        }
    )

    # Create session management section (moved here before tools_items)
    session_section = column(
        create_label_div("Session Management:", width=200),
        #create_label_div("Save Session:", width=200),
        save_status_div,  # Compact status message above filename
        save_filename_input,
        save_dir_input,
        save_session_button,
        #create_div(text="<hr>", width=400),
        #create_label_div("Load Session:", width=200),
        load_session_select,
        row(refresh_sessions_button, load_session_button),

        export_log_button,
        create_label_div("Undo/Redo:", width=200),
        undo_redo_status,
        row(undo_button, redo_button),
    )

    # Create status display
    status_text = f"""
    <h3>{'3D' if is_3d_volume else '4D'} Data Explorer Dashboard</h3>
    <p><b>Instructions:</b></p>
    <ul>
        <li><b>Plot1:</b> 2D map view - click to select position</li>
        <li><b>Plot2:</b> {'1D probe data' if is_3d_volume else '2D probe data'}</li>
    </ul>
    <p>Ready to explore data...</p>
    """
    # Create status display with constrained height to prevent overlap
    status_div = create_div(
        text=status_text,
        width=260,  # Match tools column width, #was 400
        height=300,  # Set max height
        styles={
            "overflow-y": "auto",
            "overflow-x": "hidden",
            "max-height": "300px"
        }
    )

    # Note: export_log_button and session_section are already created above
    # Create clear cache button
    clear_cache_button = create_button(
        label="Clear Cache & Reload",
        button_type="warning",
        width=150
    )

    def on_clear_cache():
        """Clear all caches and force reload of data."""
        import os
        print("=" * 80)
        print("🔄 Clearing all caches...")

        # Clear in-memory caches
        cache_cleared = False

        # Clear volume_b cache
        if hasattr(self.process_4dnexus, '_cached_volume_b'):
            self.process_4dnexus._cached_volume_b = None
            cache_cleared = True
            print("  ✅ Cleared _cached_volume_b")
        if hasattr(self.process_4dnexus, '_cached_volume_b_path'):
            self.process_4dnexus._cached_volume_b_path = None
            print("  ✅ Cleared _cached_volume_b_path")

        # Clear coordinate caches
        if hasattr(self.process_4dnexus, '_cached_probe_x_coords'):
            self.process_4dnexus._cached_probe_x_coords = None
            cache_cleared = True
            print("  ✅ Cleared _cached_probe_x_coords")
        if hasattr(self.process_4dnexus, '_cached_probe_x_coords_path'):
            self.process_4dnexus._cached_probe_x_coords_path = None
            print("  ✅ Cleared _cached_probe_x_coords_path")
        if hasattr(self.process_4dnexus, '_cached_probe_y_coords'):
            self.process_4dnexus._cached_probe_y_coords = None
            cache_cleared = True
            print("  ✅ Cleared _cached_probe_y_coords")
        if hasattr(self.process_4dnexus, '_cached_probe_y_coords_path'):
            self.process_4dnexus._cached_probe_y_coords_path = None
            print("  ✅ Cleared _cached_probe_y_coords_path")

        # Delete memmap cache files
        # Files are stored in the same directory as the nexus file (or memmap_cache_dir if set)
        memmap_files_deleted = 0
        try:
            # Determine the directory where memmap files are stored
            if hasattr(self.process_4dnexus, 'memmap_cache_dir') and self.process_4dnexus.memmap_cache_dir:
                cache_dir = self.process_4dnexus.memmap_cache_dir
            else:
                # Default: same directory as nexus file
                cache_dir = os.path.dirname(self.process_4dnexus.nexus_filename)
            
            if os.path.exists(cache_dir):
                # Find all memmap files for this nexus file
                nexus_basename = os.path.splitext(os.path.basename(self.process_4dnexus.nexus_filename))[0]
                for filename in os.listdir(cache_dir):
                    if filename.startswith(nexus_basename) and filename.endswith('.float32.dat'):
                        filepath = os.path.join(cache_dir, filename)
                        try:
                            # Close any open memmap handles first
                            # (This is a best-effort attempt - the file might be open elsewhere)
                            os.remove(filepath)
                            memmap_files_deleted += 1
                            print(f"  ✅ Deleted memmap cache: {filename}")
                        except PermissionError as e:
                            print(f"  ⚠️ Could not delete {filename} (file may be in use): {e}")
                            print(f"     You may need to restart the dashboard to release the file handle")
                        except Exception as e:
                            print(f"  ⚠️ Could not delete {filename}: {e}")
            else:
                print(f"  ⚠️ Cache directory does not exist: {cache_dir}")
        except Exception as e:
            print(f"  ⚠️ Error accessing memmap cache directory: {e}")

        # Force reload by clearing volume dataset references and memmap filename
        # This will cause load_nexus_data to reload from HDF5 instead of memmap
        if hasattr(self.process_4dnexus, 'mmap_filename'):
            self.process_4dnexus.mmap_filename = None
            print("  ✅ Cleared mmap_filename reference")
        
        # Clear the volume reference so it will be reloaded
        if hasattr(self.process_4dnexus, 'volume_dataset'):
            # Don't clear volume_dataset itself (it's the HDF5 reference), but clear any cached memmap
            pass

        print(f"✅ Cache clearing complete. Cleared {cache_cleared} in-memory caches, deleted {memmap_files_deleted} memmap files.")
        print("=" * 80)
        print("⚠️ NOTE: To fully reload data, you may need to refresh the page or reinitialize the dashboard.")

        # Update status (status_div is defined in the same function scope)
        try:
            status_div.text = f"<span style='color: green;'>✅ Cache cleared. Data will reload fresh on next update.</span>"
        except NameError:
            # status_div not available, just print to console
            print("✅ Cache cleared. Data will reload fresh on next update.")

        # Force a refresh of the current plots
        try:
            # These functions are defined in the same scope, so they should be accessible
            show_slice()
        except (NameError, Exception) as e:
            print(f"⚠️ Could not refresh Plot2: {e}")

        try:
            show_slice_b()
        except (NameError, Exception) as e:
            print(f"⚠️ Could not refresh Plot2B: {e}")

    clear_cache_button.on_click(on_clear_cache)

    # Build tools items list (needed for layout)
    # Note: Range inputs are now above each plot, not in tools column
    tools_items = [
        back_to_selection_button,
        clear_cache_button,
        session_section,
        palette_section,
        plot1_shape_section,
        plot2_shape_section,  # Plot2 width/height controls
        plot2b_shape_section,  # Plot2B width/height controls (only shown if plot2b exists)
        probe_scale_section,  # Probe Scale control for Plot2 and Plot2b
        # Color scale selectors are now inline with range toggles, not in tools_items
    ]

    # Note: compute_plot3_button and compute_plot3_from_plot2b_button are now added to plot2_items
    # (between plot2 and plot2b range) instead of tools_items

    tools_items.extend([
        create_div(text="<hr>", width=400),
        status_div,
    ])

    # Track which volume Plot3 was computed from ('volume' or 'volume_b')
    # This is used by compute_plot2_from_plot3() to use the correct source volume
    # Use a mutable container to avoid nonlocal issues when code is executed via exec()
    plot3_source_volume = ['volume']  # Default to main volume (use list for mutability)

    # Function to compute Plot3 from Plot2 selection
    def compute_plot3_from_plot2():
        """Compute Plot3 image by summing over selected Z,U range in Plot2."""
        from bokeh.io import curdoc

        # Update button text IMMEDIATELY before any computation
        original_button_label = compute_plot3_button.label
        compute_plot3_button.label = "Computing ..."
        compute_plot3_button.disabled = True

        # Schedule the actual computation in the next tick so button update is visible first
        def do_computation():
            import time as _time
            t_start = _time.time()
            print("=" * 80)
            print("🔍 DEBUG: compute_plot3_from_plot2() called")
            print(f"  rect2: min_x={rect2.min_x}, max_x={rect2.max_x}, min_y={rect2.min_y}, max_y={rect2.max_y}")
            if box_annotation_2 is not None:
                print(f"  box_annotation_2: left={box_annotation_2.left}, right={box_annotation_2.right}, bottom={box_annotation_2.bottom}, top={box_annotation_2.top}")
            print(f"  Volume shape: {volume.shape}")
            print(f"  Volume size (MB): {volume.nbytes / (1024*1024):.2f}")

            # Get selection from BoxSelectTool using utility function
            # This handles selection_trigger_source, BoxSelectTool overlay, geometry, box_annotation, and rect fallbacks
            # plot2_selection_trigger is accessible via closure (defined in outer create_dashboard function)
            try:
                plot2_trigger = plot2_selection_trigger
            except NameError:
                plot2_trigger = None
            
            selection_left, selection_right, selection_bottom, selection_top = get_box_select_selection(
                plot2, box_annotation_2, rect2, 
                selection_trigger_source=plot2_trigger,
                debug=True
            )
            
            # Use selection values (utility function handles all fallbacks)
            left_val = selection_left
            right_val = selection_right
            bottom_val = selection_bottom
            top_val = selection_top

            print(f"  is_3d_volume: {is_3d_volume}")
            print(f"  volume.shape: {volume.shape}")
            print(f"  len(volume.shape): {len(volume.shape)}")

            try:
                # Check if we have valid selection values
                use_box_annotation = (left_val is not None and right_val is not None and 
                                     bottom_val is not None and top_val is not None and
                                     not (np.isnan(left_val) or np.isnan(right_val) or 
                                          np.isnan(bottom_val) or np.isnan(top_val)))

                # Check volume dimensions and Plot1 mode
                is_actually_3d = len(volume.shape) == 3
                # When Plot1 is 1D and volume is 3D, treat it like 4D (Plot2 shows 2D slice)
                if is_actually_3d and plot1_is_1d:
                    # When Plot1 is 1D, 3D volume (x,z,u) means Plot2 shows (z,u)
                    # Sum over selected (z,u) region to get 1D result (x)
                    # This is handled in the 4D path below
                    is_actually_3d = False  # Use 4D path logic
                
                if is_actually_3d:
                    # Normal 3D case: When Plot1 is 2D, 3D volume means Plot2 shows 1D probe
                    # Sum over Z dimension for selected range to get 2D (x,y)
                    if use_box_annotation:
                        # Convert annotation coordinates to indices (use extracted values)
                        if hasattr(self.process_4dnexus, 'probe_x_coords_picked') and self.process_4dnexus.probe_x_coords_picked:
                            try:
                                probe_coords = self.process_4dnexus.load_probe_coordinates()
                                if probe_coords is not None and len(probe_coords) > 0 and left_val is not None and right_val is not None:
                                    z1_idx = int(np.argmin(np.abs(probe_coords - left_val)))
                                    z2_idx = int(np.argmin(np.abs(probe_coords - right_val)))
                                else:
                                    z1_idx = int(left_val) if left_val is not None and not np.isnan(left_val) else 0
                                    z2_idx = int(right_val) if right_val is not None and not np.isnan(right_val) else volume.shape[2]-1
                            except Exception:
                                z1_idx = int(left_val) if left_val is not None and not np.isnan(left_val) else 0
                                z2_idx = int(right_val) if right_val is not None and not np.isnan(right_val) else volume.shape[2]-1
                        else:
                            z1_idx = int(left_val) if left_val is not None and not np.isnan(left_val) else 0
                            z2_idx = int(right_val) if right_val is not None and not np.isnan(right_val) else volume.shape[2]-1
                        z_lo, z_hi = (z1_idx, z2_idx) if z1_idx <= z2_idx else (z2_idx, z1_idx)
                    else:
                        # Use rect2 values
                        z1, z2 = rect2.min_x, rect2.max_x
                        z_lo, z_hi = (int(z1), int(z2)) if z1 <= z2 else (int(z2), int(z1))

                    z_lo = max(0, min(z_lo, volume.shape[2]-1))
                    z_hi = max(0, min(z_hi, volume.shape[2]-1))
                    if z_hi <= z_lo:
                        z_hi = min(z_lo + 1, volume.shape[2])

                    print(f"  ✅ Using Z range: {z_lo} to {z_hi}")
                    # Normal 3D case: sum over Z dimension to get 2D (x,y)
                    piece = volume[:, :, z_lo:z_hi]
                    img = np.sum(piece, axis=2)  # sum over Z dimension
                else:
                    # For 4D: sum over Z and U dimensions (box annotation is 2D: x=U, y=Z)
                    if use_box_annotation:
                        # Box annotation coordinates are in plot space (x=U dimension, y=Z dimension)
                        # Convert annotation coordinates to volume indices
                        plot2_x_coords = probe_2d_plot.get_flipped_x_coords()
                        plot2_y_coords = probe_2d_plot.get_flipped_y_coords()

                        # Use the extracted numeric values (left_val, right_val, bottom_val, top_val)
                        # Convert x coordinates (U dimension) to indices
                        if plot2_x_coords is not None and len(plot2_x_coords) > 0 and left_val is not None and right_val is not None:
                            u1_idx = int(np.argmin(np.abs(plot2_x_coords - left_val)))
                            u2_idx = int(np.argmin(np.abs(plot2_x_coords - right_val)))
                        else:
                            u1_idx = int(left_val) if left_val is not None and not np.isnan(left_val) else 0
                            u2_idx = int(right_val) if right_val is not None and not np.isnan(right_val) else u_size-1

                        # Convert y coordinates (Z dimension) to indices
                        if plot2_y_coords is not None and len(plot2_y_coords) > 0 and bottom_val is not None and top_val is not None:
                            z1_idx = int(np.argmin(np.abs(plot2_y_coords - bottom_val)))
                            z2_idx = int(np.argmin(np.abs(plot2_y_coords - top_val)))
                        else:
                            z1_idx = int(bottom_val) if bottom_val is not None and not np.isnan(bottom_val) else 0
                            z2_idx = int(top_val) if top_val is not None and not np.isnan(top_val) else volume.shape[2]-1

                        # Ensure indices are in correct order
                        z_lo, z_hi = (z1_idx, z2_idx) if z1_idx <= z2_idx else (z2_idx, z1_idx)
                        u_lo, u_hi = (u1_idx, u2_idx) if u1_idx <= u2_idx else (u2_idx, u1_idx)

                        print(f"  🔍 Converted to indices: z_lo={z_lo}, z_hi={z_hi}, u_lo={u_lo}, u_hi={u_hi}")
                    else:
                        # Use rect2 values (fallback when box_annotation is not available)
                        plot2_needs_flip = probe_2d_plot.needs_flip if hasattr(probe_2d_plot, 'needs_flip') else False
                        if plot2_needs_flip:
                            z1, z2 = rect2.min_x, rect2.max_x
                            u1, u2 = rect2.min_y, rect2.max_y
                        else:
                            z1, z2 = rect2.min_x, rect2.max_x
                            u1, u2 = rect2.min_y, rect2.max_y

                        z_lo, z_hi = (int(z1), int(z2)) if z1 <= z2 else (int(z2), int(z1))
                        u_lo, u_hi = (int(u1), int(u2)) if u1 <= u2 else (int(u2), int(u1))

                    z_lo = max(0, min(z_lo, z_size-1))
                    z_hi = max(0, min(z_hi, z_size-1))
                    u_lo = max(0, min(u_lo, u_size-1))
                    u_hi = max(0, min(u_hi, u_size-1))
                    if z_hi <= z_lo:
                        z_hi = min(z_lo + 1, z_size)
                    if u_hi <= u_lo:
                        u_hi = min(u_lo + 1, u_size)

                    print(f"  ✅ Using Z range: {z_lo} to {z_hi}, U range: {u_lo} to {u_hi}")

                    # Debug: Check if we're using the full volume (which would be slow)
                    z_range_size = z_hi - z_lo
                    u_range_size = u_hi - u_lo
                    z_total = z_size
                    u_total = u_size
                    z_percent = (z_range_size / z_total * 100) if z_total > 0 else 0
                    u_percent = (u_range_size / u_total * 100) if u_total > 0 else 0
                    print(f"  📊 Selection size: Z={z_range_size}/{z_total} ({z_percent:.1f}%), U={u_range_size}/{u_total} ({u_percent:.1f}%)")

                    if z_range_size == z_total and u_range_size == u_total:
                        print(f"  ⚠️ WARNING: Using FULL volume! This will be slow. Check selection bounds.")
                    elif z_percent > 50 or u_percent > 50:
                        print(f"  ⚠️ WARNING: Using large portion of volume ({z_percent:.1f}% Z, {u_percent:.1f}% U). This may be slow.")
                    else:
                        print(f"  ✅ Using small selection ({z_percent:.1f}% Z, {u_percent:.1f}% U). Should be fast.")

                    # Extract only the selected region (this should be fast if bounds are correct)
                    t_slice = time.time()
                    if len(volume.shape) == 3 and plot1_is_1d:
                        # Volume is 3D (x,z,u) when Plot1 is 1D - extract slice at all x positions
                        # Plot2 shows (z,u), so sum over selected (z,u) to get 1D (x)
                        print(f"  🔄 Extracting volume slice: volume[:, {z_lo}:{z_hi}, {u_lo}:{u_hi}]")
                        piece = volume[:, z_lo:z_hi, u_lo:u_hi]
                        print(f"  ⏱️  Slicing took {time.time() - t_slice:.3f}s. Piece shape: {piece.shape}")
                        print(f"  🔄 Summing over Z and U dimensions to get 1D result...")
                        t_sum = time.time()
                        img = np.sum(piece, axis=(1, 2))  # sum over Z and U (axes 1 and 2) to get 1D (x)
                    elif len(volume.shape) == 4:
                        # Normal 4D volume case (x,y,z,u)
                        print(f"  🔄 Extracting volume slice: volume[:, :, {z_lo}:{z_hi}, {u_lo}:{u_hi}]")
                        piece = volume[:, :, z_lo:z_hi, u_lo:u_hi]
                        print(f"  ⏱️  Slicing took {time.time() - t_slice:.3f}s. Piece shape: {piece.shape}")
                        print(f"  🔄 Summing over Z and U dimensions...")
                        t_sum = time.time()
                        img = np.sum(piece, axis=(2, 3))  # sum over Z and U (axes 2 and 3) to get 2D (x,y)
                    else:
                        raise ValueError(f"Unexpected volume shape: {volume.shape}, expected 3D (with Plot1 1D) or 4D")
                    t_slice_done = time.time()
                    t_sum_done = time.time()
                    print(f"  ⏱️  Summing took {t_sum_done - t_sum:.3f}s. Result shape: {img.shape}")

                # Normalize to [0,1]
                img = np.nan_to_num(img, nan=0.0, posinf=0.0, neginf=0.0)
                vmin = float(np.min(img))
                vmax = float(np.max(img))
                if vmax > vmin:
                    img = (img - vmin) / (vmax - vmin)
                else:
                    img = np.zeros_like(img)

                # Apply Plot1's flip state to match Plot1's orientation
                if plot1_needs_flip:
                    img = np.transpose(img)

                # Store image data for update (need to schedule in Bokeh event loop)
                plot3_img_data = img.copy()
                plot3_x_start = plot3.x_range.start
                plot3_x_end = plot3.x_range.end
                plot3_y_start = plot3.y_range.start
                plot3_y_end = plot3.y_range.end
                
                # Track that Plot3 was computed from Plot2a (main volume)
                plot3_source_volume[0] = 'volume'  # Track which volume Plot3 was computed from

                # Update Plot3 based on Plot1 type (1D line plot or 2D image)
                if plot1_is_1d and plot1_1d_plot is not None and source3_1d is not None:
                    # Plot3 should be a 1D line plot when Plot1 is 1D
                    # img is 1D, so create line plot data
                    if len(img.shape) == 1:
                        # Use plot3_x_coords for x-axis
                        plot3_x_data = plot3_x_coords if plot3_x_coords is not None else np.arange(len(img))
                        plot3_y_data = img
                    else:
                        # If somehow 2D, flatten it
                        plot3_x_data = plot3_x_coords if plot3_x_coords is not None else np.arange(img.size)
                        plot3_y_data = img.flatten()
                    
                    # Store original data for log scale transformation
                    plot3_1d_data_original[0] = plot3_y_data.copy() if hasattr(plot3_y_data, 'copy') else np.array(plot3_y_data)
                    
                    # Apply log transformation if enabled
                    if plot3_log_scale_toggle is not None and plot3_log_scale_toggle.active:
                        plot3_y_data = symlog_transform(plot3_y_data)
                    
                    def update_plot3_source_1d():
                        source3_1d.data = {
                            "x": plot3_x_data,
                            "y": plot3_y_data,
                        }
                        # Update y_range to fit the data
                        if len(plot3_y_data) > 0:
                            y_min = float(np.min(plot3_y_data))
                            y_max = float(np.max(plot3_y_data))
                            if y_max > y_min:
                                plot3.y_range.start = y_min - 0.1 * (y_max - y_min)
                                plot3.y_range.end = y_max + 0.1 * (y_max - y_min)
                    
                    # Schedule the update in the next Bokeh tick
                    curdoc().add_next_tick_callback(update_plot3_source_1d)
                else:
                    # Plot3 should be a 2D image when Plot1 is 2D
                    def update_plot3_source():
                        source3.data = {
                            "image": [plot3_img_data],
                            "x": [plot3_x_start],
                            "dw": [plot3_x_end - plot3_x_start],
                            "y": [plot3_y_start],
                            "dh": [plot3_y_end - plot3_y_start],
                        }
                        # Bokeh 3.x automatically detects data changes, no need for change.emit()

                    # Schedule the update in the next Bokeh tick
                    curdoc().add_next_tick_callback(update_plot3_source)

                # Update range based on mode (only for 2D images, not 1D line plots)
                if not (plot1_is_1d and plot1_1d_plot is not None):
                    # Only update color mapper for 2D images
                    try:
                        if range3_min_input is not None and range3_min_input.disabled:
                            # Dynamic mode - compute from actual image data
                            plot3_min = float(np.percentile(plot3_img_data[~np.isnan(plot3_img_data) & ~np.isinf(plot3_img_data)], 1))
                            plot3_max = float(np.percentile(plot3_img_data[~np.isnan(plot3_img_data) & ~np.isinf(plot3_img_data)], 99))
                            if color_mapper3 is not None:
                                color_mapper3.low = plot3_min
                                color_mapper3.high = plot3_max
                            # Update range inputs so user can see the computed values
                            update_range_inputs_safely(
                                range3_min_input, range3_max_input, plot3_min, plot3_max, use_callback=False
                            )
                            print(f"  ✅ Plot3 range updated dynamically: min={plot3_min:.6f}, max={plot3_max:.6f}")
                        else:
                            # User Specified mode - use input values or default [0, 1] for normalized data
                            try:
                                if range3_min_input is not None and range3_min_input.value:
                                    min_val = float(range3_min_input.value)
                                else:
                                    min_val = 0.0
                                if range3_max_input is not None and range3_max_input.value:
                                    max_val = float(range3_max_input.value)
                                else:
                                    max_val = 1.0
                                if color_mapper3 is not None:
                                    color_mapper3.low = min_val
                                    color_mapper3.high = max_val
                            except:
                                if color_mapper3 is not None:
                                    color_mapper3.low = 0.0
                                    color_mapper3.high = 1.0
                    except NameError:
                        # Range inputs not defined yet - use default [0, 1] for normalized data
                        if color_mapper3 is not None:
                            color_mapper3.low = 0.0
                            color_mapper3.high = 1.0

                print(f"  ✅ Plot3 computed successfully. Image shape: {plot3_img_data.shape}")
                t_end = _time.time()
                print(f"  ⏱️  Total computation time: {t_end - t_start:.3f}s")
                print("=" * 80)
            except Exception as e:
                import traceback
                print(f"  ❌ Error computing Plot3: {e}")
                traceback.print_exc()
                print("=" * 80)
            finally:
                # Restore button text and enable it immediately
                compute_plot3_button.label = original_button_label
                compute_plot3_button.disabled = False

        # Schedule computation in next tick so button update is visible first
        curdoc().add_next_tick_callback(do_computation)

    compute_plot3_button.on_click(lambda: compute_plot3_from_plot2())

    # Function to compute Plot3 from Plot2B selection
    def compute_plot3_from_plot2b():
        """Compute Plot3 image by summing over selected Z,U range in Plot2B."""
        from bokeh.io import curdoc

        # Update button text IMMEDIATELY before any computation
        original_button_label_2b = compute_plot3_from_plot2b_button.label
        compute_plot3_from_plot2b_button.label = "Computing ..."
        compute_plot3_from_plot2b_button.disabled = True

        # Schedule the actual computation in the next tick so button update is visible first
        def do_computation_2b():
            import time as _time
            t_start = _time.time()
            print("=" * 80)
            print("🔍 DEBUG: compute_plot3_from_plot2b() called")
            print(f"  rect2b: min_x={rect2b.min_x}, max_x={rect2b.max_x}, min_y={rect2b.min_y}, max_y={rect2b.max_y}")
            if box_annotation_2b is not None:
                print(f"  box_annotation_2b: left={box_annotation_2b.left}, right={box_annotation_2b.right}, bottom={box_annotation_2b.bottom}, top={box_annotation_2b.top}")
            
            # Get selection from BoxSelectTool using utility function
            # plot2b_selection_trigger might not exist (only plot2 has it), so handle gracefully
            try:
                plot2b_trigger = plot2b_selection_trigger
            except NameError:
                plot2b_trigger = None
            
            selection_left_2b, selection_right_2b, selection_bottom_2b, selection_top_2b = get_box_select_selection(
                plot2b, box_annotation_2b, rect2b, 
                selection_trigger_source=plot2b_trigger,
                debug=True
            )
            
            try:
                if not plot2b_is_2d:
                    # Plot2B is 1D - sum over Z dimension
                    if selection_left_2b is not None and selection_right_2b is not None:
                        z1, z2 = selection_left_2b, selection_right_2b
                        print(f"  ✅ Using BoxSelectTool selection (plot2b): z=[{z1}, {z2}]")
                    else:
                        z1, z2 = rect2b.min_x, rect2b.max_x
                        print(f"  ⚠️ Using rect2b (fallback): z=[{z1}, {z2}]")
                    
                    # Determine correct dimension indices based on Plot1 mode and volume_b shape
                    if plot1_is_1d and len(volume_b.shape) == 2:
                        # When Plot1 is 1D and volume_b is 2D (x,z), Plot2B shows 1D (z)
                        # Sum over z to get 1D (x)
                        z_lo, z_hi = (int(z1), int(z2)) if z1 <= z2 else (int(z2), int(z1))
                        z_lo = max(0, min(z_lo, volume_b.shape[1]-1))
                        z_hi = max(0, min(z_hi, volume_b.shape[1]-1))
                        if z_hi <= z_lo:
                            z_hi = min(z_lo + 1, volume_b.shape[1])
                        piece = volume_b[:, z_lo:z_hi]
                        img = np.sum(piece, axis=1)  # sum over z to get 1D (x)
                    else:
                        # Normal 3D case: volume_b is (x,y,z), sum over z to get 2D (x,y)
                        z_lo, z_hi = (int(z1), int(z2)) if z1 <= z2 else (int(z2), int(z1))
                        z_lo = max(0, min(z_lo, volume_b.shape[2]-1))
                        z_hi = max(0, min(z_hi, volume_b.shape[2]-1))
                        if z_hi <= z_lo:
                            z_hi = min(z_lo + 1, volume_b.shape[2])
                        piece = volume_b[:, :, z_lo:z_hi]
                        img = np.sum(piece, axis=2)  # sum over z to get 2D (x,y)
                else:
                    # Plot2B is 2D - sum over Z and U dimensions
                    plot2b_needs_flip = probe_2d_plot_b.needs_flip if hasattr(probe_2d_plot_b, 'needs_flip') else False
                    
                    # Use BoxSelectTool selection if available
                    if (selection_left_2b is not None and selection_right_2b is not None and 
                        selection_bottom_2b is not None and selection_top_2b is not None):
                        # Selection coordinates are in plot space
                        if plot2b_needs_flip:
                            z1, z2 = selection_left_2b, selection_right_2b
                            u1, u2 = selection_bottom_2b, selection_top_2b
                        else:
                            z1, z2 = selection_left_2b, selection_right_2b
                            u1, u2 = selection_bottom_2b, selection_top_2b
                        print(f"  ✅ Using BoxSelectTool selection (plot2b): z=[{z1}, {z2}], u=[{u1}, {u2}]")
                    else:
                        # Fallback to rect2b
                        if plot2b_needs_flip:
                            z1, z2 = rect2b.min_x, rect2b.max_x
                            u1, u2 = rect2b.min_y, rect2b.max_y
                        else:
                            z1, z2 = rect2b.min_x, rect2b.max_x
                            u1, u2 = rect2b.min_y, rect2b.max_y
                        print(f"  ⚠️ Using rect2b (fallback): z=[{z1}, {z2}], u=[{u1}, {u2}]")

                    z_lo, z_hi = (int(z1), int(z2)) if z1 <= z2 else (int(z2), int(z1))
                    u_lo, u_hi = (int(u1), int(u2)) if u1 <= u2 else (int(u2), int(u1))
                    
                    # Determine correct dimension indices based on Plot1 mode and volume_b shape
                    if plot1_is_1d and len(volume_b.shape) == 3:
                        # When Plot1 is 1D and volume_b is 3D (x,z,u), Plot2B shows 2D (z,u)
                        # Sum over (z,u) to get 1D (x)
                        z_lo = max(0, min(z_lo, volume_b.shape[1]-1))
                        z_hi = max(0, min(z_hi, volume_b.shape[1]-1))
                        u_lo = max(0, min(u_lo, volume_b.shape[2]-1))
                        u_hi = max(0, min(u_hi, volume_b.shape[2]-1))
                        if z_hi <= z_lo:
                            z_hi = min(z_lo + 1, volume_b.shape[1])
                        if u_hi <= u_lo:
                            u_hi = min(u_lo + 1, volume_b.shape[2])
                        piece = volume_b[:, z_lo:z_hi, u_lo:u_hi]
                        img = np.sum(piece, axis=(1, 2))  # sum over z and u to get 1D (x)
                    else:
                        # Normal 4D case: volume_b is (x,y,z,u), sum over (z,u) to get 2D (x,y)
                        z_lo = max(0, min(z_lo, volume_b.shape[2]-1))
                        z_hi = max(0, min(z_hi, volume_b.shape[2]-1))
                        u_lo = max(0, min(u_lo, volume_b.shape[3]-1))
                        u_hi = max(0, min(u_hi, volume_b.shape[3]-1))
                        if z_hi <= z_lo:
                            z_hi = min(z_lo + 1, volume_b.shape[2])
                        if u_hi <= u_lo:
                            u_hi = min(u_lo + 1, volume_b.shape[3])
                        piece = volume_b[:, :, z_lo:z_hi, u_lo:u_hi]
                        img = np.sum(piece, axis=(2, 3))  # sum over z and u to get 2D (x,y)

                # Normalize to [0,1]
                img = np.nan_to_num(img, nan=0.0, posinf=0.0, neginf=0.0)
                vmin = float(np.min(img))
                vmax = float(np.max(img))
                if vmax > vmin:
                    img = (img - vmin) / (vmax - vmin)
                else:
                    img = np.zeros_like(img)

                # Apply Plot1's flip state to match Plot1's orientation
                if plot1_needs_flip:
                    img = np.transpose(img)

                # Store image data for update (need to schedule in Bokeh event loop)
                plot3_img_data_2b = img.copy()
                plot3_x_start_2b = plot3.x_range.start
                plot3_x_end_2b = plot3.x_range.end
                plot3_y_start_2b = plot3.y_range.start
                plot3_y_end_2b = plot3.y_range.end
                
                # Track that Plot3 was computed from Plot2b (volume_b)
                plot3_source_volume[0] = 'volume_b'  # Track which volume Plot3 was computed from

                # Update Plot3 based on Plot1 type (1D line plot or 2D image)
                if plot1_is_1d and plot1_1d_plot is not None and source3_1d is not None:
                    # Plot3 should be a 1D line plot when Plot1 is 1D
                    # img is 1D, so create line plot data
                    if len(img.shape) == 1:
                        # Use plot3_x_coords for x-axis
                        plot3_x_data_2b = plot3_x_coords if plot3_x_coords is not None else np.arange(len(img))
                        plot3_y_data_2b = img
                    else:
                        # If somehow 2D, flatten it
                        plot3_x_data_2b = plot3_x_coords if plot3_x_coords is not None else np.arange(img.size)
                        plot3_y_data_2b = img.flatten()
                    
                    # Store original data for log scale transformation
                    plot3_1d_data_original[0] = plot3_y_data_2b.copy() if hasattr(plot3_y_data_2b, 'copy') else np.array(plot3_y_data_2b)
                    
                    # Apply log transformation if enabled
                    if plot3_log_scale_toggle is not None and plot3_log_scale_toggle.active:
                        plot3_y_data_2b = symlog_transform(plot3_y_data_2b)
                    
                    def update_plot3_source_2b_1d():
                        source3_1d.data = {
                            "x": plot3_x_data_2b,
                            "y": plot3_y_data_2b,
                        }
                        # Update y_range to fit the data
                        if len(plot3_y_data_2b) > 0:
                            y_min = float(np.min(plot3_y_data_2b))
                            y_max = float(np.max(plot3_y_data_2b))
                            if y_max > y_min:
                                plot3.y_range.start = y_min - 0.1 * (y_max - y_min)
                                plot3.y_range.end = y_max + 0.1 * (y_max - y_min)
                    
                    # Schedule the update in the next Bokeh tick
                    curdoc().add_next_tick_callback(update_plot3_source_2b_1d)
                else:
                    # Plot3 should be a 2D image when Plot1 is 2D
                    def update_plot3_source_2b():
                        source3.data = {
                            "image": [plot3_img_data_2b],
                            "x": [plot3_x_start_2b],
                            "dw": [plot3_x_end_2b - plot3_x_start_2b],
                            "y": [plot3_y_start_2b],
                            "dh": [plot3_y_end_2b - plot3_y_start_2b],
                        }
                        # Bokeh 3.x automatically detects data changes, no need for change.emit()

                    # Schedule the update in the next Bokeh tick
                    curdoc().add_next_tick_callback(update_plot3_source_2b)

                # Update range based on mode (only for 2D images, not 1D line plots)
                if not (plot1_is_1d and plot1_1d_plot is not None):
                    # Only update color mapper for 2D images
                    try:
                        if range3_min_input is not None and range3_min_input.disabled:
                            # Dynamic mode - compute from actual image data
                            plot3_min = float(np.percentile(plot3_img_data_2b[~np.isnan(plot3_img_data_2b) & ~np.isinf(plot3_img_data_2b)], 1))
                            plot3_max = float(np.percentile(plot3_img_data_2b[~np.isnan(plot3_img_data_2b) & ~np.isinf(plot3_img_data_2b)], 99))
                            if color_mapper3 is not None:
                                color_mapper3.low = plot3_min
                                color_mapper3.high = plot3_max
                            # Update range inputs so user can see the computed values
                            update_range_inputs_safely(
                                range3_min_input, range3_max_input, plot3_min, plot3_max, use_callback=False
                            )
                            print(f"  ✅ Plot3 range updated dynamically: min={plot3_min:.6f}, max={plot3_max:.6f}")
                        else:
                            # User Specified mode - use input values or default [0, 1] for normalized data
                            try:
                                if range3_min_input is not None and range3_min_input.value:
                                    min_val = float(range3_min_input.value)
                                else:
                                    min_val = 0.0
                                if range3_max_input is not None and range3_max_input.value:
                                    max_val = float(range3_max_input.value)
                                else:
                                    max_val = 1.0
                                if color_mapper3 is not None:
                                    color_mapper3.low = min_val
                                    color_mapper3.high = max_val
                            except:
                                if color_mapper3 is not None:
                                    color_mapper3.low = 0.0
                                    color_mapper3.high = 1.0
                    except NameError:
                        # Range inputs not defined yet - use default [0, 1] for normalized data
                        if color_mapper3 is not None:
                            color_mapper3.low = 0.0
                            color_mapper3.high = 1.0

                print(f"  ✅ Plot3 computed successfully from Plot2B. Image shape: {plot3_img_data_2b.shape}")
            except Exception as e:
                import traceback
                print(f"  ❌ Error computing Plot3 from Plot2B: {e}")
                traceback.print_exc()
            finally:
                # Restore button text and enable it
                if compute_plot3_from_plot2b_button is not None:
                    compute_plot3_from_plot2b_button.label = original_button_label_2b
                    compute_plot3_from_plot2b_button.disabled = False

        # Schedule computation in next tick so button update is visible first
        curdoc().add_next_tick_callback(do_computation_2b)

    if compute_plot3_from_plot2b_button is not None:
        compute_plot3_from_plot2b_button.on_click(lambda: compute_plot3_from_plot2b())

    # Create buttons to compute Plot2a and Plot2b from Plot3 selection
    compute_plot2a_from_plot3_button = create_button(
        label="Recompute Probe1",
        button_type="success",
        width=200
    )

    compute_plot2b_from_plot3_button = None
    if plot2b is not None:
        compute_plot2b_from_plot3_button = create_button(
            label="Recompute Probe2",
            button_type="success",
            width=200
        )

    # Connect button click handlers
    compute_plot2a_from_plot3_button.on_click(lambda: compute_plot2_from_plot3())
    if compute_plot2b_from_plot3_button is not None:
        compute_plot2b_from_plot3_button.on_click(lambda: compute_plot2b_from_plot3())
    
    # Add buttons to range3_section (under Linear/Log selector)
    # Wrap buttons in a row for proper layout
    if range3_section is not None:
        button_items = [compute_plot2a_from_plot3_button]
        if compute_plot2b_from_plot3_button is not None:
            button_items.append(compute_plot2b_from_plot3_button)
        range3_section.children.append(row(*button_items, spacing=5))

    # Add TapTool to Plot3 for region selection
    tap_tool3 = TapTool()
    plot3.add_tools(tap_tool3)

    # Tap handler for Plot3 to update crosshairs and optionally set selection region
    def on_plot3_tap(event):
        """Handle tap events on Plot3 to update crosshair position (synchronized with Plot1) and optionally set selection region."""
        # First, update crosshairs (same as Plot1)
        if hasattr(event, 'x') and hasattr(event, 'y'):
            # Find closest indices in the flipped coordinate arrays (same as Plot1)
            x_idx = np.argmin(np.abs(plot3_x_coords - event.x))
            # When Plot1 is 1D, plot3_y_coords is None, so use index-based coordinates
            if plot3_y_coords is not None:
                y_idx = np.argmin(np.abs(plot3_y_coords - event.y))
            else:
                # When Plot1 is 1D, y-axis is index-based (0 to shape[0]-1)
                # Use plot1_1d_data if available, otherwise fallback
                if plot1_is_1d and plot1_1d_data is not None:
                    data_shape_0 = plot1_1d_data.shape[0]
                elif plot1_data is not None:
                    data_shape_0 = plot1_data.shape[0]
                else:
                    data_shape_0 = len(plot1_x_coords) if plot1_x_coords is not None else 1
                y_idx = max(0, min(int(round(event.y)), data_shape_0 - 1))

            # Convert back to original coordinate space for sliders
            # Sliders use original x_coords and y_coords (not flipped)
            # Temporarily disable state saves to prevent multiple saves
            _skip_slider_state_save["value"] = True
            
            try:
                # Update both sliders (handlers will update plots but won't save state)
                # When Plot1 is 1D, y_coords is None, so only update x_slider
                if y_coords is None:
                    # Plot1 is 1D - only update x_slider
                    x_slider.value = x_coords[x_idx] if x_idx < len(x_coords) else x_coords[-1]
                elif map_plot.needs_flip:
                    # When flipped: plot3_x_coords is actually y_coords, plot3_y_coords is actually x_coords
                    x_slider.value = y_coords[y_idx] if y_idx < len(y_coords) else y_coords[-1]
                    y_slider.value = x_coords[x_idx] if x_idx < len(x_coords) else x_coords[-1]
                else:
                    # Not flipped: plot3_x_coords is x_coords, plot3_y_coords is y_coords
                    x_slider.value = x_coords[x_idx] if x_idx < len(x_coords) else x_coords[-1]
                    y_slider.value = y_coords[y_idx] if y_idx < len(y_coords) else y_coords[-1]
                
                # Slider change handlers will automatically call draw_cross1() (which also calls draw_cross3()) and show_slice()
                # Save state once for both slider changes (after both are updated)
                debounced_save_state("Plot3 clicked (both sliders changed)", update_undo_redo=True)
            finally:
                _skip_slider_state_save["value"] = False
        
        # Also handle selection region if modifier keys are pressed
        x_coord = event.x
        y_coord = event.y

        if plot1_needs_flip:
            # When flipped, swap coordinates
            temp_x = y_coord
            temp_y = x_coord
            x_coord = temp_x
            y_coord = temp_y

        if event.modifiers.get("shift", False):
            # Shift+click: Set min values only
            rect3.set(min_x=x_coord, min_y=y_coord)
            draw_rect3()
        elif event.modifiers.get("ctrl", False) or event.modifiers.get('meta', False) or event.modifiers.get('cmd', False):
            # Ctrl/Cmd+click: Set max values only
            rect3.set(max_x=x_coord, max_y=y_coord)
            draw_rect3()
        elif event.modifiers.get("alt", False):
            # Alt+click: Clear and set both min and max to same value (selection region)
            clear_rect(plot3, rect3)
            rect3.set(min_x=x_coord, min_y=y_coord, max_x=x_coord, max_y=y_coord)
            draw_rect(plot3, rect3, x_coord, x_coord, y_coord, y_coord)
            # Compute Plot2 from Plot3 selection
            compute_plot2_from_plot3()

    # Function to draw rect3 on Plot3
    def draw_rect3():
        """Draw selection rectangle on Plot3."""
        draw_rect(plot3, rect3, rect3.min_x, rect3.max_x, rect3.min_y, rect3.max_y)

    # Function to compute Plot2 from Plot3 selection
    def compute_plot2_from_plot3():
        """Compute Plot2a by summing over selected X,Y region in Plot3."""
        from bokeh.io import curdoc

        # Update button text IMMEDIATELY before any computation
        original_button_label_2a = compute_plot2a_from_plot3_button.label
        compute_plot2a_from_plot3_button.label = "Computing ..."
        compute_plot2a_from_plot3_button.disabled = True

        # Schedule the actual computation in the next tick so button update is visible first
        def do_computation_2a():
            import time as _time
            t_start = _time.time()
            print("=" * 80)
            print("🔍 DEBUG: compute_plot2_from_plot3() called")
            print(f"  rect3: min_x={rect3.min_x}, max_x={rect3.max_x}, min_y={rect3.min_y}, max_y={rect3.max_y}")
            if box_annotation_3 is not None:
                print(f"  box_annotation_3: left={box_annotation_3.left}, right={box_annotation_3.right}, bottom={box_annotation_3.bottom}, top={box_annotation_3.top}")

            # Get selection from BoxSelectTool using utility function
            # plot3_selection_trigger might not exist, so handle gracefully
            try:
                plot3_trigger = plot3_selection_trigger
            except NameError:
                plot3_trigger = None
            
            selection_left_3, selection_right_3, selection_bottom_3, selection_top_3 = get_box_select_selection(
                plot3, box_annotation_3, rect3,
                selection_trigger_source=plot3_trigger,
                debug=True
            )

            try:
                # Get selection from BoxSelectTool using utility function
                # This handles BoxSelectTool overlay, geometry, box_annotation, and rect fallbacks
                selection_left_3, selection_right_3, selection_bottom_3, selection_top_3 = get_box_select_selection(
                    plot3, box_annotation_3, rect3, debug=True
                )

                # Use selection values (utility function handles all fallbacks)
                use_box_annotation_3 = (selection_left_3 is not None and selection_right_3 is not None and 
                                       selection_bottom_3 is not None and selection_top_3 is not None and
                                       not (np.isnan(selection_left_3) or np.isnan(selection_right_3) or 
                                            np.isnan(selection_bottom_3) or np.isnan(selection_top_3)))
                
                if use_box_annotation_3:
                    x1_coord = min(selection_left_3, selection_right_3)
                    x2_coord = max(selection_left_3, selection_right_3)
                    y1_coord = min(selection_bottom_3, selection_top_3)
                    y2_coord = max(selection_bottom_3, selection_top_3)
                    print(f"  ✅ Using selection: x=[{x1_coord}, {x2_coord}], y=[{y1_coord}, {y2_coord}]")
                else:
                    # Fallback to rect3 (shouldn't happen as utility handles this, but keep for safety)
                    x1_coord = rect3.min_x
                    x2_coord = rect3.max_x
                    y1_coord = rect3.min_y
                    y2_coord = rect3.max_y
                    print(f"  ⚠️ Using rect3 fallback: x=[{x1_coord}, {x2_coord}], y=[{y1_coord}, {y2_coord}]")

                # Determine which volume to use based on Plot3's source
                # Plot3 can be computed from Plot2a (volume) or Plot2b (volume_b)
                # plot3_source_volume tracks which volume was used to compute Plot3
                plot3_volume = volume  # Default to main volume
                plot3_use_b = False
                
                # Check which source Plot3 was computed from
                # plot3_source_volume is a list container to avoid nonlocal issues
                try:
                    if plot3_source_volume[0] == 'volume_b':
                        # Plot3 was computed from Plot2b, so use volume_b
                        # volume_b should be accessible from closure
                        try:
                            if volume_b is not None:
                                plot3_volume = volume_b
                                plot3_use_b = True
                                print(f"  📊 Using volume_b for Plot2 computation (Plot3 was computed from Plot2b)")
                            else:
                                print(f"  ⚠️ WARNING: Plot3 was computed from Plot2b but volume_b is None, using main volume")
                        except NameError:
                            print(f"  ⚠️ WARNING: Plot3 was computed from Plot2b but volume_b is not defined, using main volume")
                    else:
                        # Plot3 was computed from Plot2a, use main volume
                        print(f"  📊 Using main volume for Plot2 computation (Plot3 was computed from Plot2a, source='{plot3_source_volume[0]}')")
                except NameError:
                    # If tracking variable doesn't exist, default to main volume
                    print(f"  📊 Using main volume for Plot2 computation (Plot3 source not tracked)")
                except Exception as e:
                    print(f"  ⚠️ WARNING: Error checking Plot3 source: {e}, using main volume")
                
                # Use the new utility function to compute 2D plot from 3D section
                def load_probe_coords():
                    """Helper to load probe coordinates."""
                    if plot3_use_b:
                        # Use Plot2b probe coordinates
                        if hasattr(self.process_4dnexus, 'probe_x_coords_picked_b') and self.process_4dnexus.probe_x_coords_picked_b:
                            try:
                                return self.process_4dnexus.load_probe_coordinates(use_b=True)
                            except:
                                return None
                    else:
                        # Use Plot2a probe coordinates
                        if hasattr(self.process_4dnexus, 'probe_x_coords_picked') and self.process_4dnexus.probe_x_coords_picked:
                            try:
                                return self.process_4dnexus.load_probe_coordinates()
                            except:
                                return None
                    return None

                slice, x_coords_1d = compute_2d_plot_from_3d_section(
                    volume=plot3_volume,  # Use the correct volume based on Plot3's source
                    x1_coord=x1_coord,
                    y1_coord=y1_coord,
                    x2_coord=x2_coord,
                    y2_coord=y2_coord,
                    get_x_index=get_x_index,
                    get_y_index=get_y_index,
                    is_3d_volume=is_3d_volume,
                    probe_coords_loader=load_probe_coords,
                    use_b=plot3_use_b,
                )

                # Convert coordinates to indices for logging
                x1 = get_x_index(x1_coord)
                y1 = get_y_index(y1_coord)
                x2 = max(x1 + 1, get_x_index(x2_coord))
                y2 = max(y1 + 1, get_y_index(y2_coord))

                print(f"  📊 Converted to indices: x=[{x1}, {x2}], y=[{y1}, {y2}]")
                print(f"  📊 Selection size: X={x2-x1}/{plot3_volume.shape[0]} ({((x2-x1)/plot3_volume.shape[0]*100):.1f}%), Y={y2-y1}/{plot3_volume.shape[1]} ({((y2-y1)/plot3_volume.shape[1]*100):.1f}%)")

                if is_3d_volume:
                    # Update 1D plot
                    source2.data = {"x": x_coords_1d, "y": slice}
                    # Explicitly trigger change event to ensure plot updates
                    try:
                        source2.change.emit()
                    except:
                        pass  # Bokeh 3.x should auto-detect, but emit() ensures immediate update
                    plot2.x_range.start = float(np.min(x_coords_1d))
                    plot2.x_range.end = float(np.max(x_coords_1d))
                    plot2.y_range.start = float(np.min(slice))
                    plot2.y_range.end = float(np.max(slice))
                    print(f"  ✅ Updated Plot2 (1D): len={len(slice)}, range=[{float(np.min(slice)):.3f}, {float(np.max(slice)):.3f}]")
                else:
                    # For 4D volumes: Apply flipping if needed (matching old behavior)
                    # Recalculate flip state based on the actual volume being used
                    # Get probe coordinate sizes for the volume we're using
                    if plot3_use_b:
                        # Using volume_b - get its probe coordinate sizes
                        probe_x_coord_size_b = None
                        probe_y_coord_size_b = None
                        if hasattr(self.process_4dnexus, 'probe_x_coords_picked_b') and self.process_4dnexus.probe_x_coords_picked_b:
                            try:
                                probe_x_coords_b = self.process_4dnexus.load_dataset_by_path(self.process_4dnexus.probe_x_coords_picked_b)
                                if probe_x_coords_b is not None:
                                    probe_x_coord_size_b = len(probe_x_coords_b) if hasattr(probe_x_coords_b, '__len__') else None
                            except:
                                pass
                        if hasattr(self.process_4dnexus, 'probe_y_coords_picked_b') and self.process_4dnexus.probe_y_coords_picked_b:
                            try:
                                probe_y_coords_b = self.process_4dnexus.load_dataset_by_path(self.process_4dnexus.probe_y_coords_picked_b)
                                if probe_y_coords_b is not None:
                                    probe_y_coord_size_b = len(probe_y_coords_b) if hasattr(probe_y_coords_b, '__len__') else None
                            except:
                                pass
                        # Recalculate flip state for volume_b
                        plot2_needs_flip = self.process_4dnexus.detect_probe_flip_needed(
                            plot3_volume.shape,
                            probe_x_coord_size_b,
                            probe_y_coord_size_b
                        )
                        print(f"  🔍 Recalculated plot2_needs_flip for volume_b: {plot2_needs_flip}")
                    else:
                        # Using main volume - use stored flip state
                        plot2_needs_flip = getattr(self.process_4dnexus, 'plot2_needs_flip', False)
                        print(f"  🔍 Using stored plot2_needs_flip: {plot2_needs_flip}")
                    
                    print(f"  📊 Slice shape before flip: {slice.shape} (should be Z, U)")
                    if plot2_needs_flip:
                        slice = np.transpose(slice)
                        print(f"  🔄 Applied transpose, slice shape after flip: {slice.shape} (now U, Z)")
                    else:
                        print(f"  ✅ No flip needed, slice shape: {slice.shape} (Z, U)")
                    
                    # Bokeh image() expects: data.shape[0] = rows (height/dh), data.shape[1] = cols (width/dw)
                    # So dw and dh should match the actual slice shape after any transpose
                    dw = float(slice.shape[1])  # width = columns = x-axis
                    dh = float(slice.shape[0])  # height = rows = y-axis
                    print(f"  📊 Final slice shape: {slice.shape}, dw={dw} (width/cols), dh={dh} (height/rows)")

                    # Use simple positioning like old code: x=[0], y=[0] with shape-based dimensions
                    source2.data = {
                        "image": [slice],
                        "x": [0.0],
                        "y": [0.0],
                        "dw": [dw],
                        "dh": [dh],
                    }
                    # Explicitly trigger change event to ensure plot updates
                    try:
                        source2.change.emit()
                    except:
                        pass  # Bokeh 3.x should auto-detect, but emit() ensures immediate update
                    
                    # Update plot ranges to match slice dimensions (0 to shape size)
                    plot2.x_range.start = 0.0
                    plot2.x_range.end = dw
                    plot2.y_range.start = 0.0
                    plot2.y_range.end = dh
                    
                    # Calculate percentile range using SCLib utility
                    probe_min, probe_max = calculate_percentile_range(slice)
                    
                    # Update color mapper (matching old behavior)
                    if color_mapper2 is not None:
                        color_mapper2.low = probe_min
                        color_mapper2.high = probe_max
                        # Force color mapper update by triggering change
                        try:
                            color_mapper2.change.emit()
                        except:
                            pass
                    
                    # Update numeric range inputs to percentile-based data range (matching old behavior)
                    try:
                        if 'range2_min_input' in locals() and range2_min_input is not None:
                            range2_min_input.value = str(probe_min)
                        if 'range2_max_input' in locals() and range2_max_input is not None:
                            range2_max_input.value = str(probe_max)
                    except Exception:
                        pass
                    
                    # Update image renderer if it exists to ensure visual refresh
                    try:
                        if 'image_renderer2' in locals() and image_renderer2 is not None:
                            # The renderer should automatically update when source2.data changes,
                            # but we can force a refresh by updating the glyph
                            if hasattr(image_renderer2, 'glyph'):
                                # Update glyph data source reference
                                image_renderer2.data_source = source2
                    except Exception as e:
                        print(f"  ⚠️ Could not update image_renderer2: {e}")
                    
                    print(f"  ✅ Updated Plot2: shape={slice.shape}, range=[{probe_min:.3f}, {probe_max:.3f}]")
                    print(f"  ✅ Updated Plot2 dimensions: dw={dw}, dh={dh} (flipped={plot2_needs_flip})")
                    print(f"  ✅ Updated Plot2 range inputs: min={probe_min:.3f}, max={probe_max:.3f}")
            except Exception as e:
                import traceback
                print(f"  ❌ Error computing Plot2a from Plot3: {e}")
                traceback.print_exc()
            finally:
                # Restore button text and enable it
                compute_plot2a_from_plot3_button.label = original_button_label_2a
                compute_plot2a_from_plot3_button.disabled = False

        # Schedule computation in next tick so button update is visible first
        curdoc().add_next_tick_callback(do_computation_2a)

    def compute_plot2b_from_plot3():
        """Compute Plot2b by summing over selected X,Y region in Plot3."""
        from bokeh.io import curdoc

        if plot2b is None:
            return

        # Update button text IMMEDIATELY before any computation
        original_button_label_2b = compute_plot2b_from_plot3_button.label
        compute_plot2b_from_plot3_button.label = "Computing ..."
        compute_plot2b_from_plot3_button.disabled = True

        # Schedule the actual computation in the next tick so button update is visible first
        def do_computation_2b():
            try:
                # Get selection from BoxSelectTool using utility function
                selection_left_3, selection_right_3, selection_bottom_3, selection_top_3 = get_box_select_selection(
                    plot3, box_annotation_3, rect3, debug=True
                )

                # Get selection from BoxSelectTool first, then box_annotation_3, otherwise use rect3
                use_box_annotation_3 = False
                x1_coord = None
                y1_coord = None
                x2_coord = None
                y2_coord = None

                # Use BoxSelectTool selection if available
                if (selection_left_3 is not None and selection_right_3 is not None and 
                    selection_bottom_3 is not None and selection_top_3 is not None):
                    use_box_annotation_3 = True
                    x1_coord = min(selection_left_3, selection_right_3)
                    x2_coord = max(selection_left_3, selection_right_3)
                    y1_coord = min(selection_bottom_3, selection_top_3)
                    y2_coord = max(selection_bottom_3, selection_top_3)
                    print(f"  ✅ Using BoxSelectTool selection (plot3 for plot2b): x=[{x1_coord}, {x2_coord}], y=[{y1_coord}, {y2_coord}]")
                elif box_annotation_3 is not None:
                    try:
                        # Extract numeric values from box_annotation_3
                        left_val_3 = float(box_annotation_3.left) if hasattr(box_annotation_3.left, '__float__') or isinstance(box_annotation_3.left, (int, float)) else None
                        right_val_3 = float(box_annotation_3.right) if hasattr(box_annotation_3.right, '__float__') or isinstance(box_annotation_3.right, (int, float)) else None
                        bottom_val_3 = float(box_annotation_3.bottom) if hasattr(box_annotation_3.bottom, '__float__') or isinstance(box_annotation_3.bottom, (int, float)) else None
                        top_val_3 = float(box_annotation_3.top) if hasattr(box_annotation_3.top, '__float__') or isinstance(box_annotation_3.top, (int, float)) else None

                        if (left_val_3 is not None and right_val_3 is not None and 
                            bottom_val_3 is not None and top_val_3 is not None and
                            not (np.isnan(left_val_3) or np.isnan(right_val_3) or np.isnan(bottom_val_3) or np.isnan(top_val_3))):
                            use_box_annotation_3 = True
                            x1_coord = min(left_val_3, right_val_3)
                            x2_coord = max(left_val_3, right_val_3)
                            y1_coord = min(bottom_val_3, top_val_3)
                            y2_coord = max(bottom_val_3, top_val_3)
                    except Exception as e:
                        print(f"  ⚠️ Could not read box_annotation_3 coordinates: {e}")

                if not use_box_annotation_3:
                    # Use rect3 values
                    x1_coord = rect3.min_x
                    x2_coord = rect3.max_x
                    y1_coord = rect3.min_y
                    y2_coord = rect3.max_y
                    print(f"  ⚠️ Using rect3 (fallback): x=[{x1_coord}, {x2_coord}], y=[{y1_coord}, {y2_coord}]")

                # Use the new utility function to compute 2D plot from 3D section
                def load_probe_coords_b():
                    """Helper to load probe coordinates for plot2b."""
                    if hasattr(self.process_4dnexus, 'probe_x_coords_picked_b') and self.process_4dnexus.probe_x_coords_picked_b:
                        try:
                            return self.process_4dnexus.load_probe_coordinates(use_b=True)
                        except:
                            return None
                    return None

                slice, x_coords_1d = compute_2d_plot_from_3d_section(
                    volume=volume_b,
                    x1_coord=x1_coord,
                    y1_coord=y1_coord,
                    x2_coord=x2_coord,
                    y2_coord=y2_coord,
                    get_x_index=get_x_index,
                    get_y_index=get_y_index,
                    is_3d_volume=not plot2b_is_2d,
                    probe_coords_loader=load_probe_coords_b,
                    use_b=True,
                )

                # Convert coordinates to indices for logging
                x1 = get_x_index(x1_coord)
                y1 = get_y_index(y1_coord)
                x2 = max(x1 + 1, get_x_index(x2_coord))
                y2 = max(y1 + 1, get_y_index(y2_coord))

                if not plot2b_is_2d:
                    # Update 1D plot
                    source2b.data = {"x": x_coords_1d, "y": slice}
                    # Bokeh 3.x automatically detects data changes, no need for change.emit()
                    plot2b.x_range.start = float(np.min(x_coords_1d))
                    plot2b.x_range.end = float(np.max(x_coords_1d))
                    plot2b.y_range.start = float(np.min(slice))
                    plot2b.y_range.end = float(np.max(slice))
                else:
                    # Update probe_2d_plot_b's data and use its flipped methods
                    probe_2d_plot_b.data = slice

                    # Get flipped data and coordinates from probe_2d_plot_b
                    flipped_slice = probe_2d_plot_b.get_flipped_data()
                    x_coords_slice = probe_2d_plot_b.get_flipped_x_coords()
                    y_coords_slice = probe_2d_plot_b.get_flipped_y_coords()

                    # Fallback if flipped methods return None
                    if flipped_slice is None:
                        flipped_slice = np.transpose(slice)  # Always transpose for Bokeh
                    if x_coords_slice is None:
                        x_coords_slice = np.arange(flipped_slice.shape[1])
                    if y_coords_slice is None:
                        y_coords_slice = np.arange(flipped_slice.shape[0])

                    # Calculate dimensions
                    dw = float(np.max(x_coords_slice) - np.min(x_coords_slice)) if len(x_coords_slice) > 0 else float(flipped_slice.shape[1])
                    dh = float(np.max(y_coords_slice) - np.min(y_coords_slice)) if len(y_coords_slice) > 0 else float(flipped_slice.shape[0])

                    source2b.data = {
                        "image": [flipped_slice],
                        "x": [float(np.min(x_coords_slice))],
                        "y": [float(np.min(y_coords_slice))],
                        "dw": [dw],
                        "dh": [dh],
                    }
                    # Bokeh 3.x automatically detects data changes, no need for change.emit()
                    # Update color mapper
                    probe_min = float(np.percentile(flipped_slice[~np.isnan(flipped_slice)], 1))
                    probe_max = float(np.percentile(flipped_slice[~np.isnan(flipped_slice)], 99))
                    color_mapper2b.low = probe_min
                    color_mapper2b.high = probe_max
            except Exception as e:
                import traceback
                print(f"  ❌ Error computing Plot2b from Plot3: {e}")
                traceback.print_exc()
            finally:
                # Restore button text and enable it
                compute_plot2b_from_plot3_button.label = original_button_label_2b
                compute_plot2b_from_plot3_button.disabled = False

        # Schedule computation in next tick so button update is visible first
        curdoc().add_next_tick_callback(do_computation_2b)

    # Reset functions using SCLib utility
    def reset_plot2():
        """Reset Plot2 to original volume slice by reloading from memmap/nexus."""
        if plot2 is None:
            return
        try:
            # Reload data from memmap/nexus by calling show_slice()
            # This will reload the current slice from the volume data source
            show_slice()
            print(f"✅ Reset Plot2 to original slice (reloaded from data source)")
        except Exception as e:
            print(f"⚠️ ERROR resetting Plot2: {e}")
            import traceback
            traceback.print_exc()
            # Fallback to stored original data if reload fails
            try:
                reset_plot_to_original_data(
                    source=source2,
                    original_data=plot2_original_data,
                    bokeh_figure=plot2,
                    color_mapper=color_mapper2,
                    original_min=plot2_original_min,
                    original_max=plot2_original_max,
                    min_input=range2_min_input if 'range2_min_input' in locals() else None,
                    max_input=range2_max_input if 'range2_max_input' in locals() else None,
                    debug=True
                )
                print(f"✅ Reset Plot2 using stored original data (fallback)")
            except Exception as e2:
                print(f"❌ ERROR in fallback reset: {e2}")
    
    def reset_plot2b():
        """Reset Plot2b to original volume slice by reloading from memmap/nexus."""
        if plot2b is None:
            return
        try:
            # Reload data from memmap/nexus by calling show_slice_b()
            # This will reload the current slice from the volume data source
            show_slice_b()
            print(f"✅ Reset Plot2b to original slice (reloaded from data source)")
        except Exception as e:
            print(f"⚠️ ERROR resetting Plot2b: {e}")
            import traceback
            traceback.print_exc()
            # Fallback to stored original data if reload fails
            try:
                reset_plot_to_original_data(
                    source=source2b,
                    original_data=plot2b_original_data,
                    bokeh_figure=plot2b,
                    color_mapper=color_mapper2b,
                    original_min=plot2b_original_min,
                    original_max=plot2b_original_max,
                    min_input=range2b_min_input if 'range2b_min_input' in locals() else None,
                    max_input=range2b_max_input if 'range2b_max_input' in locals() else None,
                    debug=True
                )
                print(f"✅ Reset Plot2b using stored original data (fallback)")
            except Exception as e2:
                print(f"❌ ERROR in fallback reset: {e2}")
    
    # Connect reset buttons
    if reset_plot2_button is not None:
        reset_plot2_button.on_click(lambda: reset_plot2())
    if reset_plot2b_button is not None:
        reset_plot2b_button.on_click(lambda: reset_plot2b())
    
    # Connect Plot3 selection to Plot2 computation
    # This will be triggered when user selects a region in Plot3
    def on_plot3_selection_change(attr, old, new):
        """Handle Plot3 selection change to compute Plot2."""
        if new and len(new) > 0:
            compute_plot2_from_plot3()

    # Note: BoxSelectTool selection is handled via JavaScript callback
    # We'll need to set up a proper callback mechanism

    # Create tools column using SCLib layout builder
    # Put status_div at the bottom of the tools column
    # Set max_height to prevent overflow and enable scrolling
    tools = create_tools_column(tools_items, width=260, max_height=800)  # Set max height to prevent overlap
    #was 400  width

    # Create plot columns with range inputs above each plot
    # Plot1 column
    plot1_items = []
    if range1_section is not None:
        plot1_items.append(range1_section)
    plot1_items.append(plot1)
    # Add sliders between plot1 and plot1b
    plot1_items.append(sliders_column)
    if plot1b is not None:
        if range1b_section is not None:
            plot1_items.append(range1b_section)
        plot1_items.append(plot1b)
    plot1_col = create_plot_column(plot1_items)

    # Plot2 column
    plot2_items = []
    if range2_section is not None:
        plot2_items.append(range2_section)
    if plot2 is not None:
        plot2_items.append(plot2)
    else:
        # Plot2 failed to create - add error message
        plot2_items.append(create_div(text="<p style='color: red;'>⚠️ Error: Plot2 could not be created. Check dataset selection.</p>"))
    # Add Plot3 computation buttons between plot2 and plot2b range
    plot2_items.append(create_label_div("Plot2 -> Plot3:", width=200))
    # Create a row with Reset button and Show Plot3 button for Plot2
    if reset_plot2_button is not None:
        plot2_items.append(row( compute_plot3_button, reset_plot2_button))
    else:
        plot2_items.append(compute_plot3_button)
    # Create a row with Reset button and Show Plot3 button for Plot2B
    if compute_plot3_from_plot2b_button is not None:
        if reset_plot2b_button is not None:
            plot2_items.append(row(compute_plot3_from_plot2b_button, reset_plot2b_button))
        else:
            plot2_items.append(compute_plot3_from_plot2b_button)
    if plot2b is not None:
        if range2b_section is not None:
            plot2_items.append(range2b_section)
        plot2_items.append(plot2b)
    plot2_col = create_plot_column(plot2_items)

    # Plot3 column
    plot3_items = []
    if range3_section is not None:
        plot3_items.append(range3_section)
    plot3_items.append(plot3)
    # Note: Plot3 -> Plot2 computation buttons are now in range3_section (under Linear/Log selector)

    plot3_col = create_plot_column(plot3_items)



    # Create plots row - include Plot3
    plots = create_plots_row([plot1_col, plot2_col, plot3_col])

    # Connect tap event handlers
    plot1.on_event("tap", on_plot1_tap)
    if plot2 is not None:
        plot2.on_event("tap", on_plot2_tap)
        plot2.on_event("doubletap", on_plot2_doubletap)
    plot3.on_event("tap", on_plot3_tap)

    # Note: Plot1B tap handler is already connected when Plot1B is created

    # Connect Plot2B tap handlers if it exists
    if plot2b is not None:
        plot2b.on_event("tap", on_plot2b_tap)
        plot2b.on_event("doubletap", on_plot2b_doubletap)

    # CRITICAL: Add handler for BoxSelectTool selection on Plot2 to automatically compute Plot3
    # Helper function that processes selection coordinates
    def on_plot2_box_select_with_coords(x0, y0, x1, y1):
        """Process BoxSelectTool selection coordinates and compute Plot3."""
        print("=" * 80)
        print("🔍 DEBUG: on_plot2_box_select_with_coords called!")
        print(f"  Coordinates: x0={x0}, y0={y0}, x1={x1}, y1={y1}")
        try:
            # Update BoxAnnotation to show persistent selection rectangle
            # This ensures the rectangle stays visible after BoxSelectTool selection disappears
            try:
                if box_annotation_2 is not None:
                    box_annotation_2.left = min(x0, x1)
                    box_annotation_2.right = max(x0, x1)
                    box_annotation_2.bottom = min(y0, y1)
                    box_annotation_2.top = max(y0, y1)
                    print(f"  ✅ Updated box_annotation_2: left={box_annotation_2.left}, right={box_annotation_2.right}, bottom={box_annotation_2.bottom}, top={box_annotation_2.top}")
            except NameError:
                print(f"  ⚠️ box_annotation_2 not available in scope")

            # Convert selection coordinates to indices
                print(f"  🔍 Converting coordinates to indices (is_3d_volume={is_3d_volume})")
                if is_3d_volume:
                    # For 1D plot: selection is x-range only
                    # Convert x coordinates to indices
                    if hasattr(self.process_4dnexus, 'probe_x_coords_picked') and self.process_4dnexus.probe_x_coords_picked:
                        try:
                            probe_coords = self.process_4dnexus.load_probe_coordinates()
                            if probe_coords is not None and len(probe_coords) > 0:
                                z1_idx = int(np.argmin(np.abs(probe_coords - min(x0, x1))))
                                z2_idx = int(np.argmin(np.abs(probe_coords - max(x0, x1))))
                                print(f"  ✅ Using probe_coords, z1_idx={z1_idx}, z2_idx={z2_idx}")
                            else:
                                z1_idx = int(min(x0, x1))
                                z2_idx = int(max(x0, x1))
                                print(f"  ✅ Using direct coordinates, z1_idx={z1_idx}, z2_idx={z2_idx}")
                        except Exception as e:
                            print(f"  ⚠️ Error loading probe_coords: {e}")
                            z1_idx = int(min(x0, x1))
                            z2_idx = int(max(x0, x1))
                    else:
                        z1_idx = int(min(x0, x1))
                        z2_idx = int(max(x0, x1))
                        print(f"  ✅ No probe_coords, using direct coordinates, z1_idx={z1_idx}, z2_idx={z2_idx}")

                    # Clamp to valid range
                    z1_idx = max(0, min(z1_idx, volume.shape[2] - 1))
                    z2_idx = max(0, min(z2_idx, volume.shape[2] - 1))
                    print(f"  ✅ Clamped indices: z1_idx={z1_idx}, z2_idx={z2_idx} (volume.shape[2]={volume.shape[2]})")

                    # Update rect2 with selection
                    rect2.set(min_x=z1_idx, max_x=z2_idx, min_y=z1_idx, max_y=z2_idx)
                    # draw_rect2()  # Disabled - using Bokeh's BoxAnnotation instead
                    print(f"  ✅ Updated rect2: min_x={rect2.min_x}, max_x={rect2.max_x}")
                else:
                    # For 2D plot: selection is both x and y ranges
                    # Convert coordinates to indices using flipped coordinate arrays
                    plot2_x_coords = probe_2d_plot.get_flipped_x_coords()
                    plot2_y_coords = probe_2d_plot.get_flipped_y_coords()
                    print(f"  🔍 plot2_x_coords shape: {plot2_x_coords.shape if plot2_x_coords is not None else None}")
                    print(f"  🔍 plot2_y_coords shape: {plot2_y_coords.shape if plot2_y_coords is not None else None}")

                    # Find closest indices in flipped coordinate arrays
                    if plot2_x_coords is not None and len(plot2_x_coords) > 0:
                        x1_idx = int(np.argmin(np.abs(plot2_x_coords - min(x0, x1))))
                        x2_idx = int(np.argmin(np.abs(plot2_x_coords - max(x0, x1))))
                    else:
                        x1_idx = int(min(x0, x1))
                        x2_idx = int(max(x0, x1))

                    if plot2_y_coords is not None and len(plot2_y_coords) > 0:
                        y1_idx = int(np.argmin(np.abs(plot2_y_coords - min(y0, y1))))
                        y2_idx = int(np.argmin(np.abs(plot2_y_coords - max(y0, y1))))
                    else:
                        y1_idx = int(min(y0, y1))
                        y2_idx = int(max(y0, y1))

                    print(f"  ✅ Indices from flipped coords: x1_idx={x1_idx}, x2_idx={x2_idx}, y1_idx={y1_idx}, y2_idx={y2_idx}")

                    # Convert back to original coordinate space (rect2 stores original indices)
                    plot2_needs_flip = probe_2d_plot.needs_flip if hasattr(probe_2d_plot, 'needs_flip') else False
                    if plot2_needs_flip:
                        # Flipped: plot2_x_coords is probe_y (u), plot2_y_coords is probe_x (z)
                        click_z1 = y1_idx  # This is the z dimension index
                        click_z2 = y2_idx  # This is the z dimension index
                        click_u1 = x1_idx  # This is the u dimension index
                        click_u2 = x2_idx  # This is the u dimension index
                    else:
                        # Not flipped: plot2_x_coords is probe_x (z), plot2_y_coords is probe_y (u)
                        click_z1 = x1_idx  # This is the z dimension index
                        click_z2 = x2_idx  # This is the z dimension index
                        click_u1 = y1_idx  # This is the u dimension index
                        click_u2 = y2_idx  # This is the u dimension index

                    print(f"  ✅ Converted to original space: z1={click_z1}, z2={click_z2}, u1={click_u1}, u2={click_u2}")

                    # Clamp to valid range
                    click_z1 = max(0, min(click_z1, z_size - 1))
                    click_z2 = max(0, min(click_z2, z_size - 1))
                    click_u1 = max(0, min(click_u1, u_size - 1))
                    click_u2 = max(0, min(click_u2, u_size - 1))

                    print(f"  ✅ Clamped indices: z1={click_z1}, z2={click_z2}, u1={click_u1}, u2={click_u2}")

                    # Update rect2 with selection
                    rect2.set(min_x=min(click_z1, click_z2), max_x=max(click_z1, click_z2),
                             min_y=min(click_u1, click_u2), max_y=max(click_u1, click_u2))
                    # draw_rect2()  # Disabled - using Bokeh's BoxAnnotation instead
                    print(f"  ✅ Updated rect2: min_x={rect2.min_x}, max_x={rect2.max_x}, min_y={rect2.min_y}, max_y={rect2.max_y}")

                # Automatically compute Plot3 from the selection
                print("  🔍 Calling compute_plot3_from_plot2()...")
                compute_plot3_from_plot2()
                print("  ✅ compute_plot3_from_plot2() completed")
                print("=" * 80)
        except Exception as e:
            print(f"⚠️ Warning: Error handling Plot2 selection: {e}")
            import traceback
            traceback.print_exc()
            print("=" * 80)

    # Connect BoxSelectTool selection handler for Plot2
    # Only set up for 2D plots (4D volumes) - 1D plots use different selection mechanism
    if plot2 is not None and not is_3d_volume:
        # Try multiple approaches to detect selection
        print("🔍 DEBUG: Setting up BoxSelectTool selection handler for Plot2...")
        box_select_tool_found = False
        box_select_tool = None
        for tool in plot2.tools:
            if isinstance(tool, BoxSelectTool):
                box_select_tool_found = True
                box_select_tool = tool
                print(f"  ✅ Found BoxSelectTool: {tool}")
                break

        if not box_select_tool_found:
            print("  ❌ No BoxSelectTool found in plot2.tools!")
            print(f"  🔍 plot2.tools: {[type(t).__name__ for t in plot2.tools]}")
        else:
            # Create a data source to store selection coordinates
            # The SelectionGeometry event handler will update this, triggering the callback
            plot2_selection_trigger = ColumnDataSource(data={"trigger": [0]})

            def on_selection_trigger(attr, old, new):
                """Triggered when selection coordinates are updated by SelectionGeometry event handler."""
                print("=" * 80)
                print("🔍 DEBUG: Selection trigger callback fired!")
                try:
                    # Get coordinates from the data source (updated by SelectionGeometry event handler)
                    data = plot2_selection_trigger.data
                    if 'x0' not in data or 'y0' not in data or 'x1' not in data or 'y1' not in data:
                        print("  ❌ Missing coordinates in trigger data source")
                        return

                    x0 = data['x0'][0] if len(data['x0']) > 0 else None
                    y0 = data['y0'][0] if len(data['y0']) > 0 else None
                    x1 = data['x1'][0] if len(data['x1']) > 0 else None
                    y1 = data['y1'][0] if len(data['y1']) > 0 else None

                    if x0 is None or y0 is None or x1 is None or y1 is None:
                        print("  ❌ Invalid coordinates in trigger data source")
                        return

                    print(f"  ✅ Selection coordinates from data source: x0={x0}, y0={y0}, x1={x1}, y1={y1}")

                    # Call the main handler with these coordinates
                    # Note: BoxAnnotation is updated by setup_selection_geometry_handler, so we don't duplicate that here
                    on_plot2_box_select_with_coords(x0, y0, x1, y1)
                except Exception as e:
                    print(f"  ⚠️ Error in selection trigger: {e}")
                    import traceback
                    traceback.print_exc()
                    print("=" * 80)

            plot2_selection_trigger.on_change('data', on_selection_trigger)

            # Use SelectionGeometry event handler from SCLib (updates box_annotation and selection_trigger_source)
            setup_selection_geometry_handler(
                plot2,
                box_annotation=box_annotation_2,
                selection_trigger_source=plot2_selection_trigger,
                debug=True
            )
            print("🔍 DEBUG: BoxSelectTool selection handler setup complete")
    elif plot2 is not None and is_3d_volume:
        print("🔍 DEBUG: Skipping BoxSelectTool setup for 1D plot (3D volume)")

    # Add BoxAnnotation update handlers for Plot2B and Plot3 using SelectionGeometry events from SCLib
    if plot2b is not None and 'box_annotation_2b' in locals() and box_annotation_2b is not None:
        setup_selection_geometry_handler(
            plot2b,
            box_annotation=box_annotation_2b,
            debug=False
        )
        print("  ✅ Set SelectionGeometry event handler on plot2b")

    if 'box_annotation_3' in locals() and box_annotation_3 is not None:
        setup_selection_geometry_handler(
            plot3,
            box_annotation=box_annotation_3,
            debug=False
        )
        print("  ✅ Set SelectionGeometry event handler on plot3")

    # Draw initial rectangles if needed
    if not is_3d_volume:
        # Initialize rect2 to cover full range for 4D volumes OR 3D volumes when Plot1 is 1D
        rect2.set(
            min_x=0, max_x=z_size-1,
            min_y=0, max_y=u_size-1
        )
        # draw_rect2()  # Disabled - using Bokeh's BoxAnnotation instead

    # Initialize rect3 to cover full range (use original coordinates, not flipped)
    # rect3 stores original coordinate values, not plot coordinates
    # When Plot1 is 1D, y_coords is None, so use data shape for y range
    if y_coords is not None:
        rect3.set(
            min_x=float(np.min(x_coords)), max_x=float(np.max(x_coords)),
            min_y=float(np.min(y_coords)), max_y=float(np.max(y_coords))
        )
    else:
        # When Plot1 is 1D, y-axis is index-based (0 to shape[0]-1)
        # Use plot1_1d_data if available, otherwise fallback to plot1_data
        if plot1_is_1d and plot1_1d_data is not None:
            data_shape_0 = plot1_1d_data.shape[0]
        elif plot1_data is not None:
            data_shape_0 = plot1_data.shape[0]
        else:
            # Fallback: use x_coords length
            data_shape_0 = len(x_coords) if x_coords is not None else 1
        rect3.set(
            min_x=float(np.min(x_coords)), max_x=float(np.max(x_coords)),
            min_y=0.0, max_y=float(data_shape_0 - 1)
        )

    # Create main dashboard layout using optimized layout
    # Extract controls from range sections for each plot
    # Each plot's controls: Min input, Max input, dynamic/userselected toggle, Linear/Log selector
    # Range section structure: [label_div, row(min_input, max_input), row(range_mode_toggle, color_scale_selector)]
    
    # Plot1a (Plot1) controls
    plot1a_controls_items = []
    if range1_section is not None and len(range1_section.children) >= 2:
        # Extract min/max row (usually index 1, skip label at index 0)
        min_max_row = None
        toggle_selector_row = None
        for i, child in enumerate(range1_section.children):
            # Check if it's a Row layout object (has children attribute and is a Row type)
            if hasattr(child, 'children') and len(getattr(child, 'children', [])) == 2:
                # Check if it's min/max row (has TextInput widgets) or toggle/selector row
                if hasattr(child.children[0], 'value') and hasattr(child.children[1], 'value'):
                    # Likely min/max inputs
                    min_max_row = child
                else:
                    # Likely toggle/selector row
                    toggle_selector_row = child
        
        if min_max_row:
            # Don't add "Min" and "Max" labels - they're already on the text boxes
            plot1a_controls_items.append(min_max_row.children[0])  # Min input
            plot1a_controls_items.append(min_max_row.children[1])  # Max input
        
        if toggle_selector_row:
            # Add toggle and selector
            plot1a_controls_items.append(toggle_selector_row.children[0])  # Range mode toggle
            plot1a_controls_items.append(toggle_selector_row.children[1])  # Color scale selector
    
    # Plot2a (Plot2) controls
    plot2a_controls_items = []
    if range2_section is not None and len(range2_section.children) >= 2:
        min_max_row = None
        toggle_selector_row = None
        for child in range2_section.children:
            if hasattr(child, 'children') and len(getattr(child, 'children', [])) == 2:
                if hasattr(child.children[0], 'value') and hasattr(child.children[1], 'value'):
                    min_max_row = child
                else:
                    toggle_selector_row = child
        
        if min_max_row:
            # Don't add "Min" and "Max" labels - they're already on the text boxes
            plot2a_controls_items.append(min_max_row.children[0])
            plot2a_controls_items.append(min_max_row.children[1])
        
        if toggle_selector_row:
            plot2a_controls_items.append(toggle_selector_row.children[0])
            plot2a_controls_items.append(toggle_selector_row.children[1])
        
        # Add compute_plot3_button to Plot2a controls (under linear/log button)
        if compute_plot3_button is not None:
            plot2a_controls_items.append(compute_plot3_button)
    
    # Plot3 controls
    plot3_controls_items = []
    if range3_section is not None and len(range3_section.children) >= 2:
        min_max_row = None
        toggle_selector_row = None
        buttons_row = None
        for child in range3_section.children:
            if hasattr(child, 'children') and len(getattr(child, 'children', [])) == 2:
                if hasattr(child.children[0], 'value') and hasattr(child.children[1], 'value'):
                    min_max_row = child
                else:
                    toggle_selector_row = child
            elif hasattr(child, 'children') and len(getattr(child, 'children', [])) >= 1:
                # Check if this is the buttons row (contains buttons)
                if len(child.children) >= 1 and hasattr(child.children[0], 'label'):
                    # Check if first child is a button (has 'label' attribute and 'on_click' or 'button_type')
                    if hasattr(child.children[0], 'button_type') or hasattr(child.children[0], 'on_click'):
                        buttons_row = child
        
        if min_max_row:
            # Don't add "Min" and "Max" labels - they're already on the text boxes
            plot3_controls_items.append(min_max_row.children[0])
            plot3_controls_items.append(min_max_row.children[1])
        
        if toggle_selector_row:
            plot3_controls_items.append(toggle_selector_row.children[0])
            plot3_controls_items.append(toggle_selector_row.children[1])
        
        # Add buttons row if it exists (contains compute_plot2a_from_plot3_button and compute_plot2b_from_plot3_button)
        if buttons_row:
            for button in buttons_row.children:
                plot3_controls_items.append(button)
    
    # Plot2b controls (if exists)
    plot2b_controls_items = []
    if plot2b is not None and range2b_section is not None and len(range2b_section.children) >= 2:
        min_max_row = None
        toggle_selector_row = None
        for child in range2b_section.children:
            if hasattr(child, 'children') and len(getattr(child, 'children', [])) == 2:
                if hasattr(child.children[0], 'value') and hasattr(child.children[1], 'value'):
                    min_max_row = child
                else:
                    toggle_selector_row = child
        
        if min_max_row:
            # Don't add "Min" and "Max" labels - they're already on the text boxes
            plot2b_controls_items.append(min_max_row.children[0])
            plot2b_controls_items.append(min_max_row.children[1])
        
        if toggle_selector_row:
            plot2b_controls_items.append(toggle_selector_row.children[0])
            plot2b_controls_items.append(toggle_selector_row.children[1])
        
        # Add compute_plot3_from_plot2b_button to Plot2b controls (under linear/log button)
        if compute_plot3_from_plot2b_button is not None:
            plot2b_controls_items.append(compute_plot3_from_plot2b_button)
    
    # Create control columns for each plot
    from SCLib_Dashboards import create_plot_column
    plot1a_controls_col = create_plot_column(plot1a_controls_items) if plot1a_controls_items else create_plot_column([])
    plot2a_controls_col = create_plot_column(plot2a_controls_items) if plot2a_controls_items else create_plot_column([])
    plot3_controls_col = create_plot_column(plot3_controls_items) if plot3_controls_items else create_plot_column([])
    plot2b_controls_col = create_plot_column(plot2b_controls_items) if plot2b_controls_items and plot2b is not None else None
    
    # Get sliders column - this should be placed above Plot1a
    sliders_column_widget = None
    if 'sliders_column' in locals() and sliders_column is not None:
        sliders_column_widget = sliders_column
    
    # Use optimized dashboard layout
    from SCLib_Dashboards import create_optimized_dashboard_layout
    dashboard = create_optimized_dashboard_layout(
        tools_column=tools,
        plot1a_controls=plot1a_controls_col,
        plot1a_plot=plot1,
        plot2a_controls=plot2a_controls_col,
        plot2a_plot=plot2 if plot2 is not None else create_div(text="<p>Plot2 not available</p>"),
        plot3_controls=plot3_controls_col,
        plot3_plot=plot3,
        plot2b_controls=plot2b_controls_col,
        plot2b_plot=plot2b,
        x_slider=None,  # Not using individual sliders, using sliders_column instead
        y_slider=None,
        sliders_column=sliders_column_widget,  # Pass the entire sliders column
        status_display=None,  # status_div is already in tools column
        tools_width=260, #was 400
        controls_width=140,
    )
    
    # Create header banner for the dashboard - spans full width of page
    from bokeh.models import Div
    sc_blue = "#4E477F"  # ScientistCloud primary color (light theme)
    header_banner = Div(
        text=f"""
        <div class="dashboard-header-banner" style="
            background-color: {sc_blue}; 
            padding: 10px 20px; 
            display: flex; 
            align-items: center; 
            border-bottom: 3px solid #75c0de;
            margin-bottom: 15px;
            border-radius: 0;
        ">
            <img src="https://scientistcloud.com/portal/assets/images/scientistCloudLogo_noText.png" 
                 style="height: 40px; margin-right: 15px;">
            <span style="
                color: white; 
                font-family: sans-serif; 
                font-size: 1.5em; 
                font-weight: bold;
                text-shadow: 1px 1px 2px rgba(0,0,0,0.1);
            ">ScientistCloud | 4D Dashboard</span>
        </div>
        """,
        sizing_mode="stretch_width",
        width_policy="max",
        styles={
            "width": "100vw",
            "max-width": "100vw",
            "margin": "0",
            "padding": "0",
            "margin-left": "calc(-50vw + 50%)",
            "margin-right": "calc(-50vw + 50%)",
            "position": "relative",
            "left": "50%",
            "right": "50%"
        }
    )
    
    # Set white background for the dashboard using CSS and button styles to match ScientistCloud
    background_css = Div(
        text="""
        <style>
            body, .bk-root {
                background-color: white !important;
            }
            .bk-root .bk {
                background-color: white !important;
            }
            
            /* Make header banner span full width of viewport - break out of all containers */
            /* Target all parent containers to allow full width */
            .bk-root {
                overflow-x: visible !important;
            }
            
            /* Force the Bokeh Div containing header to break out using absolute positioning */
            .bk-Div:has(.dashboard-header-banner) {
                position: absolute !important;
                top: 0 !important;
                left: 0 !important;
                width: 100vw !important;
                max-width: 100vw !important;
                min-width: 100vw !important;
                margin: 0 !important;
                padding: 0 !important;
                z-index: 1000 !important;
                box-sizing: border-box !important;
            }
            
            /* Make the inner header div also span full width */
            .dashboard-header-banner {
                width: 100% !important;
                max-width: 100% !important;
                min-width: 100% !important;
                margin-left: 0 !important;
                margin-right: 0 !important;
                box-sizing: border-box !important;
            }
            
            /* Ensure body and html allow full width */
            html, body {
                overflow-x: visible !important;
                width: 100% !important;
                max-width: 100% !important;
            }
            
            /* Style the internal buttons to match ScientistCloud colors from main.css */
            /* Bokeh buttons use .bk-btn class and button_type is stored as a data attribute */
            /* We need to use JavaScript to apply styles based on button_type attribute */
            
            /* Primary button - matches main.css primary color (light theme: #4E477F, dark theme: #6f66a9) */
            .bk-btn-primary,
            .bk-btn[data-button-type="primary"],
            button.bk-btn[data-button-type="primary"] {
                background-color: #4E477F !important;
                border-color: #4E477F !important;
                color: white !important;
                font-weight: bold !important;
            }
            
            .bk-btn-primary:hover,
            .bk-btn[data-button-type="primary"]:hover,
            button.bk-btn[data-button-type="primary"]:hover {
                background-color: #6f66a9 !important;
                border-color: #6f66a9 !important;
                color: white !important;
            }
            
            /* Info button - matches main.css info color (light theme: #1a4d73, dark theme: #B5AEDF) */
            .bk-btn-info,
            .bk-btn[data-button-type="info"],
            button.bk-btn[data-button-type="info"] {
                background-color: #1a4d73 !important;
                border-color: #1a4d73 !important;
                color: white !important;
            }
            
            .bk-btn-info:hover,
            .bk-btn[data-button-type="info"]:hover,
            button.bk-btn[data-button-type="info"]:hover {
                background-color: #B5AEDF !important;
                border-color: #B5AEDF !important;
                color: white !important;
                opacity: 0.9;
            }
            
            /* Danger button - matches main.css danger color (#6BB6E9) */
            .bk-btn-danger,
            .bk-btn[data-button-type="danger"],
            button.bk-btn[data-button-type="danger"] {
                background-color: #6BB6E9 !important;
                border-color: #6BB6E9 !important;
                color: white !important;
            }
            
            .bk-btn-danger:hover,
            .bk-btn[data-button-type="danger"]:hover,
            button.bk-btn[data-button-type="danger"]:hover {
                background-color: #6BB6E9 !important;
                border-color: #6BB6E9 !important;
                color: white !important;
                opacity: 0.9;
            }
            
            /* Success button - matches main.css success color (#76a38e) */
            .bk-btn-success,
            .bk-btn[data-button-type="success"],
            button.bk-btn[data-button-type="success"] {
                background-color: #76a38e !important;
                border-color: #76a38e !important;
                color: white !important;
            }
            
            .bk-btn-success:hover,
            .bk-btn[data-button-type="success"]:hover,
            button.bk-btn[data-button-type="success"]:hover {
                background-color: #76a38e !important;
                border-color: #76a38e !important;
                color: white !important;
                opacity: 0.9;
            }
            
            /* Warning button - matches main.css warning color (#E3A54F) */
            .bk-btn-warning,
            .bk-btn[data-button-type="warning"],
            button.bk-btn[data-button-type="warning"] {
                background-color: #E3A54F !important;
                border-color: #E3A54F !important;
                color: white !important;
            }
            
            .bk-btn-warning:hover,
            .bk-btn[data-button-type="warning"]:hover,
            button.bk-btn[data-button-type="warning"]:hover {
                background-color: #E3A54F !important;
                border-color: #E3A54F !important;
                color: white !important;
                opacity: 0.9;
            }
            
            /* Default button - matches main.css outline styles */
            .bk-btn-default,
            .bk-btn[data-button-type="default"],
            button.bk-btn[data-button-type="default"],
            .bk-btn:not([data-button-type]):not(.bk-btn-primary):not(.bk-btn-success):not(.bk-btn-warning):not(.bk-btn-danger):not(.bk-btn-info) {
                color: #4E477F !important;
                border-color: #4E477F !important;
                background-color: transparent !important;
            }
            
            .bk-btn-default:hover,
            .bk-btn[data-button-type="default"]:hover,
            button.bk-btn[data-button-type="default"]:hover,
            .bk-btn:not([data-button-type]):not(.bk-btn-primary):not(.bk-btn-success):not(.bk-btn-warning):not(.bk-btn-danger):not(.bk-btn-info):hover {
                background-color: #4E477F !important;
                border-color: #4E477F !important;
                color: white !important;
            }
            
            /* Use JavaScript to apply button styles based on Bokeh's internal button_type */
            /* Bokeh stores button_type in the model, accessible via Bokeh's document */
        </style>
        <script>
            // Apply button styles based on Bokeh button_type from model
            function applyButtonStyles() {
                // Access Bokeh's document to get all button models
                if (typeof Bokeh !== 'undefined' && Bokeh.documents && Bokeh.documents.length > 0) {
                    const doc = Bokeh.documents[0];
                    const buttonModels = doc.get_model_by_name ? 
                        Object.values(doc._all_models).filter(m => m.type === 'Button') :
                        [];
                    
                    buttonModels.forEach(function(model) {
                        const view = doc.get_model_by_id ? doc.get_model_by_id(model.id) : null;
                        if (view && view.el) {
                            const button = view.el;
                            const buttonType = model.button_type || 'default';
                            
                            // Apply styles based on button type
                            if (buttonType === 'primary') {
                                button.style.setProperty('background-color', '#4E477F', 'important');
                                button.style.setProperty('border-color', '#4E477F', 'important');
                                button.style.setProperty('color', 'white', 'important');
                                button.style.setProperty('font-weight', 'bold', 'important');
                            } else if (buttonType === 'success') {
                                button.style.setProperty('background-color', '#76a38e', 'important');
                                button.style.setProperty('border-color', '#76a38e', 'important');
                                button.style.setProperty('color', 'white', 'important');
                            } else if (buttonType === 'warning') {
                                button.style.setProperty('background-color', '#E3A54F', 'important');
                                button.style.setProperty('border-color', '#E3A54F', 'important');
                                button.style.setProperty('color', 'white', 'important');
                            } else if (buttonType === 'danger') {
                                button.style.setProperty('background-color', '#6BB6E9', 'important');
                                button.style.setProperty('border-color', '#6BB6E9', 'important');
                                button.style.setProperty('color', 'white', 'important');
                            } else if (buttonType === 'info') {
                                button.style.setProperty('background-color', '#1a4d73', 'important');
                                button.style.setProperty('border-color', '#1a4d73', 'important');
                                button.style.setProperty('color', 'white', 'important');
                            } else {
                                button.style.setProperty('color', '#4E477F', 'important');
                                button.style.setProperty('border-color', '#4E477F', 'important');
                                button.style.setProperty('background-color', 'transparent', 'important');
                            }
                        }
                    });
                }
                
                // Fallback: style buttons by finding them in DOM
                const buttons = document.querySelectorAll('.bk-btn, button.bk-btn');
                buttons.forEach(function(button) {
                    // Try to get button_type from data attribute or Bokeh model
                    const modelId = button.getAttribute('data-model-id');
                    if (modelId && typeof Bokeh !== 'undefined') {
                        try {
                            const doc = Bokeh.documents && Bokeh.documents[0];
                            if (doc) {
                                const model = doc.get_model_by_id ? doc.get_model_by_id(modelId) : null;
                                if (model && model.button_type) {
                                    const buttonType = model.button_type;
                                    if (buttonType === 'primary') {
                                        button.style.setProperty('background-color', '#4E477F', 'important');
                                        button.style.setProperty('border-color', '#4E477F', 'important');
                                        button.style.setProperty('color', 'white', 'important');
                                    } else if (buttonType === 'success') {
                                        button.style.setProperty('background-color', '#76a38e', 'important');
                                        button.style.setProperty('border-color', '#76a38e', 'important');
                                        button.style.setProperty('color', 'white', 'important');
                                    } else if (buttonType === 'warning') {
                                        button.style.setProperty('background-color', '#E3A54F', 'important');
                                        button.style.setProperty('border-color', '#E3A54F', 'important');
                                        button.style.setProperty('color', 'white', 'important');
                                    } else if (buttonType === 'danger') {
                                        button.style.setProperty('background-color', '#6BB6E9', 'important');
                                        button.style.setProperty('border-color', '#6BB6E9', 'important');
                                        button.style.setProperty('color', 'white', 'important');
                                    }
                                }
                            }
                        } catch(e) {
                            // Ignore errors
                        }
                    }
                });
            }
            
            // Apply styles when DOM is ready and after Bokeh renders
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', function() {
                    setTimeout(applyButtonStyles, 100);
                    setTimeout(applyButtonStyles, 500);
                    setTimeout(applyButtonStyles, 1000);
                });
            } else {
                setTimeout(applyButtonStyles, 100);
                setTimeout(applyButtonStyles, 500);
                setTimeout(applyButtonStyles, 1000);
            }
            
            // Also observe for new buttons added dynamically
            if (typeof MutationObserver !== 'undefined') {
                const observer = new MutationObserver(function(mutations) {
                    setTimeout(applyButtonStyles, 50);
                });
                observer.observe(document.body, { childList: true, subtree: true });
            }
            
            // Force header banner to span full width - aggressive approach
            function makeHeaderFullWidth() {
                const headerBanners = document.querySelectorAll('.dashboard-header-banner');
                headerBanners.forEach(function(header) {
                    // Find the parent Bokeh Div
                    let parentDiv = header.closest('.bk-Div');
                    if (parentDiv) {
                        // Break out of all containers using viewport width
                        parentDiv.style.setProperty('position', 'absolute', 'important');
                        parentDiv.style.setProperty('top', '0', 'important');
                        parentDiv.style.setProperty('left', '0', 'important');
                        parentDiv.style.setProperty('width', '100vw', 'important');
                        parentDiv.style.setProperty('max-width', '100vw', 'important');
                        parentDiv.style.setProperty('min-width', '100vw', 'important');
                        parentDiv.style.setProperty('margin', '0', 'important');
                        parentDiv.style.setProperty('padding', '0', 'important');
                        parentDiv.style.setProperty('z-index', '1000', 'important');
                        parentDiv.style.setProperty('box-sizing', 'border-box', 'important');
                        
                        // Find all parent containers and remove width constraints
                        let current = parentDiv.parentElement;
                        while (current && current !== document.body) {
                            if (current.style) {
                                current.style.setProperty('overflow-x', 'visible', 'important');
                                current.style.setProperty('max-width', 'none', 'important');
                                if (current.classList.contains('bk-root') || current.classList.contains('bk-column')) {
                                    current.style.setProperty('position', 'relative', 'important');
                                }
                            }
                            current = current.parentElement;
                        }
                    }
                    // Make the inner div span full width
                    header.style.setProperty('width', '100%', 'important');
                    header.style.setProperty('max-width', '100%', 'important');
                    header.style.setProperty('min-width', '100%', 'important');
                    header.style.setProperty('margin-left', '0', 'important');
                    header.style.setProperty('margin-right', '0', 'important');
                });
                
                // Add padding to the main dashboard content to account for header
                const dashboardContent = document.querySelector('.bk-root > .bk-column');
                if (dashboardContent && dashboardContent.children.length > 1) {
                    // The second child should be the main dashboard (after header)
                    const mainContent = dashboardContent.children[1];
                    if (mainContent) {
                        const headerHeight = 70; // Approximate header height
                        mainContent.style.setProperty('margin-top', headerHeight + 'px', 'important');
                    }
                }
            }
            
            // Apply header width on load and after Bokeh renders
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', function() {
                    setTimeout(makeHeaderFullWidth, 100);
                    setTimeout(makeHeaderFullWidth, 500);
                    setTimeout(makeHeaderFullWidth, 1000);
                });
            } else {
                setTimeout(makeHeaderFullWidth, 100);
                setTimeout(makeHeaderFullWidth, 500);
                setTimeout(makeHeaderFullWidth, 1000);
            }
            
            // Observe for header changes
            if (typeof MutationObserver !== 'undefined') {
                const headerObserver = new MutationObserver(function(mutations) {
                    setTimeout(makeHeaderFullWidth, 50);
                });
                headerObserver.observe(document.body, { childList: true, subtree: true });
            }
        </script>
        <style>
        </style>
        """,
        width=0,
        height=0,
        margin=(0, 0, 0, 0)
    )
    
    # Wrap dashboard with header banner and background CSS
    from bokeh.layouts import column as bokeh_column
    dashboard = bokeh_column(background_css, header_banner, dashboard, sizing_mode="stretch_both")

    # Start background memmap cache creation after dashboard is created
    # This allows the dashboard to display immediately while memmap is computed in background
    from bokeh.io import curdoc
    def start_background_memmap():
        """Start memmap cache creation in background after dashboard is rendered.

        Only starts the main volume memmap. Other memmap files will be created
        on-demand when needed, or can be created later to avoid HDF5 contention.
        """
        try:
            # Only start main volume memmap creation to avoid overwhelming HDF5 file
            # Other memmap files (volume_picked, volume_picked_b) will be created
            # on-demand when those datasets are accessed, or can be created later
            self.process_4dnexus.create_memmap_cache_background()
            print("✅ Background memmap cache creation started (main volume only)")
        except Exception as e:
            print(f"⚠️ Warning: failed to start background memmap caching: {e}")

    # Schedule background memmap creation after the dashboard is rendered
    # Use a 10 second delay to ensure dashboard is fully interactive first
    curdoc().add_timeout_callback(start_background_memmap, 10000)  # 10 seconds

    # If session was loaded from tmp_dashboard or main dashboard, automatically load it after dashboard is created
    session_filepath = None
    is_from_main = False
    if hasattr(self.process_4dnexus, '_session_filepath_to_load'):
        session_filepath = self.process_4dnexus._session_filepath_to_load
        delattr(self.process_4dnexus, '_session_filepath_to_load')
        is_from_main = False
    elif hasattr(self.process_4dnexus, '_session_filepath_to_load_from_main'):
        session_filepath = self.process_4dnexus._session_filepath_to_load_from_main
        delattr(self.process_4dnexus, '_session_filepath_to_load_from_main')
        is_from_main = True

    if session_filepath:
        def auto_load_session():
            """Automatically load session after dashboard is fully created."""
            try:
                # Set flag to prevent range change callbacks from firing during session loading
                _session_loading_state["is_loading"] = True

                import json
                # Set the session select value to match the filepath
                session_filename = session_filepath.name
                # Find matching option in load_session_select
                for option in load_session_select.options:
                    if option.startswith(session_filename):
                        load_session_select.value = option
                        break

                # Directly load session state (don't recreate dashboard again to avoid infinite loop)
                # Read and load session state directly
                with open(session_filepath, 'r') as f:
                        session_data = json.load(f)

                # Load the session (this will restore plot states)
                session.load_session(session_filepath, restore_data=False)

                # Restore plot states from loaded session
                if hasattr(session, '_loaded_plot_states'):
                    for plot_id, plot_state in session._loaded_plot_states.items():
                        plot = session.get_plot(plot_id)
                        plot_type = plot_state.get("plot_type", None)

                        if plot:
                            # Plot exists in session, restore its state
                            plot.load_state(plot_state, restore_data=False)
                        elif plot_id == "plot1":
                            # Restore map_plot state (plot may not be in session yet)
                            map_plot.load_state(plot_state, restore_data=False)
                            # Re-add to session if not already there
                            if "plot1" not in session.plots:
                                session.add_plot("plot1", map_plot)
                        elif plot_id == "plot2":
                            # Restore probe plot state based on plot type
                            if plot_type == "PROBE_1DPlot" or (is_3d_volume and hasattr(plot2_history, 'plot')):
                                if hasattr(plot2_history, 'plot'):
                                    plot2_history.plot.load_state(plot_state, restore_data=False)
                                    if "plot2" not in session.plots:
                                        session.add_plot("plot2", plot2_history.plot)
                            elif plot_type == "PROBE_2DPlot" or (not is_3d_volume and hasattr(plot2_history, 'plot')):
                                if hasattr(plot2_history, 'plot'):
                                    plot2_history.plot.load_state(plot_state, restore_data=False)
                                    if "plot2" not in session.plots:
                                        session.add_plot("plot2", plot2_history.plot)

                # Update UI to reflect loaded state
                update_ui_after_state_change()

                # Clear and rebuild history with loaded state
                session_history.clear()
                session_history.save_state("Session loaded")
                undo_redo_callbacks["update"]()

                status_div.text = f"✅ Session loaded from {session_filepath.name}<br>All settings restored"
                source_name = "main dashboard" if is_from_main else "tmp_dashboard"
                print(f"✅ Auto-loaded session from {source_name}: {session_filepath.name}")

                # CRITICAL: Redraw crosshairs after ALL updates are complete (use nested callbacks)
                # This ensures crosshairs are drawn after plot ranges and all UI updates are finished
                from bokeh.io import curdoc
                def redraw_crosshairs_after_updates():
                    """Redraw crosshairs after all UI updates are complete."""
                    try:
                        # draw_cross1() and draw_cross1b() now handle re-creation automatically
                        # if renderers are missing from the plot
                        draw_cross1()
                        if plot1b is not None:
                            draw_cross1b()
                        print("✅ Crosshairs redrawn after session load")
                    except Exception as e:
                        print(f"⚠️ Warning: Error redrawing crosshairs after session load: {e}")
                        import traceback
                        traceback.print_exc()

                # Schedule crosshair redraw after current tick completes
                # Use a double-nested callback to ensure it happens after all range updates
                def schedule_crosshair_redraw():
                    def finalize_session_load():
                        # Redraw crosshairs
                        redraw_crosshairs_after_updates()
                        # Clear the flag after crosshairs are drawn
                        _session_loading_state["is_loading"] = False
                    curdoc().add_next_tick_callback(finalize_session_load)

                curdoc().add_next_tick_callback(schedule_crosshair_redraw)
            except Exception as e:
                # Clear the flag even if there's an error
                _session_loading_state["is_loading"] = False
                print(f"⚠️ Warning: Failed to auto-load session: {e}")
                import traceback
                traceback.print_exc()

        # Schedule session loading after dashboard is fully rendered
        curdoc().add_next_tick_callback(auto_load_session)

    # Note: dashboard variable is set above and will be available in the namespace for exec()
    # No return statement needed - exec() doesn't support returns at module level

except Exception as e:
    import traceback
    error_msg = str(e) if e else "Unknown error"
    print(f"Error in create_dashboard: {error_msg}")
    traceback.print_exc()
    # Set dashboard to error message div on exception
    dashboard = create_div(text=f"<h2>Error Loading Dashboard</h2><p>Error: {error_msg}</p><pre>{traceback.format_exc()}</pre>")
