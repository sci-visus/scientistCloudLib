"""
Nexus/HDF5 Data Processor

This module provides a specialized data processor for Nexus/HDF5 files,
extending the base processor with HDF5-specific functionality.
"""

import os
import numpy as np
import h5py
import threading
from typing import Optional, Dict, List, Tuple, Any
from .SCData_base_processor import BaseDataProcessor


class ProcessNexus(BaseDataProcessor):
    """
    Specialized data processor for Nexus/HDF5 files.
    
    This class handles HDF5-specific operations including dataset discovery,
    lazy loading, and memmap cache creation.
    """
    
    def __init__(
        self,
        nexus_filename: str,
        mmap_filename: Optional[str] = None,
        cached_cast_float: bool = True,
        status_callback: Optional[Any] = None,
        track_changes: bool = True,
    ):
        """
        Initialize a ProcessNexus instance.
        
        Args:
            nexus_filename: Path to the Nexus/HDF5 file
            mmap_filename: Optional path to memmap cache file
            cached_cast_float: Whether to cast to float32 in cache
            status_callback: Optional callback for status messages
            track_changes: Whether to track state changes
        """
        super().__init__(
            filename=nexus_filename,
            mmap_filename=mmap_filename,
            cached_cast_float=cached_cast_float,
            status_callback=status_callback,
            track_changes=track_changes,
        )
        
        self.nexus_filename = nexus_filename  # Alias for compatibility
        
        # Clean up any incomplete .tmp memmap files on initialization
        self._cleanup_incomplete_memmap_files()
    
    def _cleanup_incomplete_memmap_files(self):
        """Clean up any incomplete .tmp memmap files from previous sessions."""
        try:
            # Determine the directory where memmap files are stored
            if self.memmap_cache_dir:
                cache_dir = self.memmap_cache_dir
            else:
                cache_dir = os.path.dirname(self.nexus_filename)
            
            if not os.path.exists(cache_dir):
                return
            
            # Find all .tmp files related to this nexus file
            nexus_basename = os.path.splitext(os.path.basename(self.nexus_filename))[0]
            tmp_files = []
            for filename in os.listdir(cache_dir):
                if filename.startswith(nexus_basename) and filename.endswith('.float32.dat.tmp'):
                    tmp_files.append(os.path.join(cache_dir, filename))
            
            # Silently remove all .tmp files (incomplete writes from previous sessions)
            # This is just cleanup on initialization - doesn't affect normal operation
            for tmp_file in tmp_files:
                try:
                    os.remove(tmp_file)
                    # Don't print message - this is expected cleanup on init
                except Exception as e:
                    # Only log if there's an actual error (permission issue, etc.)
                    self.debug_print(f"⚠️ Could not remove incomplete memmap file {os.path.basename(tmp_file)}: {e}")
        except Exception as e:
            self.debug_print(f"⚠️ Error cleaning up incomplete memmap files: {e}")
        self.h5_file = None
        
        # Store initial state after initialization
        if self.track_changes:
            self._initial_state = self._capture_state(include_data=False)
    
    def get_choices(self) -> bool:
        """
        Discover and categorize all datasets in the HDF5 file.
        
        Returns:
            True if successful, False otherwise
        """
        DEBUG_PREV = self.DEBUG
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
                            datasets.extend(find_all_datasets(item, full_path))
                    return datasets
                
                all_datasets = find_all_datasets(f)
                self.debug_print(f"Found {len(all_datasets)} datasets (recursively)")
                
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
                        dataset = f[dataset_path]
                        if hasattr(dataset, 'shape'):
                            shape = dataset.shape
                            ndim = len(shape)
                            
                            dim_info = {
                                'path': dataset_path,
                                'shape': shape,
                                'dtype': str(dataset.dtype)
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
    
    def load_dataset_by_path(self, dataset_path: str, use_memmap: bool = True) -> Optional[Any]:
        """
        Load a specific dataset from the HDF5 file by path.
        Uses memmap if available, otherwise returns HDF5 dataset reference for efficient slicing.
        Only loads into memory if use_memmap=False and no memmap exists.
        
        Args:
            dataset_path: Path to the dataset within the HDF5 file
            use_memmap: If True, use memmap if available, otherwise return HDF5 dataset reference
            
        Returns:
            numpy.ndarray (if loaded into memory), np.memmap (if memmap exists), 
            h5py.Dataset (if use_memmap=True and no memmap), or None if error
        """
        try:
            # First, check if memmap exists for this dataset
            if use_memmap:
                target_mmap = self.get_memmap_filename_for(dataset_path)
                if os.path.exists(target_mmap):
                    try:
                        # Get dataset shape and dtype from HDF5 file
                        if hasattr(self, 'h5_file') and self.h5_file is not None:
                            f = self.h5_file
                        else:
                            f = h5py.File(self.nexus_filename, 'r')
                            should_close = True
                        
                        dataset = f[dataset_path]
                        shape = dataset.shape
                        dtype = np.dtype('float32' if self.cached_cast_float else dataset.dtype)
                        
                        if 'should_close' in locals() and should_close:
                            f.close()
                        
                        # Load memmap
                        volume_memmap = np.memmap(target_mmap, dtype=dtype, shape=shape, mode="r")
                        self.debug_print(f"Using memmap for {dataset_path}")
                        return volume_memmap
                    except Exception as e:
                        self.debug_print(f"Error loading memmap for {dataset_path}: {e}, falling back to HDF5")
            
            # No memmap available - return HDF5 dataset reference for efficient slicing
            # This allows slicing without loading entire dataset into memory
            if hasattr(self, 'h5_file') and self.h5_file is not None:
                f = self.h5_file
                dataset = f[dataset_path]
                if use_memmap:
                    # Return HDF5 dataset reference (lazy loading)
                    self.debug_print(f"Using HDF5 dataset reference for {dataset_path} (no memmap)")
                    return dataset
                else:
                    # Load into memory only if explicitly requested
                    data = np.array(dataset)
                    return data
            else:
                # Fallback: open file temporarily
                # For persistent access, we need to keep the file open or load into memory
                # Since we can't keep file open without storing reference, load into memory
                # The caller should cache this result to avoid repeated loads
                with h5py.File(self.nexus_filename, 'r') as f:
                    dataset = f[dataset_path]
                    if use_memmap:
                        # Load into memory since we can't keep file handle open
                        # Caller should cache this to avoid repeated loads
                        self.debug_print(f"Loading {dataset_path} into memory (no persistent file handle)")
                        data = np.array(dataset)
                        return data
                    else:
                        data = np.array(dataset)
                        return data
        except Exception as e:
            self.debug_print(f"Error loading dataset {dataset_path}: {e}")
            return None
    
    def load_probe_coordinates(self, use_b: bool = False) -> Optional[np.ndarray]:
        """
        Load probe coordinates from the nexus file using the already open file handle.
        
        Args:
            use_b: If True, use probe_x_coords_picked_b instead of probe_x_coords_picked
            
        Returns:
            numpy.ndarray: Probe coordinates or None if error
        """
        coord_path = getattr(self, 'probe_x_coords_picked_b', None) if use_b else self.probe_x_coords_picked
        if not coord_path:
            return None
        
        if self.h5_file is None:
            self.debug_print("Error: HDF5 file handle is not open.")
            return None
            
        try:
            probe_coords = np.array(self.h5_file.get(coord_path))
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
        if self.volume_picked is None:
            self.volume_picked = "map_mi_sic_0p33mm_002/data/PIL11"
        if self.x_coords_picked is None:
            self.x_coords_picked = "map_mi_sic_0p33mm_002/data/samx"
        if self.y_coords_picked is None:
            self.y_coords_picked = "map_mi_sic_0p33mm_002/data/samz"
        
        if getattr(self, 'plot1_single_dataset_picked', None) is None:
            if self.presample_picked is None:
                self.presample_picked = "map_mi_sic_0p33mm_002/scalar_data/presample_intensity"
            if self.postsample_picked is None:
                self.postsample_picked = "map_mi_sic_0p33mm_002/scalar_data/postsample_intensity"

        self.debug_print(f"----> LOAD_DATA: nexus_filename: {self.nexus_filename}")
        self.debug_print(f"\t volume_picked: {self.volume_picked}")
        self.debug_print(f"\t x_coords_picked: {self.x_coords_picked}")
        self.debug_print(f"\t y_coords_picked: {self.y_coords_picked}")
        
        # Open HDF5 file and keep it open
        if not hasattr(self, 'h5_file') or self.h5_file is None:
            self.h5_file = h5py.File(self.nexus_filename, "r")
            self.file_handle = self.h5_file
        
        f = self.h5_file
        self.volume_dataset = f[self.volume_picked]
        
        # If a secondary probe dataset (Plot2B) is selected, keep an HDF5 dataset ref too
        if getattr(self, 'volume_picked_b', None):
            try:
                self.volume_dataset_b = f[self.volume_picked_b]
            except Exception as _e:
                self.debug_print(f"WARNING: unable to open volume_picked_b '{self.volume_picked_b}': {_e}")
        
        # Load coordinate datasets
        x_coords_raw = np.array(f.get(self.x_coords_picked))
        y_coords_raw = np.array(f.get(self.y_coords_picked))
        
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
                self.single_dataset = np.array(f.get(self.plot1_single_dataset_picked))
            except Exception as e:
                self.debug_print(f"ERROR loading single dataset '{self.plot1_single_dataset_picked}': {e}")
                raise
            self.presample_dataset = None
            self.postsample_dataset = None
        else:
            self.single_dataset = None
            self.presample_dataset = np.array(f.get(self.presample_picked))
            self.postsample_dataset = np.array(f.get(self.postsample_picked))

        shape = self.volume_dataset.shape
        dtype = np.dtype("float32" if self.cached_cast_float else self.volume_dataset.dtype)
        self.shape = shape
        self.dtype = dtype

        # Use memmap if it exists, otherwise use direct HDF5 access
        # IMPORTANT: Use volume-specific memmap filename based on current volume_picked
        # Generate memmap filename that includes the volume path to avoid conflicts between different volumes
        volume_specific_mmap_filename = self.get_memmap_filename_for(self.volume_picked) if self.volume_picked else self.mmap_filename
        
        volume_memmap = None  # Initialize to ensure it's always assigned
        if volume_specific_mmap_filename and os.path.exists(volume_specific_mmap_filename):
            import time
            validation_start = time.time()
            self.debug_print(f"Using existing memmap cache file: {volume_specific_mmap_filename}")
            try:
                volume_memmap = np.memmap(volume_specific_mmap_filename, dtype=self.dtype, shape=self.shape, mode="r")
                
                # Validate cache: check if it's all zeros (corrupted cache)
                # Use fast sequential sampling instead of slow random sampling
                # Sample from strategic locations: corners, center, and a few slices
                validation_passed = False
                try:
                    # For large arrays, sample strategically to avoid slow random I/O
                    # IMPORTANT: For 4D data (x, y, z, u), we need to check actual probe slices
                    # which are at volume[x, y, :, :] - these are the slices that will be displayed
                    if volume_memmap.size > 1000000:
                        # Large array: sample from specific slices and corners (fast sequential access)
                        sample_values = []
                        
                        # For 4D data, check actual probe slices that will be used
                        if len(volume_memmap.shape) == 4:
                            # Check a few probe slices from different map positions
                            # These are the slices that will actually be displayed in Plot2
                            x_dim, y_dim, z_dim, u_dim = volume_memmap.shape
                            
                            # Sample probe slices from different map positions
                            # Check first, middle, and last map positions
                            map_positions = [
                                (0, 0),  # First map position
                                (x_dim // 2, y_dim // 2),  # Middle map position
                                (x_dim - 1, y_dim - 1),  # Last map position
                            ]
                            
                            for x, y in map_positions:
                                try:
                                    # Get the probe slice at this map position
                                    probe_slice = volume_memmap[x, y, :, :]
                                    # Sample from this slice (check if it has non-zero values)
                                    sample_values.append(probe_slice.flatten()[:500])
                                except:
                                    pass
                            
                            # Also check some edge slices along x and y dimensions
                            if x_dim > 1:
                                mid_y = y_dim // 2
                                sample_values.append(volume_memmap[x_dim // 2, mid_y, :, :].flatten()[:500])
                            if y_dim > 1:
                                mid_x = x_dim // 2
                                sample_values.append(volume_memmap[mid_x, y_dim // 2, :, :].flatten()[:500])
                        else:
                            # For 3D or other shapes, use original strategy
                            # Sample from first and last slices along each dimension
                            if len(volume_memmap.shape) >= 1:
                                # First and last elements along first dimension
                                idx0 = tuple([0] + [slice(None)] * (len(volume_memmap.shape) - 1))
                                idx1 = tuple([-1] + [slice(None)] * (len(volume_memmap.shape) - 1))
                                sample_values.append(volume_memmap[idx0].flatten()[:1000])
                                sample_values.append(volume_memmap[idx1].flatten()[:1000])
                            
                            if len(volume_memmap.shape) >= 2:
                                # Middle slice along first dimension
                                mid_idx = volume_memmap.shape[0] // 2
                                idx_mid = tuple([mid_idx] + [slice(None)] * (len(volume_memmap.shape) - 1))
                                sample_values.append(volume_memmap[idx_mid].flatten()[:1000])
                            
                            # Sample corners (first and last elements)
                            corner_indices = []
                            for dim_size in volume_memmap.shape:
                                corner_indices.append([0, min(100, dim_size - 1)])
                            
                            # Get a few corner samples
                            import itertools
                            for corner in itertools.product(*corner_indices[:min(4, len(corner_indices))]):
                                if len(corner) == len(volume_memmap.shape):
                                    try:
                                        sample_values.append(np.array([volume_memmap[corner]]))
                                    except:
                                        pass
                        
                        if sample_values:
                            sample_values = np.concatenate([v.flatten() for v in sample_values if v.size > 0])
                        else:
                            # Fallback: sample first 1000 elements sequentially
                            sample_values = volume_memmap.flat[:1000]
                    else:
                        # Small array: can sample more thoroughly
                        sample_size = min(1000, volume_memmap.size)
                        # Use sequential sampling instead of random (much faster)
                        step = max(1, volume_memmap.size // sample_size)
                        sample_indices = np.arange(0, volume_memmap.size, step)[:sample_size]
                        sample_values = volume_memmap.flat[sample_indices]
                    
                    # Check if all sampled values are zero (or very close to zero)
                    # For 4D data, we need a higher threshold since we're checking actual probe slices
                    non_zero_count = np.count_nonzero(sample_values)
                    total_samples = len(sample_values) if hasattr(sample_values, '__len__') else sample_values.size
                    
                    # For 4D data, require at least 1% non-zero values in probe slices
                    # This catches cases where edges have data but probe slices are all zeros
                    if len(volume_memmap.shape) == 4:
                        min_non_zero_ratio = 0.01  # 1% of probe slice should have non-zero values
                        non_zero_ratio = non_zero_count / total_samples if total_samples > 0 else 0
                        validation_passed = (non_zero_ratio >= min_non_zero_ratio)
                        if not validation_passed:
                            self.debug_print(f"⚠️ Validation failed: only {non_zero_ratio*100:.2f}% non-zero values in probe slices (required {min_non_zero_ratio*100:.1f}%)")
                    else:
                        validation_passed = (non_zero_count > 0)
                    validation_time = time.time() - validation_start
                    
                except Exception as validation_error:
                    # If validation fails, assume file is OK (don't block loading)
                    validation_time = time.time() - validation_start
                    self.debug_print(f"Validation check failed (non-critical): {validation_error} (took {validation_time:.3f}s)")
                    validation_passed = True  # Assume OK to avoid blocking
                
                if not validation_passed:
                    self.debug_print(f"⚠️ WARNING: Memmap cache appears corrupted (all zeros in sample). Regenerating...")
                    # Close the memmap and delete the corrupted file
                    # Explicitly close the memmap to ensure file handle is released
                    try:
                        if hasattr(volume_memmap, '_mmap'):
                            volume_memmap._mmap.close()
                    except:
                        pass
                    del volume_memmap
                    # Force garbage collection to ensure file handle is released
                    import gc
                    gc.collect()
                    
                    # Now try to remove the file
                    try:
                        # On some systems, we may need to wait a moment for the file handle to be released
                        import time
                        time.sleep(0.1)
                        os.remove(volume_specific_mmap_filename)
                        self.debug_print(f"✅ Deleted corrupted cache file: {volume_specific_mmap_filename}")
                    except FileNotFoundError:
                        self.debug_print(f"Cache file already removed: {volume_specific_mmap_filename}")
                    except PermissionError as e:
                        self.debug_print(f"⚠️ Could not delete corrupted cache file (permission error): {e}")
                        self.debug_print(f"   File may be locked. You may need to manually delete: {volume_specific_mmap_filename}")
                    except Exception as e:
                        self.debug_print(f"⚠️ Could not delete corrupted cache file: {e}")
                        self.debug_print(f"   You may need to manually delete: {volume_specific_mmap_filename}")
                    volume_memmap = None
                    self.mmap_filename = None
                else:
                    self.debug_print(f"✅ Successfully loaded memmap file (validated: {non_zero_count}/{total_samples} non-zero values, took {validation_time:.3f}s)")
                    # Update self.mmap_filename to the volume-specific one for consistency
                    self.mmap_filename = volume_specific_mmap_filename
            except Exception as e:
                self.debug_print(f"ERROR loading memmap file: {e}")
                self.mmap_filename = None
                volume_memmap = None
        
        # If memmap wasn't loaded (file doesn't exist or error occurred), use direct HDF5 access
        if volume_memmap is None:
            self.debug_print("Using direct HDF5 dataset reference (lazy loading)")
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
        """Create memmap cache file in a background thread.
        
        Uses its own HDF5 file handle to avoid blocking the main dataset access.
        """
        def _create_memmap():
            try:
                # Use volume-specific memmap filename based on current volume_picked
                if not hasattr(self, 'volume_picked') or not self.volume_picked:
                    self.debug_print("ERROR: volume_picked not set, cannot create memmap cache")
                    return
                
                volume_specific_mmap_filename = self.get_memmap_filename_for(self.volume_picked)
                
                if not volume_specific_mmap_filename:
                    self.debug_print("Skipping memmap cache creation (no mmap filename provided)")
                    return
                
                if os.path.exists(volume_specific_mmap_filename):
                    self.debug_print(f"Memmap cache already exists, skipping creation: {volume_specific_mmap_filename}")
                    return
                
                # Use .tmp file for atomic write - only rename to final name when complete
                tmp_filename = volume_specific_mmap_filename + '.tmp'
                
                # Silently clean up any existing .tmp file (incomplete write from previous session)
                # This is just cleanup - doesn't affect the normal load-from-nxs flow
                if os.path.exists(tmp_filename):
                    try:
                        os.remove(tmp_filename)
                        # Don't print message - this is expected cleanup, not a user action
                    except:
                        pass
                
                mmap_dir = os.path.dirname(volume_specific_mmap_filename)
                if not os.access(mmap_dir, os.W_OK):
                    self.debug_print(f"PERMISSION ERROR: No write permission to directory: {mmap_dir}")
                    return
                
                self.debug_print(f"🔄 Background: Starting memmap cache creation: {volume_specific_mmap_filename}")
                
                # Open our own HDF5 file handle to avoid blocking the main dataset access
                # This allows slicing to continue while memmap is being created
                with h5py.File(self.nexus_filename, 'r') as f:
                    dset = f[self.volume_picked]
                    shape = dset.shape
                    dtype = np.dtype('float32' if self.cached_cast_float else dset.dtype)
                    
                    self.debug_print(f"🔄 Background: Creating memmap file (shape={shape}, dtype={dtype})...")
                    # Create the .tmp file first to ensure it exists
                    # Calculate file size
                    element_size = np.dtype(dtype).itemsize
                    file_size = int(np.prod(shape) * element_size)
                    # Create empty file of correct size
                    with open(tmp_filename, 'wb') as f:
                        f.seek(file_size - 1)
                        f.write(b'\0')
                    # Now open as memmap for writing
                    write = np.memmap(tmp_filename, dtype=dtype, shape=shape, mode="r+")
                    
                    # Process in chunks to avoid loading entire dataset into memory
                    if len(shape) == 4:
                        for u in range(shape[0]):
                            if u % 10 == 0 or u == shape[0] - 1:
                                self.debug_print(f"🔄 Background: Caching 4D slice {u+1}/{shape[0]}")
                            try:
                                # Read slice directly from HDF5 (efficient, doesn't load entire dataset)
                                piece = dset[u, :, :, :]
                                piece = piece.astype(np.float32) if self.cached_cast_float else piece
                                write[u, :, :, :] = piece
                            except Exception as e:
                                self.debug_print(f"❌ Background: ERROR caching slice {u}: {e}")
                                import traceback
                                self.debug_print(traceback.format_exc())
                                if os.path.exists(volume_specific_mmap_filename):
                                    os.remove(volume_specific_mmap_filename)
                                return
                    elif len(shape) == 3:
                        for u in range(shape[0]):
                            if u % 10 == 0 or u == shape[0] - 1:
                                self.debug_print(f"🔄 Background: Caching 3D slice {u+1}/{shape[0]}")
                            try:
                                piece = dset[u, :, :]
                                piece = piece.astype(np.float32) if self.cached_cast_float else piece
                                write[u, :, :] = piece
                            except Exception as e:
                                self.debug_print(f"❌ Background: ERROR caching slice {u}: {e}")
                                import traceback
                                self.debug_print(traceback.format_exc())
                                # Clean up .tmp file on error
                                if os.path.exists(tmp_filename):
                                    try:
                                        os.remove(tmp_filename)
                                    except:
                                        pass
                                return
                    else:
                        # For 1D/2D datasets, load all at once (smaller datasets)
                        data = dset[:]
                        data = data.astype(np.float32) if self.cached_cast_float else data
                        write[...] = data
                    
                    # Flush and properly close the .tmp file
                    write.flush()
                    # Explicitly sync the underlying mmap to disk
                    if hasattr(write, '_mmap'):
                        write._mmap.flush()
                    # Close the memmap
                    if hasattr(write, '_mmap'):
                        write._mmap.close()
                    del write
                    
                    # Force file system sync to ensure file is written to disk
                    try:
                        import time
                        time.sleep(0.1)  # Brief pause to ensure file system sync
                        # Also try to sync the file explicitly if possible
                        if os.path.exists(tmp_filename):
                            with open(tmp_filename, 'rb') as f:
                                f.flush()
                                os.fsync(f.fileno())
                    except:
                        pass  # fsync might not be available on all systems
                    
                    # Verify .tmp file exists before renaming
                    if not os.path.exists(tmp_filename):
                        self.debug_print(f"❌ Background: ERROR .tmp file does not exist after write: {tmp_filename}")
                        return
                    
                    # Atomically rename .tmp to final filename
                    try:
                        os.rename(tmp_filename, volume_specific_mmap_filename)
                        self.debug_print(f"✅ Background: Memmap cache file created successfully: {volume_specific_mmap_filename}")
                        # Update self.mmap_filename to the volume-specific one for consistency
                        self.mmap_filename = volume_specific_mmap_filename
                    except Exception as e:
                        self.debug_print(f"❌ Background: ERROR renaming .tmp file to final name: {e}")
                        # Clean up .tmp file if rename failed
                        if os.path.exists(tmp_filename):
                            try:
                                os.remove(tmp_filename)
                            except:
                                pass
                
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
                
                # Use .tmp file for atomic write
                tmp_filename = target_mmap + '.tmp'
                
                # Silently clean up any existing .tmp file (incomplete write from previous session)
                # This is just cleanup - doesn't affect the normal load-from-nxs flow
                if os.path.exists(tmp_filename):
                    try:
                        os.remove(tmp_filename)
                        # Don't print message - this is expected cleanup, not a user action
                    except:
                        pass
                
                mmap_dir = os.path.dirname(target_mmap)
                if not os.access(mmap_dir, os.W_OK):
                    self.debug_print(f"PERMISSION ERROR: No write permission to directory: {mmap_dir}")
                    return
                with h5py.File(self.nexus_filename, 'r') as f:
                    dset = f[dataset_path]
                    shape = dset.shape
                    dtype = 'float32' if self.cached_cast_float else str(dset.dtype)
                    self.debug_print(f"🔄 Background: Creating memmap for {dataset_path} -> {target_mmap} shape={shape} dtype={dtype}")
                    # Create the .tmp file first to ensure it exists
                    dtype_final = np.float32 if self.cached_cast_float else dset.dtype
                    element_size = np.dtype(dtype_final).itemsize
                    file_size = int(np.prod(shape) * element_size)
                    # Create empty file of correct size
                    with open(tmp_filename, 'wb') as f:
                        f.seek(file_size - 1)
                        f.write(b'\0')
                    # Now open as memmap for writing
                    write = np.memmap(tmp_filename, dtype=dtype_final, shape=shape, mode='r+')
                    if len(shape) == 4:
                        for u in range(shape[0]):
                            if u % 10 == 0 or u == shape[0]-1:
                                self.debug_print(f"🔄 Background: Caching 4D slice {u+1}/{shape[0]}")
                            try:
                                piece = dset[u, :, :, :]
                                piece = piece.astype(np.float32) if self.cached_cast_float else piece
                                write[u, :, :, :] = piece
                            except Exception as e:
                                self.debug_print(f"❌ Background: ERROR caching slice {u}: {e}")
                                import traceback
                                self.debug_print(traceback.format_exc())
                                # Clean up .tmp file on error
                                if os.path.exists(tmp_filename):
                                    try:
                                        os.remove(tmp_filename)
                                    except:
                                        pass
                                return
                    elif len(shape) == 3:
                        for u in range(shape[0]):
                            if u % 50 == 0 or u == shape[0]-1:
                                self.debug_print(f"🔄 Background: Caching 3D slice {u+1}/{shape[0]}")
                            piece = dset[u, :, :]
                            piece = piece.astype(np.float32) if self.cached_cast_float else piece
                            write[u, :, :] = piece
                    else:
                        data = dset[:]
                        data = data.astype(np.float32) if self.cached_cast_float else data
                        write[...] = data
                    
                    # Flush and properly close the .tmp file
                    write.flush()
                    # Explicitly sync the underlying mmap to disk
                    if hasattr(write, '_mmap'):
                        write._mmap.flush()
                    # Close the memmap
                    if hasattr(write, '_mmap'):
                        write._mmap.close()
                    del write
                    
                    # Force file system sync to ensure file is written to disk
                    try:
                        import time
                        time.sleep(0.1)  # Brief pause to ensure file system sync
                        # Also try to sync the file explicitly if possible
                        if os.path.exists(tmp_filename):
                            with open(tmp_filename, 'rb') as f:
                                f.flush()
                                os.fsync(f.fileno())
                    except:
                        pass  # fsync might not be available on all systems
                    
                    # Verify .tmp file exists before renaming
                    if not os.path.exists(tmp_filename):
                        self.debug_print(f"❌ Background: ERROR .tmp file does not exist after write: {tmp_filename}")
                        return
                    
                    # Atomically rename .tmp to final filename
                    try:
                        os.rename(tmp_filename, target_mmap)
                        self.debug_print(f"✅ Background: Memmap created for {dataset_path}")
                    except Exception as e:
                        self.debug_print(f"❌ Background: ERROR renaming .tmp file to final name: {e}")
                        # Clean up .tmp file if rename failed
                        if os.path.exists(tmp_filename):
                            try:
                                os.remove(tmp_filename)
                            except:
                                pass
            except Exception as e:
                self.debug_print(f"❌ Background: ERROR creating memmap for {dataset_path}: {e}")
        threading.Thread(target=_create, args=(dataset_path,), daemon=True).start()
    
    def close(self) -> None:
        """Close HDF5 file handle."""
        if self.h5_file is not None:
            try:
                self.h5_file.close()
            except Exception:
                pass
            self.h5_file = None
            self.file_handle = None
    
    # Alias for compatibility with existing code
    def load_nexus_data(self):
        """Alias for load_data() for backward compatibility."""
        return self.load_data()


# Alias for backward compatibility
Process4dNexus = ProcessNexus

