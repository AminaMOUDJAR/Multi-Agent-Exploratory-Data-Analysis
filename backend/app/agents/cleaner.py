"""Cleaner agent — drop empty columns, trim strings, coerce dates,
deduplicate rows, and impute missing values (median / mode).
"""
import pandas as pd

_DATE_SAMPLE = 200


def _try_parse_dates(df: pd.DataFrame):
    """Convert object columns that are ≥80% date-parseable to datetime64."""
    converted = []
    for col in df.select_dtypes(include="object").columns:
        sample = df[col].dropna().head(_DATE_SAMPLE)
        if sample.empty:
            continue
        done = False
        for kwargs in ({}, {"format": "mixed"}):
            try:
                if pd.to_datetime(sample, errors="coerce", **kwargs).isna().mean() <= 0.2:
                    df[col] = pd.to_datetime(df[col], errors="coerce", **kwargs)
                    converted.append(str(col))
                    done = True
                    break
            except (ValueError, TypeError):
                continue
        _ = done
    return df, converted


def cleaner_agent(state: dict) -> dict:
    df = state.get("df")
    if df is None:
        return {}

    report = {
        "rows_before": int(len(df)),
        "duplicates_removed": 0,
        "dropped_columns": [],
        "imputations": [],
        "missing_before": {},
        "date_converted": [],
        "whitespace_trimmed_cells": 0,
    }

    # 1) drop fully-empty columns
    drop = [c for c in df.columns if df[c].isna().all()]
    if drop:
        df = df.drop(columns=drop)
        report["dropped_columns"] = [str(c) for c in drop]

    # 2) snapshot missingness BEFORE imputation (used by Profiler + charts)
    report["missing_before"] = {str(c): int(v) for c, v in df.isna().sum().items() if v > 0}

    # 3) trim whitespace on string cells
    for c in df.select_dtypes(include="object").columns:
        s = df[c]
        mask = s.map(lambda v: isinstance(v, str) and v != v.strip())
        if mask.any():
            report["whitespace_trimmed_cells"] += int(mask.sum())
            df[c] = s.where(~mask, s.str.strip())

    # 4) date coercion (before imputation so dates aren't mode-filled as strings)
    df, converted = _try_parse_dates(df)
    report["date_converted"] = converted

    # 5) deduplicate
    n0 = len(df)
    df = df.drop_duplicates().reset_index(drop=True)
    report["duplicates_removed"] = int(n0 - len(df))

    # 6) impute
    for c in df.columns:
        n_miss = int(df[c].isna().sum())
        if n_miss == 0:
            continue
        if pd.api.types.is_numeric_dtype(df[c]) and not pd.api.types.is_bool_dtype(df[c]):
            fill = df[c].median()
            df[c] = df[c].fillna(fill if not pd.isna(fill) else 0)
            report["imputations"].append({"column": str(c), "strategy": "median", "missing": n_miss})
        elif pd.api.types.is_datetime64_any_dtype(df[c]):
            mode = df[c].mode(dropna=True)
            if len(mode):
                df[c] = df[c].fillna(mode.iloc[0])
                report["imputations"].append({"column": str(c), "strategy": "mode(date)", "missing": n_miss})
        else:
            mode = df[c].mode(dropna=True)
            fill = mode.iloc[0] if len(mode) else "Unknown"
            df[c] = df[c].fillna(fill)
            report["imputations"].append({"column": str(c), "strategy": "mode", "missing": n_miss})

    report["rows_after"] = int(len(df))
    return {"df": df, "cleaning": report}
