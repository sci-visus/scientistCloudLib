"""
Bokeh-specific utilities for dashboard visualizations.

This module provides utilities for working with Bokeh plots, including
selection tools, annotations, and plot interactions.
"""

from typing import Optional, Tuple, Any, Callable, Dict
import numpy as np
from bokeh.models import BoxSelectTool, BoxAnnotation, ColumnDataSource
from bokeh.events import SelectionGeometry


def get_box_select_selection(
    bokeh_figure: Any,
    box_annotation: Optional[BoxAnnotation] = None,
    fallback_rect: Optional[Any] = None,
    selection_trigger_source: Optional[Any] = None,
    debug: bool = False,
) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
    """
    Extract selection bounds from a Bokeh plot's BoxSelectTool.
    
    This function tries multiple methods to get the selection:
    1. Reads from BoxSelectTool's overlay property
    2. Reads from BoxSelectTool's geometry property (Bokeh 3.x)
    3. Falls back to box_annotation values if available
    4. Finally falls back to fallback_rect if provided
    
    Args:
        bokeh_figure: Bokeh figure object containing the BoxSelectTool
        box_annotation: Optional BoxAnnotation object to update and use as fallback
        fallback_rect: Optional object with min_x, max_x, min_y, max_y attributes
        selection_trigger_source: Optional ColumnDataSource that stores selection coordinates (x0, y0, x1, y1)
        debug: If True, print debug messages
    
    Returns:
        Tuple of (left, right, bottom, top) coordinates, or (None, None, None, None) if no selection
    """
    selection_left = None
    selection_right = None
    selection_bottom = None
    selection_top = None
    
    # Method 0: Check selection_trigger_source FIRST (most reliable - updated directly by CustomJS)
    if selection_trigger_source is not None:
        try:
            data = selection_trigger_source.data
            if 'x0' in data and 'y0' in data and 'x1' in data and 'y1' in data:
                if len(data['x0']) > 0 and len(data['y0']) > 0 and len(data['x1']) > 0 and len(data['y1']) > 0:
                    x0 = float(data['x0'][0])
                    y0 = float(data['y0'][0])
                    x1 = float(data['x1'][0])
                    y1 = float(data['y1'][0])
                    
                    if not (np.isnan(x0) or np.isnan(y0) or np.isnan(x1) or np.isnan(y1)):
                        selection_left = min(x0, x1)
                        selection_right = max(x0, x1)
                        selection_bottom = min(y0, y1)
                        selection_top = max(y0, y1)
                        if debug:
                            print(f"  ✅ Using selection_trigger_source: left={selection_left}, right={selection_right}, bottom={selection_bottom}, top={selection_top}")
        except Exception as e:
            if debug:
                print(f"  ⚠️ Could not read from selection_trigger_source: {e}")
    
    # Helper function to extract numeric value and check for NaN
    def extract_and_validate_value(attr_value):
        """Extract numeric value from attribute, handling Node objects and checking for NaN."""
        if attr_value is None:
            return None
        
        # Try direct numeric conversion first
        if isinstance(attr_value, (int, float)):
            val = float(attr_value)
            return val if not np.isnan(val) else None
        
        # Try to get value from Node object (Bokeh Node objects)
        # Node objects might have different ways to access their value
        if hasattr(attr_value, 'value'):
            try:
                val = attr_value.value
                if isinstance(val, (int, float)):
                    val = float(val)
                    return val if not np.isnan(val) else None
                # If value is also a Node, try to get its value
                if hasattr(val, 'value'):
                    try:
                        nested_val = val.value
                        if isinstance(nested_val, (int, float)):
                            nested_val = float(nested_val)
                            return nested_val if not np.isnan(nested_val) else None
                    except:
                        pass
            except Exception:
                pass
        
        # Try accessing as a property descriptor (Bokeh 3.x)
        # In Bokeh, properties are descriptors, but accessing them should return the value
        # If we get a Node, it might be a reference that needs resolution
        if hasattr(attr_value, '__get__'):
            try:
                # Try to get the value from the descriptor
                val = attr_value.__get__(None, type(attr_value))
                if isinstance(val, (int, float)):
                    val = float(val)
                    return val if not np.isnan(val) else None
                # If it returns another object, try to extract value from it
                if hasattr(val, 'value'):
                    try:
                        nested_val = val.value
                        if isinstance(nested_val, (int, float)):
                            nested_val = float(nested_val)
                            return nested_val if not np.isnan(nested_val) else None
                    except:
                        pass
            except:
                pass
        
        # Try to access through document if it's a Node (Bokeh internal)
        # Node objects in Bokeh might need document context to resolve
        if hasattr(attr_value, 'id') and hasattr(attr_value, '__class__'):
            # This might be a Bokeh model - try to get the actual property value
            # In Bokeh, model properties should return values directly when accessed
            # But if we're getting a Node, the value might not be set yet
            pass
        
        # Try direct conversion (might work if Node has __float__ or similar)
        try:
            val = float(attr_value)
            return val if not np.isnan(val) else None
        except (ValueError, TypeError, AttributeError):
            # Try string conversion
            if isinstance(attr_value, str):
                try:
                    val = float(attr_value)
                    return val if not np.isnan(val) else None
                except:
                    pass
            return None
    
    # Method 1: Check box_annotation FIRST (most reliable - updated by CustomJS callbacks)
    if box_annotation is not None:
        try:
            if debug:
                print(f"  🔍 Checking box_annotation: left={box_annotation.left}, right={box_annotation.right}, bottom={box_annotation.bottom}, top={box_annotation.top}")
                print(f"  🔍 box_annotation.left type: {type(box_annotation.left)}")
            
            # Try multiple ways to get the value from box_annotation
            # In Bokeh, properties should return actual values, but Node objects might be descriptors
            left_raw = box_annotation.left
            right_raw = box_annotation.right
            bottom_raw = box_annotation.bottom
            top_raw = box_annotation.top
            
            if debug:
                print(f"  🔍 Raw values: left={left_raw} (type={type(left_raw)}), right={right_raw}, bottom={bottom_raw}, top={top_raw}")
            
            # Try using getattr as well (might help with descriptors)
            try:
                left_attr = getattr(box_annotation, 'left', None)
                right_attr = getattr(box_annotation, 'right', None)
                bottom_attr = getattr(box_annotation, 'bottom', None)
                top_attr = getattr(box_annotation, 'top', None)
                if debug and (left_attr != left_raw or right_attr != right_raw):
                    print(f"  🔍 getattr values differ: left={left_attr}, right={right_attr}")
            except:
                pass
            
            left_val = extract_and_validate_value(left_raw)
            right_val = extract_and_validate_value(right_raw)
            bottom_val = extract_and_validate_value(bottom_raw)
            top_val = extract_and_validate_value(top_raw)
            
            if debug:
                print(f"  🔍 Extracted from box_annotation: left={left_val}, right={right_val}, bottom={bottom_val}, top={top_val}")
            
            if (left_val is not None and right_val is not None and 
                bottom_val is not None and top_val is not None):
                selection_left = left_val
                selection_right = right_val
                selection_bottom = bottom_val
                selection_top = top_val
                if debug:
                    print(f"  ✅ Using box_annotation (updated by callback): left={selection_left}, right={selection_right}, bottom={selection_bottom}, top={selection_top}")
            elif debug:
                print(f"  ⚠️ box_annotation values are None or invalid (left={left_val}, right={right_val}, bottom={bottom_val}, top={top_val})")
        except Exception as e:
            if debug:
                print(f"  ⚠️ Could not read from box_annotation: {e}")
                import traceback
                traceback.print_exc()
    
    # Find BoxSelectTool in the plot's tools
    box_select_tool = None
    for tool in bokeh_figure.tools:
        if isinstance(tool, BoxSelectTool):
            box_select_tool = tool
            break
    
    # Method 2: Check BoxSelectTool overlay (only if box_annotation didn't have valid values)
    if selection_left is None and box_select_tool is not None:
        try:
            # Method 1: Check if BoxSelectTool has an overlay with selection bounds
            if hasattr(box_select_tool, 'overlay') and box_select_tool.overlay is not None:
                overlay = box_select_tool.overlay
                if hasattr(overlay, 'left') and overlay.left is not None:
                    # Check if values are valid (not NaN)
                    left_val = overlay.left
                    right_val = overlay.right
                    bottom_val = overlay.bottom
                    top_val = overlay.top
                    
                    # Convert to float and check for NaN
                    try:
                        left_val = float(left_val) if left_val is not None else None
                        right_val = float(right_val) if right_val is not None else None
                        bottom_val = float(bottom_val) if bottom_val is not None else None
                        top_val = float(top_val) if top_val is not None else None
                    except (ValueError, TypeError):
                        left_val = right_val = bottom_val = top_val = None
                    
                    # Only use if all values are valid and not NaN
                    if (left_val is not None and right_val is not None and 
                        bottom_val is not None and top_val is not None and
                        not (np.isnan(left_val) or np.isnan(right_val) or 
                             np.isnan(bottom_val) or np.isnan(top_val))):
                        selection_left = left_val
                        selection_right = right_val
                        selection_bottom = bottom_val
                        selection_top = top_val
                        if debug:
                            print(f"  ✅ Using BoxSelectTool overlay: left={selection_left}, right={selection_right}, bottom={selection_bottom}, top={selection_top}")
                        # Update box_annotation to match
                        if box_annotation is not None:
                            box_annotation.left = selection_left
                            box_annotation.right = selection_right
                            box_annotation.bottom = selection_bottom
                            box_annotation.top = selection_top
                    elif debug:
                        print(f"  ⚠️ BoxSelectTool overlay has NaN values: left={left_val}, right={right_val}, bottom={bottom_val}, top={top_val}")
        except Exception as e:
            if debug:
                print(f"  ⚠️ Could not read from BoxSelectTool overlay: {e}")
        
        # Method 2: Try to get selection from tool's geometry (Bokeh 3.x)
        if selection_left is None:
            try:
                if hasattr(box_select_tool, 'geometry') and box_select_tool.geometry is not None:
                    geom = box_select_tool.geometry
                    if hasattr(geom, 'x0') and hasattr(geom, 'x1') and hasattr(geom, 'y0') and hasattr(geom, 'y1'):
                        x0 = float(geom.x0) if geom.x0 is not None else None
                        x1 = float(geom.x1) if geom.x1 is not None else None
                        y0 = float(geom.y0) if geom.y0 is not None else None
                        y1 = float(geom.y1) if geom.y1 is not None else None
                        
                        if (x0 is not None and x1 is not None and y0 is not None and y1 is not None and
                            not (np.isnan(x0) or np.isnan(x1) or np.isnan(y0) or np.isnan(y1))):
                            selection_left = min(x0, x1)
                            selection_right = max(x0, x1)
                            selection_bottom = min(y0, y1)
                            selection_top = max(y0, y1)
                            if debug:
                                print(f"  ✅ Using BoxSelectTool geometry: left={selection_left}, right={selection_right}, bottom={selection_bottom}, top={selection_top}")
                            # Update box_annotation to match
                            if box_annotation is not None:
                                box_annotation.left = selection_left
                                box_annotation.right = selection_right
                                box_annotation.bottom = selection_bottom
                                box_annotation.top = selection_top
            except Exception as e:
                if debug:
                    print(f"  ⚠️ Could not read from BoxSelectTool geometry: {e}")
        
        # Method 3: Try to get selection from plot's x_range and y_range if tool has active selection
        if selection_left is None:
            try:
                # In Bokeh 3.x, persistent selections might be stored in the plot's range
                # Check if there's a selection by looking at the plot's selection geometry
                if hasattr(bokeh_figure, 'x_range') and hasattr(bokeh_figure, 'y_range'):
                    # Check if there's a selection geometry stored in the tool
                    if hasattr(box_select_tool, 'select_every_mousemove') and hasattr(box_select_tool, 'dimensions'):
                        # Try to get selection from the tool's callback or selection event
                        # This is a fallback - the selection might be in the JavaScript side
                        pass
            except Exception as e:
                if debug:
                    print(f"  ⚠️ Could not read from plot ranges: {e}")
    
    # Final fallback to rect if provided (only if nothing else worked)
    if selection_left is None and fallback_rect is not None:
        try:
            selection_left = fallback_rect.min_x
            selection_right = fallback_rect.max_x
            selection_bottom = fallback_rect.min_y
            selection_top = fallback_rect.max_y
            if debug:
                print(f"  ⚠️ Using fallback_rect: left={selection_left}, right={selection_right}, bottom={selection_bottom}, top={selection_top}")
        except Exception as e:
            if debug:
                print(f"  ⚠️ Could not read from fallback_rect: {e}")
    
    return selection_left, selection_right, selection_bottom, selection_top


