"""
Zarr Data Processor

This module provides a specialized data processor for Zarr files,
extending the base processor with Zarr-specific functionality.
"""

import os
import numpy as np
import threading
from typing import Optional, Dict, List, Tuple, Any

# Import zarr for runtime use
try:
    import zarr
    ZARR_AVAILABLE = True
except ImportError:
    ZARR_AVAILABLE = False
    zarr = None

from .SCData_base_processor import BaseDataProcessor


class ProcessZarr(BaseDataProcessor):
    """
    Specialized data processor for Zarr files.
    
    This class handles Zarr-specific operations including dataset discovery,
    lazy loading, and memmap cache creation.
    """
    
    def __init__(
        self,
        zarr_filename: str,
        mmap_filename: Optional[str] = None,
        cached_cast_float: bool = True,
        status_callback: Optional[Any] = None,
        track_changes: bool = True,
    ):
        """
        Initialize a ProcessZarr instance.
        
        Args:
            zarr_filename: Path to the Zarr file or directory
            mmap_filename: Optional path to memmap cache file
            cached_cast_float: Whether to cast to float32 in cache
            status_callback: Optional callback for status messages
            track_changes: Whether to track state changes
        """
        if not ZARR_AVAILABLE:
            raise ImportError("zarr library is required for ProcessZarr. Install with: pip install zarr")
        
        super().__init__(
            filename=zarr_filename,
            mmap_filename=mmap_filename,
            cached_cast_float=cached_cast_float,
            status_callback=status_callback,
            track_changes=track_changes,
        )
        
        self.zarr_filename = zarr_filename  # Alias for compatibility
        self.zarr_group = None
        
        # Store initial state after initialization
        if self.track_changes:
            self._initial_state = self._capture_state(include_data=False)
    
    def _open_zarr(self):
        """Open the Zarr file/group."""
        if self.zarr_group is None:
            if os.path.isdir(self.zarr_filename):
                # Zarr directory
                self.zarr_group = zarr.open(self.zarr_filename, mode='r')
            elif os.path.isfile(self.zarr_filename):
                # Zarr file (zip format)
                self.zarr_group = zarr.open(self.zarr_filename, mode='r')
            else:
                raise FileNotFoundError(f"Zarr file not found: {self.zarr_filename}")
            self.file_handle = self.zarr_group
        return self.zarr_group
    
    def get_choices(self) -> bool:
        """
        Discover and categorize all datasets in the Zarr file.
        
        Returns:
            True if successful, False otherwise
        """
        DEBUG_PREV = self.DEBUG
        self.DEBUG = False
        self.debug_print("=== get_choices() started ===")
        
        if not self.zarr_filename or not os.path.exists(self.zarr_filename):
            self.debug_print(f"ERROR: Zarr file not found: {self.zarr_filename}")
            return False
    
        self.debug_print(f"Opening Zarr file: {self.zarr_filename}")
    
        try:
            zarr_group = self._open_zarr()
            
            # Recursively find all arrays in the Zarr group
            def find_all_arrays(group, prefix=""):
                """Recursively find all arrays in a Zarr group"""
                arrays = []
                for key in group.keys():
                    full_path = f"{prefix}/{key}" if prefix else key
                    item = group[key]
                    if isinstance(item, zarr.Array):
                        arrays.append(full_path)
                    elif isinstance(item, zarr.Group):
                        arrays.extend(find_all_arrays(item, full_path))
                return arrays
            
            all_datasets = find_all_arrays(zarr_group)
            self.debug_print(f"Found {len(all_datasets)} arrays (recursively)")
            
            # Categorize datasets by name/keywords
            names_categories = {
                'volume_data': [],
                'coordinate_data': [],
                'intensity_data': [],
                'other_data': []
            }
            
            for dataset_path in all_datasets:
                path_lower = dataset_path.lower()
                
                if any(keyword in path_lower for keyword in ['pil', 'volume', 'data/i', 'intensity', 'waxs', 'detector']):
                    names_categories['volume_data'].append(dataset_path)
                elif any(keyword in path_lower for keyword in ['samx', 'samz', 'xrfx', 'xrfz', 'x', 'z', 'coord']):
                    names_categories['coordinate_data'].append(dataset_path)
                elif any(keyword in path_lower for keyword in ['presample', 'postsample', 'intensity']):
                    names_categories['intensity_data'].append(dataset_path)
                else:
                    names_categories['other_data'].append(dataset_path)
            
            self.names_categories = names_categories
            
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
                try:
                    # Navigate to the array
                    path_parts = dataset_path.split('/')
                    array = zarr_group
                    for part in path_parts:
                        array = array[part]
                    
                    if isinstance(array, zarr.Array):
                        shape = array.shape
                        ndim = len(shape)
                        
                        dim_info = {
                            'path': dataset_path,
                            'shape': shape,
                            'dtype': str(array.dtype)
                        }
                        
                        if ndim == 4:
                            dimensions_categories['4d'].append(dim_info)
                        elif ndim == 3:
                            dimensions_categories['3d'].append(dim_info)
                        elif ndim == 2:
                            dimensions_categories['2d'].append(dim_info)
                        elif ndim == 1:
                            dimensions_categories['1d'].append(dim_info)
                        elif ndim == 0:
                            dimensions_categories['scalar'].append(dim_info)
                        else:
                            dimensions_categories['unknown'].append(dim_info)
                    else:
                        dimensions_categories['unknown'].append({
                            'path': dataset_path,
                            'shape': 'group',
                            'dtype': 'group'
                        })
                except Exception as e:
                    dimensions_categories['unknown'].append({
                        'path': dataset_path,
                        'shape': 'error',
                        'dtype': 'error',
                        'error': str(e)
                    })
            
            self.dimensions_categories = dimensions_categories
            self.choices_done = True
            
            self.debug_print("=== get_choices() completed successfully ===")
            
            self.DEBUG = DEBUG_PREV
            
            if self.track_changes:
                self._record_change("get_choices", {
                    "num_datasets": len(all_datasets),
                    "num_4d": len(dimensions_categories['4d']),
                    "num_3d": len(dimensions_categories['3d']),
                    "num_2d": len(dimensions_categories['2d']),
                    "num_1d": len(dimensions_categories['1d']),
                })
            
            return True
        except Exception as e:
            self.debug_print(f'ERROR in get_choices(): {e}')
            return False
    
    def _get_array_by_path(self, dataset_path: str) -> Optional["zarr.Array"]:
        """Get a Zarr array by path."""
        try:
            zarr_group = self._open_zarr()
            path_parts = dataset_path.split('/')
            array = zarr_group
            for part in path_parts:
                array = array[part]
            if isinstance(array, zarr.Array):
                return array
            return None
        except Exception as e:
            self.debug_print(f"Error getting array {dataset_path}: {e}")
            return None
    
    def load_dataset_by_path(self, dataset_path: str) -> Optional[np.ndarray]:
        """
        Load a specific dataset from the Zarr file by path.
        
        Args:
            dataset_path: Path to the dataset within the Zarr file
            
        Returns:
            numpy.ndarray: The loaded dataset, or None if error
        """
        try:
            array = self._get_array_by_path(dataset_path)
            if array is None:
                return None
            # Zarr arrays support numpy-like indexing
            data = np.array(array[:])
            return data
        except Exception as e:
            self.debug_print(f"Error loading dataset {dataset_path}: {e}")
            return None
    
    def load_probe_coordinates(self, use_b: bool = False) -> Optional[np.ndarray]:
        """
        Load probe coordinates from the zarr file.
        
        Args:
            use_b: If True, use probe_x_coords_picked_b instead of probe_x_coords_picked
            
        Returns:
            numpy.ndarray: Probe coordinates or None if error
        """
        coord_path = getattr(self, 'probe_x_coords_picked_b', None) if use_b else self.probe_x_coords_picked
        if not coord_path:
            return None
            
        try:
            array = self._get_array_by_path(coord_path)
            if array is None:
                return None
            probe_coords = np.array(array[:])
            return probe_coords
        except Exception as e:
            self.debug_print(f"❌ Failed to load probe coordinates from {coord_path}: {e}")
            return None
    
    def load_data(self) -> Tuple[Any, Optional[np.ndarray], Optional[np.ndarray], np.ndarray, np.ndarray, np.ndarray]:
        """
        Load the main data (volume, presample, postsample, coordinates, preview).
        
        Returns:
            Tuple of (volume, presample, postsample, x_coords, y_coords, preview)
        """
        # Set default dataset paths if not already set
        # Note: These defaults are HDF5-specific - Zarr files may have different structures
        # Users should set these explicitly for Zarr files
        if self.volume_picked is None:
            # Try to find a 4D or 3D dataset
            datasets_4d = self.get_datasets_by_dimension(4)
            datasets_3d = self.get_datasets_by_dimension(3)
            if datasets_4d:
                self.volume_picked = datasets_4d[0]['path']
            elif datasets_3d:
                self.volume_picked = datasets_3d[0]['path']
            else:
                raise ValueError("No volume dataset found. Please set volume_picked explicitly.")
        
        if self.x_coords_picked is None:
            datasets_1d = self.get_datasets_by_dimension(1)
            # Try to find coordinate datasets
            for ds in datasets_1d:
                path_lower = ds['path'].lower()
                if any(kw in path_lower for kw in ['samx', 'xrfx', 'x']):
                    self.x_coords_picked = ds['path']
                    break
            if self.x_coords_picked is None and datasets_1d:
                self.x_coords_picked = datasets_1d[0]['path']
        
        if self.y_coords_picked is None:
            datasets_1d = self.get_datasets_by_dimension(1)
            for ds in datasets_1d:
                path_lower = ds['path'].lower()
                if any(kw in path_lower for kw in ['samz', 'xrfz', 'z']):
                    self.y_coords_picked = ds['path']
                    break
            if self.y_coords_picked is None and datasets_1d:
                # Use a different 1D dataset than x_coords
                for ds in datasets_1d:
                    if ds['path'] != self.x_coords_picked:
                        self.y_coords_picked = ds['path']
                        break
        
        if getattr(self, 'plot1_single_dataset_picked', None) is None:
            datasets_2d = self.get_datasets_by_dimension(2)
            if self.presample_picked is None and datasets_2d:
                for ds in datasets_2d:
                    path_lower = ds['path'].lower()
                    if 'presample' in path_lower or 'postsample' in path_lower:
                        if 'presample' in path_lower:
                            self.presample_picked = ds['path']
                        else:
                            self.postsample_picked = ds['path']
                if self.presample_picked is None and datasets_2d:
                    self.presample_picked = datasets_2d[0]['path']
                if self.postsample_picked is None and datasets_2d:
                    for ds in datasets_2d:
                        if ds['path'] != self.presample_picked:
                            self.postsample_picked = ds['path']
                            break

        self.debug_print(f"----> LOAD_DATA: zarr_filename: {self.zarr_filename}")
        self.debug_print(f"\t volume_picked: {self.volume_picked}")
        self.debug_print(f"\t x_coords_picked: {self.x_coords_picked}")
        self.debug_print(f"\t y_coords_picked: {self.y_coords_picked}")
        
        zarr_group = self._open_zarr()
        
        # Get volume array
        self.volume_dataset = self._get_array_by_path(self.volume_picked)
        if self.volume_dataset is None:
            raise ValueError(f"Volume dataset not found: {self.volume_picked}")
        
        # If a secondary probe dataset (Plot2B) is selected
        if getattr(self, 'volume_picked_b', None):
            try:
                self.volume_dataset_b = self._get_array_by_path(self.volume_picked_b)
            except Exception as _e:
                self.debug_print(f"WARNING: unable to open volume_picked_b '{self.volume_picked_b}': {_e}")
        
        # Load coordinate datasets
        x_array = self._get_array_by_path(self.x_coords_picked)
        y_array = self._get_array_by_path(self.y_coords_picked)
        
        if x_array is None or y_array is None:
            raise ValueError("Coordinate datasets not found")
        
        x_coords_raw = np.array(x_array[:])
        y_coords_raw = np.array(y_array[:])
        
        # Ensure arrays are at least 1D
        if x_coords_raw.ndim == 0:
            self.x_coords_dataset = np.array([x_coords_raw])
        else:
            self.x_coords_dataset = np.atleast_1d(x_coords_raw)
            
        if y_coords_raw.ndim == 0:
            self.y_coords_dataset = np.array([y_coords_raw])
        else:
            self.y_coords_dataset = np.atleast_1d(y_coords_raw)
        
        # Check if we're in single dataset mode for Plot1
        if getattr(self, 'plot1_single_dataset_picked', None):
            self.debug_print(f"Using single dataset for preview: {self.plot1_single_dataset_picked}")
            try:
                single_array = self._get_array_by_path(self.plot1_single_dataset_picked)
                if single_array is None:
                    raise ValueError(f"Single dataset not found: {self.plot1_single_dataset_picked}")
                self.single_dataset = np.array(single_array[:])
            except Exception as e:
                self.debug_print(f"ERROR loading single dataset '{self.plot1_single_dataset_picked}': {e}")
                raise
            self.presample_dataset = None
            self.postsample_dataset = None
        else:
            self.single_dataset = None
            presample_array = self._get_array_by_path(self.presample_picked)
            postsample_array = self._get_array_by_path(self.postsample_picked)
            if presample_array is None or postsample_array is None:
                raise ValueError("Presample or postsample dataset not found")
            self.presample_dataset = np.array(presample_array[:])
            self.postsample_dataset = np.array(postsample_array[:])

        shape = self.volume_dataset.shape
        dtype = np.dtype("float32" if self.cached_cast_float else self.volume_dataset.dtype)
        self.shape = shape
        self.dtype = dtype

        # Use memmap if it exists, otherwise use direct Zarr access
        if self.mmap_filename and os.path.exists(self.mmap_filename):
            self.debug_print(f"Using existing memmap cache file: {self.mmap_filename}")
            try:
                volume_memmap = np.memmap(self.mmap_filename, dtype=self.dtype, shape=self.shape, mode="r")
                self.debug_print(f"Successfully loaded memmap file")
            except Exception as e:
                self.debug_print(f"ERROR loading memmap file: {e}")
                self.mmap_filename = None
        
        if self.mmap_filename is None:
            self.debug_print("Using direct Zarr array reference (lazy loading)")
            # For Zarr, we can use the array directly with lazy loading
            volume_memmap = self.volume_dataset
        
        # Verify coordinate dimensions match volume dimensions
        if not hasattr(self.x_coords_dataset, '__len__') or len(self.x_coords_dataset) != self.volume_dataset.shape[0]:
            raise ValueError(
                f"X coordinates dimension mismatch: volume has {self.volume_dataset.shape[0]} elements, "
                f"but x_coords has {len(self.x_coords_dataset) if hasattr(self.x_coords_dataset, '__len__') else 'scalar'} elements"
            )
        if not hasattr(self.y_coords_dataset, '__len__') or len(self.y_coords_dataset) != self.volume_dataset.shape[1]:
            raise ValueError(
                f"Y coordinates dimension mismatch: volume has {self.volume_dataset.shape[1]} elements, "
                f"but y_coords has {len(self.y_coords_dataset) if hasattr(self.y_coords_dataset, '__len__') else 'scalar'} elements"
            )

        self.target_x = self.x_coords_dataset.shape[0]
        self.target_y = self.y_coords_dataset.shape[0]
        self.target_size = self.target_x * self.target_y

        # Create preview based on mode
        if getattr(self, 'plot1_single_dataset_picked', None):
            # Single dataset mode
            if self.single_dataset.ndim > 1:
                single_dataset_flat = self.single_dataset.flatten()
            else:
                single_dataset_flat = self.single_dataset
            
            if single_dataset_flat.size != self.target_x * self.target_y:
                raise ValueError(
                    f"Single dataset size mismatch: dataset has {single_dataset_flat.size} elements, "
                    f"but expected {self.target_x * self.target_y}"
                )
            preview_rect = np.reshape(single_dataset_flat, (self.target_x, self.target_y))
            self.preview = np.nan_to_num(preview_rect, nan=0.0, posinf=0.0, neginf=0.0)
            
            if np.max(self.preview) > np.min(self.preview):
                self.preview = (self.preview - np.min(self.preview)) / (np.max(self.preview) - np.min(self.preview))
            
            self.preview = self.preview.astype(np.float32)
        else:
            # Ratio mode
            assert self.presample_dataset.size == self.target_x * self.target_y
            assert self.postsample_dataset.size == self.target_x * self.target_y
            presample_rect = np.reshape(self.presample_dataset, (self.target_x, self.target_y))
            postsample_rect = np.reshape(self.postsample_dataset, (self.target_x, self.target_y))

            self.presample_zeros = np.sum(presample_rect == 0)
            self.postsample_zeros = np.sum(postsample_rect == 0)

            epsilon = 1e-10
            self.presample_conditioned = np.where(presample_rect == 0, epsilon, presample_rect)
            self.postsample_conditioned = np.where(postsample_rect == 0, epsilon, postsample_rect)

            self.preview = self.presample_conditioned / self.postsample_conditioned
            self.preview = np.nan_to_num(self.preview, nan=0.0, posinf=1.0, neginf=0.0)

            if np.max(self.preview) > np.min(self.preview):
                self.preview = (self.preview - np.min(self.preview)) / (np.max(self.preview) - np.min(self.preview))

            self.preview = self.preview.astype(np.float32)
        
        if self.track_changes:
            self._record_change("load_data", {
                "volume_shape": list(volume_memmap.shape) if hasattr(volume_memmap, 'shape') else None,
                "preview_shape": list(self.preview.shape) if self.preview is not None else None
            })
        
        return volume_memmap, self.presample_dataset, self.postsample_dataset, self.x_coords_dataset, self.y_coords_dataset, self.preview
    
    def create_memmap_cache_background(self) -> None:
        """Create memmap cache file in a background thread."""
        def _create_memmap():
            try:
                if not self.mmap_filename:
                    self.debug_print("Skipping memmap cache creation (no mmap filename provided)")
                    return
                if self.mmap_filename and os.path.exists(self.mmap_filename):
                    self.debug_print("Memmap cache already exists, skipping creation")
                    return
                
                mmap_dir = os.path.dirname(self.mmap_filename)
                if not os.access(mmap_dir, os.W_OK):
                    self.debug_print(f"PERMISSION ERROR: No write permission to directory: {mmap_dir}")
                    return
                
                if not hasattr(self, 'volume_dataset') or self.volume_dataset is None:
                    self.debug_print("ERROR: volume_dataset not loaded, cannot create memmap cache")
                    return
                
                self.debug_print(f"🔄 Background: Starting memmap cache creation: {self.mmap_filename}")
                
                self.debug_print("🔄 Background: Loading Zarr array into memory for caching...")
                try:
                    volume_data = np.array(self.volume_dataset[:])
                    self.debug_print(f"✅ Background: Successfully loaded Zarr data into memory (shape: {volume_data.shape})")
                except Exception as zarr_error:
                    self.debug_print(f"❌ Background: ERROR loading Zarr array: {zarr_error}")
                    return
                
                self.debug_print("🔄 Background: Creating memmap file from loaded data...")
                write = np.memmap(self.mmap_filename, dtype=self.dtype, shape=self.shape, mode="w+")
                
                for u in range(self.shape[0]):
                    if u % 50 == 0 or u == self.shape[0] - 1:
                        self.debug_print(f"🔄 Background: Caching slice {u+1}/{self.shape[0]}")
                    try:
                        piece = volume_data[u, :, :, :]
                        piece = piece.astype(np.float32) if self.cached_cast_float else piece
                        write[u, :, :, :] = piece
                    except Exception as e:
                        self.debug_print(f"❌ Background: ERROR caching slice {u}: {e}")
                        if os.path.exists(self.mmap_filename):
                            os.remove(self.mmap_filename)
                        return
                
                write.flush()
                del write
                del volume_data
                self.debug_print(f"✅ Background: Memmap cache file created successfully: {self.mmap_filename}")
                
            except Exception as e:
                self.debug_print(f"❌ Background: ERROR creating memmap cache: {e}")
        
        thread = threading.Thread(target=_create_memmap, daemon=True)
        thread.start()
        self.debug_print("🚀 Started background thread for memmap cache creation")
    
    def create_memmap_cache_background_for(self, dataset_path: str) -> None:
        """Create a memmap cache for an arbitrary dataset path in background."""
        def _create(dataset_path):
            try:
                if dataset_path is None:
                    return
                target_mmap = self.get_memmap_filename_for(dataset_path)
                if os.path.exists(target_mmap):
                    self.debug_print(f"Memmap cache already exists for {dataset_path}, skipping: {target_mmap}")
                    return
                mmap_dir = os.path.dirname(target_mmap)
                if not os.access(mmap_dir, os.W_OK):
                    self.debug_print(f"PERMISSION ERROR: No write permission to directory: {mmap_dir}")
                    return
                
                array = self._get_array_by_path(dataset_path)
                if array is None:
                    self.debug_print(f"ERROR: Array not found: {dataset_path}")
                    return
                
                shape = array.shape
                dtype = 'float32' if self.cached_cast_float else str(array.dtype)
                self.debug_print(f"🔄 Background: Creating memmap for {dataset_path} -> {target_mmap} shape={shape} dtype={dtype}")
                write = np.memmap(target_mmap, dtype=np.float32 if self.cached_cast_float else array.dtype, shape=shape, mode='w+')
                
                if len(shape) == 4:
                    for u in range(shape[0]):
                        if u % 50 == 0 or u == shape[0]-1:
                            self.debug_print(f"🔄 Background: Caching 4D slice {u+1}/{shape[0]}")
                        piece = np.array(array[u, :, :, :])
                        piece = piece.astype(np.float32) if self.cached_cast_float else piece
                        write[u, :, :, :] = piece
                elif len(shape) == 3:
                    for u in range(shape[0]):
                        if u % 50 == 0 or u == shape[0]-1:
                            self.debug_print(f"🔄 Background: Caching 3D slice {u+1}/{shape[0]}")
                        piece = np.array(array[u, :, :])
                        piece = piece.astype(np.float32) if self.cached_cast_float else piece
                        write[u, :, :] = piece
                else:
                    data = np.array(array[:])
                    data = data.astype(np.float32) if self.cached_cast_float else data
                    write[...] = data
                write.flush()
                del write
                self.debug_print(f"✅ Background: Memmap created for {dataset_path}")
            except Exception as e:
                self.debug_print(f"❌ Background: ERROR creating memmap for {dataset_path}: {e}")
        threading.Thread(target=_create, args=(dataset_path,), daemon=True).start()
    
    def close(self) -> None:
        """Close Zarr file handle."""
        if self.zarr_group is not None:
            # Zarr groups don't need explicit closing, but we'll clear the reference
            self.zarr_group = None
            self.file_handle = None

