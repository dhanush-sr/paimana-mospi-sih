# -*- coding: utf-8 -*-
"""Scrape PAIMANA's public dashboard API for PROJECT-LEVEL data.

This is the find that changes the project. /Home/GetTileData returns
ProjectsCountTabDetails: 1,775 project records with 26 fields each, as clean
JSON. GetFreezeDates reports monthly snapshots from 2025-07 to 2026-07, so the
same projects can be pulled 13 times and joined on ProjectId into a real panel -
no PDF table parsing involved.

Mechanics recovered from the page (it makes no XHR on load; everything is a form
POST):
    Month, Year, MonthYear, SectorId, PROJ_MINISTRY_ID, StateId, CostRange,
    __RequestVerificationToken  <- anti-CSRF, lifted from #myForm

Two things worth knowing about the payload:
  * the top-level scalars (ProjectCount, Cost_Overrun, ...) are all zero
    placeholders. The real data is in the nested lists.
  * the derived overrun fields (DELAYED_TIME, COST_OVERRUN, COR_PERC, TOR_PERC)
    are zero for every record, so overruns must be COMPUTED from
    RevisedCost - OriginalCost and RevisedDate - OriginalEndDate.
  * StateName is null on the unfiltered call, so state is recovered by
    re-querying per StateId and tagging the returned ProjectIds.
"""
import json
import os
import re
import time
import urllib3
import requests

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ROOT = r"C:\Users\LENOVO\Downloads\SIH2026\PAIMANA"
OUT = os.path.join(ROOT, "dashboard")
os.makedirs(OUT, exist_ok=True)

B = "https://paimana-proj.mospi.gov.in"
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) research/1.0",
     "X-Requested-With": "XMLHttpRequest",
     "Referer": f"{B}/Home/PublicDashboardNew"}

s = requests.Session()
s.verify = False
s.headers.update(H)


def new_token():
    page = s.get(f"{B}/Home/PublicDashboardNew", timeout=90).text
    m = re.search(r'name="__RequestVerificationToken"[^>]*value="([^"]+)"', page)
    return m.group(1) if m else ""


TOKEN = new_token()
print("csrf token:", "OK" if TOKEN else "MISSING")

freeze = s.get(f"{B}/Home/GetFreezeDates", timeout=60).json()
sectors = s.get(f"{B}/Home/GetSectorList", timeout=60).json()
states = s.get(f"{B}/Home/GetStateList", timeout=60).json()
ministries = s.get(f"{B}/Home/GetMinistryList", params={"sectorId": ""}, timeout=60).json()
json.dump({"freeze": freeze, "sectors": sectors, "states": states, "ministries": ministries},
          open(os.path.join(OUT, "dimensions.json"), "w", encoding="utf-8"), indent=1)
print(f"freeze window {freeze.get('firstFreeze')} .. {freeze.get('lastFreeze')} | "
      f"{len(sectors)} sectors, {len(states)} states, {len(ministries)} ministries")


def month_range(first, last):
    fy, fm = map(int, first.split("-"))
    ly, lm = map(int, last.split("-"))
    out, y, m = [], fy, fm
    while (y, m) <= (ly, lm):
        out.append(f"{y}-{m:02d}")
        m = 1 if m == 12 else m + 1
        y = y + 1 if m == 1 else y
    return out


MONTHS = month_range(freeze.get("firstFreeze", "2025-07"), freeze.get("lastFreeze", "2026-07"))
print(f"{len(MONTHS)} snapshots: {MONTHS}")


def tiles(my, state="", sector="", ministry=""):
    global TOKEN
    y, m = my.split("-")
    payload = {"Month": m, "Year": y, "MonthYear": my,
               "SectorId": sector, "PROJ_MINISTRY_ID": ministry,
               "StateId": state, "CostRange": "",
               "__RequestVerificationToken": TOKEN}
    for attempt in range(3):
        try:
            r = s.post(f"{B}/Home/GetTileData", data=payload, timeout=240)
            if r.status_code == 200 and r.text.strip()[:1] == "{":
                j = r.json()
                if j.get("success"):
                    return j.get("data") or {}
            if r.status_code in (400, 403):        # token may have rotated
                TOKEN = new_token()
                payload["__RequestVerificationToken"] = TOKEN
        except Exception:
            pass
        time.sleep(2)
    return {}


# ---------- 1. project panel across every snapshot ----------
panel, t0 = [], time.time()
for my in MONTHS:
    data = tiles(my)
    recs = data.get("ProjectsCountTabDetails") or []
    totals = (data.get("totalProjectsTabData") or [{}])[0]
    for r in recs:
        r = dict(r)
        r["freeze_month"] = my
        panel.append(r)
    print(f"  {my}: {len(recs):>5} projects | "
          f"total={totals.get('TotalProject')} cost={totals.get('TotalCost')} "
          f"exp={totals.get('CummulativeExpenditure')} | {time.time()-t0:.0f}s", flush=True)
    time.sleep(0.4)

p = os.path.join(OUT, "project_panel.json")
json.dump(panel, open(p, "w", encoding="utf-8"), indent=1)
print(f"\npanel rows: {len(panel):,} -> {p}")

# ---------- 2. state tagging (StateName is null unfiltered) ----------
latest = MONTHS[-1]
state_map = {}
for st in states:
    data = tiles(latest, state=st["Value"])
    for r in data.get("ProjectsCountTabDetails") or []:
        state_map.setdefault(r["ProjectId"], []).append(st["Text"])
    time.sleep(0.25)
json.dump(state_map, open(os.path.join(OUT, "project_states.json"), "w", encoding="utf-8"),
          indent=1)
print(f"state tags resolved for {len(state_map):,} projects "
      f"(multi-state: {sum(1 for v in state_map.values() if len(v) > 1)})")

# ---------- 3. panel shape ----------
ids = {r["ProjectId"] for r in panel}
seen = {}
for r in panel:
    seen.setdefault(r["ProjectId"], set()).add(r["freeze_month"])
depth = {}
for v in seen.values():
    depth[len(v)] = depth.get(len(v), 0) + 1
print(f"\nunique projects: {len(ids):,}")
print("observations per project:")
for k in sorted(depth):
    print(f"  seen in {k:>2} snapshots: {depth[k]:,}")
print(f"\nwrote {OUT}")
