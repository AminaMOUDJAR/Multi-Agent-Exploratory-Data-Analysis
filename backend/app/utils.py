"""JSON-safety helpers.

pandas/sklearn produce numpy scalars and NaN/Inf floats that break strict JSON
(browsers reject `NaN` tokens). Everything returned to the frontend goes
through `to_native` first.
"""
import datetime as dt
import math

import numpy as np
import pandas as pd


def to_native(obj):
    if obj is None or isinstance(obj, (bool, str, int)):
        return obj
    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        f = float(obj)
        return None if (math.isnan(f) or math.isinf(f)) else f
    if isinstance(obj, np.ndarray):
        return to_native(obj.tolist())
    if isinstance(obj, (dt.datetime, dt.date)):
        return obj.isoformat()
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat() if not pd.isna(obj) else None
    if obj is pd.NaT:
        return None
    if isinstance(obj, pd.Series):
        return to_native(obj.tolist())
    if isinstance(obj, dict):
        return {str(k): to_native(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [to_native(v) for v in obj]
    return obj


def num_or_none(value, ndigits=4):
    """float(value) rounded, or None when NaN/Inf/not-a-number."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return round(f, ndigits)


def short(value, limit=40):
    s = str(value)
    return s if len(s) <= limit else s[: limit - 1] + "…"
