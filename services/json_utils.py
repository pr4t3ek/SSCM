"""Recursively convert pandas/numpy values to plain JSON-serializable types.

Flask's default JSON provider chokes on numpy scalars, pandas Timestamps and
NaN/NaT, so every API route funnels its response dict through `json_safe()`
before calling `jsonify()`.
"""
import math
import numpy as np
import pandas as pd


def json_safe(value):
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if isinstance(value, (pd.Series,)):
        return json_safe(value.tolist())
    if isinstance(value, (pd.DataFrame,)):
        return json_safe(value.to_dict(orient="records"))
    if isinstance(value, np.ndarray):
        return json_safe(value.tolist())
    if value is None:
        return None
    if isinstance(value, (pd.Timestamp,)):
        if pd.isna(value):
            return None
        return value.strftime("%Y-%m-%d")
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return round(value, 6) if not value.is_integer() else value
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value
