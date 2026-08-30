"""Per-project driver analysis — PS expected outcome (f).

Answers "why was MY project flagged?", which is the first thing a line ministry asks.
SHAP contributions are computed once at score time and cached in SQLite, so the API is a
lookup rather than a computation.
"""
import argparse, json, os, sqlite3
import numpy as np, pandas as pd, joblib
import shap
from common import PANEL, MODELS, DB
import features as F
from train import sector_dummies

# plain-English names — a monitoring officer, not a modeller, reads these
LABEL = {
    "mons_to_due": "Time left to the deadline",
    "cur_slip": "Delay already on record",
    "physical_progress": "Physical progress",
    "fin_pct": "Share of budget spent",
    "gap": "Progress vs spending gap",
    "prior_revs": "Times revised before",
    "pp_delta_3m": "Progress in the last 3 months",
    "exp_delta_3m": "Spending in the last 3 months",
    "mons_since_sanction": "Age since sanction",
    "cost": "Project cost",
    "original_cost": "Original cost",
    "expenditure": "Money spent",
    "overdue": "Already past due date",
    "nobs": "Months of history we hold",
}


def pretty(name):
    if name.startswith("sector_"):
        return f"Sector: {name[7:]}"
    return LABEL.get(name, name.replace("_", " ").capitalize())


def compute(target="schedule", top_k=6):
    df = pd.read_parquet(PANEL)
    for c in ["t", "sanction_date", "original_end_date", "revised_date"]:
        df[c] = pd.to_datetime(df[c]).dt.date
    b = joblib.load(os.path.join(MODELS, f"{target}.joblib"))
    X, meta = F.build_matrix(df, require_label=False)
    X, _ = sector_dummies(X, meta, cats=b["sector_cols"])
    X = X.reindex(columns=b["features"], fill_value=np.nan).astype(float)

    # the calibrated wrapper isn't a tree; explain the underlying booster
    ex = shap.TreeExplainer(b["raw"])
    sv = ex.shap_values(X)
    if isinstance(sv, list):
        sv = sv[1]
    if sv.ndim == 3:
        sv = sv[:, :, 1]
    print(f"  SHAP computed for {sv.shape[0]} rows x {sv.shape[1]} features")

    rows = []
    cols = list(X.columns)
    for i in range(len(meta)):
        c = sv[i]
        order = np.argsort(-np.abs(c))[:top_k]
        for r, j in enumerate(order, 1):
            if abs(c[j]) < 1e-6:
                continue
            rows.append({
                "pid": int(meta.pid.iloc[i]), "month": meta.month.iloc[i],
                "rank": r, "feature": cols[j], "label": pretty(cols[j]),
                "value": None if pd.isna(X.iloc[i, j]) else float(X.iloc[i, j]),
                "contribution": float(c[j]),
                "direction": "raises" if c[j] > 0 else "lowers",
            })
    out = pd.DataFrame(rows)
    con = sqlite3.connect(DB)
    out.to_sql("drivers", con, if_exists="replace", index=False)
    con.execute("CREATE INDEX IF NOT EXISTS ix_drivers ON drivers(pid, month)")
    con.commit(); con.close()
    print(f"  cached {len(out)} driver rows for {out.pid.nunique()} projects")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default="schedule")
    a = ap.parse_args()
    print("DRIVER ANALYSIS (PS outcome f)")
    d = compute(a.target)
    ex = d[(d.month == d.month.max())].groupby("pid").head(4)
    pid = ex.pid.iloc[0]
    print(f"\n  example — pid {pid}:")
    for _, r in d[(d.pid == pid) & (d.month == d.month.max())].iterrows():
        v = "n/a" if r.value is None else f"{r.value:.1f}"
        print(f"    {r.direction:6s} risk  {r.label:34s} (value {v:>8s})  impact {r.contribution:+.3f}")
