# all the actual ML lives here:
#   - pearson correlation matrix + strongest pairs
#   - kmeans (k=3) with a 2d PCA projection so the scatter is plottable
#   - isolation forest for anomalies
#   - a tiny pytorch autoencoder, but ONLY if torch happens to be installed
#     (it's a soft dep on purpose, don't make people install torch for a histogram)
#
# the "_viz" key at the bottom holds arrays sized for plotting. it gets stripped
# out of the json report in main.py and the visualizer bakes it into figures.
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from ..utils import num_or_none

try:  # optional, see note above
    import torch
    import torch.nn as nn

    HAS_TORCH = True
except Exception:
    torch = None
    nn = None
    HAS_TORCH = False

MAX_VIZ_POINTS = 3000  # cap the scatter, plotly chokes on 100k dots
MAX_AE_ROWS = 20000
AE_MIN_ROWS = 100


def _autoencoder_mse(Z: np.ndarray):
    """train a small dense AE on the scaled features, return per-row
    reconstruction mse. rows it can't reconstruct well are the weird ones.
    returns None if the dataset is too small/big for it to make sense."""
    n, d = Z.shape
    if not (AE_MIN_ROWS <= n <= MAX_AE_ROWS and d >= 3):
        return None
    torch.manual_seed(42)
    X = torch.tensor(Z, dtype=torch.float32)
    h1, h2 = max(8, d // 2), max(4, d // 3)
    autoencoder = nn.Sequential(
        nn.Linear(d, h1), nn.ReLU(),
        nn.Linear(h1, h2), nn.ReLU(),
        nn.Linear(h2, h1), nn.ReLU(),
        nn.Linear(h1, d),
    )
    optimizer = torch.optim.Adam(autoencoder.parameters(), lr=1e-3)
    for _ in range(40):
        optimizer.zero_grad()
        loss = ((autoencoder(X) - X) ** 2).mean()
        loss.backward()
        optimizer.step()
    with torch.no_grad():
        mse = ((autoencoder(X) - X) ** 2).mean(dim=1).numpy()
    return mse


def modeler_agent(state: dict) -> dict:
    df = state.get("df")
    if df is None:
        return {}

    num = df.select_dtypes(include=np.number)
    modeling = {
        "numeric_columns": [str(c) for c in num.columns],
        "correlation": None,
        "clustering": None,
        "anomalies": None,
        "autoencoder": None,
    }
    if num.shape[1] < 2 or len(df) < 5:
        return {"modeling": modeling}  # not enough to do anything useful

    # numeric + non-constant + imputed. a constant column breaks scaling.
    work = num.copy()
    for c in work.columns:
        if work[c].nunique(dropna=True) <= 1:
            work = work.drop(columns=c)
    work = work.fillna(work.median())
    if work.shape[1] < 2 or len(work) < 5:
        return {"modeling": modeling}

    # --- correlations (on the original numeric cols, not the trimmed work set) ---
    corr = num.corr()
    cols = [str(c) for c in corr.columns]
    pairs = []
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            r = num_or_none(corr.iloc[i, j], 3)
            if r is not None:
                pairs.append({"x": cols[i], "y": cols[j], "r": r})
    pairs.sort(key=lambda p: abs(p["r"]), reverse=True)
    matrix = {c1: {c2: num_or_none(corr.loc[c1, c2], 3) for c2 in cols} for c1 in cols}
    modeling["correlation"] = {"matrix": matrix, "top_pairs": pairs[:8]}

    # scale once, every model below wants standardized features
    Z = StandardScaler().fit_transform(work.values.astype(float))
    feat_names = [str(c) for c in work.columns]

    # --- pca, just for the 2d scatter ---
    pca = PCA(n_components=2, random_state=42)
    P = pca.fit_transform(Z)

    # --- kmeans ---
    labels = None
    k = 3 if len(Z) >= 15 else 2
    if len(Z) >= 2 * k:
        km = KMeans(n_clusters=k, n_init=10, random_state=42)
        labels = km.fit_predict(Z)
        modeling["clustering"] = {
            "k": int(k),
            "features": feat_names,
            "sizes": [int(s) for s in np.bincount(labels, minlength=k)],
            "pca_explained_variance": [num_or_none(v, 3) for v in pca.explained_variance_ratio_],
        }

    # --- isolation forest, 2% contamination as a starting guess ---
    iso = IsolationForest(n_estimators=150, contamination=0.02, random_state=42)
    pred = iso.fit_predict(Z)
    anomaly_flags = pred == -1
    modeling["anomalies"] = {
        "method": "isolation_forest",
        "count": int(anomaly_flags.sum()),
        "rate": round(float(anomaly_flags.mean()), 4),
        "example_row_numbers": (np.where(anomaly_flags)[0][:20] + 1).tolist(),
    }

    # --- torch AE, best effort ---
    if HAS_TORCH:
        try:
            mse = _autoencoder_mse(Z)
            if mse is not None:
                threshold = float(np.quantile(mse, 0.98))
                ae_flags = mse > threshold
                modeling["autoencoder"] = {
                    "available": True,
                    "count": int(ae_flags.sum()),
                    "threshold": num_or_none(threshold, 6),
                    "overlap_with_isolation_forest": int((ae_flags & anomaly_flags).sum()),
                    "mse_stats": {"mean": num_or_none(mse.mean(), 6), "max": num_or_none(mse.max(), 6)},
                }
        except Exception:  # AE failing should never kill the pipeline
            modeling["autoencoder"] = {"available": False, "error": "autoencoder training failed"}

    # --- arrays for the charts ---
    # subsample the normal points so the scatter stays light, but ALWAYS keep
    # every anomaly, those are the interesting dots
    rng = np.random.default_rng(42)
    anom_idx = np.where(anomaly_flags)[0]
    norm_idx = np.where(~anomaly_flags)[0]
    room = max(0, MAX_VIZ_POINTS - len(anom_idx))
    take_norm = rng.choice(norm_idx, size=min(len(norm_idx), room), replace=False)
    sel = np.concatenate([anom_idx, take_norm]).astype(int)
    modeling["_viz"] = {
        "pca_x": P[sel, 0].tolist(),
        "pca_y": P[sel, 1].tolist(),
        "cluster_labels": labels[sel].tolist() if labels is not None else None,
        "anomaly": anomaly_flags[sel].tolist(),
        "features": feat_names,
    }

    return {"modeling": modeling}
