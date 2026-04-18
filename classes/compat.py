"""Compatibility utility helpers that replace astrocats package helpers."""
import numbers


def is_integer(value):
    """Return True when value can be interpreted as an integer."""
    if isinstance(value, bool):
        return False
    if isinstance(value, numbers.Integral):
        return True
    if value is None:
        return False
    try:
        text = str(value).strip()
        if text == "":
            return False
        if "." in text:
            return False
        int(text)
        return True
    except Exception:
        return False


def is_number(value):
    """Return True when value can be interpreted as a finite float."""
    if isinstance(value, bool):
        return False
    if isinstance(value, numbers.Real):
        return True
    if value is None:
        return False
    try:
        text = str(value).strip()
        if text == "":
            return False
        float(text)
        return True
    except Exception:
        return False
