# -*- coding: utf-8 -*-
"""Comprehensive fetch of every MoSPI project-monitoring report we can reach.

Supersedes download_flash_reports.py, which was too narrow in two ways:
  * it started at 2006, but the flash archive demonstrably goes back to at
    least 2001 (FR_june_2001.pdf resolves)
  * it only fetched monthly flash reports, ignoring the quarterly PISR series
    and the separate monthly Review Report series

Three sources, merged into one tree:
  ipm.mospi.gov.in     legacy OCMS-era archive  (flash + quarterly)
  www.mospi.gov.in     publication_reports      (some flash)
  paimana-proj...      live successor portal    (flash + QPISR + review)

Existing files are skipped, so this is safe to re-run and safe to run after the
earlier downloader.

Note: the archive host is case-insensitive, so Oct-Dec_2015.pdf and
oct-dec_2015.pdf are the same file. Candidates are tried in order and the first
hit wins, which collapses those duplicates naturally.
"""
import csv
import os
import re
import time
import urllib3
import requests
from urllib.parse import urljoin, unquote
from concurrent.futures import ThreadPoolExecutor, as_completed

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) research/1.0"}

ROOT = r"C:\Users\LENOVO\Downloads\SIH2026\PAIMANA"
FLASH = os.path.join(ROOT, "files")
QUART = os.path.join(ROOT, "files", "quarterly")
REVIEW = os.path.join(ROOT, "files", "review")
for d in (FLASH, QUART, REVIEW):
    os.makedirs(d, exist_ok=True)

MONTHS = ["january", "february", "march", "april", "may", "june",
          "july", "august", "september", "october", "november", "december"]
Y0, Y1 = 1995, 2027
IPM = "https://ipm.mospi.gov.in"
UAT = "https://www.uatipm.mospi.gov.in"
PUB = "https://www.mospi.gov.in/sites/default/files/publication_reports"
PAI = "https://paimana-proj.mospi.gov.in"


def fy(y, m):
    """Financial year folder: April-March."""
    return f"{y}-{str(y + 1)[2:]}" if m >= 4 else f"{y - 1}-{str(y)[2:]}"


def mon_tokens(m):
    full = MONTHS[m - 1]
    ab3 = full[:3]
    out, seen = [], set()
    for t in (ab3, full, "sept" if m == 9 else None, ab3.capitalize(),
              full.capitalize(), ab3.upper(), full.upper()):
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out


def flash_urls(y, m):
    f = fy(y, m)
    u = []
    for host in (IPM, UAT):
        for tok in mon_tokens(m):
            u.append(f"{host}/Content/ArchiveReport/flash/{f}/FR_{tok}_{y}.pdf")
    for tok in mon_tokens(m):
        u.append(f"{PUB}/FlashReport_{tok}_{y}.pdf")
    mm = MONTHS[m - 1]
    for nm in (f"FlashReport_{mm.capitalize()}_{y}.pdf", f"FR{mm.capitalize()}{y}.pdf",
               f"FR_{mm.capitalize()}{y}.pdf", f"FR_{mm.upper()}_{y}.pdf",
               f"FlashReport{mm.capitalize()}{y}.pdf"):
        u.append(f"{PAI}/Content/PDF/{nm}")
    return u


def quarter_urls(y, q):
    """q: 1=Apr-Jun 2=Jul-Sep 3=Oct-Dec 4=Jan-Mar (Jan-Mar belongs to prior FY)."""
    label = ["Apr-Jun", "Jul-Sep", "Oct-Dec", "Jan-Mar"][q - 1]
    anchor_month = [6, 9, 12, 2][q - 1]
    f = fy(y, anchor_month)
    u = []
    for host in (IPM, UAT):
        for lab in (label, label.lower(), label.upper(), label.replace("-", "_")):
            u.append(f"{host}/Content/ArchiveReport/quarterly/{f}/{lab}_{y}.pdf")
    return u


def fetch(dest, urls):
    if os.path.exists(dest) and os.path.getsize(dest) > 50_000:
        return "cached", os.path.getsize(dest), ""
    for url in urls:
        try:
            r = requests.get(url, headers=H, verify=False, timeout=120, stream=True)
            if r.status_code != 200:
                r.close()
                continue
            buf, total = [], 0
            for ch in r.iter_content(65536):
                if not buf and ch[:4] != b"%PDF":
                    break
                buf.append(ch)
                total += len(ch)
            r.close()
            if not buf or total < 50_000:
                continue
            with open(dest, "wb") as fh:
                for ch in buf:
                    fh.write(ch)
            return "ok", total, url
        except Exception:
            continue
    return "missing", 0, ""


