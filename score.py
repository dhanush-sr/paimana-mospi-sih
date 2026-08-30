"""Monthly triage: 1,981 projects -> a 50-project shortlist an officer can act on.

Risk alone is not escalation-worthiness. See 01_SOLUTION_SPEC.md 4.4:
   exposure = P(revision) x unspent money,  among projects still SAVABLE.
Actionability (would PM attention unblock it?) is NOT computable -- RevisedDateReason
is 0% populated -- so the officer applies that filter to our 50.
"""
import argparse, json, os, sqlite3
import numpy as np, pandas as pd, joblib
from common import PANEL, MODELS, REPORTS, DB
import features as F
from train import sector_dummies

TARGET_PRECISION = 0.80
MAX_PER_SECTOR = 15          # stop one sector monopolising the PM's agenda


def load(target):
    b = joblib.load(os.path.join(MODELS, f"{target}.joblib"))
    live = {n: F.REGISTRY[n]["reads"] for n in F.CORE}
    if b["manifest"] != live:                       # stale feature definitions
        raise SystemExit("feature manifest mismatch — retrain before scoring")
    return b


def score(month=None, target="schedule", top=50):
    df = pd.read_parquet(PANEL)
    for c in ["t", "sanction_date", "original_end_date", "revised_date"]:
        df[c] = pd.to_datetime(df[c]).dt.date
    b = load(target)
    X, meta = F.build_matrix(df, require_label=False)
    X, _ = sector_dummies(X, meta, cats=b["sector_cols"])
    X = X.reindex(columns=b["features"], fill_value=np.nan).astype(float)

    p = b["model"].predict_proba(X)[:, 1]
    d = meta.copy()
    d["p"] = p
    d["cost"] = X["cost"].to_numpy()
    d["expenditure"] = X["expenditure"].to_numpy()
    d["physical_progress"] = X["physical_progress"].to_numpy()
    d["mons_to_due"] = X["mons_to_due"].to_numpy()
    d["cur_slip"] = X["cur_slip"].to_numpy()
    d["nobs"] = X["nobs"].to_numpy()
    d["pp_delta_3m"] = X["pp_delta_3m"].to_numpy()
    d["unspent"] = (d.cost - d.expenditure).clip(lower=0)
    d["exposure"] = d.p * d.unspent

    # IMPLAUSIBILITY: can the remaining work fit in the remaining time at the observed pace?
    # Without this, the shortlist fills with 99%-built projects that merely have unpaid
    # milestones -- high exposure, low escalation value. See 01_SOLUTION_SPEC.md 4.4.
    d["work_left"] = (100 - d.physical_progress).clip(lower=0)
    d["req_pace"] = d.work_left / d.mons_to_due.clip(lower=0.5)     # %/month needed
    d["obs_pace"] = (d.pp_delta_3m / 3).clip(lower=0)               # %/month recent
    d["shortfall"] = (d.req_pace - d.obs_pace).clip(lower=0)
    # ponytail: saturating discount, half-weight at 5%/month shortfall. Tune HALF if the
    # shortlist skews to hopeless mega-projects over savable mid-size ones.
    HALF = 5.0
    d["urgency"] = d.exposure * (d.shortfall / (d.shortfall + HALF))

    # thresholds from TRAIN ONLY, never tuned on the scoring month
    tr = d[d.month < b["split"]]
    ytr = tr[f"y_{target}"].to_numpy()
    hi = _threshold_for_precision(tr.p.to_numpy(), ytr, TARGET_PRECISION)
    lo = float(np.quantile(tr.p, 0.60))

    # ABSTAIN is about EVIDENCE, not just probability
    thin = (d.nobs < 3) | d.mons_to_due.isna()
    d["band"] = np.where(thin, "ABSTAIN",
                np.where(d.p >= hi, "FLAG",
                np.where(d.p >= lo, "WATCH", "CALM")))
    d["savable"] = (d.mons_to_due > 0) & (d.mons_to_due <= 12) & (d.cur_slip.fillna(0) < 1095)

    month = month or d.month.max()
    cur = d[d.month == month].copy()
    pool = cur[(cur.band.isin(["FLAG", "WATCH"])) & cur.savable]
    short = _cap_by_sector(pool.sort_values("urgency", ascending=False), MAX_PER_SECTOR, top)

    con = sqlite3.connect(DB)
    keep = ["pid", "month", "name", "sector", "ministry", "agency", "state", "p", "cost",
            "expenditure", "unspent", "exposure", "urgency", "physical_progress",
            "mons_to_due", "req_pace", "obs_pace", "shortfall", "band", "savable"]
    out = cur[keep].copy(); out["model_version"] = target; out["rank"] = np.nan
    out.loc[short.index, "rank"] = range(1, len(short) + 1)
    out.to_sql("scores", con, if_exists="replace", index=False)
    con.commit(); con.close()

    summ = {"month": month, "target": target, "pool": int(len(cur)),
            "bands": cur.band.value_counts().to_dict(),
            "savable": int(cur.savable.sum()), "shortlist": int(len(short)),
            "thresholds": {"flag": float(hi), "watch": float(lo)},
            "shortlist_exposure_cr": float(short.exposure.sum()),
            "shortlist_unspent_cr": float(short.unspent.sum())}
    if cur[f"y_{target}"].notna().any():
        summ["shortlist_precision"] = float(short[f"y_{target}"].mean())
        summ["top50_by_risk_precision"] = float(
            cur.nlargest(top, "p")[f"y_{target}"].mean())
    json.dump(summ, open(os.path.join(REPORTS, f"shortlist_{target}.json"), "w"), indent=1)
    return short, summ


def _threshold_for_precision(p, y, target):
    order = np.argsort(-p)
    ys = y[order]
    cum = np.cumsum(ys) / np.arange(1, len(ys) + 1)
    ok = np.where(cum >= target)[0]
    return float(p[order][ok[-1]]) if len(ok) else float(np.quantile(p, 0.9))


def _cap_by_sector(d, cap, top):
    out, seen = [], {}
    for i, r in d.iterrows():
        c = seen.get(r.sector, 0)
        if c >= cap:
            continue
        seen[r.sector] = c + 1
        out.append(i)
        if len(out) >= top:
            break
    return d.loc[out]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--month", default=None)
    ap.add_argument("--target", default="schedule")
    ap.add_argument("--top", type=int, default=50)
    a = ap.parse_args()
    short, s = score(a.month, a.target, a.top)
    print(f"\nESCALATION SHORTLIST — {s['month']}  ({s['target']})")
    print(f"  pool {s['pool']} projects | bands {s['bands']} | savable {s['savable']}")
    print(f"  thresholds flag>={s['thresholds']['flag']:.3f} watch>={s['thresholds']['watch']:.3f}")
    print(f"  shortlist {s['shortlist']} projects, ₹{s['shortlist_exposure_cr']:,.0f} cr exposed")
    if "shortlist_precision" in s:
        print(f"  precision: triage {s['shortlist_precision']:.2f} | pure-risk top{a.top} {s['top50_by_risk_precision']:.2f}")
    print()
    print(f"{'#':>3} {'p':>5} {'unspent':>9} {'built':>6} {'due':>6} {'need':>8} {'doing':>7}  project")
    for i, (_, r) in enumerate(short.iterrows(), 1):
        print(f"{i:3d} {r.p:5.2f} {r.unspent:9,.0f} {r.physical_progress:5.0f}% "
              f"{r.mons_to_due:5.1f}m {r.req_pace:6.1f}%/m {r.obs_pace:5.1f}%/m  {str(r['name'])[:40]}")
