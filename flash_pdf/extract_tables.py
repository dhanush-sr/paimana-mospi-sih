# -*- coding: utf-8 -*-
"""Table-structure extraction from the flash reports. Replaces extract_projects.py.

The regex-over-flattened-text approach failed for a specific, diagnosable reason:
section headings appear on only ~61% of pages, so attributing a section by
carrying the last-seen heading forward mislabelled every unheaded page. That is
how "projects reporting additional delayed" ended up with 138,128 records when
the table itself spans ~27 pages and contains no project codes at all.

This uses PyMuPDF find_tables(), which returns real cell geometry. Two things
follow from that:

  * the section title sits in the table's own first row, plus the page text
    directly above its bbox - so section attribution is per-table and needs no
    carry-forward
  * columns are addressable by header text rather than by position, which
    matters because layouts differ per section and per era

Every row keeps its full raw cell list alongside the mapped fields, so nothing
is discarded even where a header is unrecognised.

Output: extracted/tables.jsonl (one JSON object per data row).
"""
import json
import os
import re
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

import fitz

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from section_map import classify

ROOT = r"C:\Users\LENOVO\Downloads\SIH2026\PAIMANA"
FILES = os.path.join(ROOT, "files")
OUT_DIR = os.path.join(ROOT, "extracted")
os.makedirs(OUT_DIR, exist_ok=True)

CODE = re.compile(r"\[?\b([NA]\d{8})\b\]?")
MONTH_NAMES = ["january", "february", "march", "april", "may", "june",
               "july", "august", "september", "october", "november", "december"]

# Canonical column names, matched against normalised header text.
# Order matters: more specific patterns first.
COLUMN_RULES = [
    ("sl_no",              r"^s\.?\s*i?\.?\s*no\.?$|^sl\.?\s*no|^s\.?no"),
    ("project",            r"^project(\s*name)?$|^name of"),
    ("approval_date",      r"date of approval|month of approval"),
    ("orig_cost",          r"^original$|^original cost|orig.*cost"),
    ("revised_cost",       r"^revised cost|original/\s*revised cost|latest.*cost"),
    ("anticipated_cost",   r"antici\s*pated cost|^antici\s*pated$"),
    ("cum_expenditure",    r"cumulative expenditure|^expenditure"),
    ("orig_doc",           r"^original$"),
    ("last_month_doc",     r"last\s*month"),
    ("this_month_doc",     r"this\s*month"),
    ("delay_months",       r"delay\s*\(?\s*in\s*months|^delay$"),
    ("orig_rev_doc",       r"original/\s*revised"),
    ("anticipated_doc",    r"antici\s*pated"),
    ("milestones",         r"milestones?\s*achieved|milestones?\s*/\s*total"),
    ("physical_progress",  r"physical\s*progress|progress\s*%"),
    ("state",              r"^state$|state\s*/\s*ut"),
    ("agency",             r"^agency|implementing"),
    ("sector",             r"^sector$"),
]
_COLS = [(n, re.compile(p, re.I)) for n, p in COLUMN_RULES]


def norm(s):
    return " ".join(str(s or "").split())


def map_header(cells):
    """Map header cells -> canonical names. Returns {col_index: name}."""
    out, used = {}, set()
    for i, c in enumerate(cells):
        t = norm(c).lower()
        if not t:
            continue
        for name, rx in _COLS:
            if name in used:
                continue
            if rx.search(t):
                out[i] = name
                used.add(name)
                break
    return out


def is_header_row(cells):
    joined = " ".join(norm(c).lower() for c in cells if c)
    if not joined:
        return False
    has_no = re.search(r"\bs\.?\s*i?\.?\s*no\b|\bsl\.?\s*no\b", joined)
    has_proj = "project" in joined or "name" in joined
    return bool(has_no and has_proj)