jobs = []
for y in range(Y0, Y1 + 1):
    for m in range(1, 13):
        jobs.append(("flash", y, m,
                     os.path.join(FLASH, f"FR_{y}_{m:02d}_{MONTHS[m-1]}.pdf"),
                     flash_urls(y, m)))
    for q in range(1, 5):
        lab = ["Apr-Jun", "Jul-Sep", "Oct-Dec", "Jan-Mar"][q - 1]
        jobs.append(("quarterly", y, q,
                     os.path.join(QUART, f"Q_{y}_{q}_{lab}.pdf"),
                     quarter_urls(y, q)))

print(f"{len(jobs)} targets  ({Y1-Y0+1} years x 12 months + 4 quarters)", flush=True)

rows, done, t0 = [], 0, time.time()
with ThreadPoolExecutor(max_workers=10) as ex:
    futs = {ex.submit(fetch, d, u): (k, y, n, d) for k, y, n, d, u in jobs}
    for fut in as_completed(futs):
        k, y, n, d = futs[fut]
        status, nbytes, url = fut.result()
        rows.append(dict(kind=k, year=y, num=n, status=status, bytes=nbytes,
                         file=os.path.basename(d), url=url))
        done += 1
        if done % 40 == 0:
            got = sum(1 for r in rows if r["status"] in ("ok", "cached"))
            print(f"  {done}/{len(jobs)} | {got} files | "
                  f"{sum(r['bytes'] for r in rows)/1048576:.0f} MB | "
                  f"{time.time()-t0:.0f}s", flush=True)

# ---- PAIMANA portal listing (flash + QPISR + review) ----
print("\nscraping PAIMANA portal listing...", flush=True)
links = {}
for page in (f"{PAI}/", f"{PAI}/WhatsNewViewMore/ViewMore"):
    try:
        r = requests.get(page, headers=H, verify=False, timeout=45)
        for h in re.findall(r'href=[\'"]([^\'"]+)', r.text):
            if "ViewPdf" not in h and ".pdf" not in h.lower():
                continue
            full = urljoin(page, h)
            name = unquote(full.split("path=")[-1]) if "path=" in full else unquote(
                full.split("/")[-1])
            links[name] = f"{PAI}/Content/PDF/{name}"
    except Exception as e:
        print("  scrape err", type(e).__name__)

for name, url in links.items():
    n = name.lower()
    if "qpisr" in n:
        dest = os.path.join(QUART, name)
    elif "review" in n:
        dest = os.path.join(REVIEW, name)
    else:
        ym = re.search(r"(20\d{2})", n)
        mo = next((i for i, mm in enumerate(MONTHS, 1) if mm in n), None)
        dest = (os.path.join(FLASH, f"FR_{ym.group(1)}_{mo:02d}_{MONTHS[mo-1]}.pdf")
                if (ym and mo) else os.path.join(FLASH, "UNDATED_" + name))
    status, nbytes, u = fetch(dest, [url])
    rows.append(dict(kind="paimana", year=0, num=0, status=status, bytes=nbytes,
                     file=os.path.basename(dest), url=u or url))
    print(f"  {status:<8} {nbytes/1048576:6.1f}MB  {os.path.basename(dest)}", flush=True)

man = os.path.join(ROOT, "manifest_all.csv")
with open(man, "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=["kind", "year", "num", "status", "bytes", "file", "url"])
    w.writeheader()
    w.writerows(sorted(rows, key=lambda r: (r["kind"], r["year"], r["num"])))

ok = [r for r in rows if r["status"] in ("ok", "cached")]
print(f"\n{'='*70}\nTOTAL {len(ok)} files, {sum(r['bytes'] for r in ok)/1048576:.0f} MB")
for k in ("flash", "quarterly", "paimana"):
    kk = [r for r in ok if r["kind"] == k]
    print(f"  {k:<11} {len(kk)}")

fl = sorted({r["year"] for r in ok if r["kind"] == "flash"})
if fl:
    print(f"\nflash year span: {fl[0]} .. {fl[-1]}")
    for y in fl:
        n = sum(1 for r in ok if r["kind"] == "flash" and r["year"] == y)
        print(f"  {y}  {'#'*n}{'.'*(12-n)}  {n}/12")
print(f"\nmanifest -> {man}")
