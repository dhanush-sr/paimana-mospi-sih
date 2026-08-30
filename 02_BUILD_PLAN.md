# Build Plan — executable

**Read `05_ARCHITECTURE.md` first** — it defines the schemas, the `Window` object, and
the module contracts this plan assumes.

**Contract:** executing this file end to end produces a running prototype.
Each phase has an **acceptance check** that must print PASS before moving on.
Phases 1–4 are the demo-critical path. Phases 5–7 are polish.

**Environment:** Python 3.14 (present), `pandas 2.3.3`, `sklearn 1.8.0` (both present).
Additional installs: `fastapi uvicorn pyarrow shap` (+ Node 20 for `ui/` in Phase 6).

**Already done — do not redo:** `data/raw/2025-07.json` … `2026-07.json` (13 files, ~11 MB).

---

## Phase 0 — repo skeleton

```
paimana/
  harvest.py  panel.py  features.py  train.py  score.py
  audit.py    ablation.py  api.py    assistant.py
  common.py                       # parsers, paths, hashing
  tests/test_core.py
  data/raw/*.json  data/panel.parquet  data/paimana.db
  models/  reports/  ui/
  requirements.txt  Dockerfile  README.md
```

`common.py` holds the three parsers (spec: `05_ARCHITECTURE.md` §3.3) that everything else needs — write once:
`parse_dmy(s)` (`dd/mm/yyyy` → date | None), `parse_num(x)` (strips commas → float | NaN),
`snapshot_month(path)`. **Every date in the feed is `dd/mm/yyyy`. Every numeric field
arrives as a string with commas.** Getting this wrong silently poisons everything downstream.

---

## Phase 1 — Panel

### 1.1 `harvest.py`
Idempotent snapshot puller. Skips months already on disk.

```python
GET  /Home/PublicDashboardNew        # session cookie + scrape __RequestVerificationToken
POST /Home/GetTileData               # form: token, Month, Year, MonthYear,
                                     #       CostRange='', PROJ_MINISTRY_ID='',
                                     #       SectorId='', StateId=''
                                     # header: X-Requested-With: XMLHttpRequest
     -> json['data']['ProjectsCountTabDetails']
```
- `time.sleep(2.5)` between requests — non-negotiable, this is a government host
- append to `data/harvest_log.jsonl`: url, params, timestamp, status, bytes, sha256
- CLI: `--month YYYY-MM`, `--all`, `--refresh`

**Acceptance:** `python3 harvest.py --all` → "13 snapshots present, 0 fetched" on 2nd run.

### 1.2 `panel.py`
13 snapshot JSONs → long panel, one row per (ProjectId, snapshot_month).

Columns: `pid, month, t, name, sector, ministry, agency, original_cost, revised_cost,
expenditure, physical_progress, sanction_date, original_end_date, revised_date`

Write `data/panel.parquet` **and** `data/paimana.db` (table `panel`, indexed on
`pid, month` — the assistant queries SQL, not parquet).

**Acceptance — assert exactly, these are measured ground truth:**
```
rows == 18601
pid.nunique() == 2243
months == 13
panel[panel.month=='2026-04'].shape[0] == 1981     # matches the PS text verbatim
```
If any assertion fails, the harvest is corrupt. **Stop and re-harvest.** Do not proceed.

### 1.3 State backfill `[VERIFIED — do this]`
`StateName` is null in the payload but the server-side filter works.

```
GET  /Home/GetStateList   header: X-Requested-With: XMLHttpRequest
     -> 36 {Value:id, Text:name} entries
POST /Home/GetTileData  with StateId=k   -> only state k's projects
```
Tag every returned `ProjectId` with state *k*; join onto the panel as a `state` column.
36 calls × 13 months ≈ 468 requests ≈ 20 min at the 2.5s throttle. Cache to
`data/states/YYYY-MM_<id>.json` and make it resumable.

**Acceptance:** ≥90% of the 2,243 projects receive a state; the union of per-state row
counts for 2026-07 is within a few percent of 1,775 (a project may span states).

---

## Phase 2 — Features + the Leakage Linter *(differentiator 4.1)*

