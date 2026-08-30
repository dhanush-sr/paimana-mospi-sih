# PAIMANA Foresight — SIH 2026, PS 26103 (MoSPI)

**Team's PICK 2.** (Pick 1 = PS 26018, Land Records.)
**Owner: Dhanush** — this PS only. 26018 ownership is separate and still open.

*Predict the revision before it is filed.*


## Flash Report corpus & India map (added by Vismay)

**Want to see the map? Open `docs/india_map_preview.html` in a browser. Nothing to install.**

| what | where |
|---|---|
| How to use the map (3 ways, simplest first) | `components/map/QUICKSTART.md` |
| Reading it correctly + integration contract | `components/map/MAP_GUIDE.md` |
| 25 years of Flash Report data (2001-2026) | `data/flash_reports/` |
| What is in the corpus, and its gaps | `data/flash_reports/CORPUS.md` |
| Extraction pipeline (download -> verify -> extract) | `flash_pdf/` |
| Data acquisition & verification report | `docs/PAIMANA_Data_Report.pdf` |

**592,608 project-level rows from 207 monthly Flash Reports, 2001-2026.** This lifts the
"cannot use two decades of OCMS history" limitation recorded in `04_RISKS_AND_GAPS.md`
section 2. Caveats: 2019 is absent from MoSPI's archive, and pre-2012 rows carry no ID
code (name matching only), so the honest line is *project-level observations from 2001,
reliable per-project tracking from 2013*.

The ~2 GB of source PDFs are **not** in git (GitHub blocks files over 100 MB and the LFS
free tier is 1 GB). They are reproducible - `flash_pdf/download_all.py` rebuilds the
corpus from the URLs in `data/flash_reports/manifest_all.csv` - and shared separately as
a zip.


## Read in this order

| file | what it is |
|---|---|
| **`00_FINDINGS.md`** | Every validated number, with reproduction commands. The PPT's ammunition. |
| **`01_SOLUTION_SPEC.md`** | What we build, the architecture, and the three things that are actually ours. |
| **`02_BUILD_PLAN.md`** | Executable. Run it top to bottom and a prototype exists. Each phase has an acceptance check. |
| **`03_PPT_NARRATIVE.md`** | The six slides, plus rehearsal notes and anticipated questions. |
| **`04_RISKS_AND_GAPS.md`** | Written adversarially against our own work. Open questions, ranked. |
| **`05_ARCHITECTURE.md`** | How it is actually built — schemas, module contracts, data flow, deployment. |

## Status as of 2026-08-27

**Data — done.** 13 monthly snapshots harvested, `data/raw/2025-07.json` … `2026-07.json`
(13 MB). 18,601 project-months, 2,243 projects. The portal does not retain this history;
it exists because we pulled each month separately.

**Validation — done.** The headline result is measured, not projected:

| | |
|---|---|
| Honest model, forward time split | **ROC-AUC 0.883** |
| Re-tested inside the post-March regime | **0.892** |
| Precision @ top-50 watchlist | **0.94** |
| "Is it overdue?" — today's heuristic | **0.472 (worse than random)** |
| The naive model everyone will build | **R² = 1.0000, coefficients −1.000 / +1.000** |

**Code — BUILT AND RUNNING.** `./run_all.sh` reproduces everything from raw snapshots.

```
harvest.py  panel.py  features.py  train.py  score.py  audit.py  ablation.py  api.py
tests/test_core.py                 # 6 checks, all pass
```

| stage | result |
|---|---|
| panel | 18,601 rows / 2,243 projects / 13 months — 4 assertions pass |
| schedule model | **AUC 0.8792**, precision@50 **0.940**, within-regime **0.8906** |
| cost model | AUC 0.9125 but precision@50 **0.160** — abstention band, by design |
| leaky demo | **R² 1.0000, coefs −1.000 / +1.000** |
| baseline "overdue" | **0.4716** — worse than random |
| shortlist | 50 projects, ₹24,854 cr exposed, sector-capped |
| integrity | 430 / 216 / 119 + break at 2026-03 — all regression asserts pass |
| ablation | agency_load **REJECTED**, −0.0095 AUC, 95% CI [−0.0135, −0.0055] |
| API | /watchlist /project /audit /ablation /metrics /benchmark /lint |
| **state recovery** | **99.0%** of rows tagged (18,417/18,601) from a field the payload returns as **null** |

| **UI** | Next.js 16 + React 19 + Tailwind v4, glassmorphic, dark/light aware |

Not built: `assistant.py` (Phase 7). The pitch does not depend on it.

State backfill is **complete** (468/468 cached). `/benchmark?by=state` works.

## The one-sentence pitch

> The portal already tells you which projects are late. We tell you which ones are about
> to become late — and we can prove in one slide that the obvious way of doing that is
> subtraction.

## Next actions

1. Execute `02_BUILD_PLAN.md` Phases 1–4 (demo-critical path), following `05_ARCHITECTURE.md`.
2. Answer the three still-open questions in `04_RISKS_AND_GAPS.md` §3.2–3.5 — each ~1 hour.
3. ~~Name an owner~~ — done: Dhanush (this PS only).
4. **Re-harvest on ~1 Sep 2026** to add the 2026-08 snapshot — one more test month.

---

## Commands

```bash
cd "/Users/dhanush/Desktop/SIH RESEARCH/paimana"

# everything, in order (~2 min; harvest is a no-op if snapshots exist)
./run_all.sh
```

Individually:

```bash
python3 harvest.py --all              # fetch any missing monthly snapshots (idempotent)
python3 harvest.py --states           # state backfill, ~20 min, resumable
python3 panel.py                      # -> data/panel.parquet + data/paimana.db
python3 tests/test_core.py            # 6 assert-based checks
python3 train.py --both --report      # schedule + cost, prints every headline number
python3 score.py --month 2026-07 --top 50    # THE SHORTLIST
python3 audit.py                      # integrity + structural break
python3 ablation.py                   # CUF sufficiency (PS clause c)
```

Serve the API:

```bash
python3 -m uvicorn api:app --port 8010
# then:
open http://127.0.0.1:8000/watchlist?top=50
open http://127.0.0.1:8000/docs          # interactive, auto-generated
```

`uvicorn` is not on PATH — always use `python3 -m uvicorn`.

**Monthly (put ~1 Sep 2026 in a calendar):**
```bash
python3 harvest.py --all && python3 harvest.py --states && ./run_all.sh
```
Miss a month and that snapshot is gone permanently — the portal keeps no history.
