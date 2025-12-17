"""
Volume Operation Utilities

This module provides utility functions for computing 2D plots from 3D sections
and 3D sources from 2D sections, used for dashboard visualizations.
"""

import numpy as np
from typing import Tuple, Optional, Callable, Union


def calculate_percentile_range(
    data: np.ndarray,
    low_percentile: float = 1.0,
    high_percentile: float = 99.0,
) -> Tuple[float, float]:
    """
    Calculate percentile-based range for data.
    
    This function calculates the low and high percentiles of data, which is
    commonly used for setting color map ranges in visualizations.
    
    Args:
        data: NumPy array (can be any shape)
        low_percentile: Lower percentile (default: 1.0)
        high_percentile: Upper percentile (default: 99.0)
    
    Returns:
        Tuple of (low_value, high_value) representing the percentile range
    """
    if data is None or data.size == 0:
        return 0.0, 1.0
    
    data_flat = data.flatten() if data.ndim > 1 else data
    data_flat = data_flat[~np.isnan(data_flat)]  # Remove NaN values
    
    if data_flat.size == 0:
        return 0.0, 1.0
    
    p_low = float(np.percentile(data_flat, low_percentile))
    p_high = float(np.percentile(data_flat, high_percentile))
    
    return p_low, p_high

# Import Bokeh utilities if available (optional dependency)
try:
    from .SCDash_bokeh_utils import get_box_select_selection
    BOKEH_AVAILABLE = True
except ImportError:
    BOKEH_AVAILABLE = False
    get_box_select_selection = None


def compute_2d_plot_from_3d_section(
    volume: np.ndarray,
    x1_coord: float,
    y1_coord: float,
    x2_coord: float,
    y2_coord: float,
    get_x_index: Callable[[float], int],
    get_y_index: Callable[[float], int],
    is_3d_volume: bool = False,
    probe_coords_loader: Optional[Callable[[], Optional[np.ndarray]]] = None,
    use_b: bool = False,
) -> Tuple[np.ndarray, Optional[np.ndarray]]:
    """
    Compute a 2D plot (1D or 2D) from a 3D/4D volume by summing over selected X,Y region.
    
    This function extracts a section from a 3D or 4D volume by:
    - For 3D volumes: Sums over X,Y dimensions to produce a 1D array (Z dimension)
    - For 4D volumes: Sums over X,Y dimensions to produce a 2D array (Z,U dimensions)
    
    Args:
        volume: 3D or 4D numpy array (shape: [X, Y, Z] or [X, Y, Z, U])
        x1_coord: Minimum X coordinate of selection region
        y1_coord: Minimum Y coordinate of selection region
        x2_coord: Maximum X coordinate of selection region
        y2_coord: Maximum Y coordinate of selection region
        get_x_index: Function to convert X coordinate to volume index
        get_y_index: Function to convert Y coordinate to volume index
        is_3d_volume: If True, volume is 3D (shape [X, Y, Z]), else 4D (shape [X, Y, Z, U])
        probe_coords_loader: Optional function to load probe coordinates for 1D plots.
                           Should return array of coordinates matching the Z dimension.
                           If use_b=True, will be called with use_b=True.
        use_b: If True, indicates this is for a "b" variant (e.g., plot2b)
    
    Returns:
        Tuple of (slice_data, x_coords):
        - slice_data: 1D array for 3D volumes, 2D array for 4D volumes
        - x_coords: Optional coordinate array for 1D plots (only for 3D volumes)
    """
    # Convert coordinates to indices
    x1 = get_x_index(x1_coord)
    y1 = get_y_index(y1_coord)
    x2 = max(x1 + 1, get_x_index(x2_coord))
    y2 = max(y1 + 1, get_y_index(y2_coord))
    
    # Check actual volume shape to handle special case: Plot1 is 1D and volume is 3D (x,z,u)
    actual_volume_shape = len(volume.shape)
    
    if actual_volume_shape == 3 and not is_3d_volume:
        # Special case: Plot1 is 1D, volume is 3D (x,z,u)
        # Plot3 is 1D showing x dimension, we select x-range and extract 2D slice (z,u)
        # y1, y2 are ignored in this case (Plot3 is 1D, so y selection doesn't apply)
        piece = volume[x1:x2, :, :]  # Extract (x_range, z, u)
        slice_data = np.mean(piece, axis=0)  # Average over x dimension to get (z, u)
        
        return slice_data, None
    elif is_3d_volume:
        # For 3D: sum over X,Y dimensions to get 1D slice
        piece = volume[x1:x2, y1:y2, :]
        slice_data = np.sum(piece, axis=(0, 1)) / ((x2 - x1) * (y2 - y1))
        
        # Get probe coordinates if available
        x_coords_1d = None
        if probe_coords_loader is not None:
            try:
                if use_b:
                    probe_coords = probe_coords_loader(use_b=True)
                else:
                    probe_coords = probe_coords_loader()
                
                if probe_coords is not None and len(probe_coords) == len(slice_data):
                    x_coords_1d = probe_coords
            except Exception:
                pass
        
        if x_coords_1d is None:
            x_coords_1d = np.arange(len(slice_data))
        
        return slice_data, x_coords_1d
    else:
        # For 4D: sum over X,Y dimensions to get 2D slice
        piece = volume[x1:x2, y1:y2, :, :]
        slice_data = np.sum(piece, axis=(0, 1)) / ((x2 - x1) * (y2 - y1))
        
        return slice_data, None


