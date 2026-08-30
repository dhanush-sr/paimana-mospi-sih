# -*- coding: utf-8 -*-
"""Realised outcomes from 25 years of COMPLETED Central Sector projects.

Why this matters for PS 26103
-----------------------------
Clause (b) asks whether AI/ML gives "significant gains over conventional
statistical methods". The conventional method in infrastructure forecasting is
reference-class forecasting: ignore the project's own plan and predict from the
realised distribution of comparable finished projects.

That cannot be built from a 13-month panel, which almost never observes a project
finish. It can be built here. The Flash Reports publish a monthly
"Month wise List of Completed Projects" whose verified header is:

    Sl. No | Project Name | Original Cost (Rs. crore)
           | Original Date of commissioning | Cumulative Expenditure (Rs. crore)

Two corrections over the first attempt, both of which changed the numbers:

  1. That date is the ORIGINALLY PLANNED commissioning date, not the actual
     completion date. Naming it "completion_year" was wrong. Used correctly it is
     more valuable: report month minus planned date = REALISED TIME OVERRUN.

  2. A completed project is re-listed in later monthly reports, so the raw rows
     contain heavy duplication. Without de-duplication one project contributed
     six times to the "worst overrun" table and every distribution was weighted
     by how long a project lingered in the listings rather than by project.

Cost caveat, stated rather than buried: "Cumulative Expenditure" is spend booked
at the time of reporting, which is not necessarily the final settled cost. It can
legitimately fall below the approved cost. So cost figures here are
spend-against-approval, NOT audited final cost.
"""
import collections
import io
import json
import os
import re
import statistics
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = r"C:\Users\LENOVO\Downloads\SIH2026\PAIMANA"
SRC = os.path.join(ROOT, "extracted", "tables.jsonl")
OUT = os.path.join(ROOT, "extracted", "completion_outcomes.json")
TXT = os.path.join(ROOT, "extracted", "completion_outcomes.txt")

MONEY = re.compile(r"^\(?-?[\d,]+(?:\.\d+)?\)?$")
DATE = re.compile(r"^(\d{1,2})[/-](\d{4})$")

lines = []


def out(s=""):
    print(s)
    lines.append(s)


def money(s):
    s = str(s).strip().replace(",", "")
    if not s or not MONEY.match(s):
        return None
    neg = s.startswith("(")
    try:
        v = float(s.strip("()"))
    except ValueError:
        return None
    return -v if neg else v


def ym(s):
    m = DATE.match(str(s).strip())
    return (int(m.group(2)), int(m.group(1))) if m else None


def norm_name(s):
    s = re.sub(r"\([^)]*\)", " ", str(s).lower())
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())[:70]


raw_rows = []
skipped = collections.Counter()
with open(SRC, encoding="utf-8") as fh:
    for line in fh:
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("is_aggregate") or r.get("section_label") != "LIFECYCLE_COMPLETED":
            continue
        cells = [str(c).strip() for c in (r.get("raw") or []) if str(c).strip()]
        if len(cells) < 4:
            skipped["too_few_cells"] += 1
            continue
        name_i = max(range(len(cells)),
                     key=lambda i: len(re.sub(r"[^A-Za-z]", "", cells[i])))
        name = cells[name_i]
        if len(re.sub(r"[^A-Za-z]", "", name)) < 6:
            skipped["no_name"] += 1
            continue
        tail = cells[name_i + 1:]
        monies = [m for m in (money(c) for c in tail) if m is not None and m > 0]
        dates = [d for d in (ym(c) for c in tail) if d]
        if len(monies) < 2:
            skipped["needs_two_amounts"] += 1
            continue
        orig, spend = monies[0], monies[1]
        ratio = spend / orig
        if not (0.05 <= ratio <= 25):
            skipped["implausible_ratio"] += 1
            continue
        raw_rows.append({
            "key": norm_name(name) + "|%.2f" % orig,
            "project": name[:90],
            "report_year": r.get("year"), "report_month": r.get("month"),
            "planned_doc": dates[0] if dates else None,
            "orig_cost": orig, "spend": spend,
            "spend_vs_approved_pct": round(100 * (ratio - 1), 2),
            "code": r.get("project_code"),
        })

# ---- de-duplicate: keep the EARLIEST report of each completed project ----
best = {}
for r in raw_rows:
    k = r["key"]
    stamp = (r["report_year"] or 9999, r["report_month"] or 99)
    if k not in best or stamp < (best[k]["report_year"] or 9999,
                                 best[k]["report_month"] or 99):
        best[k] = r
rows = list(best.values())

