"""Read-only API. Every response carries model_version + snapshot_month."""
import json, os, sqlite3
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from common import DB, REPORTS
import features as F

app = FastAPI(title="PAIMANA Foresight", version="1.0")


def clean(o):
    """NaN/Inf are not JSON. SQLite hands them back for any gap in the panel
    (e.g. a month with no expenditure recorded), which 500s the response."""
    import math
    if isinstance(o, float):
        return None if (math.isnan(o) or math.isinf(o)) else o
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    return o


def q(sql, params=()):
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)      # read-only, always
    try:
        return clean(pd.read_sql(sql, con, params=params).to_dict("records"))
    finally:
        con.close()


def envelope(data, month=None, model="schedule"):
    return {"data": clean(data), "model_version": model, "snapshot_month": month,
            "generated_at": pd.Timestamp.utcnow().isoformat()}


def _report(name):
    p = os.path.join(REPORTS, name)
    if not os.path.exists(p):
        raise HTTPException(404, f"{name} not generated yet")
    return json.load(open(p))


@app.get("/watchlist")
def watchlist(month: str = None, top: int = 50):
    month = month or q("SELECT MAX(month) m FROM scores")[0]["m"]
    rows = q("SELECT * FROM scores WHERE month=? AND rank IS NOT NULL "
             "ORDER BY rank LIMIT ?", (month, top))
    return envelope(rows, month)


@app.get("/project/{pid}")
def project(pid: int):
    rows = q("SELECT * FROM panel WHERE pid=? ORDER BY month", (pid,))
    if not rows:
        raise HTTPException(404, "unknown project")
    return envelope({"timeline": rows,
                     "scores": q("SELECT * FROM scores WHERE pid=?", (pid,)),
                     "integrity": q("SELECT * FROM integrity WHERE pid=?", (pid,))})


@app.get("/audit")
def audit(month: str = None):
    rep = _report("integrity.json")
    rows = q("SELECT * FROM integrity WHERE month=?", (month,)) if month else []
    return envelope({"summary": rep, "findings": rows}, month)


@app.get("/ablation")
def ablation():
    return envelope(_report("ablation.json"))


@app.get("/metrics")
def metrics(target: str = "schedule"):
    return envelope(_report(f"{target}_metrics.json"), model=target)


@app.get("/benchmark")
def benchmark(by: str = "sector", month: str = None):
    if by not in ("sector", "ministry", "agency", "state"):
        raise HTTPException(400, "by must be sector|ministry|agency|state")
    month = month or q("SELECT MAX(month) m FROM scores")[0]["m"]
    rows = q(f"SELECT {by} AS grp, COUNT(*) n, AVG(p) mean_risk, "
             f"SUM(unspent) unspent_cr, SUM(exposure) exposure_cr "
             f"FROM scores WHERE month=? GROUP BY {by} ORDER BY exposure_cr DESC", (month,))
    return envelope(rows, month)


@app.post("/lint")
def lint(manifest: dict):
    """Model validation as a service: does a submitted feature set read the future?

    MoSPI will receive many models claiming high accuracy. This says which are real.
    """
    bad = [n for n, reads in manifest.items() if "t+" in str(reads).replace(" ", "")]
    return {"pass": not bad, "leaking_features": bad,
            "checked": len(manifest),
            "note": "a feature may only read months <= t; labels read t+1..t+h"}


@app.get("/explain/{pid}")
def explain(pid: int, month: str = None):
    """PS outcome (f): why this project? Cached SHAP contributions."""
    month = month or q("SELECT MAX(month) m FROM scores")[0]["m"]
    rows = q("SELECT * FROM drivers WHERE pid=? AND month=? ORDER BY rank", (pid, month))
    if not rows:
        raise HTTPException(404, "no drivers cached — run explain.py")
    return envelope(rows, month)


