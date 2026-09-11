# first stop: get the file into a dataframe. handles csv/tsv/txt (sniffs the
# delimiter) plus xlsx via openpyxl. latin1 fallback because real-world csvs
# are never utf-8 when you need them to be.
import os

import pandas as pd

from ..config import MAX_ROWS


def loader_agent(state: dict) -> dict:
    path = state.get("file_path", "")
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext in (".xlsx", ".xls"):
            df = pd.read_excel(path)
        else:
            try:
                # sep=None + python engine = delimiter sniffing, catches ; and \t files
                df = pd.read_csv(path, sep=None, engine="python")
            except UnicodeDecodeError:
                df = pd.read_csv(path, sep=None, engine="python", encoding="latin1")
    except Exception as exc:  # whatever broke, the api caller deserves to know
        return {"df": None, "error": f"Could not parse file: {exc}"}

    df.columns = [str(c).strip() or f"col_{i}" for i, c in enumerate(df.columns)]

    truncated = False
    if len(df) > MAX_ROWS:
        df = df.iloc[:MAX_ROWS]
        truncated = True

    return {
        "df": df,
        "file_name": state.get("file_name") or os.path.basename(path),
        "load_info": {
            "rows_loaded": int(len(df)),
            "columns": int(df.shape[1]),
            "truncated_to_max_rows": truncated,
        },
    }
