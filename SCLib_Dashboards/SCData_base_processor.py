"""
Base Data Processor Class for Dashboard Data Management

This module provides a generic data processor class that can be specialized
for different file formats (Nexus/HDF5, Zarr, etc.).

The class supports:
- Dataset discovery and categorization
- State management (save/load JSON)
- Change tracking for logging
- Memmap cache management
- Coordinate and preview data handling
"""

import os
import numpy as np
import json
import threading
import hashlib
from typing import Optional, Dict, List, Tuple, Any, Union, Callable
from datetime import datetime
from enum import Enum
import copy


class DatasetCategory(Enum):
    """Dataset categorization types"""
    VOLUME_DATA = "volume_data"
    COORDINATE_DATA = "coordinate_data"
    INTENSITY_DATA = "intensity_data"
    OTHER_DATA = "other_data"


class BaseDataProcessor:
    """
    Base class for data processors with comprehensive state management.
    
    This class encapsulates common data processing functionality including
    dataset discovery, categorization, state management, and change tracking.
    """
    
    def __init__(
        self,
        filename: str,
        mmap_filename: Optional[str] = None,
        cached_cast_float: bool = True,
        status_callback: Optional[Callable[[str], None]] = None,
        track_changes: bool = True,
    ):
        """
        Initialize a BaseDataProcessor instance.
        
        Args:
            filename: Path to the data file
            mmap_filename: Optional path to memmap cache file
            cached_cast_float: Whether to cast to float32 in cache
            status_callback: Optional callback for status messages
            track_changes: Whether to track state changes for logging
        """
        self.filename = filename
        self.mmap_filename = mmap_filename
        self.cached_cast_float = cached_cast_float
        self.status_callback = status_callback
        self.track_changes = track_changes
        self.DEBUG = True
        
        # Dataset selections
        self.volume_picked = None
        self.presample_picked = None
        self.postsample_picked = None
        self.x_coords_picked = None
        self.y_coords_picked = None
        self.preview_picked = None
        self.probe_x_coords_picked = None
        self.probe_y_coords_picked = None
        self.plot1_single_dataset_picked = None
        
        # Optional duplicate plot selections
        self.volume_picked_b = None
        self.presample_picked_b = None
        self.postsample_picked_b = None
        self.plot1b_single_dataset_picked = None
        self.probe_x_coords_picked_b = None
        self.probe_y_coords_picked_b = None
        
        # Dataset references (format-specific)
        self.volume_dataset = None
        self.volume_dataset_b = None
        self.presample_dataset = None
        self.postsample_dataset = None
        self.x_coords_dataset = None
        self.y_coords_dataset = None
        self.preview_dataset = None
        
        # Data arrays
        self.target_x = None
        self.target_y = None
        self.target_size = None
        self.presample_zeros = None
        self.postsample_zeros = None
        self.presample_conditioned = None
        self.postsample_conditioned = None
        self.preview = None
        self.single_dataset = None
        
        # Metadata
        self.shape = None
        self.dtype = None
        self.names_categories = None
        self.dimensions_categories = None
        
        # Memmap cache directory
        self.memmap_cache_dir = os.getenv('MEMMAP_CACHE_DIR', None)
        
        # Flag to track if choices have been loaded (must be set before _capture_state)
        self.choices_done = False
        
        # File handle (format-specific implementations should manage this)
        self.file_handle = None
        
        # State management
        self._change_history: List[Dict[str, Any]] = []
        
        # Store initial state after initialization
        if self.track_changes:
            self._initial_state = self._capture_state(include_data=False)
        else:
            self._initial_state = None
    
    def debug_print(self, *args, **kwargs):
        """Print debug messages only if DEBUG is True"""
        message = ' '.join(str(arg) for arg in args)
        if self.status_callback:
            self.status_callback(message)
        if self.DEBUG:
            print(*args, **kwargs)
    
    def _record_change(self, action: str, details: Dict[str, Any]) -> None:
        """
        Record a state change for logging purposes.
        
        Args:
            action: Action that caused the change
            details: Dictionary with change details
        """
        if not self.track_changes:
            return
        
        change_record = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "details": details,
            "state_snapshot": self._capture_state(include_data=False)
        }
        self._change_history.append(change_record)
    
    def _capture_state(self, include_data: bool = False) -> Dict[str, Any]:
        """
        Capture current state as a dictionary.
        
        Args:
            include_data: Whether to include data arrays in the state
            
        Returns:
            Dictionary containing all processor state
        """
        state = {
            "filename": self.filename,
            "mmap_filename": self.mmap_filename,
            "cached_cast_float": self.cached_cast_float,
            "volume_picked": self.volume_picked,
            "presample_picked": self.presample_picked,
            "postsample_picked": self.postsample_picked,
            "x_coords_picked": self.x_coords_picked,
            "y_coords_picked": self.y_coords_picked,
            "preview_picked": self.preview_picked,
            "probe_x_coords_picked": self.probe_x_coords_picked,
            "probe_y_coords_picked": self.probe_y_coords_picked,
            "plot1_single_dataset_picked": self.plot1_single_dataset_picked,
            "volume_picked_b": self.volume_picked_b,
            "presample_picked_b": self.presample_picked_b,
            "postsample_picked_b": self.postsample_picked_b,
            "plot1b_single_dataset_picked": self.plot1b_single_dataset_picked,
            "probe_x_coords_picked_b": self.probe_x_coords_picked_b,
            "probe_y_coords_picked_b": self.probe_y_coords_picked_b,
            "target_x": self.target_x,
            "target_y": self.target_y,
            "target_size": self.target_size,
            "shape": list(self.shape) if self.shape is not None else None,
            "dtype": str(self.dtype) if self.dtype is not None else None,
            "choices_done": self.choices_done,
        }
        
        if include_data:
            # Note: Including full data arrays can be very large
            # Consider only including metadata about data arrays
            if self.preview is not None:
                state["preview_shape"] = list(self.preview.shape)
                state["preview_dtype"] = str(self.preview.dtype)
            if self.x_coords_dataset is not None:
                state["x_coords_shape"] = list(self.x_coords_dataset.shape)
            if self.y_coords_dataset is not None:
                state["y_coords_shape"] = list(self.y_coords_dataset.shape)
        
        # Include categorization results
        if self.names_categories is not None:
            state["names_categories"] = copy.deepcopy(self.names_categories)
        if self.dimensions_categories is not None:
            state["dimensions_categories"] = copy.deepcopy(self.dimensions_categories)
        
        return state
    
    def get_state(self, include_data: bool = False) -> Dict[str, Any]:
        """
        Get current state as a dictionary.
        
        Args:
            include_data: Whether to include data arrays in the state
            
        Returns:
            Dictionary containing all processor state
        """
        return self._capture_state(include_data=include_data)
    
    def get_state_json(self, include_data: bool = False, indent: int = 2) -> str:
        """
        Get current state as a JSON string.
        
        Args:
            include_data: Whether to include data arrays in the state
            indent: JSON indentation level
            
        Returns:
            JSON string containing all processor state
        """
        state = self.get_state(include_data=include_data)
        return json.dumps(state, indent=indent, default=str)
    
    def load_state(self, state: Union[Dict[str, Any], str], restore_data: bool = False) -> None:
        """
        Load state from a dictionary or JSON string.
        
        Args:
            state: State dictionary or JSON string
            restore_data: Whether to restore data arrays (if present in state)
        """
        if isinstance(state, str):
            state = json.loads(state)
        
        # Restore all properties
        self.filename = state.get("filename", self.filename)
        self.mmap_filename = state.get("mmap_filename", self.mmap_filename)
        self.cached_cast_float = state.get("cached_cast_float", self.cached_cast_float)
        self.volume_picked = state.get("volume_picked", self.volume_picked)
        self.presample_picked = state.get("presample_picked", self.presample_picked)
        self.postsample_picked = state.get("postsample_picked", self.postsample_picked)
        self.x_coords_picked = state.get("x_coords_picked", self.x_coords_picked)
        self.y_coords_picked = state.get("y_coords_picked", self.y_coords_picked)
        self.preview_picked = state.get("preview_picked", self.preview_picked)
        self.probe_x_coords_picked = state.get("probe_x_coords_picked", self.probe_x_coords_picked)
        self.probe_y_coords_picked = state.get("probe_y_coords_picked", self.probe_y_coords_picked)
        self.plot1_single_dataset_picked = state.get("plot1_single_dataset_picked", self.plot1_single_dataset_picked)
        self.volume_picked_b = state.get("volume_picked_b", self.volume_picked_b)
        self.presample_picked_b = state.get("presample_picked_b", self.presample_picked_b)
        self.postsample_picked_b = state.get("postsample_picked_b", self.postsample_picked_b)
        self.plot1b_single_dataset_picked = state.get("plot1b_single_dataset_picked", self.plot1b_single_dataset_picked)
        self.probe_x_coords_picked_b = state.get("probe_x_coords_picked_b", self.probe_x_coords_picked_b)
        self.probe_y_coords_picked_b = state.get("probe_y_coords_picked_b", self.probe_y_coords_picked_b)
        self.target_x = state.get("target_x", self.target_x)
        self.target_y = state.get("target_y", self.target_y)
        self.target_size = state.get("target_size", self.target_size)
        
        shape = state.get("shape", None)
        if shape is not None:
            self.shape = tuple(shape)
        dtype_str = state.get("dtype", None)
        if dtype_str is not None:
            self.dtype = np.dtype(dtype_str)
        
        self.choices_done = state.get("choices_done", False)
        
        # Restore categorization results
        if "names_categories" in state:
            self.names_categories = state["names_categories"]
        if "dimensions_categories" in state:
            self.dimensions_categories = state["dimensions_categories"]
        
        # Track this change
        if self.track_changes:
            self._record_change("load_state", {"restore_data": restore_data})
    
    def get_change_history(self) -> List[Dict[str, Any]]:
        """
        Get the history of state changes.
        
        Returns:
            List of change records
        """
        return copy.deepcopy(self._change_history)
    
    def clear_change_history(self) -> None:
        """Clear the change history."""
        self._change_history = []
    
    def reset_state(self) -> None:
        """Reset processor to initial state."""
        if self._initial_state is not None:
            self.load_state(self._initial_state, restore_data=False)
        if self.track_changes:
            self._record_change("reset_state", {})
    
    # Abstract methods that must be implemented by subclasses
    def get_choices(self) -> bool:
        """
        Discover and categorize all datasets in the file.
        
        Returns:
            True if successful, False otherwise
        """
        raise NotImplementedError("Subclasses must implement get_choices()")
    
    def load_dataset_by_path(self, dataset_path: str) -> Optional[np.ndarray]:
        """
        Load a specific dataset from the file by path.
        
        Args:
            dataset_path: Path to the dataset within the file
            
        Returns:
            numpy.ndarray: The loaded dataset, or None if error
        """
        raise NotImplementedError("Subclasses must implement load_dataset_by_path()")
    
    def load_data(self) -> Tuple[Any, Optional[np.ndarray], Optional[np.ndarray], np.ndarray, np.ndarray, np.ndarray]:
        """
        Load the main data (volume, presample, postsample, coordinates, preview).
        
        Returns:
            Tuple of (volume, presample, postsample, x_coords, y_coords, preview)
        """
        raise NotImplementedError("Subclasses must implement load_data()")
    
    def load_probe_coordinates(self, use_b: bool = False) -> Optional[np.ndarray]:
        """
        Load probe coordinates from the file.
        
        Args:
            use_b: If True, use probe_x_coords_picked_b instead of probe_x_coords_picked
            
        Returns:
            numpy.ndarray: Probe coordinates or None if error
        """
        raise NotImplementedError("Subclasses must implement load_probe_coordinates()")
    
    # Common utility methods
    def get_datasets_by_dimension(self, target_dimension: Union[int, str]) -> List[Dict[str, Any]]:
        """
        Get datasets filtered by dimension.
        
        Args:
            target_dimension: Target dimension (1, 2, 3, 4, 'scalar', 'unknown')
            
        Returns:
            List of datasets with the specified dimension
        """
        if not hasattr(self, 'dimensions_categories') or self.dimensions_categories is None:
            return []
        
        if isinstance(target_dimension, int):
            dim_key = f'{target_dimension}d'
        else:
            dim_key = target_dimension
            
        return self.dimensions_categories.get(dim_key, [])
    
    def print_dimension_summary(self) -> None:
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
    
    def get_largest_datasets_by_dimension(self, max_datasets: int = 5) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get the largest datasets for each dimension category.
        
        Args:
            max_datasets: Maximum number of datasets to return per dimension
            
        Returns:
            Dictionary with dimension keys and lists of largest datasets
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
    
    def get_dataset_size_from_path(self, dataset_path: str) -> Optional[int]:
        """
        Get the size of a 1D dataset from the datasets list without loading it.
        
        Args:
            dataset_path: Path to the dataset
            
        Returns:
            Size of the dataset (for 1D datasets) or None if not found
        """
        datasets_1d = self.get_datasets_by_dimension(1)
        for dataset in datasets_1d:
            if dataset['path'] == dataset_path:
                shape = dataset.get('shape', ())
                if isinstance(shape, tuple) and len(shape) == 1:
                    return shape[0]
        return None
    
    def find_1d_dataset_by_size(
        self, 
        target_size: int, 
        exclude_paths: Optional[List[str]] = None
    ) -> Optional[str]:
        """
        Find a 1D dataset with the specified size.
        
        Args:
            target_size: Target size for the 1D dataset
            exclude_paths: Optional list of paths to exclude from search
            
        Returns:
            Dataset path with shape info as string (format: "path (shape)") or None
        """
        if exclude_paths is None:
            exclude_paths = []
        
        datasets_1d = self.get_datasets_by_dimension(1)
        for dataset in datasets_1d:
            dataset_path = dataset['path']
            # Check if this path should be excluded
            excluded = False
            for exclude_path in exclude_paths:
                if isinstance(exclude_path, str):
                    # If exclude_path is a choice string, extract the path
                    if ' (' in exclude_path:
                        exclude_path_clean = exclude_path[:exclude_path.rfind(' (')]
                    else:
                        exclude_path_clean = exclude_path
                    if dataset_path == exclude_path_clean:
                        excluded = True
                        break
            if excluded:
                continue
            
            shape = dataset.get('shape', ())
            if isinstance(shape, tuple) and len(shape) == 1 and shape[0] == target_size:
                return f"{dataset['path']} {dataset['shape']}"
        return None
    
    def find_1d_dataset_in_parent_by_size(
        self, 
        dataset_path: str, 
        target_size: int, 
        coord_index: int
    ) -> Optional[str]:
        """
        Find a 1D dataset in the same parent directory with the specified size.
        
        Args:
            dataset_path: Full path like "dir1/dir2/data1"
            target_size: Target size for the coordinate dataset
            coord_index: Which dimension index (0=x, 1=y, 2=z, 3=u) - for logging only
            
        Returns:
            Dataset path with shape info as string (format: "path (shape)") or None
        """
        # Get parent directory
        parent_dir = '/'.join(dataset_path.split('/')[:-1])
        if not parent_dir:
            return None
        
        # Look for 1D datasets in the same parent directory
        datasets_1d = self.get_datasets_by_dimension(1)
        for dataset in datasets_1d:
            dataset_path_full = dataset['path']
            # Check if it's in the same parent directory
            if dataset_path_full.startswith(parent_dir + '/'):
                shape = dataset.get('shape', ())
                if isinstance(shape, tuple) and len(shape) == 1 and shape[0] == target_size:
                    return f"{dataset_path_full} {dataset['shape']}"
        return None
    
    def auto_populate_map_coords(self, plot1_shape: Optional[Tuple[int, ...]]) -> Tuple[Optional[str], Optional[str]]:
        """
        Auto-populate Map X and Map Y coordinates based on 2D dataset shape.
        
        Args:
            plot1_shape: Shape tuple of the 2D dataset (should be 2D)
            
        Returns:
            Tuple of (map_x_choice, map_y_choice) as strings with shape info, or (None, None)
        """
        if plot1_shape is None or len(plot1_shape) != 2:
            return None, None
        
        map_x_size, map_y_size = plot1_shape[0], plot1_shape[1]
        
        # Find 1D datasets matching the sizes
        map_x_choice = self.find_1d_dataset_by_size(map_x_size)
        map_y_choice = self.find_1d_dataset_by_size(
            map_y_size,
            exclude_paths=[map_x_choice] if map_x_choice else []
        )
        
        return map_x_choice, map_y_choice
    
    def auto_populate_probe_coords(
        self, 
        probe_dataset_path: str, 
        probe_shape: Optional[Tuple[int, ...]]
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Auto-populate Probe X and Probe Y coordinates based on probe dataset shape.
        
        Dimension semantics (convention):
        - 3D datasets: shape = (map_x, map_y, probe_z) where probe_z is the probe dimension
        - 4D datasets: shape = (map_x, map_y, probe_z, probe_u) where probe_z and probe_u are probe dimensions
        
        For 3D datasets: Probe X should be size probe_z, Probe Y should be None
        For 4D datasets: Probe X should be size probe_z, Probe Y should be size probe_u
        
        Args:
            probe_dataset_path: Path to the probe dataset
            probe_shape: Shape tuple of the probe dataset (should be 3D or 4D)
            
        Returns:
            Tuple of (probe_x_choice, probe_y_choice) as strings with shape info, or (None, None)
        """
        if probe_shape is None:
            return None, None
        
        if len(probe_shape) == 3:
            # 3D dataset: shape is (map_x, map_y, probe_z)
            # Dimension indices: 0=map_x, 1=map_y, 2=probe_z
            probe_z_size = probe_shape[2]  # probe dimension at index 2
            probe_x_choice = self.find_1d_dataset_in_parent_by_size(probe_dataset_path, probe_z_size, 2)
            return probe_x_choice, None  # No Probe Y for 3D
        elif len(probe_shape) == 4:
            # 4D dataset: shape is (map_x, map_y, probe_z, probe_u)
            # Dimension indices: 0=map_x, 1=map_y, 2=probe_z, 3=probe_u
            probe_z_size = probe_shape[2]  # probe z dimension at index 2
            probe_u_size = probe_shape[3]   # probe u dimension at index 3
            probe_x_choice = self.find_1d_dataset_in_parent_by_size(probe_dataset_path, probe_z_size, 2)
            probe_y_choice = self.find_1d_dataset_in_parent_by_size(probe_dataset_path, probe_u_size, 3)
            return probe_x_choice, probe_y_choice
        
        return None, None
    
    def detect_map_flip_needed(
        self,
        data_shape: Tuple[int, ...],
        x_coord_size: Optional[int],
        y_coord_size: Optional[int]
    ) -> bool:
        """
        Detect if map coordinates need to be flipped (swapped) to match data dimensions.
        
        Dimension semantics:
        - 2D data: shape = (dim0, dim1) where dim0 is first spatial dimension, dim1 is second
        - x_coord_size should match dim0, y_coord_size should match dim1 for no flip
        - If x_coord_size matches dim1 and y_coord_size matches dim0, flip is needed
        
        Args:
            data_shape: Shape tuple of the 2D dataset (should be 2D)
            x_coord_size: Size of the X coordinate dataset (1D)
            y_coord_size: Size of the Y coordinate dataset (1D)
            
        Returns:
            True if coordinates need to be flipped (swapped), False otherwise
        """
        if len(data_shape) != 2:
            return False
        
        if x_coord_size is None or y_coord_size is None:
            return False
        
        dim0_size, dim1_size = data_shape[0], data_shape[1]
        
        # Normal case: x_coord matches dim0, y_coord matches dim1
        if x_coord_size == dim0_size and y_coord_size == dim1_size:
            return False
        
        # Flipped case: x_coord matches dim1, y_coord matches dim0
        if x_coord_size == dim1_size and y_coord_size == dim0_size:
            return True
        
        # Sizes don't match either way - warn but don't flip
        self.debug_print(
            f"Warning: Map coordinate sizes ({x_coord_size}, {y_coord_size}) "
            f"don't match data shape {data_shape} - no flip applied"
        )
        return False
    
    def detect_probe_flip_needed(
        self,
        volume_shape: Tuple[int, ...],
        probe_x_size: Optional[int],
        probe_y_size: Optional[int]
    ) -> bool:
        """
        Detect if probe coordinates need to be flipped (swapped) to match volume dimensions.
        
        Dimension semantics (convention):
        - 4D volume: shape = (map_x, map_y, probe_z, probe_u)
        - Dimension indices: 0=map_x, 1=map_y, 2=probe_z, 3=probe_u
        - probe_x_size should match probe_z (index 2), probe_y_size should match probe_u (index 3) for no flip
        - If probe_x_size matches probe_u (index 3) and probe_y_size matches probe_z (index 2), flip is needed
        
        Note: This only applies to 4D volumes. 3D volumes don't need probe flipping.
        
        Args:
            volume_shape: Shape tuple of the volume dataset (should be 4D)
            probe_x_size: Size of the Probe X coordinate dataset (1D)
            probe_y_size: Size of the Probe Y coordinate dataset (1D)
            
        Returns:
            True if coordinates need to be flipped (swapped), False otherwise
        """
        if len(volume_shape) != 4:
            return False  # Only 4D volumes can have probe flipping
        
        if probe_x_size is None or probe_y_size is None:
            return False
        
        # Dimension indices: 0=map_x, 1=map_y, 2=probe_z, 3=probe_u
        probe_z_size = volume_shape[2]  # probe z dimension at index 2
        probe_u_size = volume_shape[3]  # probe u dimension at index 3
        
        # Data convention: initial_slice = volume[:, :, :, :] has shape (z, u)
        # - initial_slice.shape[0] = z (from volume.shape[2])
        # - initial_slice.shape[1] = u (from volume.shape[3])
        # 
        # User wants: z (shape[0]) on x-axis, u (shape[1]) on y-axis
        # But Bokeh interprets: shape[0] = y-axis, shape[1] = x-axis
        # So we need to transpose if: px matches u (shape[1]) and py matches z (shape[0])
        # Because we need u on x-axis, which means u should be shape[1] after transpose
        # 
        # Normal case: probe_x matches probe_z (shape[0]), probe_y matches probe_u (shape[1])
        # This means: z should be on x-axis, u should be on y-axis
        # But Bokeh puts shape[0] on y-axis, so we DON'T transpose - data stays (z, u)
        # Wait, that doesn't work. Let me think...
        # 
        # Actually: if px matches z and py matches u, user wants z on x-axis
        # Bokeh: shape[0] = y-axis, shape[1] = x-axis
        # So if data is (z, u): shape[0]=z goes to y-axis (wrong), shape[1]=u goes to x-axis (wrong)
        # We need z on x-axis, so z should be shape[1]
        # We need u on y-axis, so u should be shape[0]
        # So we need to transpose: (z, u) → (u, z)
        # 
        # Normal case: probe_x matches probe_z, probe_y matches probe_u
        # User wants: z (shape[0]) on x-axis, u (shape[1]) on y-axis
        # But Bokeh: shape[0] = y-axis, shape[1] = x-axis
        # So if data is (z, u): shape[0]=z goes to y-axis (wrong), shape[1]=u goes to x-axis (wrong)
        # We need z on x-axis, so z should be shape[1] → need transpose
        # We need u on y-axis, so u should be shape[0] → need transpose
        # So transpose: (z, u) → (u, z)
        # Normal case: probe_x matches probe_z, probe_y matches probe_u
        # This means: px (x-axis) matches z, py (y-axis) matches u
        # User wants: z on x-axis, u on y-axis
        # Data is (z, u): shape[0]=z, shape[1]=u
        # Bokeh: shape[0] = y-axis, shape[1] = x-axis
        # To get z on x-axis: z should be shape[1] → need transpose
        # To get u on y-axis: u should be shape[0] → need transpose
        # So transpose: (z, u) → (u, z)
        if probe_x_size == probe_z_size and probe_y_size == probe_u_size:
            return True  # Need to transpose: (z, u) → (u, z) so z becomes shape[1] (x-axis)
        
        # Flipped case: probe_x matches probe_u, probe_y matches probe_z
        # This means: px (x-axis) matches u, py (y-axis) matches z
        # User wants: u on x-axis, z on y-axis
        # Data is (z, u): shape[0]=z, shape[1]=u
        # Bokeh: shape[0] = y-axis, shape[1] = x-axis
        # To get u on x-axis: u should be shape[1] → u is already shape[1] ✓
        # To get z on y-axis: z should be shape[0] → z is already shape[0] ✓
        # So no transpose needed
        if probe_x_size == probe_u_size and probe_y_size == probe_z_size:
            return False  # No transpose: (z, u) stays as is, u is already shape[1] (x-axis)
        
        # Sizes don't match either way - warn but don't flip
        # Check if sizes are actually strings (paths) instead of integers - this indicates a bug in the caller
        if isinstance(probe_x_size, str) or isinstance(probe_y_size, str):
            self.debug_print(
                f"ERROR: detect_probe_flip_needed received coordinate paths instead of sizes! "
                f"probe_x_size={probe_x_size}, probe_y_size={probe_y_size}. "
                f"Caller should use get_dataset_size_from_path() first."
            )
            return False
        
        self.debug_print(
            f"Warning: Probe coordinate sizes (x={probe_x_size}, y={probe_y_size}) "
            f"don't match volume probe dimensions (z={probe_z_size}, u={probe_u_size}) - no flip applied"
        )
        return False
    
    def debug_print(self, message: str) -> None:
        """Print debug message if DEBUG is enabled."""
        if self.DEBUG:
            print(message)
    
    def get_memmap_filename_for(self, dataset_path: str) -> str:
        """
        Generate a human-readable, deterministic memmap filename based on dataset path.
        
        Args:
            dataset_path: Path to the dataset
            
        Returns:
            Path to memmap cache file
        """
        base_dir = self.memmap_cache_dir or os.path.dirname(self.filename)
        file_stem = os.path.splitext(os.path.basename(self.filename))[0]
        dataset_key = dataset_path.strip('/').replace('/', '_')
        
        if not dataset_key:
            dataset_key = hashlib.md5(dataset_path.encode('utf-8')).hexdigest()[:12]
        
        return os.path.join(base_dir, f"{file_stem}.{dataset_key}.float32.dat")
    
    def create_memmap_cache_background(self) -> None:
        """
        Create memmap cache file in a background thread.
        This allows plots to display immediately while caching happens in the background.
        """
        raise NotImplementedError("Subclasses should implement create_memmap_cache_background()")
    
    def create_memmap_cache_background_for(self, dataset_path: str) -> None:
        """
        Create a memmap cache for an arbitrary dataset path in background.
        
        Args:
            dataset_path: Path to the dataset to cache
        """
        raise NotImplementedError("Subclasses should implement create_memmap_cache_background_for()")
    
    def set_volume_picked(self, path: str) -> None:
        """Set the volume dataset path."""
        old_path = self.volume_picked
        self.volume_picked = path
        if self.track_changes:
            self._record_change("set_volume_picked", {
                "old_path": old_path,
                "new_path": path
            })
    
    def set_coordinates(self, x_path: Optional[str] = None, y_path: Optional[str] = None) -> None:
        """Set coordinate dataset paths."""
        old_x = self.x_coords_picked
        old_y = self.y_coords_picked
        
        if x_path is not None:
            self.x_coords_picked = x_path
        if y_path is not None:
            self.y_coords_picked = y_path
        
        if self.track_changes:
            self._record_change("set_coordinates", {
                "old_x": old_x,
                "old_y": old_y,
                "new_x": self.x_coords_picked,
                "new_y": self.y_coords_picked
            })
    
    def set_plot1_mode(
        self,
        single_dataset_path: Optional[str] = None,
        numerator_path: Optional[str] = None,
        denominator_path: Optional[str] = None
    ) -> None:
        """
        Set Plot1 mode (single dataset or ratio).
        
        Args:
            single_dataset_path: Path for single dataset mode
            numerator_path: Path for numerator in ratio mode
            denominator_path: Path for denominator in ratio mode
        """
        old_single = self.plot1_single_dataset_picked
        old_num = self.presample_picked
        old_den = self.postsample_picked
        
        if single_dataset_path is not None:
            self.plot1_single_dataset_picked = single_dataset_path
            self.presample_picked = None
            self.postsample_picked = None
        elif numerator_path is not None and denominator_path is not None:
            self.plot1_single_dataset_picked = None
            self.presample_picked = numerator_path
            self.postsample_picked = denominator_path
        
        if self.track_changes:
            self._record_change("set_plot1_mode", {
                "old_single": old_single,
                "old_numerator": old_num,
                "old_denominator": old_den,
                "new_single": self.plot1_single_dataset_picked,
                "new_numerator": self.presample_picked,
                "new_denominator": self.postsample_picked
            })
    
    def close(self) -> None:
        """Close file handles and clean up resources."""
        if self.file_handle is not None:
            try:
                self.file_handle.close()
            except Exception:
                pass
            self.file_handle = None
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