def setup_selection_geometry_handler(
    bokeh_figure: Any,
    box_annotation: Optional[BoxAnnotation] = None,
    selection_trigger_source: Optional[ColumnDataSource] = None,
    on_selection_callback: Optional[Callable] = None,
    debug: bool = False,
) -> None:
    """
    Set up a SelectionGeometry event handler for a Bokeh plot.
    
    This is the recommended way to handle box selections in Bokeh 3.x,
    as it provides reliable access to selection coordinates in data space.
    
    Args:
        bokeh_figure: Bokeh figure object to attach the event handler to
        box_annotation: Optional BoxAnnotation to update with selection bounds
        selection_trigger_source: Optional ColumnDataSource to update with selection coordinates (x0, y0, x1, y1)
        on_selection_callback: Optional callback function to call with (x0, y0, x1, y1) when selection is made
        debug: If True, print debug messages
    """
    def on_selection_geometry(event):
        """Handle SelectionGeometry event from BoxSelectTool."""
        # SelectionGeometry events don't have a 'tool' attribute in Bokeh 3.4
        # We check the geometry type instead - 'rect' indicates box selection
        if event.geometry.get("type") == "rect":
            x0 = event.geometry.get("x0")
            x1 = event.geometry.get("x1")
            y0 = event.geometry.get("y0")
            y1 = event.geometry.get("y1")
            
            if x0 is not None and x1 is not None and y0 is not None and y1 is not None:
                if debug:
                    print(f"  ✅ SelectionGeometry event: x0={x0}, y0={y0}, x1={x1}, y1={y1}")
                
                # Update selection_trigger_source if provided
                if selection_trigger_source is not None:
                    try:
                        selection_trigger_source.data = {
                            "trigger": [selection_trigger_source.data.get("trigger", [0])[0] + 1],
                            "x0": [x0],
                            "y0": [y0],
                            "x1": [x1],
                            "y1": [y1]
                        }
                    except Exception as e:
                        if debug:
                            print(f"  ⚠️ Error updating selection_trigger_source: {e}")
                
                # Update BoxAnnotation to show persistent rectangle
                if box_annotation is not None:
                    try:
                        box_annotation.left = min(x0, x1)
                        box_annotation.right = max(x0, x1)
                        box_annotation.bottom = min(y0, y1)
                        box_annotation.top = max(y0, y1)
                        if debug:
                            print(f"  ✅ Updated box_annotation: left={box_annotation.left}, right={box_annotation.right}, bottom={box_annotation.bottom}, top={box_annotation.top}")
                    except Exception as e:
                        if debug:
                            print(f"  ⚠️ Error updating box_annotation: {e}")
                
                # Call user-provided callback if provided
                if on_selection_callback is not None:
                    try:
                        on_selection_callback(x0, y0, x1, y1)
                    except Exception as e:
                        if debug:
                            print(f"  ⚠️ Error in on_selection_callback: {e}")
            else:
                if debug:
                    print(f"  ⚠️ SelectionGeometry event missing coordinates")
        else:
            if debug:
                print(f"  ⚠️ SelectionGeometry event: tool={event.tool}, type={event.geometry.get('type')}")
    
    bokeh_figure.on_event(SelectionGeometry, on_selection_geometry)
    if debug:
        print(f"  ✅ Set SelectionGeometry event handler on {bokeh_figure}")