def is_data_row(cells, colmap):
    """First mapped cell should look like a serial number, and the row must
    carry some substantive text - filters out rulers like ['1','2','3',...]."""
    vals = [norm(c) for c in cells]
    nonempty = [v for v in vals if v]
    if len(nonempty) < 3:
        return False
    # a column-number ruler row: every cell a small integer, ascending
    ints = [v for v in nonempty if re.fullmatch(r"\d{1,2}", v)]
    if len(ints) == len(nonempty):
        return False
    # needs at least one longish text cell (a project name)
    if not any(len(v) > 12 and re.search(r"[A-Za-z]{4}", v) for v in vals):
        return False
    return True


def title_candidates(page, table, data):
    """Every plausible heading string for this table, best-guess order.

    Headings are frequently split across two lines, e.g.
        "Details of On Schedule Projects w.r.t. Original Schedule"
        "Costing Rs. 150 Crore and above (May 2024)"
    Taking only the nearest line above the table yields the second line, which
    carries no section information at all - that alone accounted for 4,943
    UNCLASSIFIED rows in a single report.
    """
    cands = []
    for r in data[:3]:
        for c in (r[:2] if r else []):
            t = norm(c)
            if len(t) > 12:
                cands.append(t)
    x0, y0, x1, y1 = table.bbox
    band = fitz.Rect(0, max(0, y0 - 170), page.rect.width, y0 + 2)
    try:
        txt = page.get_text("text", clip=band) or ""
    except Exception:
        txt = ""
    lines = [norm(l) for l in txt.splitlines() if len(norm(l)) > 8]
    # nearest-first, then pairwise joins to recover split headings
    cands.extend(reversed(lines[-5:]))
    for a, b in zip(lines, lines[1:]):
        cands.append(f"{a} {b}")
    return cands


# A heading always reads like a heading. Project names do not.
# Plural "projects" only: a bare singular "Project" appears inside project names
# ("Rajasthan Atomic Power Project -7 And 8") and let them through as headings.
HEADINGISH = re.compile(
    r"list of|details of|\bprojects\b|costing rs|annexure|summary|sector[- ]wise|"
    r"state[- ]wise|w\.r\.t|overrun|milestone|commissioning", re.I)


def resolve_title(page, table, data):
    """Pick the first candidate that classifies to a real section.

    Deliberately returns nothing rather than falling back to an arbitrary long
    line: on continuation pages the nearest text above a table is often the
    previous table's last project name, and accepting it produced 137 bogus
    "sections" like 'NAGPUR RING ROAD PACKAGE-2'. An empty title lets the
    structural inheritance below fill it in correctly.
    """
    cands = title_candidates(page, table, data)
    for t in cands:
        lab = classify(t)
        if lab not in ("UNCLASSIFIED", "JUNK"):
            return t, lab
    for t in cands:
        if len(t) > 15 and HEADINGISH.search(t):
            return t, classify(t)
    return "", "UNCLASSIFIED"


def col_signature(colmap, ncols):
    return (ncols, tuple(sorted(colmap.values())))


