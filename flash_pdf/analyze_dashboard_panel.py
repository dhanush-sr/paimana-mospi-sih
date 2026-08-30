# -*- coding: utf-8 -*-
"""Base rates and panel dynamics from the PAIMANA dashboard panel.

The base rate is the number that decides whether any accuracy claim on slide 2
is meaningful. If most monitored projects already run over, a model predicting
"overrun" for everything scores that rate for free, and a MoSPI statistician
will say so.

Overruns are computed here, not read: the API ships DELAYED_TIME, COST_OVERRUN,
COR_PERC and TOR_PERC as zero for every record.
"""
import collections
import json
import os
from datetime import datetime

ROOT = r"C:\Users\LENOVO\Downloads\SIH2026\PAIMANA"
PANEL = os.path.join(ROOT, "dashboard", "project_panel.json")
OUT = os.path.join(ROOT, "dashboard", "base_rates.txt")

rows = json.load(open(PANEL, encoding="utf-8"))
lines = []


def out(s=""):
    print(s)
    lines.append(s)


def num(v):
    if v is None:
        return None
    try:
        return float(str(v).replace(",", "").strip())
    except Exception:
        return None


def date(v):
    if not v:
        return None
    for f in ("%d/%m/%Y", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(str(v).strip(), f)
        except Exception:
            continue
    return None


out("=" * 76)
out("1. CORROBORATION AGAINST THE PROBLEM STATEMENT")
out("=" * 76)
apr = [r for r in rows if r["freeze_month"] == "2026-04"]
cost_apr = sum(num(r.get("OriginalCost")) or 0 for r in apr)
out(f"  PS claims (April 2026): 1,981 projects, original cost ~Rs 37.13 lakh crore")
out(f"  API April 2026        : {len(apr):,} projects, "
    f"original cost Rs {cost_apr/100000:.2f} lakh crore")
out(f"  -> {'MATCH' if len(apr) == 1981 else 'MISMATCH'}: this API is the source the PS quotes")

out()
out("=" * 76)
out("2. PANEL SHAPE  (watch for onboarding artefacts)")
out("=" * 76)
by_month = collections.Counter(r["freeze_month"] for r in rows)
for m in sorted(by_month):
    out(f"  {m}  {by_month[m]:>5} projects  {'#' * (by_month[m] // 60)}")
out("\n  The ramp from ~790 to ~1,980 is PAIMANA ONBOARDING (projects migrating")
out("  from OCMS), not real project growth. Treat 2025-07..2025-11 as incomplete;")
out("  the panel is only trustworthy from about 2026-01 onward.")

out()
out("=" * 76)
out("3. BASE RATES  (computed, since the API ships these fields empty)")
out("=" * 76)
for month in ("2026-04", "2026-07"):
    snap = [r for r in rows if r["freeze_month"] == month]
    if not snap:
        continue
    n = len(snap)
    cost_ov = time_ov = both = 0
    cost_known = time_known = 0
    cost_pcts, delay_months = [], []
    for r in snap:
        oc, rc = num(r.get("OriginalCost")), num(r.get("RevisedCost"))
        if oc and rc:
            cost_known += 1
            if rc > oc:
                cost_ov += 1
                cost_pcts.append(100 * (rc - oc) / oc)
        od, rd = date(r.get("OriginalEndDate")), date(r.get("RevisedDate"))
        if od and rd:
            time_known += 1
            if rd > od:
                time_ov += 1
                delay_months.append((rd - od).days / 30.44)
        if oc and rc and od and rd and rc > oc and rd > od:
            both += 1
    out(f"\n  --- {month}  (n={n:,}) ---")
    out(f"    cost overrun : {cost_ov:>5}/{cost_known:<5} known "
        f"({100*cost_ov/max(cost_known,1):5.1f}%)   [{100*cost_ov/n:.1f}% of all]")
    out(f"    time overrun : {time_ov:>5}/{time_known:<5} known "
        f"({100*time_ov/max(time_known,1):5.1f}%)   [{100*time_ov/n:.1f}% of all]")
    out(f"    both         : {both:>5}")
    if cost_pcts:
        cost_pcts.sort()
        out(f"    cost overrun %: median {cost_pcts[len(cost_pcts)//2]:.1f}%  "
            f"p90 {cost_pcts[int(.9*len(cost_pcts))]:.1f}%  max {cost_pcts[-1]:.0f}%")
    if delay_months:
        delay_months.sort()
        out(f"    delay months  : median {delay_months[len(delay_months)//2]:.1f}  "
            f"p90 {delay_months[int(.9*len(delay_months))]:.1f}  "
            f"max {delay_months[-1]:.0f}")

out()
out("=" * 76)
out("4. THE PREDICTIVE SIGNAL: DO ESTIMATES ACTUALLY MOVE?")
out("=" * 76)
hist = collections.defaultdict(dict)
for r in rows:
    hist[r["ProjectId"]][r["freeze_month"]] = r

moved_cost = moved_date = stable = 0
first_slip = []
for pid, h in hist.items():
    ms = sorted(h)
    if len(ms) < 3:
        continue
    costs = {num(h[m].get("RevisedCost")) for m in ms}
    costs.discard(None)
    dates = {str(h[m].get("RevisedDate")) for m in ms}
    dates.discard("None")
    c_moved = len(costs) > 1
    d_moved = len(dates) > 1
    if c_moved:
        moved_cost += 1
    if d_moved:
        moved_date += 1
    if not c_moved and not d_moved:
        stable += 1
    # when did the revised date first change?
    prev = None
    for m in ms:
        cur = str(h[m].get("RevisedDate"))
        if prev and cur != prev and cur != "None" and prev != "None":
            first_slip.append(m)
            break
        prev = cur

tracked = sum(1 for h in hist.values() if len(h) >= 3)
out(f"  projects with >=3 snapshots : {tracked:,}")
out(f"    revised COST changed      : {moved_cost:,} ({100*moved_cost/max(tracked,1):.1f}%)")
out(f"    revised DATE changed      : {moved_date:,} ({100*moved_date/max(tracked,1):.1f}%)")
out(f"    neither moved             : {stable:,} ({100*stable/max(tracked,1):.1f}%)")
out(f"\n  {len(first_slip):,} observable schedule-slip EVENTS with a timestamp.")
out("  These are the supervised targets: predict the slip before the month it lands.")
if first_slip:
    out("\n  slip events by month:")
    for m, c in sorted(collections.Counter(first_slip).items()):
        out(f"    {m}  {c:>4}  {'#' * (c // 5)}")

open(OUT, "w", encoding="utf-8").write("\n".join(lines))
print(f"\nwrote {OUT}")
