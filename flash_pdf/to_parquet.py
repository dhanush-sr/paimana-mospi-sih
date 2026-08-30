# -*- coding: utf-8 -*-
"""Convert extracted/tables.jsonl to Parquet for sharing.

tables.jsonl is ~450 MB, which GitHub hard-blocks (100 MB per file). Parquet with
dictionary encoding and zstd is a good fit for this data because almost every
column is low-cardinality and highly repetitive - section labels, file names,
years, and section titles repeat across hundreds of thousands of rows.

The `raw` cell list is kept as a JSON string rather than dropped: it is the
guarantee that nothing was silently discarded where a header went unrecognised.
It is also the bulk of the bytes, so a second, slimmer file is written without it
for anyone who only needs the mapped columns.
"""
import io
import json
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import pandas as pd

ROOT = r"C:\Users\LENOVO\Downloads\SIH2026\PAIMANA"
SRC = os.path.join(ROOT, "extracted", "tables.jsonl")
OUT_FULL = os.path.join(ROOT, "extracted", "flash_report_rows.parquet")
OUT_SLIM = os.path.join(ROOT, "extracted", "flash_report_rows.slim.parquet")

COLS = ["file", "year", "month", "page", "table", "row", "section_title",
        "section_label", "title_inherited", "is_aggregate", "project_code",
        "sl_no", "project", "agency", "sector", "state", "approval_date",
        "orig_cost", "revised_cost", "anticipated_cost", "cum_expenditure",
        "orig_doc", "last_month_doc", "this_month_doc", "delay_months",
        "orig_rev_doc", "anticipated_doc", "milestones", "physical_progress"]

rows = []
n = bad = 0
with open(SRC, encoding="utf-8") as fh:
    for line in fh:
        n += 1
        try:
            r = json.loads(line)
        except Exception:
            bad += 1
            continue
        rec = {c: r.get(c) for c in COLS}
        rec["raw"] = json.dumps(r.get("raw", []), ensure_ascii=False)
        rows.append(rec)

print(f"read {n:,} lines ({bad} unparseable)")
df = pd.DataFrame(rows)

# Low-cardinality strings -> dictionary encoding does the heavy lifting.
for c in ("file", "section_title", "section_label", "sector", "state", "agency"):
    if c in df.columns:
        df[c] = df[c].astype("category")
for c in ("year", "month", "page", "table", "row"):
    if c in df.columns:
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("Int32")

df.to_parquet(OUT_FULL, engine="pyarrow", compression="zstd", index=False)
df.drop(columns=["raw"]).to_parquet(OUT_SLIM, engine="pyarrow",
                                    compression="zstd", index=False)

src_mb = os.path.getsize(SRC) / 1048576
full_mb = os.path.getsize(OUT_FULL) / 1048576
slim_mb = os.path.getsize(OUT_SLIM) / 1048576
print(f"\n  source  tables.jsonl              {src_mb:8.1f} MB")
print(f"  full    flash_report_rows.parquet  {full_mb:8.1f} MB  "
      f"({src_mb/max(full_mb,0.01):.1f}x smaller)")
print(f"  slim    (no raw cells)             {slim_mb:8.1f} MB  "
      f"({src_mb/max(slim_mb,0.01):.1f}x smaller)")
print(f"\n  under GitHub's 100 MB file limit: "
      f"full={'YES' if full_mb < 100 else 'NO'}  slim={'YES' if slim_mb < 100 else 'NO'}")
print(f"\n  rows: {len(df):,}  | project-level: {(~df['is_aggregate'].fillna(False)).sum():,}")
