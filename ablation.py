"""CUF Sufficiency Protocol — PS clause (c).

"...the extent to which predictive performance is attributable to the current CUF fields
vis-a-vis additional variables not presently captured in the CUF."

Tests whether a CANDIDATE variable earns its place on a national statistical form.
Descriptive association is not evidence. Incremental, sector-controlled AUC is.
"""
import argparse, json, os
import numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score, average_precision_score
from common import PANEL, REPORTS
import features as F
from train import sector_dummies, SPLIT

N_BOOT = 200


def candidates(df, meta):
    """Variables NOT in the monitoring feed, derivable from data MoSPI already holds."""
    d = df.sort_values(["pid", "t"])
    load = d.groupby(["month", "agency"]).pid.transform("count")
    load = pd.Series(load.to_numpy(), index=pd.MultiIndex.from_arrays([d.pid, d.month]))
    key = pd.MultiIndex.from_arrays([meta.pid, meta.month])
    return {"agency_load": load.reindex(key).to_numpy()}


def run(candidate="agency_load", split=SPLIT, target="schedule"):
    df = pd.read_parquet(PANEL)
    for c in ["t", "sanction_date", "original_end_date", "revised_date"]:
        df[c] = pd.to_datetime(df[c]).dt.date
    X, meta = F.build_matrix(df)
    X, _ = sector_dummies(X, meta)
    y = meta[f"y_{target}"].to_numpy()
    tr, te = meta.month < split, meta.month >= split

    def fit_score(Xf):
        m = HistGradientBoostingClassifier(max_iter=300, learning_rate=.06,
                                           random_state=0).fit(Xf[tr].astype(float), y[tr])
        return m.predict_proba(Xf[te].astype(float))[:, 1]

    p_base = fit_score(X)
    cand = candidates(df, meta)[candidate]
    X2 = X.copy(); X2[candidate] = cand
    p_cand = fit_score(X2)

    yte = y[te]
    a0, a1 = roc_auc_score(yte, p_base), roc_auc_score(yte, p_cand)
    pr0, pr1 = average_precision_score(yte, p_base), average_precision_score(yte, p_cand)

    rng = np.random.default_rng(0); deltas = []
    for _ in range(N_BOOT):
        i = rng.integers(0, len(yte), len(yte))
        if len(set(yte[i])) < 2:
            continue
        deltas.append(roc_auc_score(yte[i], p_cand[i]) - roc_auc_score(yte[i], p_base[i]))
    lo, hi = np.percentile(deltas, [2.5, 97.5])

    verdict = ("ACCEPTED" if lo > 0 else "REJECTED" if hi < 0 else "INCONCLUSIVE")
    # descriptive association, for contrast with the incremental result
    dd = pd.DataFrame({"c": cand, "y": y})
    bins = pd.cut(dd.c, [0, 5, 20, 50, 150, 10**9], labels=["1-5", "6-20", "21-50", "51-150", "150+"])
    desc = dd.groupby(bins, observed=True).y.agg(["mean", "count"])

    rep = {"candidate": candidate, "target": target, "split": split,
           "auc_cuf_only": float(a0), "auc_with_candidate": float(a1),
           "delta_auc": float(a1 - a0), "ci95": [float(lo), float(hi)],
           "pr_cuf_only": float(pr0), "pr_with_candidate": float(pr1),
           "verdict": verdict,
           "descriptive_rate_by_bin": {str(k): float(v) for k, v in desc["mean"].items()}}
    json.dump(rep, open(os.path.join(REPORTS, "ablation.json"), "w"), indent=1)

    print(f"CUF SUFFICIENCY PROTOCOL — candidate '{candidate}'\n")
    print("  descriptive association (what makes it look promising):")
    for k, r in desc.iterrows():
        print(f"    portfolio {str(k):8s} revision rate {r['mean']:.3f}  (n={int(r['count'])})")
    spread = desc['mean'].max() / max(desc['mean'].min(), 1e-9)
    print(f"    -> {spread:.1f}x spread\n")
    print(f"  CUF-derived features only : AUC {a0:.4f}  PR {pr0:.4f}")
    print(f"  + {candidate:<22s}: AUC {a1:.4f}  PR {pr1:.4f}")
    print(f"  incremental AUC           : {a1-a0:+.4f}   95% CI [{lo:+.4f}, {hi:+.4f}]")
    print(f"\n  VERDICT: {verdict}" + ("  — no incremental value once sector is controlled"
                                        if verdict == "REJECTED" else ""))
    return rep


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate", default="agency_load")
    ap.add_argument("--target", default="schedule")
    a = ap.parse_args()
    run(a.candidate, target=a.target)
