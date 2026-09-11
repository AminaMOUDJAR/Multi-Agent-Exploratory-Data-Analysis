# cleanups, in order:
#   1. drop columns that are 100% empty
#   2. snapshot missingness (the profiler and a chart want the *before* numbers)
#   3. trim stray whitespace on string cells
#   4. try to turn object columns into real dates (must happen before imputing,
#      otherwise dates get mode-filled as strings and stay strings)
#   5. drop dupes
#   6. impute: median for numeric, mode for the rest
import pandas as pd

_DATE_SAMPLE = 200


def _try_parse_dates(df: pd.DataFrame):
    # only convert a column if >=80% of it parses as a date, don't want to
    # mangle free text that happens to look date-ish. sample the head for speed.
    converted = []
    for col in df.select_dtypes(include="object").columns:
        sample = df[col].dropna().head(_DATE_SAMPLE)
        if sample.empty:
            continue
        for kwargs in ({}, {"format": "mixed"}):
            try:
                if pd.to_datetime(sample, errors="coerce", **kwargs).isna().mean() <= 0.2:
                    df[col] = pd.to_datetime(df[col], errors="coerce", **kwargs)
                    converted.append(str(col))
                    break
            except (ValueError, TypeError):
                continue
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

    # 1) fully empty columns are dead weight
    drop = [c for c in df.columns if df[c].isna().all()]
    if drop:
        df = df.drop(columns=drop)
        report["dropped_columns"] = [str(c) for c in drop]

    # 2) snapshot BEFORE imputation
    report["missing_before"] = {str(c): int(v) for c, v in df.isna().sum().items() if v > 0}

    # 3) "foo " != "foo", excel files are full of these
    for c in df.select_dtypes(include="object").columns:
        s = df[c]
        mask = s.map(lambda v: isinstance(v, str) and v != v.strip())
        if mask.any():
            report["whitespace_trimmed_cells"] += int(mask.sum())
            df[c] = s.where(~mask, s.str.strip())

    # 4) dates (see note at top, order matters)
    df, converted = _try_parse_dates(df)
    report["date_converted"] = converted

    # 5) exact dupes out
    n0 = len(df)
    df = df.drop_duplicates().reset_index(drop=True)
    report["duplicates_removed"] = int(n0 - len(df))

    # 6) fill the holes
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
