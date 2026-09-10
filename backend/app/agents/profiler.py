"""Profiler agent — schema, dtypes, roles, missingness, per-column stats."""
import pandas as pd

from ..utils import num_or_none, short


def _classify(s: pd.Series) -> str:
    if pd.api.types.is_bool_dtype(s):
        return "boolean"
    if pd.api.types.is_datetime64_any_dtype(s):
        return "datetime"
    if pd.api.types.is_numeric_dtype(s):
        return "numeric"
    if s.dtype == object:
        if s.nunique(dropna=True) == len(s) and len(s) > 50:
            return "identifier"
        return "categorical"
    return "other"


def profiler_agent(state: dict) -> dict:
    df = state.get("df")
    if df is None:
        return {}

    cleaning = state.get("cleaning", {}) or {}
    missing_before = cleaning.get("missing_before", {})
    n_rows, n_cols = df.shape

    counts = {"numeric": 0, "categorical": 0, "datetime": 0, "boolean": 0, "identifier": 0, "other": 0}
    columns = []

    for c in df.columns:
        s = df[c]
        role = _classify(s)
        counts[role] = counts.get(role, 0) + 1

        info = {
            "name": str(c),
            "dtype": str(s.dtype),
            "role": role,
            "missing": int(s.isna().sum()),
            "missing_before": int(missing_before.get(str(c), 0)),
            "unique": int(s.nunique(dropna=True)),
        }

        if role == "numeric":
            d = s.describe()
            info["stats"] = {
                "mean": num_or_none(d["mean"]),
                "std": num_or_none(d["std"]),
                "min": num_or_none(d["min"], 6),
                "median": num_or_none(s.median()),
                "max": num_or_none(d["max"], 6),
            }
        elif role in ("categorical", "boolean"):
            vc = s.value_counts().head(3)
            info["top_values"] = [{"value": short(k), "count": int(v)} for k, v in vc.items()]
        elif role == "datetime":
            if s.notna().any():
                info["range"] = [s.min().isoformat(), s.max().isoformat()]

        if role in ("identifier", "other"):
            info["sample"] = [short(v) for v in pd.unique(s.dropna().head(50))[:3]]

        columns.append(info)

    total_missing_before = sum(missing_before.values())
    overview = {
        "rows": int(n_rows),
        "columns": int(n_cols),
        "column_types": counts,
        "missing_cells_before_cleaning": int(total_missing_before),
        "missing_pct": round(100.0 * total_missing_before / max(1, n_rows * n_cols), 2),
        "duplicate_rows_removed": int(cleaning.get("duplicates_removed", 0)),
        "memory_mb": round(float(df.memory_usage(deep=True).sum()) / 1e6, 2),
        "completeness_pct": round(100.0 * (1 - total_missing_before / max(1, n_rows * n_cols)), 2),
    }
    return {"profile": {"overview": overview, "columns": columns}}
