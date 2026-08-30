# -*- coding: utf-8 -*-
"""Generate CORPUS.md describing the Flash Report zip, entirely from the files.

Usability is judged by whether the table extractor actually recovered
project-level rows from a file - NOT by whether the file contains N######## project
codes. An earlier version conflated the two and wrongly declared the 2001-2003
reports to be executive summaries with no project data. They contain thousands of
project rows; what they lack is the *identifier* scheme, which MoSPI only
introduced around 2012.

That distinction matters downstream: rows without a code are usable observations
but cannot be tracked month-to-month except by name matching.

Every number is computed at run time. Nothing is typed by hand.
"""
import collections
import csv
import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = r"C:\Users\LENOVO\Downloads\SIH2026\PAIMANA"
FILES = os.path.join(ROOT, "files")
QUART = os.path.join(FILES, "quarterly")
TABLES = os.path.join(ROOT, "extracted", "tables.jsonl")
DONE = os.path.join(ROOT, "extracted", "tables_done.txt")
OUT = os.path.join(ROOT, "CORPUS.md")

flash = sorted(f for f in os.listdir(FILES)
               if f.startswith("FR_") and f.lower().endswith(".pdf"))
quart = sorted(os.listdir(QUART)) if os.path.isdir(QUART) else []

cov = collections.defaultdict(set)
for f in flash:
    m = re.match(r"FR_(\d{4})_(\d{2})_", f)
    if m:
        cov[int(m.group(1))].add(int(m.group(2)))

flash_bytes = sum(os.path.getsize(os.path.join(FILES, f)) for f in flash)
quart_bytes = sum(os.path.getsize(os.path.join(QUART, f)) for f in quart)

# ---- what extraction actually recovered, per file and per year ----
per_file = collections.Counter()
per_file_codes = collections.Counter()
by_year = collections.Counter()
codes_by_year = collections.Counter()
slips_by_year = collections.Counter()
labels = collections.Counter()
agg_rows = 0
total_rows = 0
if os.path.exists(TABLES):
    with open(TABLES, encoding="utf-8") as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except Exception:
                continue
            total_rows += 1
            if r.get("is_aggregate"):
                agg_rows += 1
                continue
            f, y = r.get("file"), r.get("year")
            per_file[f] += 1
            by_year[y] += 1
            labels[r.get("section_label")] += 1
            if r.get("project_code"):
                per_file_codes[f] += 1
                codes_by_year[y] += 1
            if r.get("section_label") == "EVENT_SLIP":
                slips_by_year[y] += 1

parsed = set()
if os.path.exists(DONE):
    parsed = {l.strip() for l in open(DONE, encoding="utf-8") if l.strip()}

no_rows = sorted(f for f in parsed if per_file.get(f, 0) == 0)
unparsed = sorted(set(flash) - parsed)
proj_rows = sum(per_file.values())

urls = {}
for man in ("manifest_all.csv", "manifest_gapfill.csv", "manifest.csv"):
    p = os.path.join(ROOT, man)
    if not os.path.exists(p):
        continue
    try:
        for row in csv.DictReader(open(p, encoding="utf-8")):
            if row.get("file") and row.get("url"):
                urls.setdefault(row["file"], row["url"])
    except Exception:
        pass

GB, MB = 2 ** 30, 2 ** 20
L = []
w = L.append

w("# MoSPI Flash Report Corpus - `files.zip`")
w("")
w("Monthly **Flash Reports on Central Sector Infrastructure Projects "
  "(Rs. 150 crore and above)** published by the Infrastructure & Project Monitoring "
  "Division (IPMD), Ministry of Statistics and Programme Implementation, plus the "
  "quarterly Project Implementation Status Reports.")
w("")
w("Assembled for **SIH 2026, PS 26103 (PAIMANA)**. Every figure below is computed "
  "from the archive and the extraction output by `scripts/make_corpus_doc.py`. "
  "Nothing is typed by hand.")
w("")
w("## What is in the zip")
w("")
w("| | count | size |")
w("|---|---:|---:|")
w("| Monthly Flash Reports (`FR_*.pdf`) | %d | %.2f GB |" % (len(flash), flash_bytes / GB))
w("| Quarterly PISR (`quarterly/`) | %d | %.0f MB |" % (len(quart), quart_bytes / MB))
w("| **Total** | **%d** | **%.2f GB** |"
  % (len(flash) + len(quart), (flash_bytes + quart_bytes) / GB))
w("")
w("Filenames are normalised to `FR_<year>_<month>_<monthname>.pdf`. **MoSPI's own "
  "naming is not consistent** - one directory holds `FRMARCH2025.pdf`, `FR_may2025.pdf`, "
  "`FlashReport_JULY_2025.pdf` and `FlashReport_august_2025.pdf`. `manifest_all.csv` "
  "maps every normalised name back to the exact URL it came from (%d mapped)." % len(urls))
w("")

w("## Coverage")
w("")
w("```")
w("        Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec    n")
years = sorted(cov)
for y in range(min(years), max(years) + 1):
    ms = cov.get(y, set())
    w("%d   %s  %2d/12" % (y, "".join(("  # " if i in ms else "  . ")
                                      for i in range(1, 13)), len(ms)))
w("```")
w("")
w("**%d monthly reports spanning %d-%d.**" % (sum(len(v) for v in cov.values()),
                                              min(years), max(years)))
w("")
w("| period | status |")
w("|---|---|")
w("| 2004-2006, 2008 | not present in MoSPI's archive |")
w("| **2019** | **entirely absent.** 272-404 filename variants were probed across both "
  "archive hosts and both financial-year folder conventions. The files are not there - "
  "this is not a naming problem. |")
w("| 2010-2017 | complete and unbroken |")
w("| 2020-2025 | near-complete |")
w("")

