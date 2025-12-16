"""
Base UI Components for Dashboard Library

This module provides factory functions for creating common Bokeh UI widgets
with consistent styling and behavior.
"""

from typing import Optional, List, Callable, Any, Dict
from bokeh.models import (
    Select,
    Slider,
    Button,
    Toggle,
    TextInput,
    RadioButtonGroup,
    Div,
)


def create_select(
    title: str,
    value: str = "",
    options: Optional[List[str]] = None,
    width: int = 300,
    callback: Optional[Callable] = None,
) -> Select:
    """
    Create a Select dropdown widget.
    
    Args:
        title: Widget title/label
        value: Default selected value
        options: List of options
        width: Widget width in pixels
        callback: Optional callback function (attr, old, new)
        
    Returns:
        Select widget
    """
    widget = Select(
        title=title,
        value=value,
        options=options or [],
        width=width
    )
    
    if callback:
        widget.on_change("value", callback)
    
    return widget


def create_slider(
    title: str,
    start: float,
    end: float,
    value: Optional[float] = None,
    step: float = 0.01,
    width: int = 200,
    callback: Optional[Callable] = None,
) -> Slider:
    """
    Create a Slider widget.
    
    Args:
        title: Widget title/label
        start: Minimum value
        end: Maximum value
        value: Initial value (defaults to midpoint)
        step: Step size
        width: Widget width in pixels
        callback: Optional callback function (attr, old, new)
        
    Returns:
        Slider widget
    """
    if value is None:
        value = start + (end - start) / 2
    
    widget = Slider(
        title=title,
        start=start,
        end=end,
        value=value,
        step=step,
        width=width
    )
    
    if callback:
        widget.on_change("value", callback)
    
    return widget


def create_button(
    label: str,
    button_type: str = "default",
    width: Optional[int] = None,
    callback: Optional[Callable] = None,
) -> Button:
    """
    Create a Button widget.
    
    Args:
        label: Button label text
        button_type: Button type ("default", "primary", "success", "warning", "danger")
        width: Optional button width in pixels
        callback: Optional callback function (no arguments)
        
    Returns:
        Button widget
    """
    kwargs = {
        "label": label,
        "button_type": button_type,
    }
    if width is not None:
        kwargs["width"] = width
    
    widget = Button(**kwargs)
    
    # Set minimal margin to reduce spacing
    widget.margin = (1, 0, 1, 0)  # (top, right, bottom, left) - minimal vertical spacing
    
    if callback:
        widget.on_click(callback)
    
    return widget


def create_toggle(
    label: str,
    active: bool = False,
    button_type: str = "default",
    width: Optional[int] = None,
    callback: Optional[Callable] = None,
) -> Toggle:
    """
    Create a Toggle button widget.
    
    Args:
        label: Toggle label text
        active: Initial active state
        button_type: Button type
        width: Optional toggle width in pixels
        callback: Optional callback function (attr, old, new)
        
    Returns:
        Toggle widget
    """
    kwargs = {
        "label": label,
        "active": active,
        "button_type": button_type,
    }
    if width is not None:
        kwargs["width"] = width
    
    widget = Toggle(**kwargs)
    
    # Set minimal margin to reduce spacing
    widget.margin = (1, 0, 1, 0)  # (top, right, bottom, left) - minimal vertical spacing
    
    if callback:
        widget.on_change("active", callback)
    
    return widget


def create_text_input(
    title: str,
    value: str = "",
    width: int = 120,
    callback: Optional[Callable] = None,
    placeholder: Optional[str] = None,
) -> TextInput:
    """
    Create a TextInput widget.
    
    Args:
        title: Input title/label
        value: Default value
        width: Widget width in pixels
        callback: Optional callback function (attr, old, new)
        placeholder: Optional placeholder text
        
    Returns:
        TextInput widget
    """
    kwargs = {
        "title": title,
        "value": value,
        "width": width,
    }
    if placeholder:
        kwargs["placeholder"] = placeholder
    
    widget = TextInput(**kwargs)
    
    # Set minimal margin to reduce spacing
    widget.margin = (1, 0, 1, 0)  # (top, right, bottom, left) - minimal vertical spacing
    
    if callback:
        widget.on_change("value", callback)
    
    return widget


def create_radio_button_group(
    labels: List[str],
    active: int = 0,
    width: Optional[int] = None,
    callback: Optional[Callable] = None,
) -> RadioButtonGroup:
    """
    Create a RadioButtonGroup widget.
    
    Args:
        labels: List of label strings
        active: Index of initially active button
        width: Optional widget width in pixels
        callback: Optional callback function (attr, old, new)
        
    Returns:
        RadioButtonGroup widget
    """
    kwargs = {
        "labels": labels,
        "active": active,
    }
    if width is not None:
        kwargs["width"] = width
    
    widget = RadioButtonGroup(**kwargs)
    
    # Set minimal margin to reduce spacing
    widget.margin = (1, 0, 1, 0)  # (top, right, bottom, left) - minimal vertical spacing
    
    if callback:
        widget.on_change("active", callback)
    
    return widget


def create_div(
    text: str = "",
    width: Optional[int] = None,
    height: Optional[int] = None,
    styles: Optional[Dict[str, str]] = None,
) -> Div:
    """
    Create a Div widget for displaying HTML content.
    
    Args:
        text: HTML content
        width: Optional width in pixels
        height: Optional height in pixels
        styles: Optional dictionary of CSS styles
        
    Returns:
        Div widget
    """
    kwargs = {"text": text}
    if width is not None:
        kwargs["width"] = width
    if height is not None:
        kwargs["height"] = height
    if styles:
        kwargs["styles"] = styles
    
    return Div(**kwargs)


def create_label_div(
    text: str,
    width: Optional[int] = None,
    bold: bool = True,
) -> Div:
    """
    Create a Div widget formatted as a label.
    
    Args:
        text: Label text
        width: Optional width in pixels
        bold: Whether to make text bold
        
    Returns:
        Div widget with label styling
    """
    html_text = f"<b>{text}</b>" if bold else text
    return create_div(text=html_text, width=width)


def create_spacer(
    width: Optional[int] = None,
    height: Optional[int] = None,
) -> Div:
    """
    Create an empty Div widget for spacing.
    
    Args:
        width: Optional width in pixels
        height: Optional height in pixels
        
    Returns:
        Empty Div widget
    """
    return create_div(text="", width=width, height=height)


def create_separator(
    width: Optional[int] = None,
) -> Div:
    """
    Create a horizontal separator (hr) Div.
    
    Args:
        width: Optional width in pixels
        
    Returns:
        Div widget with horizontal rule
    """
    return create_div(text="<hr>", width=width)

