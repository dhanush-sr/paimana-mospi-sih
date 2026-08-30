"""Shared parsers, paths, provenance. Everything downstream depends on these being right."""
import hashlib, json, os
from datetime import datetime, date

ROOT = os.path.dirname(os.path.abspath(__file__))
RAW  = os.path.join(ROOT, "data", "raw")
STATES = os.path.join(ROOT, "data", "states")
DB   = os.path.join(ROOT, "data", "paimana.db")
PANEL= os.path.join(ROOT, "data", "panel.parquet")
MODELS = os.path.join(ROOT, "models")
REPORTS= os.path.join(ROOT, "reports")
LOG  = os.path.join(ROOT, "data", "harvest_log.jsonl")
BASE = "https://paimana-proj.mospi.gov.in"

for _d in (RAW, STATES, MODELS, REPORTS):
    os.makedirs(_d, exist_ok=True)


def parse_dmy(s):
    """dd/mm/yyyy -> date. Empty/garbage -> None. NEVER today(), NEVER epoch."""
    if s is None:
        return None
    s = str(s).strip()
    if not s:
        return None
    try:
        return datetime.strptime(s, "%d/%m/%Y").date()
    except ValueError:
        return None


def parse_num(x):
    """'1,234.5' -> 1234.5. Empty/None -> None. NEVER 0.0 (a missing cost is not free)."""
    if x is None:
        return None
    s = str(x).replace(",", "").strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def snapshot_month(path):
    """data/raw/2026-07.json -> '2026-07'"""
    return os.path.basename(path)[:-5]


def month_to_date(m):
    y, mo = m.split("-")
    return date(int(y), int(mo), 1)


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def log_request(**kw):
    kw.setdefault("ts", datetime.utcnow().isoformat() + "Z")
    with open(LOG, "a") as f:
        f.write(json.dumps(kw) + "\n")


def demo():
    assert parse_dmy("13/07/2024") == date(2024, 7, 13)
    assert parse_dmy("") is None and parse_dmy(None) is None
    assert parse_dmy("2024-07-13") is None          # wrong format must not silently parse
    assert parse_num("1,234.5") == 1234.5
    assert parse_num("") is None and parse_num(None) is None
    assert parse_num("2587.04") == 2587.04
    assert snapshot_month("data/raw/2026-07.json") == "2026-07"
    assert month_to_date("2026-07") == date(2026, 7, 1)
    print("common.py OK")


if __name__ == "__main__":
    demo()