@app.get("/brief/{pid}")
def brief(pid: int, month: str = None):
    """The escalation note IPMD would actually send. Everything needed to defend it."""
    month = month or q("SELECT MAX(month) m FROM scores")[0]["m"]
    sc = q("SELECT * FROM scores WHERE pid=? AND month=?", (pid, month))
    if not sc:
        raise HTTPException(404, "project not scored for that month")
    s = sc[0]
    drivers = q("SELECT * FROM drivers WHERE pid=? AND month=? ORDER BY rank LIMIT 5", (pid, month))
    timeline = q("SELECT * FROM panel WHERE pid=? ORDER BY month", (pid,))
    integrity = q("SELECT * FROM integrity WHERE pid=?", (pid,))
    src = timeline[-1]["src_sha256"] if timeline else None

    pp, mtd = s.get("physical_progress"), s.get("mons_to_due")
    req, obs = s.get("req_pace"), s.get("obs_pace")
    finding = None
    if pp is not None and mtd is not None and req is not None:
        finding = (f"{pp:.0f}% built with {mtd:.1f} months to the recorded deadline. "
                   f"Finishing requires {req:.1f}% per month; the observed rate over the "
                   f"last three months is {obs:.1f}% per month.")
    return envelope({
        "project": {k: s.get(k) for k in
                    ("pid","name","sector","ministry","agency","state","cost",
                     "expenditure","unspent","physical_progress","mons_to_due","rank","band","p")},
        "finding": finding,
        "drivers": drivers,
        "timeline": timeline,
        "integrity_flags": integrity,
        "limits": [
            "This is a forecast of an administrative revision, not a judgement about the project or its agency.",
            "We cannot say WHY the project is delayed: the reason fields are not populated in the public feed.",
            "Whether escalation would help depends on the nature of the blocker, which this system does not observe.",
        ],
        "provenance": {"snapshot_month": month, "model": "schedule",
                       "source_sha256": src, "months_held": len(timeline)},
    }, month)


@app.get("/changes")
def changes(month: str = None):
    """What moved since last month. A monitor that can't answer this is just a report."""
    months = [r["month"] for r in q("SELECT DISTINCT month FROM panel ORDER BY month")]
    month = month or months[-1]
    i = months.index(month)
    if i == 0:
        return envelope({"entered": [], "left": [], "worsened": [], "deadline_moved": []}, month)
    prev = months[i - 1]
    cur = q("SELECT pid,name,sector,state,shortfall,mons_to_due,physical_progress,rank "
            "FROM scores WHERE month=?", (month,))
    curmap = {r["pid"]: r for r in cur}
    short_now = {r["pid"] for r in cur if r["rank"] is not None}
    pn = {r["pid"]: r for r in q("SELECT * FROM panel WHERE month=?", (prev,))}
    pc = {r["pid"]: r for r in q("SELECT * FROM panel WHERE month=?", (month,))}
    moved = [{"pid": p, "name": pc[p]["name"], "from": pn[p]["revised_date"],
              "to": pc[p]["revised_date"]}
             for p in set(pn) & set(pc)
             if pn[p]["revised_date"] and pc[p]["revised_date"]
             and pn[p]["revised_date"] != pc[p]["revised_date"]]
    return envelope({
        "prev_month": prev,
        "new_projects": [{"pid": p, "name": pc[p]["name"]} for p in set(pc) - set(pn)][:40],
        "dropped_projects": [{"pid": p, "name": pn[p]["name"]} for p in set(pn) - set(pc)][:40],
        "deadline_moved": sorted(moved, key=lambda x: x["name"])[:60],
        "shortlist_size": len(short_now),
    }, month)


@app.get("/search")
def search(term: str = Query("", alias="q"), limit: int = 20):
    """Look up ANY of the 2,243 projects, not only our top 50."""
    if len(term) < 2:
        return envelope([])
    rows = q("SELECT DISTINCT pid, name, sector, state FROM panel "
             "WHERE name LIKE ? ORDER BY name LIMIT ?", (f"%{term}%", limit))
    return envelope(rows)


@app.get("/")
def root():
    return {"service": "PAIMANA Foresight",
            "endpoints": ["/watchlist", "/project/{pid}", "/explain/{pid}",
                          "/brief/{pid}", "/changes", "/search", "/audit",
                          "/ablation", "/metrics", "/benchmark", "/lint"]}