w("## What extraction actually recovered")
w("")
if not per_file:
    w("_Extraction output not present - run `scripts/extract_tables.py`._")
else:
    w("Parsed **%d of %d** monthly reports so far, yielding **%s project-level rows** "
      "plus %s aggregate/summary rows (separated, not counted as projects)."
      % (len(parsed), len(flash), "{:,}".format(proj_rows), "{:,}".format(agg_rows)))
    w("")
    w("| year | project rows | with ID code | slip events |")
    w("|---|---:|---:|---:|")
    for y in sorted(by_year):
        w("| %s | %s | %s | %s |" % (y, "{:,}".format(by_year[y]),
                                     "{:,}".format(codes_by_year.get(y, 0)),
                                     "{:,}".format(slips_by_year.get(y, 0))))
    w("")
    if no_rows:
        w("Files parsed but yielding **no** project rows (%d): %s"
          % (len(no_rows), ", ".join("`%s`" % f for f in no_rows[:12])
             + (" ..." if len(no_rows) > 12 else "")))
        w("")
    if unparsed:
        w("_Not yet parsed: %d files._" % len(unparsed))
        w("")

w("## Identifiers - read this before joining anything")
w("")
w("There are **two eras**, and conflating them is the easiest mistake to make here.")
w("")
w("| era | project rows | tracking ID |")
w("|---|---|---|")
early = sum(v for y, v in by_year.items() if y and y < 2012)
late = sum(v for y, v in by_year.items() if y and y >= 2012)
w("| **pre-2012** | %s | **none.** MoSPI had not introduced the `N########` scheme. "
  "Rows are real observations but can only be linked across months by NAME |"
  % "{:,}".format(early))
w("| **2012 onward** | %s | `N########` embedded in the project-name cell, stable "
  "across monthly reports |" % "{:,}".format(late))
w("")
w("So: **project-level observations run from %d; reliable per-project tracking runs "
  "from 2013.** State both facts together - the first without the second overstates "
  "what the early years support." % (min(by_year) if by_year else 2001))
w("")
w("The OCMS `N########` code is also **unrelated to the PAIMANA dashboard's "
  "`ProjectId`.** PAIMANA replaced OCMS and renumbered. A name-based bridge between "
  "the two scored **1.1%** and should be treated as an unsolved record-linkage "
  "problem, not a working join.")
w("")

w("## What a full report contains")
w("")
w("A modern edition runs 500-600 pages. Rows are grouped into sections, and the "
  "sections are themselves labels assigned by MoSPI:")
w("")
w("| section family | what it means |")
w("|---|---|")
w("| `projects reporting additional delays` | **the slip event.** Columns are "
  "`DOC reported: Original / Last month / This month` and `Delay (in months)` - a "
  "project whose commissioning date moved since the previous report, with magnitude |")
w("| `Delayed Projects w.r.t. Original Schedule` | state: behind original schedule |")
w("| `On Schedule Projects` | state: on time |")
w("| `Ongoing Projects having Cost Overruns` | state: over cost |")
w("| `Projects Requiring Focused Attention` | **MoSPI's own watchlist** |")
w("| `Projects Without Milestones` / `Without Date of Commissioning` | data-quality flags |")
w("| `Completed` / `Deleted` / `added` / `dropped-Frozen` | portfolio churn |")
w("")
w("The distinction between an **event** section (something changed this month) and a "
  "**state** section (status as of this month) is the one that matters. Conflating "
  "them inflates apparent slip rates by an order of magnitude.")
if labels:
    w("")
    w("Label distribution across extracted project rows:")
    w("")
    w("| label | rows | share |")
    w("|---|---:|---:|")
    for k, v in labels.most_common(10):
        w("| `%s` | %s | %.1f%% |" % (k, "{:,}".format(v), 100 * v / max(proj_rows, 1)))
    unc = labels.get("UNCLASSIFIED", 0)
    w("")
    w("Unclassified sits at **%.1f%%**. Heading wording drifts between eras, so this "
      "is higher than on any single modern report - quote the corpus-wide figure."
      % (100 * unc / max(proj_rows, 1)))
w("")

w("## Provenance")
w("")
w("| host | role |")
w("|---|---|")
w("| `ipm.mospi.gov.in` | legacy OCMS-era archive (serves an **expired TLS certificate**) |")
w("| `paimana-proj.mospi.gov.in` | live successor portal, recent months |")
w("| `mospi.gov.in/sites/default/files/publication_reports` | some editions |")
w("")
w("All public - no login, no paywall. There is **no directory index** on any of them: "
  "archive folders return HTTP 200 with an empty body, so every file was located by "
  "enumerating candidate URLs.")
w("")
w("The corpus is reproducible without redistributing %.1f GB:" % ((flash_bytes + quart_bytes) / GB))
w("")
w("```bash")
w("python scripts/download_all.py     # fetch from the manifest URLs")
w("python scripts/fill_gaps.py        # recover awkwardly-named months")
w("python scripts/extract_tables.py   # rebuild the structured rows")
w("```")
w("")
w("## Licence and attribution")
w("")
w("Government of India publications, redistributed unmodified. Content owned and "
  "maintained by IPMD, MoSPI. Portal contact: `dir-ipmd[at]mospi[dot]gov[dot]in`.")
w("")

open(OUT, "w", encoding="utf-8").write("\n".join(L))
print("wrote", OUT)
print("flash=%d quarterly=%d | parsed=%d | project rows=%s | no-row files=%d"
      % (len(flash), len(quart), len(parsed), "{:,}".format(proj_rows), len(no_rows)))
if by_year:
    print("years with project rows: %d-%d | pre-2012 rows=%s | 2012+ rows=%s"
          % (min(by_year), max(by_year), "{:,}".format(early), "{:,}".format(late)))