### 2.1 `features.py`
**Implement the `Window` object from `05_ARCHITECTURE.md` §4.2 first** — it is what makes
leakage structurally impossible. The decorator below is the second layer, not the first.

Every feature is a registered function declaring its time dependency:

```python
@feature(reads="t")        # only the current snapshot
def physical_progress(win): ...

@feature(reads="t-3..t")   # trailing window
def pp_delta_3m(win): ...

@feature(reads="t+1..t+3") # LABEL ONLY — linter rejects if used as a feature
def label_revision_next_3m(win): ...
```

**`assert_no_leakage(feature_set)`** raises if any registered feature declares a
window containing `t+k`. Call it at the top of `train.py`. This is a shipped product
feature, not a dev convenience.

**Feature list (validated — these produced AUC 0.883):**

| feature | definition |
|---|---|
| `original_cost`, `cost` | `revised_cost.fillna(original_cost)` |
| `expenditure`, `physical_progress` | as reported at *t* |
| `fin_pct` | `100 * expenditure / cost` |
| `gap` | `physical_progress − fin_pct` (physical vs financial divergence) |
| `mons_since_sanction` | `(t − sanction_date).days / 30.44` |
| `mons_to_due` | `(revised_date or original_end_date − t).days / 30.44` — **strongest, Δ0.051** |
| `overdue` | `mons_to_due < 0` |
| `cur_slip` | `(revised_date − original_end_date).days` — known at *t*, legitimate |
| `prior_revs` | count of revisions strictly before *t* — **AUC 0.623 alone** |
| `pp_delta_3m`, `exp_delta_3m` | 3-month deltas (stall detection) |
| `nobs` | months observed — **required**, controls the onboarding ramp (791→1,987) |
| `sector_*` | one-hot, `dummy_na=True` |

> **Do not add `agency_load`.** Tested: 0.883 → 0.863. Confounded with sector.
> Keep the finding for the ablation slide; keep the feature out of the model.

### 2.2 Labels
```python
label_schedule = revised_date changes in any of t+1, t+2, t+3   # 13.81% of transitions
label_cost     = revised_cost changes in any of t+1, t+2, t+3   #  1.00% — rare, see §5
```

**Acceptance:** `assert_no_leakage()` passes; deliberately mis-declare one feature as
`reads="t+1"` and confirm the linter **fails the build**. Test both directions.

---

## Phase 3 — Train, calibrate, evaluate

### 3.1 `train.py`
```
--target {schedule,cost}  --split-month 2026-04  --calibrate isotonic  --report
```

Pipeline:
1. `assert_no_leakage()`
2. time split: train `t < split`, test `t >= split` — **never random split**
3. `HistGradientBoostingClassifier(max_iter=300, learning_rate=0.06, random_state=0)`
4. isotonic calibration on a held-out fold carved from train (never from test)
5. metrics: ROC-AUC, PR-AUC + base rate, precision@{50,100,200}, **ECE**, reliability diagram
6. baselines printed alongside: `overdue`, `prior_revs`, and the leaky model
7. persist `models/{target}.joblib` + `reports/{target}_metrics.json`

**Acceptance — reproduce the measured numbers within ±0.01:**
```
schedule: AUC 0.883   PR 0.726 (base 0.263)   p@50 0.94
baselines: overdue 0.472   prior_revs 0.623
leaky demo: R² 1.0000, coef −1.000 / +1.000
within-regime (train Mar+Apr26 → test Jun+Jul26): AUC 0.892
```

### 3.2 `score.py` — risk score + abstention *(differentiator 4.2)*
- calibrated probability → 0–100 composite
- three bands: **flag** (high conf) / **watch** / **abstain → route to analyst**
- abstention thresholds chosen on the *train* fold to hit a target precision, then
  reported on test. Never tuned on test.
- cost target: expect a wide abstention band. **That is the intended, honest behaviour.**

**Acceptance:** `score.py --month 2026-07 --top 50` prints 50 projects; precision on the
realised outcome ≈ 0.94; at least one row in the cost model shows `ABSTAIN`.

---

