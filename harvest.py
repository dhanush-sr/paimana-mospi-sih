"""Pull PAIMANA monthly snapshots. Idempotent, rate-limited, logged.

The PS's own dataset link (/ReportPage) returns {"html":""}. The project-level data
lives behind an undocumented POST that needs a session cookie + anti-forgery token.
"""
import argparse, json, os, re, sys, time
import requests
from common import RAW, STATES, BASE, log_request, sha256_bytes

THROTTLE = 2.5          # seconds between requests. Government host. Non-negotiable.
MONTHS = [(2025, m) for m in range(7, 13)] + [(2026, m) for m in range(1, 8)]
UA = "SIH2026-research/1.0 (academic; contact via SIH portal)"


def session():
    s = requests.Session()
    s.headers.update({"User-Agent": UA})
    r = s.get(f"{BASE}/Home/PublicDashboardNew", timeout=60)
    r.raise_for_status()
    m = re.search(r'name="__RequestVerificationToken"[^>]*value="([^"]+)"', r.text)
    if not m:
        sys.exit("could not find anti-forgery token — page layout changed?")
    return s, m.group(1)


def fetch(s, tok, year, month, state_id=""):
    params = {
        "__RequestVerificationToken": tok,
        "Month": str(month), "Year": str(year), "MonthYear": f"{year}-{month:02d}",
        "CostRange": "", "PROJ_MINISTRY_ID": "", "SectorId": "", "StateId": str(state_id),
    }
    r = s.post(f"{BASE}/Home/GetTileData", data=params,
               headers={"X-Requested-With": "XMLHttpRequest"}, timeout=120)
    log_request(url=f"{BASE}/Home/GetTileData",
                params={k: v for k, v in params.items() if k != "__RequestVerificationToken"},
                status=r.status_code, bytes=len(r.content), sha256=sha256_bytes(r.content))
    r.raise_for_status()
    return r.json()["data"]


def state_list(s):
    r = s.get(f"{BASE}/Home/GetStateList",
              headers={"X-Requested-With": "XMLHttpRequest"}, timeout=60)
    r.raise_for_status()
    return r.json()


def harvest_months(refresh=False):
    s, tok = session()
    got = 0
    for y, m in MONTHS:
        path = os.path.join(RAW, f"{y}-{m:02d}.json")
        if os.path.exists(path) and not refresh:
            continue
        d = fetch(s, tok, y, m)
        json.dump(d, open(path, "w"))
        n = len(d.get("ProjectsCountTabDetails") or [])
        print(f"  fetched {y}-{m:02d}: {n} rows")
        got += 1
        time.sleep(THROTTLE)
    print(f"{len(MONTHS)} snapshots present, {got} fetched")


def harvest_states():
    """StateName is null in the payload, but the server-side filter works.
    Tag each ProjectId with the StateId whose filtered response contains it."""
    s, tok = session()
    states = state_list(s)
    print(f"  {len(states)} states/UTs")
    done = 0
    for y, m in MONTHS:
        for st in states:
            path = os.path.join(STATES, f"{y}-{m:02d}_{st['Value']}.json")
            if os.path.exists(path):
                continue
            try:
                d = fetch(s, tok, y, m, state_id=st["Value"])
            except Exception as e:                      # token can expire on long runs
                print(f"    refresh session ({e})")
                s, tok = session()
                d = fetch(s, tok, y, m, state_id=st["Value"])
            pids = [r["ProjectId"] for r in (d.get("ProjectsCountTabDetails") or [])]
            json.dump({"month": f"{y}-{m:02d}", "state_id": st["Value"],
                       "state": st["Text"], "pids": pids}, open(path, "w"))
            done += 1
            if done % 40 == 0:
                print(f"    {done} state-months cached")
            time.sleep(THROTTLE)
    print(f"state backfill complete ({done} fetched this run)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="fetch any missing monthly snapshots")
    ap.add_argument("--states", action="store_true", help="backfill state membership (~20 min)")
    ap.add_argument("--refresh", action="store_true", help="re-fetch even if cached")
    a = ap.parse_args()
    if a.states:
        harvest_states()
    else:
        harvest_months(refresh=a.refresh)
