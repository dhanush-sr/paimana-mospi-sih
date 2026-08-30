# -*- coding: utf-8 -*-
"""State-level metrics for the India map, computed from the harvested panel.

Overruns are computed from RevisedDate vs OriginalEndDate and RevisedCost vs
OriginalCost. The API's own DELAYED_TIME / COST_OVERRUN / COR_PERC / TOR_PERC
fields are returned 0% populated and are unusable.

Multi-state corridors: 9.2% of projects touch more than one state. A project is
counted in EVERY state it touches, so state counts deliberately sum to more than
the national total. That is the honest treatment for a map - collapsing a
Delhi-Meerut corridor into one state is exactly the distortion a map should fix -
and the overlap is reported explicitly so nobody double-counts national exposure.
"""
import collections
import io
import json
import os
import sys
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = r"C:\Users\LENOVO\Downloads\SIH2026"
DASH = os.path.join(ROOT, "PAIMANA", "dashboard")
OUT = os.path.join(ROOT, "geo", "state_metrics.json")

panel = json.load(open(os.path.join(DASH, "project_panel.json"), encoding="utf-8"))
pstates = json.load(open(os.path.join(DASH, "project_states.json"), encoding="utf-8"))


def num(v):
    try:
        return float(str(v).replace(",", "").strip())
    except Exception:
        return None


def dt(v):
    if not v:
        return None
    for f in ("%d/%m/%Y", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(str(v).strip(), f)
        except Exception:
            pass
    return None


month = max(r["freeze_month"] for r in panel)
snap = [r for r in panel if r["freeze_month"] == month]
print(f"snapshot {month}: {len(snap)} projects")

# previous month, to derive "newly slipped since last snapshot"
months = sorted({r["freeze_month"] for r in panel})
prev_month = months[months.index(month) - 1] if len(months) > 1 else None
prev = {r["ProjectId"]: r for r in panel if r["freeze_month"] == prev_month} if prev_month else {}

agg = collections.defaultdict(lambda: dict(
    projects=0, cost=0.0, expenditure=0.0, delayed=0, delayed_known=0,
    cost_over=0, cost_known=0, delay_months=[], newly_slipped=0, progress=[]))

untagged = 0
national_cost = 0.0
for r in snap:
    pid = str(r.get("ProjectId"))
    sts = pstates.get(pid) or []
    oc, rc = num(r.get("OriginalCost")), num(r.get("RevisedCost"))
    od, rd = dt(r.get("OriginalEndDate")), dt(r.get("RevisedDate"))
    exp = num(r.get("Expenditure"))
    pp = num(r.get("PhysicalProgress"))
    if oc:
        national_cost += oc
    if not sts:
        untagged += 1
        continue
    slipped_now = False
    p = prev.get(r.get("ProjectId"))
    if p is not None and str(p.get("RevisedDate")) != str(r.get("RevisedDate")) \
            and r.get("RevisedDate"):
        slipped_now = True
    for s in sts:
        a = agg[s]
        a["projects"] += 1
        if oc:
            a["cost"] += oc
        if exp:
            a["expenditure"] += exp
        if pp is not None:
            a["progress"].append(pp)
        if od and rd:
            a["delayed_known"] += 1
            if rd > od:
                a["delayed"] += 1
                a["delay_months"].append((rd - od).days / 30.44)
        if oc and rc:
            a["cost_known"] += 1
            if rc > oc:
                a["cost_over"] += 1
        if slipped_now:
            a["newly_slipped"] += 1

out = {}
for s, a in agg.items():
    dl = sorted(a["delay_months"])
    pr = sorted(a["progress"])
    out[s] = {
        "projects": a["projects"],
        "cost_cr": round(a["cost"], 2),
        "expenditure_cr": round(a["expenditure"], 2),
        "delayed": a["delayed"],
        "delayed_known": a["delayed_known"],
        "delayed_pct": round(100 * a["delayed"] / a["delayed_known"], 1) if a["delayed_known"] else None,
        "cost_over": a["cost_over"],
        "cost_known": a["cost_known"],
        "cost_over_pct": round(100 * a["cost_over"] / a["cost_known"], 1) if a["cost_known"] else None,
        "median_delay_months": round(dl[len(dl) // 2], 1) if dl else None,
        "median_progress": round(pr[len(pr) // 2], 1) if pr else None,
        "newly_slipped": a["newly_slipped"],
    }

sum_state_projects = sum(v["projects"] for v in out.values())
multi = sum(1 for v in pstates.values() if len(v) > 1)
meta = {
    "snapshot": month,
    "previous_snapshot": prev_month,
    "national_projects": len(snap),
    "national_cost_cr": round(national_cost, 2),
    "state_rows_sum": sum_state_projects,
    "overlap_note": ("State counts sum to %d against %d national projects because %d "
                     "projects (%.1f%%) are multi-state corridors counted in each state "
                     "they touch. Do not sum state columns to get a national total."
                     % (sum_state_projects, len(snap), multi, 100 * multi / max(len(pstates), 1))),
    "untagged_projects": untagged,
    "states_covered": len(out),
    "derivation": ("delayed = RevisedDate > OriginalEndDate; cost_over = RevisedCost > "
                   "OriginalCost. The API's DELAYED_TIME/COST_OVERRUN/COR_PERC/TOR_PERC "
                   "fields are 0% populated and are not used."),
}

json.dump({"meta": meta, "states": out}, open(OUT, "w", encoding="utf-8"), indent=1)
print(json.dumps(meta, indent=1))
print(f"\nwrote {OUT}")
top = sorted(out.items(), key=lambda kv: -kv[1]["projects"])[:8]
print("\ntop states by project count:")
for s, v in top:
    print(f"  {s:<28} {v['projects']:>4} projects  Rs {v['cost_cr']:>12,.0f} cr  "
          f"delayed {v['delayed_pct']}%")
