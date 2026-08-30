# -*- coding: utf-8 -*-
"""Verify the downloaded corpus before any analysis is run on it.

A file existing is not the same as a file being usable. Government portals
happily return 200 with an HTML error page, and scanned-era PDFs can carry no
text layer at all - either would silently produce empty results downstream and
look like a finding. This checks, per file:

  * real PDF, opens, page count
  * has an extractable text layer (scanned-only files are useless to us)
  * contains project codes (the anchor the extractor depends on)
  * content hash, to catch the same report saved under two names

Writes verification_report.txt and flags anything that should not be trusted.
"""
import collections
import hashlib
import os
import re
import sys

from pypdf import PdfReader

ROOT = r"C:\Users\LENOVO\Downloads\SIH2026\PAIMANA"
DIRS = [("flash", os.path.join(ROOT, "files")),
        ("quarterly", os.path.join(ROOT, "files", "quarterly")),
        ("review", os.path.join(ROOT, "files", "review"))]
OUT = os.path.join(ROOT, "verification_report.txt")

CODE = re.compile(r"\b[NA]\d{8}\b")
lines = []


def out(s=""):
    print(s)
    lines.append(s)


def check(path):
    rec = dict(file=os.path.basename(path), mb=os.path.getsize(path) / 1048576,
               pages=0, textpages=0, codes=0, sha="", problem="")
    try:
        with open(path, "rb") as fh:
            data = fh.read()
        rec["sha"] = hashlib.sha256(data).hexdigest()[:16]
        if data[:4] != b"%PDF":
            rec["problem"] = "NOT_A_PDF"
            return rec
        reader = PdfReader(path)
        rec["pages"] = len(reader.pages)
        # Sample rather than read every page of a 575-page file.
        idxs = list(range(0, rec["pages"], max(1, rec["pages"] // 12)))[:12]
        codes = set()
        for i in idxs:
            try:
                t = reader.pages[i].extract_text() or ""
            except Exception:
                continue
            if t.strip():
                rec["textpages"] += 1
            codes.update(CODE.findall(t))
        rec["codes"] = len(codes)
        if rec["textpages"] == 0:
            rec["problem"] = "NO_TEXT_LAYER"
        elif rec["codes"] == 0:
            rec["problem"] = "NO_PROJECT_CODES"
    except Exception as e:
        rec["problem"] = f"OPEN_FAIL:{type(e).__name__}"
    return rec


all_recs = []
for kind, d in DIRS:
    if not os.path.isdir(d):
        continue
    files = sorted(f for f in os.listdir(d) if f.lower().endswith(".pdf"))
    out("=" * 78)
    out(f"{kind.upper()}  ({len(files)} files)  {d}")
    out("=" * 78)
    recs = [check(os.path.join(d, f)) for f in files]
    for r in recs:
        r["kind"] = kind
    all_recs.extend(recs)

    good = [r for r in recs if not r["problem"]]
    bad = [r for r in recs if r["problem"]]
    out(f"  usable          : {len(good)}/{len(recs)}")
    out(f"  total size      : {sum(r['mb'] for r in recs):.0f} MB")
    if good:
        out(f"  pages           : {sum(r['pages'] for r in good):,} "
            f"(median {sorted(r['pages'] for r in good)[len(good)//2]})")
    if bad:
        out(f"  PROBLEMS ({len(bad)}):")
        for r in bad:
            out(f"    {r['problem']:<22} {r['file']}  ({r['mb']:.1f}MB, {r['pages']}p)")
    out()

# ---- duplicates ----
by_hash = collections.defaultdict(list)
for r in all_recs:
    if r["sha"]:
        by_hash[r["sha"]].append(r["file"])
dupes = {h: fs for h, fs in by_hash.items() if len(fs) > 1}
out("=" * 78)
out("DUPLICATE CONTENT (same file saved under different names)")
out("=" * 78)
if dupes:
    for h, fs in list(dupes.items())[:25]:
        out(f"  {h}  {' | '.join(sorted(fs))}")
    out(f"  -> {len(dupes)} duplicate groups")
else:
    out("  none")

# ---- flash coverage ----
out()
out("=" * 78)
out("FLASH COVERAGE BY YEAR")
out("=" * 78)
got = collections.defaultdict(set)
for r in all_recs:
    if r["kind"] != "flash" or r["problem"]:
        continue
    m = re.match(r"FR_(\d{4})_(\d{2})_", r["file"])
    if m:
        got[int(m.group(1))].add(int(m.group(2)))
if got:
    ys = sorted(got)
    total = 0
    for y in range(ys[0], ys[-1] + 1):
        ms = got.get(y, set())
        total += len(ms)
        bar = "".join("#" if i in ms else "." for i in range(1, 13))
        miss = [i for i in range(1, 13) if i not in ms]
        out(f"  {y}  {bar}  {len(ms):>2}/12" +
            (f"   missing: {','.join(map(str, miss))}" if miss and len(miss) < 12 else ""))
    out(f"\n  span {ys[0]}-{ys[-1]}  |  {total} monthly reports  |  "
        f"{100*total/((ys[-1]-ys[0]+1)*12):.0f}% of calendar months")

usable = [r for r in all_recs if not r["problem"]]
out()
out("=" * 78)
out(f"VERDICT: {len(usable)}/{len(all_recs)} files usable, "
    f"{sum(r['pages'] for r in usable):,} pages, "
    f"{sum(r['mb'] for r in usable):.0f} MB")
out("=" * 78)

open(OUT, "w", encoding="utf-8").write("\n".join(lines))
print(f"\nwrote {OUT}")
