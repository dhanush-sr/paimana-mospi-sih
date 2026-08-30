"""Train, calibrate, evaluate. Forward time split only — never random."""
import argparse, json, os
import numpy as np, pandas as pd, joblib
from datetime import date
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, average_precision_score
from common import PANEL, MODELS, REPORTS
import features as F

SPLIT = "2026-04"


def sector_dummies(X, meta, cats=None):
    s = pd.get_dummies(meta.sector, prefix="sector", dummy_na=True)
    if cats is not None:
        s = s.reindex(columns=cats, fill_value=False)
    return pd.concat([X.reset_index(drop=True), s.reset_index(drop=True)], axis=1), list(s.columns)


def ece(y, p, bins=10):
    """expected calibration error"""
    idx = np.digitize(p, np.linspace(0, 1, bins + 1)[1:-1])
    e = 0.0
    for b in range(bins):
        m = idx == b
        if m.sum():
            e += m.mean() * abs(y[m].mean() - p[m].mean())
    return float(e)


def leaky_demo(df):
    """The model everyone else will build. R^2 = 1.0 because it is subtraction."""
    d = df.dropna(subset=["original_end_date", "revised_date"]).copy()
    d["y"] = [(r - o).days for r, o in zip(d.revised_date, d.original_end_date)]
    d["oed"] = d.original_end_date.map(lambda x: x.toordinal())
    d["rev"] = d.revised_date.map(lambda x: x.toordinal())
    X = d[["oed", "rev", "original_cost"]].fillna(0)
    Xtr, Xte, ytr, yte = train_test_split(X, d.y, test_size=.3, random_state=0)
    lr = LinearRegression().fit(Xtr, ytr)
    return {"r2": float(lr.score(Xte, yte)),
            "coef_original_end_date": float(lr.coef_[0]),
            "coef_revised_date": float(lr.coef_[1])}


def run(target="schedule", split=SPLIT, report=False):
    df = pd.read_parquet(PANEL)
    for c in ["t", "sanction_date", "original_end_date", "revised_date"]:
        df[c] = pd.to_datetime(df[c]).dt.date
    F.assert_no_leakage()
    X, meta = F.build_matrix(df)
    X, seccols = sector_dummies(X, meta)
    feats = list(X.columns)
    y = meta[f"y_{target}"].to_numpy()

    tr = meta.month < split
    te = ~tr
    Xtr, Xte, ytr, yte = X[tr].astype(float), X[te].astype(float), y[tr], y[te]
    assert not set(meta.month[tr]) & set(meta.month[te]), "train/test month overlap"

    base = HistGradientBoostingClassifier(max_iter=300, learning_rate=.06, random_state=0)
    raw = base.fit(Xtr, ytr)
    p_raw = raw.predict_proba(Xte)[:, 1]

    # calibration on a held-out slice carved from TRAIN ONLY (never test)
    cal = CalibratedClassifierCV(
        HistGradientBoostingClassifier(max_iter=300, learning_rate=.06, random_state=0),
        method="isotonic", cv=3).fit(Xtr, ytr)
    p = cal.predict_proba(Xte)[:, 1]

    m = {
        "target": target, "split": split,
        "n_train": int(tr.sum()), "n_test": int(te.sum()),
        "base_rate_train": float(ytr.mean()), "base_rate_test": float(yte.mean()),
        "roc_auc": float(roc_auc_score(yte, p_raw)),
        "roc_auc_calibrated": float(roc_auc_score(yte, p)),
        "pr_auc": float(average_precision_score(yte, p_raw)),
        "ece_uncalibrated": ece(yte, p_raw), "ece_calibrated": ece(yte, p),
    }
    for k in (50, 100, 200):
        m[f"precision_at_{k}"] = float(yte[np.argsort(-p_raw)[:k]].mean())
    ov, pr = Xte["overdue"].fillna(0).to_numpy(), Xte["prior_revs"].fillna(0).to_numpy()
    m["baseline_overdue_auc"] = float(roc_auc_score(yte, ov))
    m["baseline_prior_revs_auc"] = float(roc_auc_score(yte, pr))
    m["leaky_demo"] = leaky_demo(df)

    # within-regime robustness (post the 2026-03 structural break)
    a = meta.month.isin(["2026-03", "2026-04"]); b = meta.month.isin(["2026-06", "2026-07"])
    if a.sum() > 100 and b.sum() > 100 and len(set(y[b])) > 1:
        r = HistGradientBoostingClassifier(max_iter=300, learning_rate=.06,
                                           random_state=0).fit(X[a].astype(float), y[a])
        m["within_regime_auc"] = float(roc_auc_score(y[b], r.predict_proba(X[b].astype(float))[:, 1]))

    joblib.dump({"model": cal, "raw": raw, "features": feats, "sector_cols": seccols,
                 "manifest": {n: F.REGISTRY[n]["reads"] for n in F.CORE},
                 "split": split, "target": target}, os.path.join(MODELS, f"{target}.joblib"))
    json.dump(m, open(os.path.join(REPORTS, f"{target}_metrics.json"), "w"), indent=1)

    if report:
        print(f"\n[{target.upper()}]  train {m['n_train']} (<{split})   test {m['n_test']} (>={split})")
        print(f"  base rate test        {m['base_rate_test']:.3f}")
        print(f"  ROC-AUC               {m['roc_auc']:.4f}")
        print(f"  PR-AUC                {m['pr_auc']:.4f}   (baseline {m['base_rate_test']:.4f})")
        for k in (50, 100, 200):
            print(f"  precision@top-{k:<4d}   {m[f'precision_at_{k}']:.3f}")
        print(f"  ECE  uncal {m['ece_uncalibrated']:.4f} -> cal {m['ece_calibrated']:.4f}")
        print(f"  baseline 'overdue'    {m['baseline_overdue_auc']:.4f}  <- today's heuristic")
        print(f"  baseline 'prior revs' {m['baseline_prior_revs_auc']:.4f}")
        if "within_regime_auc" in m:
            print(f"  within-regime re-test {m['within_regime_auc']:.4f}  (Mar+Apr -> Jun+Jul)")
        L = m["leaky_demo"]
        print(f"  LEAKY DEMO            R2={L['r2']:.4f}  coefs {L['coef_original_end_date']:+.3f} / "
              f"{L['coef_revised_date']:+.3f}   <- subtraction")
    return m


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default="schedule", choices=["schedule", "cost"])
    ap.add_argument("--split", default=SPLIT)
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--both", action="store_true")
    a = ap.parse_args()
    for t in (["schedule", "cost"] if a.both else [a.target]):
        run(t, a.split, report=a.report or a.both)
