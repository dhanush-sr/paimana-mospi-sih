"""Snapshots -> project-month panel. Raw is immutable; this is derived and recomputable."""
import glob, json, os, sqlite3
import pandas as pd
from common import RAW, STATES, DB, PANEL, parse_dmy, parse_num, snapshot_month, month_to_date, sha256_bytes

# 0%-populated in every snapshot -> deliberately NOT carried. See 05_ARCHITECTURE.md §3.1
DROPPED = ["StateName", "AgencyId", "AgencyName", "RevisedCostReason", "CreationDate",
           "StartDate", "RevisedDateReason", "DELAYED_TIME", "COST_OVERRUN_PERC",
           "COST_OVERRUN", "COR_PERC", "TOR_PERC", "OnboardingDelay", "Remarks"]

EXPECT = {"rows": 18601, "projects": 2243, "months": 13, "2026-04": 1981}


def load_states():
    """{(pid, month): 'State Name'} from the state backfill, if present."""
    out, multi = {}, {}
    for fp in sorted(glob.glob(os.path.join(STATES, "*.json"))):
        d = json.load(open(fp))
        for pid in d["pids"]:
            k = (pid, d["month"])
            out.setdefault(k, d["state"])              # first match by StateId order
            multi.setdefault(k, []).append(d["state"])
    return out, multi


def build():
    states, multi = load_states()
    rows = []
    for fp in sorted(glob.glob(os.path.join(RAW, "*.json"))):
        m = snapshot_month(fp)
        blob = open(fp, "rb").read()
        sha = sha256_bytes(blob)
        for r in (json.loads(blob).get("ProjectsCountTabDetails") or []):
            pid = r["ProjectId"]
            rows.append(dict(
                pid=pid, month=m, t=month_to_date(m),
                name=r["ProjectName"], sector=r["SectorName"],
                ministry=r["LineMinistry"], agency=r.get("COMPANYNAME"),
                state=states.get((pid, m)),
                original_cost=parse_num(r.get("OriginalCost")),
                revised_cost=parse_num(r.get("RevisedCost")),
                expenditure=parse_num(r.get("Expenditure")),
                physical_progress=parse_num(r.get("PhysicalProgress")),
                sanction_date=parse_dmy(r.get("SanctionDate")),
                original_end_date=parse_dmy(r.get("OriginalEndDate")),
                revised_date=parse_dmy(r.get("RevisedDate")),
                src_sha256=sha,
            ))
    df = pd.DataFrame(rows).sort_values(["pid", "t"]).reset_index(drop=True)

    # These are ground truth (00_FINDINGS.md §1.3). A mismatch means a corrupt harvest.
    got = {"rows": len(df), "projects": df.pid.nunique(),
           "months": df.month.nunique(), "2026-04": int((df.month == "2026-04").sum())}
    for k, v in EXPECT.items():
        assert got[k] == v, f"panel assertion failed: {k} expected {v}, got {got[k]}. Re-harvest."
    print(f"  panel {got['rows']} rows / {got['projects']} projects / {got['months']} months")
    print(f"  2026-04 = {got['2026-04']} projects (matches the PS text and MoSPI's Flash Report)")

    n_state = df.state.notna().sum()
    print(f"  state tagged: {n_state}/{len(df)} ({n_state/len(df)*100:.1f}%)"
          + ("  [run harvest.py --states]" if n_state == 0 else ""))

    df.to_parquet(PANEL, index=False)
    con = sqlite3.connect(DB)
    d2 = df.copy()
    for c in ["t", "sanction_date", "original_end_date", "revised_date"]:
        d2[c] = d2[c].astype(str)
    d2.to_sql("panel", con, if_exists="replace", index=False)
    con.execute("CREATE INDEX IF NOT EXISTS ix_panel_pid ON panel(pid)")
    con.execute("CREATE INDEX IF NOT EXISTS ix_panel_month ON panel(month)")
    # multi-state side table for benchmarking
    ms = [dict(pid=p, month=mo, state=s) for (p, mo), lst in multi.items() for s in set(lst)]
    if ms:
        pd.DataFrame(ms).to_sql("project_states", con, if_exists="replace", index=False)
        print(f"  project_states side table: {len(ms)} rows")
    con.commit(); con.close()

    fill = (df.notna().mean() * 100).round(1)
    print("\n  fill rates:")
    for k, v in fill.items():
        if k not in ("pid", "month", "t", "src_sha256"):
            print(f"    {k:20s} {v:5.1f}%")
    return df


if __name__ == "__main__":
    build()
