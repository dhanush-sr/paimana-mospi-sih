# -*- coding: utf-8 -*-
"""Fill every month still missing from files/, using the wide variant net.

probe_gap_years.py found 2025 reports under seven different naming conventions
but only *printed* them - it had no download path, so the hits were discarded.
This repeats that search for every month actually absent from disk and writes
the files.

The variant net is deliberately much wider than download_all.py's: two-digit
years, no-separator forms, alternate prefixes, both financial-year folders, and
the PAIMANA content directory as well as the two archive hosts.
"""
import csv
import os
import re
import time
import urllib3
import requests
from concurrent.futures import ThreadPoolExecutor

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) research/1.0"}

ROOT = r"C:\Users\LENOVO\Downloads\SIH2026\PAIMANA"
FLASH = os.path.join(ROOT, "files")
MONTHS = ["january", "february", "march", "april", "may", "june",
          "july", "august", "september", "october", "november", "december"]
HOSTS = ["https://ipm.mospi.gov.in", "https://www.uatipm.mospi.gov.in"]
PAI = "https://paimana-proj.mospi.gov.in/Content/PDF"
PUB = "https://www.mospi.gov.in/sites/default/files/publication_reports"
Y0, Y1 = 2001, 2026


def fys(y, m):
    a = f"{y}-{str(y+1)[2:]}" if m >= 4 else f"{y-1}-{str(y)[2:]}"
    b = f"{y-1}-{str(y)[2:]}" if m >= 4 else f"{y}-{str(y+1)[2:]}"
    return [a, b]


def names(y, m):
    full = MONTHS[m - 1]
    ab = full[:3]
    yy = str(y)[2:]
    toks = {ab, full, ab.capitalize(), full.capitalize(), ab.upper(), full.upper()}
    if m == 9:
        toks |= {"sept", "Sept", "SEPT"}
    out = set()
    for t in toks:
        out |= {
            f"FR_{t}_{y}.pdf", f"FR_{t}{y}.pdf", f"FR{t}{y}.pdf",
            f"FR_{t}_{yy}.pdf", f"FR_{t}{yy}.pdf", f"FR-{t}-{y}.pdf",
            f"FlashReport_{t}_{y}.pdf", f"FlashReport{t}{y}.pdf",
            f"FlashReport_{t}{y}.pdf", f"Flash_{t}_{y}.pdf",
            f"{t}_{y}.pdf", f"FR_{y}_{t}.pdf",
        }
    return out


def urls(y, m):
    u = []
    for host in HOSTS:
        for f in fys(y, m):
            for n in names(y, m):
                u.append(f"{host}/Content/ArchiveReport/flash/{f}/{n}")
    for n in names(y, m):
        u.append(f"{PAI}/{n}")
        u.append(f"{PUB}/{n}")
    return u


def try_url(url):
    try:
        r = requests.get(url, headers=H, verify=False, timeout=45, stream=True)
        if r.status_code != 200:
            r.close()
            return None
        buf, total = [], 0
        for ch in r.iter_content(65536):
            if not buf and ch[:4] != b"%PDF":
                break
            buf.append(ch)
            total += len(ch)
        r.close()
        if not buf or total < 50_000:
            return None
        return url, b"".join(buf)
    except Exception:
        return None


missing = []
for y in range(Y0, Y1 + 1):
    for m in range(1, 13):
        dest = os.path.join(FLASH, f"FR_{y}_{m:02d}_{MONTHS[m-1]}.pdf")
        if not (os.path.exists(dest) and os.path.getsize(dest) > 50_000):
            missing.append((y, m, dest))

print(f"{len(missing)} months missing from disk; searching wide net", flush=True)

rows, t0 = [], time.time()
for i, (y, m, dest) in enumerate(missing, 1):
    cand = urls(y, m)
    found = None
    with ThreadPoolExecutor(max_workers=24) as ex:
        for res in ex.map(try_url, cand):
            if res:
                found = res
                break
    if found:
        url, data = found
        with open(dest, "wb") as fh:
            fh.write(data)
        rows.append(dict(year=y, month=m, status="ok", bytes=len(data),
                         file=os.path.basename(dest), url=url))
        print(f"  [{i}/{len(missing)}] GOT {y}-{m:02d}  {len(data)/1048576:5.1f}MB  "
              f"{url.rsplit('/',1)[-1]}", flush=True)
    else:
        rows.append(dict(year=y, month=m, status="missing", bytes=0, file="", url=""))
        if i % 10 == 0:
            print(f"  [{i}/{len(missing)}] ... {time.time()-t0:.0f}s", flush=True)

man = os.path.join(ROOT, "manifest_gapfill.csv")
with open(man, "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=["year", "month", "status", "bytes", "file", "url"])
    w.writeheader()
    w.writerows(rows)

got = [r for r in rows if r["status"] == "ok"]
print(f"\nrecovered {len(got)}/{len(missing)} missing months "
      f"({sum(r['bytes'] for r in got)/1048576:.0f} MB)")

on_disk = {}
for f in os.listdir(FLASH):
    mm = re.match(r"FR_(\d{4})_(\d{2})_", f)
    if mm and os.path.getsize(os.path.join(FLASH, f)) > 50_000:
        on_disk.setdefault(int(mm.group(1)), set()).add(int(mm.group(2)))
print("\nFLASH COVERAGE NOW:")
tot = 0
for y in range(Y0, Y1 + 1):
    ms = on_disk.get(y, set())
    tot += len(ms)
    print(f"  {y}  " + "".join("#" if i in ms else "." for i in range(1, 13)) +
          f"  {len(ms):>2}/12")
print(f"\n  {tot} monthly reports on disk")
print(f"manifest -> {man}")