## Phase 4 — The two modules nobody asked for

### 4.1 `audit.py` — Data Integrity Monitor
Scan consecutive-month transitions and emit `reports/integrity.json`:

| check | expected count |
|---|---|
| expenditure decreased | **427** |
| physical progress decreased | **212** |
| completion date pulled earlier | **119** |
| \|cost delta\| > ₹10,000 cr | flags the **−₹175,291 cr** outlier |
| **structural break** in monthly revision rate | detects **2026-03** (1.95% → 23.96%) |

Break detection: flag any month where the rate exceeds 3× the trailing 3-month mean.
Keep it that simple — the March jump is 12×, no sophistication needed.

**Acceptance:** all five counts reproduce exactly; break detector returns `2026-03`.

### 4.2 `ablation.py` — CUF Sufficiency Protocol *(PS clause c, differentiator 4.3)*
```
--candidate agency_load --control sector
```
Reports CUF-only baseline vs +candidate, with incremental AUC/PR and a bootstrap CI.

**Acceptance:** reproduces `0.8830 → 0.8631` for `agency_load`, and labels it
**REJECTED — no incremental value, confounded with sector.**

---

## Phase 5 — API

`api.py` (FastAPI), all reads from SQLite, all responses carry `model_version` + `snapshot_month`:

```
GET /watchlist?month=2026-07&top=50&target=schedule
GET /project/{pid}                # full 13-month timeline
GET /explain/{pid}?month=2026-07  # SHAP contributions
GET /audit?month=2026-07
GET /ablation
GET /benchmark?sector=...         # peer percentiles (PS outcome e)
```

**Acceptance:** `uvicorn api:app` → `/watchlist` returns 50 scored rows with reasons.

---

## Phase 6 — UI

`ui/` Next.js + D3. Five views, mapped to the demo script in `01_SOLUTION_SPEC.md` §5:

1. **Watchlist** — ranked table, risk band colour, one-line reason per row
2. **Project timeline** — 13 snapshots as a strip; revisions as step changes; anomalies marked
3. **Explain** — SHAP waterfall
4. **Integrity feed** — the 758 anomalies + the March break annotated on a rate chart
5. **Ablation** — CUF baseline vs candidate, with the rejection verdict shown

Keep it read-only. No auth, no write paths — it is a demo.

**Acceptance:** the six-step demo (§5) runs start to finish without a terminal.

---

## Phase 7 — Assistant *(PS outcome h)*

`assistant.py`: NL → **parameterised SQL** over `data/paimana.db`, executed read-only,
results rendered. Self-hosted quantised model via vLLM.

**Hard rule: the LLM never computes a number.** It selects a query and narrates the
result. Every figure in an answer carries the SQL that produced it. If no query fits,
it says so — it does not estimate.

**Acceptance:** "Which road projects are most likely to slip next quarter?" returns
rows from `/watchlist` with the SQL shown. A question the schema cannot answer
("why was this project delayed?") returns an explicit refusal referencing the empty
`RevisedDateReason` field — which is also the clause (c) talking point.

---

## Phase 8 — Tests

`tests/test_core.py`, assert-based, no framework:
- `parse_dmy('13/07/2024')` → date(2024,7,13); `parse_dmy('')` → None
- `parse_num('1,234.5')` → 1234.5
- panel row/project/month counts (Phase 1 assertions)
- leakage linter fails on a deliberately mis-declared feature
- time split never lets a test month into train
- a project with a single observation produces no label (no silent NaN→0)

---

## Order of execution

```
Phase 1 → 2 → 3 → 4      # demo-critical. Stop here and the pitch still works.
Phase 5 → 6              # makes it presentable
Phase 7 → 8              # PS outcome (h) + hygiene
```

**If time runs short, cut Phase 7 first, then Phase 6.** The watchlist, the leakage
proof, and the integrity feed are the pitch. A dashboard without them is a dashboard.

---

## Re-harvest before submission

The panel grows one row per project per month. Re-run `harvest.py --all` in
**early September 2026** to pick up 2026-08. More months = a longer test window = a
stronger number. Put a calendar reminder on it.