def reset_plot_to_original_data(
    source: ColumnDataSource,
    original_data: Dict[str, Any],
    bokeh_figure: Any,
    color_mapper: Optional[Any] = None,
    original_min: Optional[float] = None,
    original_max: Optional[float] = None,
    min_input: Optional[Any] = None,
    max_input: Optional[Any] = None,
    debug: bool = False,
) -> None:
    """
    Reset a plot to its original data and settings.
    
    This function restores a plot's data source, color mapper range, range inputs,
    and plot ranges to their original values. Useful for resetting plots after
    they've been modified by computations.
    
    Args:
        source: ColumnDataSource to restore
        original_data: Dictionary with original data (keys: "image", "x", "y", "dw", "dh" for 2D,
                      or "x", "y" for 1D)
        bokeh_figure: Bokeh figure object to reset ranges on
        color_mapper: Optional color mapper to reset range on
        original_min: Original minimum value for color mapper
        original_max: Original maximum value for color mapper
        min_input: Optional range minimum input widget to update
        max_input: Optional range maximum input widget to update
        debug: If True, print debug messages
    """
    try:
        import copy
        
        # Deep copy the original data to avoid reference issues
        restored_data = copy.deepcopy(original_data)
        source.data = restored_data
        
        # Update color mapper to original range if provided
        if color_mapper is not None and original_min is not None and original_max is not None:
            color_mapper.low = original_min
            color_mapper.high = original_max
        
        # Update range inputs if provided
        if min_input is not None and original_min is not None:
            try:
                min_input.value = str(original_min)
            except:
                pass
        if max_input is not None and original_max is not None:
            try:
                max_input.value = str(original_max)
            except:
                pass
        
        # Reset plot ranges if original data has position/size info
        if "x" in original_data and "dw" in original_data:
            # 2D plot with image data
            bokeh_figure.x_range.start = original_data["x"][0]
            bokeh_figure.x_range.end = original_data["x"][0] + original_data["dw"][0]
            bokeh_figure.y_range.start = original_data["y"][0]
            bokeh_figure.y_range.end = original_data["y"][0] + original_data["dh"][0]
        elif "x" in original_data and len(original_data["x"]) > 0:
            # 1D plot - reset based on x and y ranges
            if len(original_data["x"]) > 0:
                x_min = float(np.min(original_data["x"]))
                x_max = float(np.max(original_data["x"]))
                bokeh_figure.x_range.start = x_min
                bokeh_figure.x_range.end = x_max
            if "y" in original_data and len(original_data["y"]) > 0:
                y_min = float(np.min(original_data["y"]))
                y_max = float(np.max(original_data["y"]))
                bokeh_figure.y_range.start = y_min
                bokeh_figure.y_range.end = y_max
        
        if debug:
            print(f"  ✅ Reset plot to original data")
    except Exception as e:
        if debug:
            print(f"  ⚠️ Error resetting plot: {e}")
            import traceback
            traceback.print_exc()



