"""Visualizer agent — builds Plotly figure specs (JSON) for the frontend.

Charts are produced on the backend and rendered by React, so the dashboard
can be regenerated/modified (e.g. by an LLM) without touching the frontend.
"""
import json
import re

import plotly.express as px
import plotly.io as pio

MAX_HIST_SAMPLE = 2000
MAX_NUMERIC_CHARTS = 8
MAX_CATEGORICAL_CHARTS = 6

_DARK = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    margin=dict(l=45, r=15, t=10, b=40),
    font=dict(size=11),
)


def _slug(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", str(name)).strip("_")[:40] or "col"


def _fig_json(fig, showlegend=None):
    layout = dict(_DARK)
    if showlegend is not None:
        layout["showlegend"] = showlegend
    fig.update_layout(**layout)
    # pio.to_json handles numpy scalars and NaN -> null
    return json.loads(pio.to_json(fig))


def visualizer_agent(state: dict) -> dict:
    df = state.get("df")
    if df is None:
        return {}

    prof = state.get("profile", {}) or {}
    modeling = state.get("modeling", {}) or {}
    cleaning = state.get("cleaning", {}) or {}
    cols_info = prof.get("columns", [])
    charts = []

    def add(cid, title, fig, wide=False, showlegend=None):
        charts.append(
            {"id": cid, "title": title, "wide": wide, "figure": _fig_json(fig, showlegend)}
        )

    # 1) missingness before cleaning
    missing = cleaning.get("missing_before", {})
    if missing:
        items = sorted(missing.items(), key=lambda kv: -kv[1])[:15]
        fig = px.bar(x=[k for k, _ in items], y=[int(v) for _, v in items],
                     labels={"x": "", "y": "missing cells"})
        fig.update_traces(marker_color="#f59e0b")
        add("missingness", "Missing values by column (before cleaning)", fig)

    # 2) correlation heatmap
    corr = (modeling.get("correlation") or {}).get("matrix")
    if corr:
        cols = list(corr.keys())
        z = [[corr[c1][c2] for c2 in cols] for c1 in cols]
        fig = px.imshow(z, x=cols, y=cols, text_auto=".2f",
                        color_continuous_scale="RdBu_r", zmin=-1, zmax=1, aspect="auto")
        fig.update_xaxes(tickangle=-40)
        fig.update_layout(coloraxis_colorbar=dict(len=0.85))
        add("heatmap", "Correlation matrix (Pearson r)", fig, wide=True, showlegend=False)

    # 3) clusters + anomalies over the PCA projection
    viz = modeling.get("_viz")
    if viz:
        if viz.get("cluster_labels") is not None:
            fig = px.scatter(
                x=viz["pca_x"], y=viz["pca_y"],
                color=[f"cluster {l}" for l in viz["cluster_labels"]],
                labels={"x": "PC1", "y": "PC2"},
                opacity=0.75,
            )
            add("clusters", "KMeans clusters (PCA projection)", fig, wide=True)
        n_anom = sum(viz["anomaly"])
        fig = px.scatter(
            x=viz["pca_x"], y=viz["pca_y"],
            color=["anomaly" if a else "normal" for a in viz["anomaly"]],
            color_discrete_map={"anomaly": "#f87171", "normal": "#38bdf8"},
            labels={"x": "PC1", "y": "PC2"},
            opacity=0.75,
        )
        add("anomalies", f"Anomalies — Isolation Forest ({n_anom} flagged, PCA view)", fig, wide=True)

    # 4) histograms for numeric columns (most-varied first)
    numeric = [c["name"] for c in cols_info if c["role"] == "numeric"]
    numeric = sorted(numeric, key=lambda c: -df[c].nunique())[:MAX_NUMERIC_CHARTS]
    for c in numeric:
        s = df[c].dropna()
        if s.empty:
            continue
        if len(s) > MAX_HIST_SAMPLE:
            s = s.sample(MAX_HIST_SAMPLE, random_state=42)
        fig = px.histogram(x=s.tolist(), nbins=30, marginal="box", labels={"x": c})
        fig.update_traces(marker_line_width=0, opacity=0.85)
        add(f"hist_{_slug(c)}", f"Distribution — {c}", fig, showlegend=False)

    # 5) bar charts for low-cardinality categoricals
    cats = [c["name"] for c in cols_info if c["role"] in ("categorical", "boolean")]
    cats = [c for c in cats if 2 <= df[c].nunique() <= 50][:MAX_CATEGORICAL_CHARTS]
    for c in cats:
        vc = df[c].astype(str).value_counts().head(10).iloc[::-1]
        fig = px.bar(x=vc.values.tolist(), y=vc.index.tolist(), orientation="h")
        fig.update_traces(marker_color="#38bdf8")
        add(f"cat_{_slug(c)}", f"Top values — {c}", fig, showlegend=False)

    return {"charts": charts}
