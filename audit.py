"""Data Integrity Monitor. Findings visible ONLY with month-to-month history.

Counts are regression tests, not just outputs: if they stop reproducing, the harvest
or the parsers changed. See 00_FINDINGS.md 3.2/3.3.
"""
import json, os, sqlite3
import numpy as np, pandas as pd
from common import PANEL, REPORTS, DB

# Consecutive OBSERVATIONS, not consecutive calendar months: 42 projects drop out of a
# snapshot and return, and a reversal across that gap is still a reversal.
# Adjacent-month-only counts are 427 / 212 / 119 (the difference is 3 / 4 / 0).
EXPECT = {"expenditure_reversal": 430, "progress_reversal": 216, "date_pulled_earlier": 119}
BIG_COST_DELTA = 10_000.0     # crore
BREAK_FACTOR = 3.0            # month rate > 3x trailing-3-month mean


def run(strict=True):
    df = pd.read_parquet(PANEL)
    for c in ["t", "original_end_date", "revised_date"]:
        df[c] = pd.to_datetime(df[c])
    d = df.sort_values(["pid", "t"])
    g = d.groupby("pid")
    prev = {c: g[c].shift(1) for c in
            ["expenditure", "physical_progress", "revised_date", "revised_cost", "month"]}

    f = {}
    f["expenditure_reversal"] = (d.expenditure < prev["expenditure"] - 0.01)
    f["progress_reversal"] = (d.physical_progress < prev["physical_progress"] - 0.01)
    f["date_pulled_earlier"] = (d.revised_date < prev["revised_date"])
    cost_delta = d.revised_cost - prev["revised_cost"]
    f["implausible_cost_delta"] = cost_delta.abs() > BIG_COST_DELTA

    findings, counts = [], {}
    for k, mask in f.items():
        mask = mask.fillna(False)
        counts[k] = int(mask.sum())
        for _, r in d[mask].iterrows():
            findings.append({"check": k, "pid": int(r.pid), "month": r.month,
                             "name": r["name"], "sector": r.sector,
                             "delta": float(cost_delta.loc[r.name]) if k == "implausible_cost_delta" else None})

    # structural break in the monthly revision rate
    chg = ((d.revised_date != prev["revised_date"]) & d.revised_date.notna()
           & prev["revised_date"].notna())
    rate = chg.groupby(d.month).mean()
    breaks = []
    for i in range(3, len(rate)):
        trail = rate.iloc[i - 3:i].mean()
        if trail > 0 and rate.iloc[i] > BREAK_FACTOR * trail:
            breaks.append({"month": rate.index[i], "rate": float(rate.iloc[i]),
                           "trailing_mean": float(trail),
                           "factor": float(rate.iloc[i] / trail)})

    rep = {"counts": counts, "monthly_revision_rate": {k: float(v) for k, v in rate.items()},
           "structural_breaks": breaks,
           "worst_cost_delta_cr": float(cost_delta.min()),
           "n_findings": len(findings)}
    json.dump(rep, open(os.path.join(REPORTS, "integrity.json"), "w"), indent=1)
    con = sqlite3.connect(DB)
    pd.DataFrame(findings).to_sql("integrity", con, if_exists="replace", index=False)
    con.commit(); con.close()

    print("DATA INTEGRITY MONITOR")
    for k, v in counts.items():
        exp = EXPECT.get(k)
        tag = "" if exp is None else (f"  [expected {exp}] {'OK' if v == exp else 'DRIFT'}")
        print(f"  {k:24s} {v:5d}{tag}")
    print(f"  worst single-month cost delta: ₹{cost_delta.min():,.0f} cr")
    for b in breaks:
        print(f"  STRUCTURAL BREAK at {b['month']}: rate {b['rate']:.3f} vs trailing "
              f"{b['trailing_mean']:.3f}  ({b['factor']:.1f}x)")
    if strict:
        for k, exp in EXPECT.items():
            assert counts[k] == exp, f"{k}: expected {exp}, got {counts[k]} — harvest/parsers changed"
        assert any(b["month"] == "2026-03" for b in breaks), "2026-03 break not detected"
        print("  all regression assertions PASS")
    return rep


if __name__ == "__main__":
    run()
