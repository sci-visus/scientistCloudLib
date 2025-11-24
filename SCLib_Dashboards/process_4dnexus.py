import os
import numpy as np
import h5py
import threading 
import hashlib




class Process4dNexus:
    def __init__(self, nexus_filename, mmap_filename, cached_cast_float=True, status_callback=None):
        self.nexus_filename = nexus_filename
        self.mmap_filename = mmap_filename
        self.cached_cast_float = cached_cast_float

        self.volume_picked = None
        self.presample_picked = None
        self.postsample_picked = None
        self.x_coords_picked = None
        self.y_coords_picked = None
        self.preview_picked = None
        self.probe_x_coords_picked = None
        self.probe_y_coords_picked = None
        self.plot1_single_dataset_picked = None  # For Plot1 single dataset mode

        # Optional duplicate plot selections
        self.volume_picked_b = None
        self.presample_picked_b = None
        self.postsample_picked_b = None
        self.plot1b_single_dataset_picked = None  # For Plot1B single dataset mode
        self.probe_x_coords_picked_b = None
        self.probe_y_coords_picked_b = None
        
        self.volume_dataset = None
        self.volume_dataset_b = None
        self.presample_dataset = None
        self.postsample_dataset = None
        self.x_coords_dataset = None
        self.y_coords_dataset = None
        self.preview_dataset = None

        self.target_x = None
        self.target_y = None
        self.target_size = None
        self.presample_zeros = None
        self.postsample_zeros = None
        self.presample_conditioned = None
        self.postsample_conditioned = None
        self.preview = None
         
        self.shape = None
        self.dtype = None

        self.names_categories = None
        self.dimensions_categories = None
        
        self.DEBUG = True  # Debug flag - set to False to silence all debug output
        #self.status_messages = []
        self.status_callback = None
        # Optional override for memmap cache directory
        self.memmap_cache_dir = os.getenv('MEMMAP_CACHE_DIR', None)

        self.choices_done = self.get_choices()
       
    # def add_status(self, message):
    #     if self.status_callback:
    #         self.status_callback(message)
    #     print(message)    

    def debug_print(self, *args, **kwargs):
        """Print debug messages only if DEBUG is True"""
        # Convert args to string for storing
        message = ' '.join(str(arg) for arg in args)
        if self.status_callback:
            self.status_callback(message)
        if self.DEBUG:
            print(*args, **kwargs)  

    def get_choices(self):
        #turning off debug output for this function
        DEBUG_PREV  = self.DEBUG
        self.DEBUG = False
        self.debug_print("=== get_choices() started ===")
        
        if not self.nexus_filename or not os.path.exists(self.nexus_filename):
            self.debug_print(f"ERROR: Nexus file not found: {self.nexus_filename}")
            return False
    
        self.debug_print(f"Opening HDF5 file: {self.nexus_filename}")
    
        try:
            with h5py.File(self.nexus_filename, 'r') as f:
                # Recursively find all datasets in the HDF5 file
                def find_all_datasets(group, prefix=""):
                    """Recursively find all datasets in an HDF5 group"""
                    datasets = []
                    for key in group.keys():
                        full_path = f"{prefix}/{key}" if prefix else key
                        item = group[key]
                        if isinstance(item, h5py.Dataset):
                            datasets.append(full_path)
                        elif isinstance(item, h5py.Group):
                            # Recursively search subgroups
                            datasets.extend(find_all_datasets(item, full_path))
                    return datasets
                
                all_datasets = find_all_datasets(f)
                self.debug_print(f"Found {len(all_datasets)} datasets (recursively)")
                self.debug_print(f"Dataset paths: {all_datasets}")
                
                 # Categorize datasets
                names_categories = {
                    'volume_data': [],
                    'coordinate_data': [],
                    'intensity_data': [],
                    'other_data': []
                }
                self.debug_print("Starting keyword-based categorization...")
                for dataset_path in all_datasets:
                    path_lower = dataset_path.lower()
                    self.debug_print(f"  Processing: {dataset_path} (lower: {path_lower})")
                    
                    # Volume/3D data (including WAXS data and detector data)
                    if any(keyword in path_lower for keyword in ['pil', 'volume', 'data/i', 'intensity', 'waxs', 'detector']):
                        names_categories['volume_data'].append(dataset_path)
                        self.debug_print(f"    -> volume_data")
                    
                    # Coordinate data
                    elif any(keyword in path_lower for keyword in ['samx', 'samz', 'xrfx', 'xrfz', 'x', 'z', 'coord']):
                        names_categories['coordinate_data'].append(dataset_path)
                        self.debug_print(f"    -> coordinate_data")
                    
                    # Intensity data
                    elif any(keyword in path_lower for keyword in ['presample', 'postsample', 'intensity']):
                        names_categories['intensity_data'].append(dataset_path)
                        self.debug_print(f"    -> intensity_data")
                    
                    # Everything else
                    else:
                        names_categories['other_data'].append(dataset_path)
                        self.debug_print(f"    -> other_data")
                
                self.names_categories = names_categories
                self.debug_print("Keyword categorization results:")
                for category, items in names_categories.items():
                    self.debug_print(f"  {category}: {len(items)} items")
                    for item in items:
                        self.debug_print(f"    - {item}")

                self.debug_print("\nStarting dimension-based categorization...")
                # Categorize datasets by actual dimensions
                dimensions_categories = {
                    '4d': [],
                    '3d': [],
                    '2d': [],
                    '1d': [],
                    'scalar': [],
                    'unknown': []
                }
                
                for dataset_path in all_datasets:
                    self.debug_print(f"  Analyzing dimensions for: {dataset_path}")
                    try:
                        # Get the actual dataset and its shape
                        dataset = f[dataset_path]
                        if hasattr(dataset, 'shape'):
                            shape = dataset.shape
                            ndim = len(shape)
                            self.debug_print(f"    Shape: {shape}, Dimensions: {ndim}, Dtype: {dataset.dtype}")
                            
                            # Categorize based on actual dimensions
                            if ndim == 4:
                                dimensions_categories['4d'].append({
                                    'path': dataset_path,
                                    'shape': shape,
                                    'dtype': str(dataset.dtype)
                                })
                                self.debug_print(f"    -> 4D dataset")
                            elif ndim == 3:
                                dimensions_categories['3d'].append({
                                    'path': dataset_path,
                                    'shape': shape,
                                    'dtype': str(dataset.dtype)
                                })
                                self.debug_print(f"    -> 3D dataset")
                            elif ndim == 2:
                                dimensions_categories['2d'].append({
                                    'path': dataset_path,
                                    'shape': shape,
                                    'dtype': str(dataset.dtype)
                                })
                                self.debug_print(f"    -> 2D dataset")
                            elif ndim == 1:
                                dimensions_categories['1d'].append({
                                    'path': dataset_path,
                                    'shape': shape,
                                    'dtype': str(dataset.dtype)
                                })
                                self.debug_print(f"    -> 1D dataset")
                            elif ndim == 0:  # Scalar datasets
                                dimensions_categories['scalar'].append({
                                    'path': dataset_path,
                                    'shape': shape,
                                    'dtype': str(dataset.dtype)
                                })
                                self.debug_print(f"    -> Scalar dataset")
                            else:
                                dimensions_categories['unknown'].append({
                                    'path': dataset_path,
                                    'shape': shape,
                                    'dtype': str(dataset.dtype)
                                })
                                self.debug_print(f"    -> Unknown dimensions")
                        else:
                            # Handle groups or other non-dataset objects
                            dimensions_categories['unknown'].append({
                                'path': dataset_path,
                                'shape': 'group',
                                'dtype': 'group'
                            })
                            self.debug_print(f"    -> Group (not a dataset)")
                    except Exception as e:
                        self.debug_print(f"    ERROR processing dataset {dataset_path}: {e}")
                        dimensions_categories['unknown'].append({
                            'path': dataset_path,
                            'shape': 'error',
                            'dtype': 'error',
                            'error': str(e)
                        })
                
                self.dimensions_categories = dimensions_categories
                
                self.debug_print("\nDimension categorization results:")
                for category, items in dimensions_categories.items():
                    self.debug_print(f"  {category}: {len(items)} items")
                    for item in items:
                        self.debug_print(f"    - {item['path']} (shape: {item['shape']}, dtype: {item['dtype']})")
                
                self.debug_print("=== get_choices() completed successfully ===")
            self.DEBUG = DEBUG_PREV
            return True
        except Exception as e:
            self.debug_print(f'ERROR in get_choices(): {e}')
            return False
             

    def get_datasets_by_dimension(self, target_dimension):
        """
        Get datasets filtered by dimension.
        
        Args:
            target_dimension (int or str): Target dimension (1, 2, 3, 4, 'scalar', 'unknown')
        
        Returns:
            list: List of datasets with the specified dimension
        """
        if not hasattr(self, 'dimensions_categories') or self.dimensions_categories is None:
            return []
        
        if isinstance(target_dimension, int):
            dim_key = f'{target_dimension}d'
        else:
            dim_key = target_dimension
            
        return self.dimensions_categories.get(dim_key, [])

    def print_dimension_summary(self):
        """Print a summary of datasets by dimension."""
        if not hasattr(self, 'dimensions_categories') or self.dimensions_categories is None:
            print("No dimension categories available. Run get_choices() first.")
            return
            
        print("Dataset categorization by dimensions:")
        print("=" * 50)
        
        for dim, datasets in self.dimensions_categories.items():
            print(f"\n{dim.upper()} datasets ({len(datasets)} total):")
            for dataset in datasets:
                print(f"  - {dataset['path']}")
                print(f"    Shape: {dataset['shape']}, Type: {dataset['dtype']}")
                if 'error' in dataset:
                    print(f"    Error: {dataset['error']}")

    def get_largest_datasets_by_dimension(self, max_datasets=5):
        """
        Get the largest datasets for each dimension category.
        
        Args:
            max_datasets (int): Maximum number of datasets to return per dimension
            
        Returns:
            dict: Dictionary with dimension keys and lists of largest datasets
        """
        if not hasattr(self, 'dimensions_categories') or self.dimensions_categories is None:
            return {}
            
        largest_datasets = {}
        
        for dim, datasets in self.dimensions_categories.items():
            if not datasets:
                continue
                
            # Sort by total size (product of shape dimensions)
            def get_size(dataset):
                if isinstance(dataset['shape'], tuple):
                    return np.prod(dataset['shape'])
                return 0
                
            sorted_datasets = sorted(datasets, key=get_size, reverse=True)
            largest_datasets[dim] = sorted_datasets[:max_datasets]
            
        return largest_datasets

    def load_dataset_by_path(self, dataset_path):
        """
        Load a specific dataset from the HDF5 file by path.
        
        Args:
            dataset_path (str): Path to the dataset within the HDF5 file
            
        Returns:
            numpy.ndarray: The loaded dataset, or None if error
        """
        try:
            with h5py.File(self.nexus_filename, 'r') as f:
                dataset = f[dataset_path]
                # Load the data into memory
                data = np.array(dataset)
                return data
        except Exception as e:
            print(f"Error loading dataset {dataset_path}: {e}")
            return None

    def load_2d_dataset_for_plot(self, dataset_path, x_coords=None, y_coords=None):
        """
        Load and prepare a 2D dataset for plotting.
        
        Args:
            dataset_path (str): Path to the 2D dataset
            x_coords (numpy.ndarray, optional): X coordinates
            y_coords (numpy.ndarray, optional): Y coordinates
            
        Returns:
            dict: Data dictionary for Bokeh ColumnDataSource
        """
        dataset = self.load_dataset_by_path(dataset_path)
        if dataset is None:
            return None
            
        if len(dataset.shape) != 2:
            print(f"Expected 2D dataset, got shape: {dataset.shape}")
            return None
        
        # Use provided coordinates or create default ones
        if x_coords is None:
            x_coords = np.arange(dataset.shape[1])
        if y_coords is None:
            y_coords = np.arange(dataset.shape[0])
        
        # Create data dictionary for Bokeh
        data = {
            "image": [dataset],
            "x": [x_coords.min()],
            "y": [y_coords.min()],
            "dw": [x_coords.max() - x_coords.min()],
            "dh": [y_coords.max() - y_coords.min()],
        }
        
        return data

    def load_3d_dataset_for_plot(self, dataset_path, slice_index=None):
        """
        Load and prepare a 3D dataset for plotting by taking a slice.
        
        Args:
            dataset_path (str): Path to the 3D dataset
            slice_index (int, optional): Index for slicing. If None, uses middle slice
            
        Returns:
            dict: Data dictionary for Bokeh ColumnDataSource
        """
        dataset = self.load_dataset_by_path(dataset_path)
        if dataset is None:
            return None
            
        if len(dataset.shape) != 3:
            print(f"Expected 3D dataset, got shape: {dataset.shape}")
            return None
        
        # Use middle slice if no slice index provided
        if slice_index is None:
            slice_index = dataset.shape[0] // 2
        
        # Take the slice
        slice_data = dataset[slice_index, :, :]
        
        # Create data dictionary for Bokeh
        data = {
            "image": [slice_data],
            "x": [0],
            "y": [0],
            "dw": [slice_data.shape[1]],
            "dh": [slice_data.shape[0]],
        }
        
        return data

    def load_4d_dataset_for_plot(self, dataset_path, slice_indices=None):
        """
        Load and prepare a 4D dataset for plotting by taking slices.
        
        Args:
            dataset_path (str): Path to the 4D dataset
            slice_indices (tuple, optional): Indices for slicing (x, y, z, t).
                                           If None, uses middle indices
            
        Returns:
            dict: Data dictionary for Bokeh ColumnDataSource
        """
        dataset = self.load_dataset_by_path(dataset_path)
        if dataset is None:
            return None
            
        if len(dataset.shape) != 4:
            print(f"Expected 4D dataset, got shape: {dataset.shape}")
            return None
        
        # Use middle indices if no slice indices provided
        if slice_indices is None:
            slice_indices = (
                dataset.shape[0] // 2,
                dataset.shape[1] // 2,
                dataset.shape[2] // 2,
                dataset.shape[3] // 2
            )
        
        # Take a 2D slice (e.g., x-y plane at given z, t)
        slice_data = dataset[slice_indices[0], slice_indices[1], :, :]
        
        # Create data dictionary for Bokeh
        data = {
            "image": [slice_data],
            "x": [0],
            "y": [0],
            "dw": [slice_data.shape[1]],
            "dh": [slice_data.shape[0]],
        }
        
        return data

    def load_probe_coordinates(self, use_b=False):
        """Load probe coordinates from the nexus file
        
        Args:
            use_b: If True, use probe_x_coords_picked_b instead of probe_x_coords_picked
        """
        coord_path = getattr(self, 'probe_x_coords_picked_b', None) if use_b else self.probe_x_coords_picked
        if not coord_path:
            return None
            
        try:
            with h5py.File(self.nexus_filename, "r") as f:
                probe_coords = np.array(f.get(coord_path))
                return probe_coords
        except Exception as e:
            print(f"❌ Failed to load probe coordinates from {coord_path}: {e}")
            return None

    def load_nexus_data(self):
        # Set default dataset paths if not already set
        if self.volume_picked is None:
            self.volume_picked = "map_mi_sic_0p33mm_002/data/PIL11"
        if self.x_coords_picked is None:
            self.x_coords_picked = "map_mi_sic_0p33mm_002/data/samx"
        if self.y_coords_picked is None:
            self.y_coords_picked = "map_mi_sic_0p33mm_002/data/samz"
        # Only set presample/postsample defaults if not in single dataset mode
        if getattr(self, 'plot1_single_dataset_picked', None) is None:
            if self.presample_picked is None:
                self.presample_picked = "map_mi_sic_0p33mm_002/scalar_data/presample_intensity"
            if self.postsample_picked is None:
                self.postsample_picked = "map_mi_sic_0p33mm_002/scalar_data/postsample_intensity"

        print(f"----> LOAD_NEX_DATA: nexus_filename: {self.nexus_filename}")
        print(f"\t volume_picked: {self.volume_picked}")
        print(f"\t x_coords_picked: {self.x_coords_picked}")
        print(f"\t y_coords_picked: {self.y_coords_picked}")
        if getattr(self, 'plot1_single_dataset_picked', None):
            print(f"\t plot1_single_dataset_picked: {self.plot1_single_dataset_picked}")
        else:
            print(f"\t presample_picked: {self.presample_picked}")
            print(f"\t postsample_picked: {self.postsample_picked}")   
            
        # Open HDF5 file and keep it open if we're using direct HDF5 access
        # Store file handle in self so it doesn't close
        if not hasattr(self, 'h5_file') or self.h5_file is None:
            self.h5_file = h5py.File(self.nexus_filename, "r")
        
        f = self.h5_file
        self.volume_dataset = f[self.volume_picked]
        # If a secondary probe dataset (Plot2B) is selected, keep an HDF5 dataset ref too
        if getattr(self, 'volume_picked_b', None):
            try:
                self.volume_dataset_b = f[self.volume_picked_b]
            except Exception as _e:
                print(f"WARNING: unable to open volume_picked_b '{self.volume_picked_b}': {_e}")
        # Load coordinate datasets and ensure they're at least 1D
        x_coords_raw = np.array(f.get(self.x_coords_picked))
        y_coords_raw = np.array(f.get(self.y_coords_picked))
        
        # Ensure arrays are at least 1D (handle scalar or 0D arrays)
        if x_coords_raw.ndim == 0:
            self.x_coords_dataset = np.array([x_coords_raw])
        else:
            self.x_coords_dataset = np.atleast_1d(x_coords_raw)
            
        if y_coords_raw.ndim == 0:
            self.y_coords_dataset = np.array([y_coords_raw])
        else:
            self.y_coords_dataset = np.atleast_1d(y_coords_raw)
        
        print(f"  Loaded x_coords: shape={self.x_coords_dataset.shape}, ndim={self.x_coords_dataset.ndim}")
        print(f"  Loaded y_coords: shape={self.y_coords_dataset.shape}, ndim={self.y_coords_dataset.ndim}")
        
        # Check if we're in single dataset mode for Plot1
        if getattr(self, 'plot1_single_dataset_picked', None):
            # Single dataset mode: use the selected dataset directly for preview
            print(f"Using single dataset for preview: {self.plot1_single_dataset_picked}")
            try:
                self.single_dataset = np.array(f.get(self.plot1_single_dataset_picked))
                print(f"  Successfully loaded single dataset, shape: {self.single_dataset.shape}, dtype: {self.single_dataset.dtype}")
            except Exception as e:
                print(f"ERROR loading single dataset '{self.plot1_single_dataset_picked}': {e}")
                import traceback
                traceback.print_exc()
                raise
            self.presample_dataset = None  # Not used in single dataset mode
            self.postsample_dataset = None  # Not used in single dataset mode
        else:
            # Ratio mode: use presample/postsample
            self.single_dataset = None  # Not used in ratio mode
            self.presample_dataset = np.array(f.get(self.presample_picked))
            self.postsample_dataset = np.array(f.get(self.postsample_picked))

        shape = self.volume_dataset.shape
        dtype = np.dtype("float32" if self.cached_cast_float else self.volume_dataset.dtype)
        self.shape = shape
        self.dtype = dtype

        # Use memmap if it exists, otherwise use direct HDF5 access
        # Don't create memmap cache during initial load - use direct HDF5 access for immediate display
        if self.mmap_filename and os.path.exists(self.mmap_filename):
            # Memmap cache exists - use it
            print(f"Using existing memmap cache file: {self.mmap_filename}")
            try:
                volume_memmap = np.memmap(self.mmap_filename, dtype=self.dtype, shape=self.shape, mode="r")
                print(f"Successfully loaded memmap file")
            except Exception as e:
                print(f"ERROR loading memmap file: {e}")
                print("Falling back to direct HDF5 access")
                self.mmap_filename = None
                # Fall through to direct HDF5 access
        else:
            # No memmap cache - use direct HDF5 access for immediate display
            print("Using direct HDF5 access (no memmap cache)")
            self.mmap_filename = None
        
        # If no memmap available, use direct HDF5 dataset access
        if self.mmap_filename is None:
            # Store the HDF5 dataset reference directly (don't load into memory immediately)
            # The dashboard will access slices on-demand
            print("Using direct HDF5 dataset reference (lazy loading)")
            # Create a wrapper that accesses the HDF5 dataset
            # For now, we'll return the dataset itself and let the dashboard handle it
            volume_memmap = self.volume_dataset  # Return HDF5 dataset reference, not a memmap
    
        # Verify coordinate dimensions match volume dimensions
        print(f"  Volume shape: {self.volume_dataset.shape}")
        print(f"  X coords length: {len(self.x_coords_dataset) if hasattr(self.x_coords_dataset, '__len__') else 'N/A (scalar)'}")
        print(f"  Y coords length: {len(self.y_coords_dataset) if hasattr(self.y_coords_dataset, '__len__') else 'N/A (scalar)'}")
        
        if not hasattr(self.x_coords_dataset, '__len__') or len(self.x_coords_dataset) != self.volume_dataset.shape[0]:
            raise ValueError(
                f"X coordinates dimension mismatch: volume has {self.volume_dataset.shape[0]} elements in first dimension, "
                f"but x_coords has {len(self.x_coords_dataset) if hasattr(self.x_coords_dataset, '__len__') else 'scalar'} elements"
            )
        if not hasattr(self.y_coords_dataset, '__len__') or len(self.y_coords_dataset) != self.volume_dataset.shape[1]:
            raise ValueError(
                f"Y coordinates dimension mismatch: volume has {self.volume_dataset.shape[1]} elements in second dimension, "
                f"but y_coords has {len(self.y_coords_dataset) if hasattr(self.y_coords_dataset, '__len__') else 'scalar'} elements"
            )

        self.target_x = self.x_coords_dataset.shape[0]
        self.target_y = self.y_coords_dataset.shape[0]
        self.target_size = self.target_x * self.target_y

        # Create preview based on mode
        if getattr(self, 'plot1_single_dataset_picked', None):
            # Single dataset mode: use the dataset directly
            try:
                print(f"  Single dataset shape: {self.single_dataset.shape}, size: {self.single_dataset.size}")
                print(f"  Target size: {self.target_x} x {self.target_y} = {self.target_x * self.target_y}")
                
                # Flatten the dataset if it's not already 1D
                if self.single_dataset.ndim > 1:
                    single_dataset_flat = self.single_dataset.flatten()
                else:
                    single_dataset_flat = self.single_dataset
                
                if single_dataset_flat.size != self.target_x * self.target_y:
                    raise ValueError(
                        f"Single dataset size mismatch: dataset has {single_dataset_flat.size} elements, "
                        f"but expected {self.target_x * self.target_y} (from {self.target_x} x {self.target_y} coords)"
                    )
                preview_rect = np.reshape(single_dataset_flat, (self.target_x, self.target_y))
                
                # Clean the data - replace any inf and nan values
                self.preview = np.nan_to_num(preview_rect, nan=0.0, posinf=0.0, neginf=0.0)
                
                # Normalize the data for rendering
                if np.max(self.preview) > np.min(self.preview):
                    self.preview = (self.preview - np.min(self.preview)) / (
                        np.max(self.preview) - np.min(self.preview)
                    )
                
                self.preview = self.preview.astype(np.float32)
                print(f"  Successfully created preview from single dataset, shape: {self.preview.shape}")
            except Exception as e:
                print(f"ERROR creating preview from single dataset: {e}")
                import traceback
                traceback.print_exc()
                raise
        else:
            # Ratio mode: use presample/postsample ratio
            assert self.presample_dataset.size == self.target_x * self.target_y
            assert self.postsample_dataset.size == self.target_x * self.target_y
            presample_rect = np.reshape( self.presample_dataset, (self.target_x, self.target_y))
            postsample_rect = np.reshape( self.postsample_dataset, (self.target_x, self.target_y))

            # Check for zeros in the data
            self.presample_zeros = np.sum(presample_rect == 0)
            self.postsample_zeros = np.sum(postsample_rect == 0)

            # Condition the data to avoid zeros
            # Add small epsilon to avoid division by zero
            epsilon = 1e-10
            self.presample_conditioned = np.where(
                presample_rect == 0, epsilon, presample_rect
            )
            self.postsample_conditioned = np.where(
                postsample_rect == 0, epsilon, postsample_rect
            )

            # Calculate preview with conditioned data
            self.preview = self.presample_conditioned / self.postsample_conditioned

            # Clean the data - replace any remaining inf and nan values
            self.preview = np.nan_to_num(self.preview, nan=0.0, posinf=1.0, neginf=0.0)

            # Normalize the data for rendering
            # # Avoid division by zero
            # Min-Max normalization to [0, 256] range
            if np.max(self.preview) > np.min(self.preview):
                self.preview = (self.preview - np.min(self.preview)) / (
                    np.max(self.preview) - np.min(self.preview)
                )  # * 255

            self.preview = self.preview.astype(np.float32)

            # # Load the volume data - try memmap first, then HDF5, then synthetic data
            # volume_memmap = None  # Initialize variable
            
            # if self.mmap_filename and os.path.exists(self.mmap_filename):
            #     # Verify memmap file content (not just size)
            #     try:
            #         volume_memmap = np.memmap(self.mmap_filename, dtype=self.dtype, shape=self.shape, mode="r")
            #         # Test a small sample to verify it's not all zeros
            #         sample_slice = volume_memmap[0, 0, :10, :10]
            #         if np.all(sample_slice == 0):
            #             print("WARNING: Memmap file contains all zeros! Removing corrupted file.")
            #             os.remove(self.mmap_filename)
            #             raise ValueError("Corrupted memmap file")
            #         print(f"Successfully loaded memmap file")
            #     except Exception as e:
            #         print(f"ERROR loading memmap file: {e}")
            #         volume_memmap = None
            
            # if volume_memmap is None:
            #     # Try loading from HDF5
            #     try:
            #         print("Loading HDF5 dataset into memory...")
            #         volume_memmap = self.volume_dataset[:]  # Load entire dataset into memory
            #         print(f"Successfully loaded HDF5 dataset (shape: {volume_memmap.shape})")
            #     except Exception as h5_error:
            #         print(f"ERROR loading HDF5 dataset: {h5_error}")
            #         print("Creating synthetic test data...")
                    
            #         # Create synthetic data for testing
            #         volume_memmap = np.zeros(self.shape, dtype=self.dtype)
            #         for u in range(self.shape[0]):
            #             for v in range(self.shape[1]):
            #                 pattern = np.sin(np.linspace(0, 4*np.pi, self.shape[2]))[:, None] * \
            #                          np.cos(np.linspace(0, 4*np.pi, self.shape[3]))[None, :]
            #                 pattern = pattern * (u + 1) * (v + 1) * 0.1
            #                 volume_memmap[u, v, :, :] = pattern
                    
            #         print(f"Created synthetic test data (shape: {volume_memmap.shape})")
        
        print(f"Successfully loaded data:")

        print(f"  Volume shape: {volume_memmap.shape}")
        print(f"  X coords shape: {self.x_coords_dataset.shape}")
        print(f"  Y coords shape: {self.y_coords_dataset.shape}")
        print(f"  Preview shape: {self.preview.shape if self.preview is not None else 'None'}")
    
        if self.presample_dataset is not None and self.postsample_dataset is not None:
            print(f"  Presample shape: {self.presample_dataset.shape}")
            print(f"  Postsample shape: {self.postsample_dataset.shape}")
        else:
            print(f"  Using single dataset mode (presample/postsample not used)")
            if hasattr(self, 'single_dataset') and self.single_dataset is not None:
                print(f"  Single dataset shape: {self.single_dataset.shape}")

        # Verify preview was created
        if self.preview is None:
            raise ValueError("Preview was not created! Check preview creation logic.")
        
        print(f"  Returning from load_nexus_data: volume={type(volume_memmap)}, presample={type(self.presample_dataset)}, postsample={type(self.postsample_dataset)}, preview={type(self.preview)}")
        return volume_memmap, self.presample_dataset, self.postsample_dataset, self.x_coords_dataset, self.y_coords_dataset, self.preview
    
    def create_memmap_cache_background(self):
        """
        Create memmap cache file in a background thread.
        This allows plots to display immediately while caching happens in the background.
        """
        def _create_memmap():
            try:
                # If no mmap filename provided, skip safely
                if not self.mmap_filename:
                    print("Skipping memmap cache creation (no mmap filename provided)")
                    return
                # Check if memmap already exists
                if self.mmap_filename and os.path.exists(self.mmap_filename):
                    print("Memmap cache already exists, skipping creation")
                    return
                
                # Check if we have write permissions
                mmap_dir = os.path.dirname(self.mmap_filename)
                if not os.access(mmap_dir, os.W_OK):
                    print(f"PERMISSION ERROR: No write permission to directory: {mmap_dir}")
                    print("Skipping memmap cache creation")
                    return
                
                if not hasattr(self, 'volume_dataset') or self.volume_dataset is None:
                    print("ERROR: volume_dataset not loaded, cannot create memmap cache")
                    return
                
                print(f"🔄 Background: Starting memmap cache creation: {self.mmap_filename}")
                
                # Load HDF5 data into memory first (this avoids dataspace errors)
                print("🔄 Background: Loading HDF5 dataset into memory for caching...")
                try:
                    volume_data = self.volume_dataset[:]  # Load entire dataset
                    print(f"✅ Background: Successfully loaded HDF5 data into memory (shape: {volume_data.shape})")
                except Exception as h5_error:
                    print(f"❌ Background: ERROR loading HDF5 dataset: {h5_error}")
                    return
                
                # Now create memmap from the loaded data
                print("🔄 Background: Creating memmap file from loaded data...")
                write = np.memmap(self.mmap_filename, dtype=self.dtype, shape=self.shape, mode="w+")
                
                # Copy data slice by slice to avoid memory issues
                for u in range(self.shape[0]):
                    if u % 50 == 0 or u == self.shape[0] - 1:  # Print progress every 50 slices
                        print(f"🔄 Background: Caching slice {u+1}/{self.shape[0]}")
                    try:
                        piece = volume_data[u, :, :, :]
                        piece = piece.astype(np.float32) if self.cached_cast_float else piece
                        assert piece.dtype == self.dtype
                        write[u, :, :, :] = piece
                    except Exception as e:
                        print(f"❌ Background: ERROR caching slice {u}: {e}")
                        # Clean up partial memmap file
                        if os.path.exists(self.mmap_filename):
                            os.remove(self.mmap_filename)
                        return
                
                write.flush()
                del write
                del volume_data  # Free memory
                print(f"✅ Background: Memmap cache file created successfully: {self.mmap_filename}")
                print(f"✅ Background: Cache file size: {os.path.getsize(self.mmap_filename) / (1024**3):.2f} GB")
                
            except Exception as e:
                print(f"❌ Background: ERROR creating memmap cache: {e}")
                import traceback
                print(traceback.format_exc())
        
        # Start background thread
        thread = threading.Thread(target=_create_memmap, daemon=True)
        thread.start()
        print("🚀 Started background thread for memmap cache creation")

    def get_memmap_filename_for(self, dataset_path):
        """Generate a human-readable, deterministic memmap filename based on picked volume name."""
        # Prefer explicit cache dir; otherwise use same dir as nexus file
        base_dir = self.memmap_cache_dir or os.path.dirname(self.nexus_filename)
        nxs_stem = os.path.splitext(os.path.basename(self.nexus_filename))[0]
        # Sanitize dataset path into a readable key (e.g., "waxs_azimuthal/data/I" -> "waxs_azimuthal_data_I")
        dataset_key = dataset_path.strip('/').replace('/', '_')
        # Fall back to hash only if key is empty for any reason
        if not dataset_key:
            dataset_key = hashlib.md5(dataset_path.encode('utf-8')).hexdigest()[:12]
        return os.path.join(base_dir, f"{nxs_stem}.{dataset_key}.float32.dat")

    def create_memmap_cache_background_for(self, dataset_path):
        """Create a memmap cache for an arbitrary dataset path (3D/4D) in background."""
        def _create(dataset_path):
            try:
                if dataset_path is None:
                    return
                target_mmap = self.get_memmap_filename_for(dataset_path)
                if os.path.exists(target_mmap):
                    print(f"Memmap cache already exists for {dataset_path}, skipping: {target_mmap}")
                    return
                mmap_dir = os.path.dirname(target_mmap)
                if not os.access(mmap_dir, os.W_OK):
                    print(f"PERMISSION ERROR: No write permission to directory: {mmap_dir}")
                    print("Skipping memmap cache creation for", dataset_path)
                    return
                with h5py.File(self.nexus_filename, 'r') as f:
                    dset = f[dataset_path]
                    shape = dset.shape
                    dtype = 'float32' if self.cached_cast_float else str(dset.dtype)
                    print(f"🔄 Background: Creating memmap for {dataset_path} -> {target_mmap} shape={shape} dtype={dtype}")
                    write = np.memmap(target_mmap, dtype=np.float32 if self.cached_cast_float else dset.dtype, shape=shape, mode='w+')
                    # Copy chunk-wise for 4D/3D
                    if len(shape) == 4:
                        for u in range(shape[0]):
                            if u % 50 == 0 or u == shape[0]-1:
                                print(f"🔄 Background: Caching 4D slice {u+1}/{shape[0]}")
                            piece = dset[u, :, :, :]
                            piece = piece.astype(np.float32) if self.cached_cast_float else piece
                            write[u, :, :, :] = piece
                    elif len(shape) == 3:
                        for u in range(shape[0]):
                            if u % 50 == 0 or u == shape[0]-1:
                                print(f"🔄 Background: Caching 3D slice {u+1}/{shape[0]}")
                            piece = dset[u, :, :]
                            piece = piece.astype(np.float32) if self.cached_cast_float else piece
                            write[u, :, :] = piece
                    else:
                        # Fallback: copy whole array
                        data = dset[:]
                        data = data.astype(np.float32) if self.cached_cast_float else data
                        write[...] = data
                    write.flush()
                    del write
                    print(f"✅ Background: Memmap created for {dataset_path}")
            except Exception as e:
                print(f"❌ Background: ERROR creating memmap for {dataset_path}: {e}")
        threading.Thread(target=_create, args=(dataset_path,), daemon=True).start()
                   
