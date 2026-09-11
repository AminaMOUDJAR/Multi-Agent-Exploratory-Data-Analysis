# the write-up agent. tries the LLM first (grounded in a compact json summary
# of everything the other agents found), falls back to a deterministic
# template if there's no key or the call blows up. so the app is fully
# usable with zero api spend, the template just reads drier.
import json

from ..config import LLM_MODEL, llm_client
from ..utils import num_or_none

MAX_CONTEXT_CHARS = 6000

SYSTEM_PROMPT = (
    "You are a senior data analyst summarizing an exploratory data analysis for a business "
    "audience. Use ONLY the JSON context provided; never invent numbers or columns. Write "
    "concise markdown (max ~350 words) with exactly these sections:\n"
    "## Overview\n## Data Quality\n## Distributions & Relationships\n"
    "## Segments & Anomalies\n## Recommended Next Steps\n"
    "Reference concrete column names and values. Prefer short bullets over long prose."
)

ASK_SYSTEM = (
    "You are a data analyst answering questions about a dataset the user uploaded. Answer ONLY "
    "from the provided report context; if the context does not contain the answer, say so and "
    "suggest what to check or re-run. Be concise (max ~150 words). Light markdown is fine."
)


def _columns_lines(cols, cap=40):
    lines = []
    for c in cols[:cap]:
        bits = [f"{c['name']} ({c['role']}/{c['dtype']}, missing_before={c['missing_before']}, unique={c['unique']})"]
        if c.get("stats"):
            st = c["stats"]
            bits.append(f"mean={st['mean']}, std={st['std']}, min={st['min']}, median={st['median']}, max={st['max']}")
        if c.get("top_values"):
            bits.append("top=" + ", ".join(f"{t['value']}({t['count']})" for t in c["top_values"]))
        if c.get("range"):
            bits.append(f"range={c['range'][0]}..{c['range'][1]}")
        lines.append("; ".join(bits))
    if len(cols) > cap:
        lines.append(f"...and {len(cols) - cap} more columns")
    return lines


def build_context(state: dict) -> str:
    """compact json summary of everything the pipeline found. feeds both the
    insights prompt here and the /ask endpoint. keep it small, tokens cost."""
    prof = state.get("profile", {}) or {}
    modeling = state.get("modeling", {}) or {}
    cleaning = state.get("cleaning", {}) or {}
    ctx = {
        "file": state.get("file_name"),
        "overview": prof.get("overview"),
        "cleaning": {
            k: cleaning.get(k)
            for k in ("rows_before", "rows_after", "duplicates_removed", "dropped_columns",
                      "imputations", "date_converted")
        },
        "columns": _columns_lines(prof.get("columns", [])),
        "top_correlations": (modeling.get("correlation") or {}).get("top_pairs", [])[:6],
        "clustering": modeling.get("clustering"),
        "anomalies": modeling.get("anomalies"),
        "autoencoder": modeling.get("autoencoder"),
    }
    return json.dumps(ctx, default=str)[:MAX_CONTEXT_CHARS]


def _llm(user_prompt: str, system: str = SYSTEM_PROMPT, max_tokens: int = 900, temperature: float = 0.3):
    client = llm_client()
    if client is None:
        return None
    try:
        resp = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return ((resp.choices[0].message.content or "").strip() or None)
    except Exception:  # any llm hiccup -> template, never a 500
        return None


def insights_agent(state: dict) -> dict:
    prof = state.get("profile", {})
    if not prof:
        return {}

    context = build_context(state)
    text = _llm(
        f"Dataset: {state.get('file_name')}\n\nContext (JSON):\n{context}\n\nWrite the EDA summary now."
    )
    source = "llm"
    if not text:
        text = _template(state)
        source = "template"

    return {
        "insights": {"source": source, "model": LLM_MODEL if source == "llm" else None, "text": text},
        "context": context,
    }


def _template(state: dict) -> str:
    # no-key fallback. same facts as the llm prompt, just stitched together.
    prof = state.get("profile", {}) or {}
    modeling = state.get("modeling", {}) or {}
    cleaning = state.get("cleaning", {}) or {}
    ov = prof.get("overview", {})
    cols = prof.get("columns", [])

    lines = [
        "## Overview",
        f"- File **{state.get('file_name')}**: {ov.get('rows')} rows × {ov.get('columns')} columns "
        + "(" + ", ".join(f"{v} {k}" for k, v in (ov.get("column_types") or {}).items() if v) + ").",
    ]

    n_imputed = sum(i.get("missing", 0) for i in cleaning.get("imputations", []))
    lines += [
        "## Data Quality",
        f"- Removed {cleaning.get('duplicates_removed', 0)} duplicate rows "
        f"({cleaning.get('rows_before', '?')} → {cleaning.get('rows_after', '?')} rows).",
        f"- Imputed {n_imputed} missing values (median for numeric, mode for categorical). "
        f"Original completeness: {ov.get('completeness_pct', 100)}%.",
    ]

    pairs = (modeling.get("correlation") or {}).get("top_pairs") or []
    if pairs:
        lines.append("## Distributions & Relationships")
        lines += [f"- {p['x']} ↔ {p['y']}: r = {p['r']:+.2f}" for p in pairs[:5]]

    clust = modeling.get("clustering")
    anom = modeling.get("anomalies")
    ae = modeling.get("autoencoder") or {}
    if clust or anom:
        lines.append("## Segments & Anomalies")
        if clust:
            lines.append(
                f"- KMeans found {clust.get('k')} segments (sizes {clust.get('sizes')}) over "
                f"{len(clust.get('features', []))} scaled numeric features."
            )
        if anom:
            rate = num_or_none((anom.get("rate") or 0) * 100, 1)
            lines.append(
                f"- {anom.get('count')} rows ({rate}%) flagged as anomalies by Isolation Forest."
            )
        if ae.get("available"):
            lines.append(
                f"- PyTorch autoencoder agrees on {ae.get('overlap_with_isolation_forest')} of "
                f"{ae.get('count')} high-reconstruction-error rows."
            )

    numeric_names = [c["name"] for c in cols if c["role"] == "numeric"]
    lines += [
        "## Recommended Next Steps",
        "- Review the flagged anomaly rows before using this data for decisions or training.",
        "- Verify that imputed values look plausible for their columns.",
        "- " + (
            f"Drill into the correlation between **{numeric_names[0]}** and its strongest pair."
            if numeric_names else "Add numeric columns to unlock correlation and clustering views."
        ),
    ]
    return "\n".join(lines)