def compute_3d_source_from_2d_section(
    volume: np.ndarray,
    z1_coord: Optional[float],
    z2_coord: Optional[float],
    u1_coord: Optional[float] = None,
    u2_coord: Optional[float] = None,
    get_z_index: Optional[Callable[[float], int]] = None,
    get_u_index: Optional[Callable[[float], int]] = None,
    plot2_x_coords: Optional[np.ndarray] = None,
    plot2_y_coords: Optional[np.ndarray] = None,
    plot2_needs_flip: bool = False,
    normalize: bool = True,
    apply_plot1_flip: bool = False,
) -> np.ndarray:
    """
    Compute a 2D image (for Plot3) from a 3D/4D volume by summing over selected Z,U range.
    
    This function extracts a 2D image from a 3D or 4D volume by:
    - For 3D volumes: Sums over Z dimension for selected range to produce 2D image (X,Y)
    - For 4D volumes: Sums over Z and U dimensions for selected range to produce 2D image (X,Y)
    
    Args:
        volume: 3D or 4D numpy array (shape: [X, Y, Z] or [X, Y, Z, U])
        z1_coord: Minimum Z coordinate (or index if get_z_index is None)
        z2_coord: Maximum Z coordinate (or index if get_z_index is None)
        u1_coord: Optional minimum U coordinate for 4D volumes (or index if get_u_index is None)
        u2_coord: Optional maximum U coordinate for 4D volumes (or index if get_u_index is None)
        get_z_index: Optional function to convert Z coordinate to volume index
        get_u_index: Optional function to convert U coordinate to volume index
        plot2_x_coords: Optional coordinate array for Plot2 X axis (U dimension for 4D)
        plot2_y_coords: Optional coordinate array for Plot2 Y axis (Z dimension for 4D)
        plot2_needs_flip: Whether Plot2 coordinates are flipped
        normalize: If True, normalize output to [0, 1] range
        apply_plot1_flip: If True, transpose the result to match Plot1 orientation
    
    Returns:
        2D numpy array (X, Y) representing the computed image
    """
    is_3d = len(volume.shape) == 3
    
    if is_3d:
        # For 3D: sum over Z dimension
        if get_z_index is not None and z1_coord is not None and z2_coord is not None:
            z1_idx = get_z_index(z1_coord)
            z2_idx = get_z_index(z2_coord)
        else:
            # Use coordinates as indices directly
            z1_idx = int(z1_coord) if z1_coord is not None else 0
            z2_idx = int(z2_coord) if z2_coord is not None else volume.shape[2] - 1
        
        z_lo, z_hi = (z1_idx, z2_idx) if z1_idx <= z2_idx else (z2_idx, z1_idx)
        z_lo = max(0, min(z_lo, volume.shape[2] - 1))
        z_hi = max(0, min(z_hi, volume.shape[2] - 1))
        if z_hi <= z_lo:
            z_hi = min(z_lo + 1, volume.shape[2])
        
        piece = volume[:, :, z_lo:z_hi]
        img = np.sum(piece, axis=2)  # sum over Z dimension
    else:
        # For 4D: sum over Z and U dimensions
        # Convert coordinates to indices
        if plot2_x_coords is not None and u1_coord is not None and u2_coord is not None:
            u1_idx = int(np.argmin(np.abs(plot2_x_coords - u1_coord)))
            u2_idx = int(np.argmin(np.abs(plot2_x_coords - u2_coord)))
        elif get_u_index is not None and u1_coord is not None and u2_coord is not None:
            u1_idx = get_u_index(u1_coord)
            u2_idx = get_u_index(u2_coord)
        else:
            u1_idx = int(u1_coord) if u1_coord is not None else 0
            u2_idx = int(u2_coord) if u2_coord is not None else volume.shape[3] - 1
        
        if plot2_y_coords is not None and z1_coord is not None and z2_coord is not None:
            z1_idx = int(np.argmin(np.abs(plot2_y_coords - z1_coord)))
            z2_idx = int(np.argmin(np.abs(plot2_y_coords - z2_coord)))
        elif get_z_index is not None and z1_coord is not None and z2_coord is not None:
            z1_idx = get_z_index(z1_coord)
            z2_idx = get_z_index(z2_coord)
        else:
            z1_idx = int(z1_coord) if z1_coord is not None else 0
            z2_idx = int(z2_coord) if z2_coord is not None else volume.shape[2] - 1
        
        z_lo, z_hi = (z1_idx, z2_idx) if z1_idx <= z2_idx else (z2_idx, z1_idx)
        u_lo, u_hi = (u1_idx, u2_idx) if u1_idx <= u2_idx else (u2_idx, u1_idx)
        
        z_lo = max(0, min(z_lo, volume.shape[2] - 1))
        z_hi = max(0, min(z_hi, volume.shape[2] - 1))
        u_lo = max(0, min(u_lo, volume.shape[3] - 1))
        u_hi = max(0, min(u_hi, volume.shape[3] - 1))
        
        if z_hi <= z_lo:
            z_hi = min(z_lo + 1, volume.shape[2])
        if u_hi <= u_lo:
            u_hi = min(u_lo + 1, volume.shape[3])
        
        piece = volume[:, :, z_lo:z_hi, u_lo:u_hi]
        img = np.sum(piece, axis=(2, 3))  # sum over Z and U
    
    # Normalize to [0, 1] if requested
    if normalize:
        img = np.nan_to_num(img, nan=0.0, posinf=0.0, neginf=0.0)
        vmin = float(np.min(img))
        vmax = float(np.max(img))
        if vmax > vmin:
            img = (img - vmin) / (vmax - vmin)
        else:
            img = np.zeros_like(img)
    
    # Apply Plot1's flip state to match Plot1's orientation
    if apply_plot1_flip:
        img = np.transpose(img)
    
    return img