def parse_file(path):
    fname = os.path.basename(path)
    m = re.match(r"FR_(\d{4})_(\d{2})_", fname)
    if not m:
        return fname, 0, []
    year, month = int(m.group(1)), int(m.group(2))
    rows = []
    try:
        doc = fitz.open(path)
    except Exception as e:
        return fname, 0, [{"__error__": f"{type(e).__name__}: {e}"}]

    npages = doc.page_count
    last_title, last_label, last_sig = "", "", None
    for pno in range(npages):
        try:
            page = doc[pno]
            tf = page.find_tables()
        except Exception:
            continue
        for ti, tab in enumerate(getattr(tf, "tables", [])):
            try:
                data = tab.extract()
            except Exception:
                continue
            if not data or len(data) < 2:
                continue

            hidx, colmap = None, {}
            for i, r in enumerate(data[:8]):
                if is_header_row(r):
                    hidx, colmap = i, map_header(r)
                    break
            start = (hidx + 1) if hidx is not None else 1

            title, label = resolve_title(page, tab, data)
            sig = col_signature(colmap, len(data[0]) if data else 0)
            # Tables with no project column are aggregate summaries, not
            # project-level rows; they must not be counted as projects.
            is_aggregate = "project" not in set(colmap.values())
            inherited = False
            if label in ("UNCLASSIFIED", "JUNK") and last_sig and sig == last_sig:
                # A continuation page of the same table: identical column
                # signature, heading printed only on the first page. Scoped to a
                # structural match, unlike the blanket carry-forward that broke
                # the previous extractor.
                title, label, inherited = last_title, last_label, True
            elif label not in ("UNCLASSIFIED", "JUNK"):
                last_title, last_label, last_sig = title, label, sig

            for ri in range(start, len(data)):
                cells = data[ri]
                if not is_data_row(cells, colmap):
                    continue
                rec = {
                    "file": fname, "year": year, "month": month,
                    "page": pno + 1, "table": ti, "row": ri,
                    "section_title": title[:120],
                    "section_label": label,
                    "title_inherited": inherited,
                    "is_aggregate": is_aggregate,
                    "raw": [norm(c) for c in cells],
                }
                for ci, name in colmap.items():
                    if ci < len(cells):
                        v = norm(cells[ci])
                        if v:
                            rec[name] = v
                blob = " ".join(rec["raw"])
                cm = CODE.search(blob)
                if cm:
                    rec["project_code"] = cm.group(1)
                rows.append(rec)
    doc.close()
    return fname, npages, rows


def main():
    """Resumable: a full pass is ~30 minutes over 65,000 pages, long enough that
    an interrupted run is likely. Completed files are recorded in a sidecar and
    skipped, and rows are appended, so restarting costs only the file that was
    in flight."""
    all_pdfs = sorted(os.path.join(FILES, f) for f in os.listdir(FILES)
                      if f.lower().endswith(".pdf") and f.startswith("FR_"))
    out_path = os.path.join(OUT_DIR, "tables.jsonl")
    done_path = os.path.join(OUT_DIR, "tables_done.txt")

    done_files = set()
    if os.path.exists(done_path):
        done_files = {l.strip() for l in open(done_path, encoding="utf-8") if l.strip()}
    pdfs = [p for p in all_pdfs if os.path.basename(p) not in done_files]

    print(f"{len(all_pdfs)} pdfs total | {len(done_files)} already done | "
          f"{len(pdfs)} to process", flush=True)
    if not pdfs:
        print("nothing to do")
        return

    t0, total, done, errors = time.time(), 0, 0, 0
    mode = "a" if done_files else "w"
    with open(out_path, mode, encoding="utf-8") as fh, \
            open(done_path, "a", encoding="utf-8") as dh, \
            ProcessPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(parse_file, p): p for p in pdfs}
        for fut in as_completed(futs):
            src = futs[fut]
            try:
                fname, npages, rows = fut.result()
            except Exception:
                errors += 1
                done += 1
                continue
            n = 0
            for r in rows:
                if "__error__" in r:
                    errors += 1
                    continue
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
                n += 1
            total += n
            fh.flush()
            dh.write(os.path.basename(src) + "\n")
            dh.flush()
            done += 1
            if done % 5 == 0:
                rate = done / max(time.time() - t0, 1)
                eta = (len(pdfs) - done) / rate / 60 if rate else 0
                print(f"  {done}/{len(pdfs)} files | {total:,} rows | "
                      f"{time.time()-t0:.0f}s | eta {eta:.0f}m", flush=True)

    print(f"\nDONE this pass: {total:,} rows from {done} pdfs ({errors} errors) "
          f"in {time.time()-t0:.0f}s")
    print(f"-> {out_path}  ({os.path.getsize(out_path)/1048576:.1f} MB)")


if __name__ == "__main__":
    main()