out("=" * 74)
out("REALISED OUTCOMES  -  completed Central Sector projects, 2001-2026")
out("=" * 74)
seen = sum(skipped.values()) + len(raw_rows)
out(f"  completed-project rows in corpus : {seen:,}")
out(f"  parsed                           : {len(raw_rows):,}")
for k, v in skipped.most_common():
    out(f"    skipped, {k:<24}{v:>7,}")
out(f"  DISTINCT projects after de-dup   : {len(rows):,}")
out(f"    (a completed project is re-listed in later reports; without this the")
out(f"     distributions weight projects by how long they lingered in the tables)")

if not rows:
    out("\nnothing parsable - not written")
    sys.exit(0)

# ---- time overrun: report date vs ORIGINAL PLANNED commissioning date ----
delays = []
for r in rows:
    if not r["planned_doc"] or not r["report_year"]:
        continue
    py, pm = r["planned_doc"]
    d = (r["report_year"] - py) * 12 + ((r["report_month"] or 6) - pm)
    if -240 <= d <= 480:
        r["time_overrun_months"] = d
        delays.append(d)

out()
out("=" * 74)
out("REALISED TIME OVERRUN   (reported complete vs ORIGINAL planned date)")
out("=" * 74)
if delays:
    delays.sort()
    n = len(delays)
    late = sum(1 for d in delays if d > 0)
    out(f"  projects with both dates      : {n:,}")
    out(f"  finished LATE vs original plan: {late:,}  ({100*late/n:.1f}%)")
    out(f"  median slippage               : {statistics.median(delays):+.0f} months")
    out(f"  p25 {delays[n//4]:+.0f}   p50 {delays[n//2]:+.0f}   "
        f"p75 {delays[3*n//4]:+.0f}   p90 {delays[int(.9*n)]:+.0f}   "
        f"p99 {delays[int(.99*n)]:+.0f} months")
    out()
    out("  THIS is the reference class for schedule. A model predicting slip must")
    out("  beat simply quoting this distribution for a comparable project.")
else:
    out("  no rows carried both a planned date and a report date")

# ---- spend against approval ----
sv = sorted(r["spend_vs_approved_pct"] for r in rows)
n = len(sv)
over = sum(1 for v in sv if v > 0)
out()
out("=" * 74)
out("SPEND AGAINST APPROVED COST   (NOT audited final cost - see caveat)")
out("=" * 74)
out(f"  above approved cost : {over:,}  ({100*over/n:.1f}%)")
out(f"  median {statistics.median(sv):+.1f}%   mean {statistics.mean(sv):+.1f}%")
out(f"  p25 {sv[n//4]:+.1f}%   p75 {sv[3*n//4]:+.1f}%   p90 {sv[int(.9*n)]:+.1f}%   "
    f"p99 {sv[int(.99*n)]:+.1f}%")
out()
out("  Caveat: 'Cumulative Expenditure' is spend booked at reporting time, not a")
out("  final audited cost, and can legitimately sit below the approved figure.")
out("  Treat the schedule numbers above as the stronger result.")

out()
out("=" * 74)
out("BY ERA")
out("=" * 74)
by = collections.defaultdict(list)
for r in rows:
    if r.get("time_overrun_months") is not None and r["report_year"]:
        by[r["report_year"]].append(r["time_overrun_months"])
out("  year      n   median slip   % late")
for y in sorted(by):
    v = sorted(by[y])
    if len(v) < 15:
        continue
    out(f"  {y}  {len(v):>5}      {statistics.median(v):+6.0f} mo   "
        f"{100*sum(1 for x in v if x>0)/len(v):5.1f}%")

worst = sorted([r for r in rows if r.get("time_overrun_months") is not None],
               key=lambda r: -r["time_overrun_months"])[:8]
out()
out("  longest realised slippage (distinct projects):")
for r in worst:
    out(f"    {r['time_overrun_months']:>4} mo  Rs {r['orig_cost']:>9,.0f} cr  "
        f"{r['project'][:54]}")

json.dump({"summary": {
    "distinct_projects": len(rows), "raw_rows": len(raw_rows),
    "pct_late": round(100 * late / len(delays), 2) if delays else None,
    "median_slip_months": statistics.median(delays) if delays else None,
    "pct_above_approved": round(100 * over / n, 2),
    "median_spend_vs_approved_pct": statistics.median(sv),
    "skipped": dict(skipped),
    "caveat": ("Cumulative Expenditure is spend at reporting time, not audited "
               "final cost. Date column is the ORIGINAL PLANNED commissioning "
               "date, not actual completion."),
}, "rows": rows}, open(OUT, "w", encoding="utf-8"), indent=1)
open(TXT, "w", encoding="utf-8").write("\n".join(lines))
print(f"\nwrote {OUT}\nwrote {TXT}")
