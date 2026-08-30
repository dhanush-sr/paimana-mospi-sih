# PAIMANA (SIH26103) — Validated Findings

**Status:** every number below was measured by us on 2026-08-27 from data we harvested ourselves.
Reproduction commands are given. Confidence tags:
`[MEASURED]` we computed it · `[VERIFIED]` confirmed from primary source · `[LIT]` from literature · `[OPEN]` not yet checked

---

## 1. The data situation — and why it is our moat

### 1.1 The portal gives you nothing, until you find the right door

`[VERIFIED]` The PS points at `https://paimana-proj.mospi.gov.in/ReportPage`.
That page renders **"Coming Soon"**. The report endpoint returns empty:

```
GET /ReportPage/Report?fyear=2025-26&month=4&quater=0&reportType=Monthly
-> {"html":""}
```

**Any team that follows the PS link finds nothing and gives up, or falls back to
scraping PIB press releases for aggregate totals.** That is the crowd's path.

### 1.2 The real door `[VERIFIED]`

The public dashboard has an undocumented POST endpoint returning **project-level records**:

```
POST https://paimana-proj.mospi.gov.in/Home/GetTileData
form: __RequestVerificationToken, Month, Year, MonthYear, CostRange,
      PROJ_MINISTRY_ID, SectorId, StateId
-> data.ProjectsCountTabDetails = [ ...1,775 project objects... ]   (~1.25 MB)
```

Requires: a session cookie + the anti-forgery token scraped from
`/Home/PublicDashboardNew`. Public data, no login, no paywall.

**26 fields per project:**
`ProjectId, ProjectName, SectorName, StateName, LineMinistry, COMPANYNAME,
AgencyId, AgencyName, OriginalCost, RevisedCost, RevisedCostReason, Expenditure,
SanctionDate, CreationDate, StartDate, OriginalEndDate, RevisedDate,
RevisedDateReason, DELAYED_TIME, COST_OVERRUN_PERC, COST_OVERRUN, COR_PERC,
TOR_PERC, PhysicalProgress, OnboardingDelay, Remarks`

### 1.3 It is a PANEL, not a snapshot — this is the whole idea `[MEASURED]`

`GET /Home/GetFreezeDates` -> `{"firstFreeze":"2025-07","lastFreeze":"2026-07"}`

Changing `Month`/`Year` returns a **different frozen monthly snapshot**. Verified by
tracking one project across months:

| snapshot | project 706718 (Imphal Airport) Expenditure |
|---|---|
| 2025-07 | 160.48 |
| 2025-10 | 155.72  ← **decreased** |
| 2026-01 | 161.30 |
| 2026-04 | 201.99 |
| 2026-07 | 212.17 |

**We harvested all 13 snapshots (2025-07 … 2026-07), ~11 MB.**

| metric | value |
|---|---|
| monthly snapshots | 13 |
| panel rows (project-months) | **18,601** |
| unique projects | **2,243** |
| projects seen in ≥2 months | 2,176 |
| projects seen in all 13 months | 552 |
| consecutive-month transitions | **16,315** |

**Cross-check that this is the PS's own source:** the 2026-04 snapshot returns
**exactly 1,981 projects** — the number quoted verbatim in the problem statement
("As of April 2026 … tracks 1,981 ongoing infrastructure projects"). `[VERIFIED]`

### 1.4 Why others will not have this `[MEASURED]`

- Firecrawl (US datacenter) **cannot resolve** `paimana-proj.mospi.gov.in` — DNS fails.
  Local Indian-routed curl gets HTTP 200. The host is effectively India-reachable only.
  Cloud-based scraping tools silently fail on it.
- The endpoint is POST-only, CSRF-protected, and undocumented — not discoverable by
  a link crawler, only by reading the dashboard's inline JS.
- **The panel is not archived by the portal.** Only the *current* value of each field is
  shown in the UI. The history exists solely because you pulled each month separately.
  Miss the window, and the past is gone.

> This satisfies criterion 12 (free, Indian, already exists, hard for others to find)
> better than any dataset link in the PS list.

### 1.5 Geography is recoverable — `StateName` is null but the filter works `[VERIFIED]`

`StateName` is 0% populated in the unfiltered payload. But the **server-side filter is
live**, and the lookup endpoint returns all **36 states/UTs**:

```
GET  /Home/GetStateList   (needs header X-Requested-With: XMLHttpRequest)
  -> [{"Value":1,"Text":"Andhra Pradesh"}, ... 36 entries ...]

POST /Home/GetTileData  with StateId=k
  -> only the projects in state k  (StateName still null, but membership is implied)
```

Verified by spot-check — the returned projects match the state ID:

| StateId | state | rows | sample project |
|---|---|---|---|
| 3 | Assam | 76 | *Guwahati Airport New Integrated Terminal* |
| 6 | Goa | 9 | *Chandorgaon-Cansaulim rail flyover* |
| 7 | Haryana | 39 | *AIIMS Majra Rewari **Haryana*** |
| 10 | Jharkhand | 103 | *Pachwara South Coal Block* |

**So geography is reconstructible by join:** call the endpoint once per StateId, tag every
returned `ProjectId` with that state. 36 calls/month; at a 2.5s throttle a full 13-month
backfill is ~20 minutes.

**DONE — executed 2026-08-27.** 468/468 state-months cached. **99.0% of panel rows now
carry a state (18,417 / 18,601).** Spot-checks all correct: Kerala->IIT Palakkad,
Assam->Numaligarh Refinery, Goa->Margao Bypass, Bihar->Buxar Thermal.

Top states by project count (2026-07): Maharashtra 161, Uttar Pradesh 138, Andhra Pradesh
119, Madhya Pradesh 112, Karnataka 105, Odisha 96, Jharkhand 96, Bihar 94.

**Caveat to state honestly:** 162 of 1,765 projects (9.2%) are multi-state corridors, and
one national programme appears under all 36 states. The scalar `state` column takes the
first match by StateId order, so a corridor may be labelled by only one of its states
(e.g. Pune-Hyderabad shows as Telangana). The `project_states` side table holds the full
set (21,472 rows) and is what benchmarking should use.

This unlocks state-level benchmarking (PS outcome e) and a map view — from a field the
payload reports as empty.

---

## 2. The central technical finding: the obvious model is arithmetic

### 2.1 The leakage trap `[MEASURED]`

The naive reading of the PS ("build a Time Overrun Prediction Model") leads here:

```
Time Overrun := RevisedDate − OriginalEndDate
```

Regress that on the columns that define it:

```
LinearRegression(time_overrun ~ OriginalEndDate + RevisedDate + OriginalCost)
  R² = 1.0000
  coef(OriginalEndDate) = −1.000
  coef(RevisedDate)     = +1.000
```

**The model learned subtraction.** R² = 1.0 exactly; coefficients are exactly −1 and +1.

This is not a strawman. It is the *default* result of loading the April 2026 file into
scikit-learn and predicting the overrun column. **We expect a large share of the 500
teams to present a >0.9 R² built this way**, and to present it as a success.

The portal already displays the overrun. Predicting it is not prediction; it is a
restatement of two columns the user is already looking at.

### 2.2 The honest reformulation `[MEASURED]`

The decision-relevant question is not *"how late is this project?"* (known) but:

> **"Which projects are about to be revised — before the revision is filed?"**

Label: *does this project receive a NEW RevisedDate within the next 3 months?*
Features: only information available at month *t*.
Split: strictly forward in time.

| | value |
|---|---|
| train (months < 2026-04) | 10,842 rows |
| test (months ≥ 2026-04) | 5,516 rows |
| base rate (test) | 0.263 |
| **ROC-AUC** | **0.8830** |
| PR-AUC | 0.7263 (vs 0.2632 baseline — **2.76× lift**) |
| **precision @ top-50** | **0.940** |
| precision @ top-100 | 0.880 |
| precision @ top-200 | 0.860 |

Model: `HistGradientBoostingClassifier(max_iter=300, lr=0.06)`. No tuning.

### 2.3 The counterintuitive result that makes the slide `[MEASURED]`

The heuristic a monitoring officer uses today — *is the project past its due date?*

```
AUC("currently overdue")   = 0.4716   ← WORSE THAN RANDOM
AUC("prior revision count")= 0.6231
AUC(our model)             = 0.8830
```

**Being overdue is not predictive of being revised.** It is slightly *anti*-predictive.
The signal the system currently surfaces most prominently is the wrong one.

*(Interpretation: a project already carrying a large slip has usually just been
revised, so it is not due for another. The at-risk project is the one approaching a
deadline it will not meet — which looks healthy on today's dashboard.)*

### 2.4 The signal is real, not one leaky column `[MEASURED]`

Permutation importance (drop in test AUC):

| feature | Δ AUC |
|---|---|
| months to due date | +0.178 |
| current slip (known at *t*) | +0.059 |
| sector = Roads & Highways | +0.032 |
| original cost | +0.010 |
| revised cost | +0.009 |
| physical progress | +0.007 |
| months observed | +0.006 |
| progress-vs-spend gap | +0.005 |

Ablation — retrain with each feature removed:

| removed | AUC | Δ |
|---|---|---|
| *(none)* | 0.8830 | — |
| months_to_due | 0.8316 | −0.051 |
| current slip | 0.8720 | −0.011 |
| progress-vs-spend gap | 0.8766 | −0.006 |
| physical progress | 0.8776 | −0.005 |
| prior revisions | 0.8805 | −0.003 |

No single feature carries it. Removing the strongest costs 5 AUC points.

### 2.5 Robustness — it survives the regime shift `[MEASURED]`

**We found a 12× discontinuity in the revision rate at March 2026** (see §3.1). Any
model trained across that boundary is suspect. So we retrained *entirely inside* the
post-shift regime:

```
train = Mar+Apr 2026 only   test = Jun+Jul 2026 only
AUC = 0.8921   PR-AUC = 0.5667   (base rate 0.166)
```

**The headline holds — slightly higher, in fact.** The result is not an artifact of
the regime change.

---

## 3. Findings about MoSPI's own data (a statistics ministry will care most about this)

### 3.1 A 12× discontinuity in March 2026 `[MEASURED]`

Monthly rate of schedule revisions:

| month | rate | | month | rate |
|---|---|---|---|---|
| 2025-08 | 6.6% | | 2026-02 | **1.95%** |
| 2025-09 | 6.3% | | 2026-03 | **23.96%** ← |
| 2025-10 | 5.7% | | 2026-04 | 19.28% |
| 2025-11 | 7.2% | | 2026-05 | 21.84% |
| 2025-12 | 5.6% | | 2026-06 | 16.62% |
| 2026-01 | 3.6% | | 2026-07 | 16.23% |

Feb → Mar is a **12-fold jump** that never reverts. Candidate explanations `[OPEN]`:
fiscal-year-end revision cycle; completion of PAIMANA onboarding; a data-cleanup drive;
a change in what counts as a revision. **We have not established which.**

Why it matters: it is a structural break in a national statistical series. Anyone
modelling this data without noticing it will produce a broken model — and MoSPI
themselves may not have flagged it.

### 3.2 Data integrity anomalies `[MEASURED]`

Across 16,315 project-month transitions:

| anomaly | count | rate |
|---|---|---|
| **Expenditure decreased** | **430** | 2.6% |
| **Physical progress decreased** | **216** | 1.3% |
| **Completion date pulled *earlier*** | **119** | 5.3% of revisions |

*Definition:* consecutive **observations**, not consecutive calendar months — 42 projects
drop out of a snapshot and return, and a reversal across that gap is still a reversal.
Adjacent-month-only counts are 427 / 212 / 119.

Cumulative expenditure and physical progress are monotone quantities. A decrease is
either a restatement, a correction, or an error — in all three cases it is a fact the
ministry wants surfaced. **None of these are visible from a single snapshot.**

Extreme value found: a single month-on-month cost revision of **−₹175,291 crore**.
Almost certainly a data entry error, and it is sitting in the live public dashboard. `[MEASURED]`

### 3.3 Revision magnitude — not just administrative rolling `[MEASURED]`

n = 2,262 schedule revisions:

| slip size | count | share |
|---|---|---|
| negative (pulled earlier) | 119 | 5.3% |
| 0–45 days | 640 | 28.3% |
| 46–100 days (~one quarter) | 560 | 24.8% |
| 101–200 days | 354 | 15.6% |
| 201–400 days | 344 | 15.2% |
| > 400 days | 245 | 10.8% |

Median 90 days. But **41% of revisions exceed 100 days** — this is real re-planning,
not clerical rounding.

### 3.4 Fields that are empty in the public feed `[MEASURED]`

Fill rate, 2026-07 snapshot (n=1,775):

| populated | empty (0%) |
|---|---|
| ProjectId, ProjectName, SectorName, LineMinistry, COMPANYNAME (100%) | StateName |
| OriginalCost (100%), OriginalEndDate (100%) | AgencyName, AgencyId |
| SanctionDate (99.3%) | StartDate, CreationDate |
| PhysicalProgress (94.8%) | **RevisedCostReason** |
| Expenditure (92.4%) | **RevisedDateReason** |
| RevisedDate (80.4%) | **Remarks** |
| RevisedCost (53.1%) | DELAYED_TIME, COST_OVERRUN, COR_PERC, TOR_PERC, OnboardingDelay |

**Consequence we must not paper over:** the three free-text fields are empty in the
public feed. **We cannot do text mining on revision reasons.** Any pitch promising
"LLM analysis of delay narratives" from public data is not deliverable. See
`04_RISKS_AND_GAPS.md` §2.

The derived overrun columns are also empty — so we compute overruns ourselves, which
is precisely how we control the leakage in §2.1.

---

## 4. Answering PS clause (c) rigorously — the part almost nobody can attempt

> *"...an assessment of the extent to which predictive performance is attributable to
> the current CUF fields vis-à-vis additional variables not presently captured in the CUF."*

This clause asks a **measurement-design** question, which is MoSPI's actual discipline.
It cannot be answered from one snapshot. We can answer it because we have the panel.

### 4.1 The single most valuable variable is not a field at all — it is history `[MEASURED]`

The CUF is a *form*: it captures the current state of a project. But the strongest
non-trivial predictors we found are **derived from the time series**, which no form captures:

- prior revision count (AUC 0.623 **on its own**)
- 3-month change in physical progress (stall detection)
- 3-month change in expenditure
- progress-vs-spend divergence trajectory

**Finding to present:** MoSPI does not need new *questions* on the form. It needs to
retain and expose the *history of answers it already collects*. That is a cheap,
concrete, actionable recommendation.

### 4.2 A candidate new field, honestly tested and honestly rejected `[MEASURED]`

Hypothesis: *agency portfolio congestion* (how many projects an agency runs at once) —
not a CUF field — should predict revisions.

Descriptively, it looks compelling:

| agency portfolio size | revision rate |
|---|---|
| 1–5 projects | 4.8% |
| 6–20 | 4.4% |
| 21–50 | 9.7% |
| 51–150 | 9.7% |
| **150+** | **20.8%** |

A 4.3× spread. NHAI alone runs 521 concurrent projects; MoRTH 315; NHIDCL 157.

**But when added to the model it made things worse:**

```
CUF-derived features only    AUC = 0.8830   PR = 0.7263
+ agency portfolio load      AUC = 0.8631   PR = 0.6556   ← WORSE
```

The apparent effect is **confounded with sector** (the mega-portfolio agencies are
roads agencies), and sector is already in the model. Portfolio load adds nothing
incremental and costs generalisation.

> **This negative result is worth more than a positive one.** It demonstrates a
> *protocol* for deciding whether a proposed new CUF field earns its place on a
> national statistical form — descriptive association is not sufficient evidence.
> Delivering that protocol is a policy contribution, not just a model.

### 4.3 What the literature says is missing — and it is not on the form `[LIT]`

Ram Singh (Delhi School of Economics), *"Delays and Cost Overruns in Infrastructure
Projects: Extent, Causes and Remedies"*, **Economic & Political Weekly** — the canonical
Indian study, **894 projects across 17 sectors**, built on this very MoSPI data series.

Findings: **contractual and institutional failures are economically and statistically
significant** causes of overruns. The literature he surveys identifies the dominant
causes as: **land acquisition delays, utility shifting, environmental and
inter-ministerial clearances, shortage of funds, litigation, contractual disputes.**

Sector baselines from that paper (mean cost overrun / % of projects delayed):

| sector | mean cost overrun | % delayed |
|---|---|---|
| Railways | 94.8% | 98.4% |
| Power | 51.9% | 60.8% |
| Roads & Highways | 15.8% | 85.4% |
| Petroleum | −16.1% | 79.7% |
| Shipping & Ports | −1.4% | 95.1% |
| Steel | −15.9% | 81.4% |

His policy recommendation: prefer **fixed-price over item-rate EPC contracts**, because
under item-rate contracts "neither government officials nor the contractors have
incentives to take the contracts seriously."

**The clause (c) answer, stated plainly:**
> Not one of the causes the canonical study identifies — land acquisition status,
> clearance status, contract type, litigation status — is a CUF field. The CUF records
> *symptoms* (cost, date, progress) and omits *causes*. We measure how far symptoms
> alone can take you (AUC 0.88 for revision timing; far weaker for cost magnitude —
> §5), and we name the specific missing fields with citation.

---

## 4.5 WHY MoSPI IS ASKING — researched, not speculated `[VERIFIED]`

This matters more than any model detail: it tells us what a winning submission looks like.

### The institutional answer

**MoSPI has a formal, funded programme whose entire purpose is to source exactly this.**

From MoSPI's own *"Scope of Work for setting up Data Innovation Lab"* (primary source,
`mospi.gov.in/uploads/documents/researchProposals/…-Srl14.docx`):

> *"In July, 25, **Data Innovation Lab** component of the **Capacity development scheme**
> was operationalised with the objective to introduce new and emerging technologies in
> the work flow of official statistics. … At present **eleven use cases have been
> identified and pilots on 8 of them are under progress.** In addition, collaboration
> with different academic institutions by way of signing the MoU has been another
> prominent outcome."*

Timeline:

| when | what |
|---|---|
| Jul 2024 | DI Lab guidelines notified |
| **Jul 2025** | DI Lab **operationalised** (Capacity Development Scheme) |
| Sep 2025 | PAIMANA replaces OCMS-2006 (25 Sep 2025, per PIB) |
| Feb 2026 | PAIMANA project-monitoring module operationalised |
| **now** | NSO still commissioning the **DPR** for the permanent Data Innovation Lab |

**They are not ignoring this. They are thirteen months into building the institution that
does it, and they are still writing the business plan for the permanent version.**

### Five concrete reasons the work isn't done in-house `[VERIFIED]`

1. **DIID issued this PS, not IPMD.** IPMD owns the project data. DIID is the
   *innovation* arm, whose mandate (mospi.gov.in/about-us/diid) is *"providing technical
   inputs/advice to various divisions … in conceptualizing and planning of projects of
   divisions"* and *"Implementation of Data Innovation-Lab component of the Capacity
   Development Scheme."* **A capability-building division is sourcing capability for an
   operational division.** That is the mechanism, working as designed.
2. **Sourcing externally is written into the plan.** The DPR scope requires *"Evaluation
   of alternative models of implementation (procurement-based, **academic collaboration**,
   hybrid, and consortium)."* SIH is the cheapest instance of that.
3. **The platform itself is outsourced.** PAIMANA was built by **NeGD (MeitY)**, not
   in-house. Limited internal build capacity is a documented fact, not an inference.
4. **They have been migrating, not analysing.** PAIMANA is ~8 months old as OCMS's
   replacement; `/ReportPage` still says "Coming Soon."
5. **The definitive study of their own data was done by an outsider** — Ram Singh at the
   Delhi School of Economics (§4.3), not by MoSPI.

### The finding that should close our pitch `[VERIFIED]`

The DPR's governance workstream specifies what the DI Lab must produce:

> Workstream C — *"Draft governance policies covering data access, **model validation,
> audit, and versioning**. Develop human-centric AI guidelines including bias mitigation,
> **explainability**, and **transparency** requirements."*
>
> Guiding principle — *"human-centric data science and AI ensuring that innovations serve
> public good, uphold transparency, **preserve quality and comparability, and strengthen
> trust in official statistics**."*
>
> Workstream D — *"Develop roadmap for phased rollout (**Pilot → Scale → Production**)."*

Now compare against what we built **before reading any of this**:

| MoSPI's stated requirement | our component |
|---|---|
| model validation | **leakage linter** (`POST /lint`) |
| audit | **hash-chained harvest log**, `src_sha256` on every row |
| versioning | **model manifest**, refuses to score on a stale feature set |
| explainability | **SHAP** per project |
| transparency / trust | **calibration + ECE + abstention** |
| preserve quality | **data integrity monitor** (427/212/119) |
| Pilot → Scale → Production | architecture §9, §11 (deliberate omissions listed) |

**We independently built the governance framework they are currently paying a consultant
to specify.** That is the strongest single argument available to us, and it is verifiable
from their own published document.

### What this changes about the pitch

They are not shopping for the highest accuracy. They are building a **capability with
governance**, and their scheme is explicitly a *proof-of-concept* pipeline
(`Pilot → Scale → Production`). So the winning submission is the one that looks
**adoptable by a division**: validated, auditable, versioned, explainable, and honest
about its limits.

That is what we have. Lead with it.

---

## 4.6 External validation of our harvest `[VERIFIED]`

MoSPI's own published Flash Reports match our snapshots exactly:

| MoSPI published | our snapshot |
|---|---|
| April 2026 Flash Report — **1,981 projects** | `2026-04.json` → **1,981 rows** |
| July 2026 Flash Report — **1,775 projects, ₹37.11 lakh crore** | `2026-07.json` → **1,775 rows**, revised cost total **₹37.11 lakh crore** |

Three independent figures, three exact matches. **Our panel is their official series.**
Put this on the feasibility slide — it costs one line and pre-empts "did you scrape
something unofficial?"

---

## 4.7 WHO CONSUMES THIS — the real decision we are serving `[VERIFIED]`

§4.5 answered *why they're asking*. This answers *what the output is actually for*, and it
reframes the product.

### IPMD does not build projects. It escalates them.

From MoSPI's own IPMD mandate page (`mospi.gov.in/about-us/ipmd`):

> *"IPMD plays a crucial role in **identifying projects falling behind schedule or
> experiencing cost overruns and apprises to PMO / CabSec / NITI Aayog** and
> Administrative Ministries/Departments through periodic communications."*

And from PAIMANA's own About-IPMD page:

> *"(d) the data collected through the OCMS portal is utilized to generate inputs for
> several **high-level meetings, including the PRAGATI monthly review, the Prime
> Minister's State visits**, for addressing **Parliamentary Questions** and requests
> under the **Right to Information (RTI) Act**."*

> *"(c) The IPMD serves as a crucial facilitator in **identifying projects falling behind
> schedule** … during the regular project review meetings with the respective
> Administrative Ministries."*

**IPMD's product is an agenda.** Each month it decides which projects get named in front
of the Prime Minister, the Cabinet Secretary, and NITI Aayog. PRAGATI reviews roughly
five projects per sitting. **The real decision is: which five, out of 1,981?**

That is exactly what a ranked watchlist is for. Our top-50 list is not a dashboard
feature — it is a first draft of the PRAGATI shortlist.

### Why this makes governance the product, not the polish

Escalation is an inherently political act: naming another ministry's project in front of
the PMO. The person doing it needs a **defensible basis** — not a hunch.

That is why the DI Lab DPR demands *model validation, audit, versioning, explainability*
(§4.5). Those are not academic virtues. They are what you need when a line ministry pushes
back on why *their* project was on the list.

| IPMD's exposure | what answers it |
|---|---|
| "why was my project escalated?" | SHAP drivers + the panel timeline |
| "your model is wrong" | calibration, ECE, forward-time evaluation |
| Parliamentary Question / RTI on the figures | hash-chained provenance to raw snapshot |
| "why did last month's list differ?" | model manifest + versioning |
| weak evidence | **abstention** — don't escalate what you can't defend |

**Reframe for the pitch:** we are not selling accuracy. We are selling *defensible
escalation*. The moat (§4.1–4.3 of the spec) is the product.

### The uncomfortable corollary — handle with care

Our measured finding that **"is it overdue?" scores AUC 0.472, worse than random**
(§2.3) is not just a modelling curiosity. If escalation today leans on visible delay,
then the current shortlist may be systematically selecting the wrong projects.

**Do not say that on stage.** Say: *"the most visible signal turns out not to predict the
next revision — which suggests the shortlist could be built on something sharper."*
Same content, no accusation.

### Top-down pressure, documented `[VERIFIED]`

> *"Following the principle of **one data, one entry** and basis the **recommendation by
> PMO / NITI Aayog**, the integration of old MoSPI's OCMS portal and DPIIT's IIG-PMG
> portal is underway."*

The modernisation was directed from above. This is not a discretionary project.

---

## 4.8 A field they announced, that is empty `[MEASURED + VERIFIED]`

MoSPI's IPMD page states:

> *"this Ministry has introduced a robust approach for the **standardization of key
> monitoring metrics namely Time Overrun & Cost Overrun** at Pre-construction &
> Construction stage by **introducing the concept of 'Project Start Date'** besides the
> Project Sanction date."*

We checked `StartDate` across **all 13 snapshots, all 18,601 rows**:

| snapshot | StartDate fill |
|---|---|
| 2025-07 … 2026-07, every month | **0.0%** |

**The field introduced to standardise overrun measurement is empty in every snapshot we
hold.** Without it, Time Overrun cannot be split into pre-construction versus
construction delay — which is the distinction they said they wanted.

*Fair counterweight, and say it:* `SanctionDate` fill rose from **64.6% (Jul 2025) to
99.3% (Jul 2026)**. Data quality is actively improving. This is a gap in an improving
system, not a broken one — frame it that way.

This is the cleanest possible clause-(c) example: **a needed field was identified, added,
and is not being populated.** We can show that in one line, from their own data.

---

## 4.9 A second use case we are NOT building — but should name `[VERIFIED]`

IPMD also *"facilitates the appraisal and approval of projects by providing quality inputs
to … Public Investment Board (PIB), Delegated Investment Board (DIB), Cabinet Committee on
Infrastructure, Expanded Board for Railways."*

So the same division that monitors overruns also advises on **approving new projects**.
Historical overrun patterns by sector/agency are directly relevant to appraising a new
proposal — predicting overrun risk *at sanction time, before money is committed.*

**We cannot build this**: our panel only observes projects post-sanction, and we have no
pre-sanction features. Do not claim it.

**Do name it as roadmap.** It shows we understand the division's full mandate, and it is
the natural Phase-2 of a `Pilot → Scale → Production` pathway.

---

## 4.10 WHAT THIS COSTS MoSPI — the actual economics `[VERIFIED]`

Researched from primary sources, because the premise "they pay ₹1.5 lakh" is wrong.

### What the posing organisation actually pays

From **sih.gov.in/faqs**, verbatim:

> *"An amount of **Rs 2.50 Lakh for Software** and Rs. 3.55 Lakh for Hardware **per problem
> statement shall be given by the organisation posing the challenges.** In addition to this
> amount, registration fee of Rs 25000/- per company is applicable. Registration fee is only
> applicable for private companies, PSU, MSME, NGO etc. **There is no registration fee for
> government departments/ministries/attached offices of ministries.**"*

> *"The **Prize money** for both categories (Hardware/Software) is **INR 1.5 Lakh**."*

So: **MoSPI pays ₹2.50 lakh per software PS**, of which ₹1.5 lakh reaches the winning team.
Ministries pay no registration fee.

### MoSPI's total outlay `[MEASURED from the PS file]`

MoSPI posted **4 software problem statements, all from DIID** — the same innovation
division identified in §4.5:

| PS | title |
|---|---|
| 26056 | Real-time Airfare Price Index |
| 26101 | AI-enabled learning platform |
| 26102 | AI-powered anomaly / fraud detection |
| **26103** | **PAIMANA project monitoring** ← ours |

**4 × ₹2.5 lakh = ₹10 lakh.** That is MoSPI's entire SIH 2026 spend.

### What ₹2.5 lakh buys, compared with their own instruments `[VERIFIED]`

MoSPI funds research through the **Grant-in-Aid component of the Capacity Development
Scheme** — the *same scheme* that funds the DI Lab (§4.5). Published rates:

| instrument | cost | what you get |
|---|---|---|
| **SIH problem statement** | **₹2.5 lakh** | ~200–500 teams attempt it in parallel |
| Minor Research Project | **₹15 lakh** / 12 months | one institution, one approach |
| Research Study | up to **₹50 lakh** (₹100 lakh exceptional) | one institution, one approach |
| Fellowship | ₹1.25 lakh/month + ₹7 lakh/yr grant, 5 yrs | one researcher |
| DI Lab DPR consultancy | 20 weeks, agency-run | design docs, RFP pack, *"all code shall be property of NSO"* |

**SIH is roughly 6× cheaper than the cheapest research grant MoSPI has**, and instead of
one institution it puts hundreds of teams on the same problem simultaneously.

SIH 2026 overall: **226 problem statements (172 software + 54 hardware), 50,000+ teams
expected**. Across all posing organisations that is ≈ **₹6.2 crore** total
(172×₹2.5L + 54×₹3.55L) — for 50,000 teams. Order of **₹500–1,200 per team-attempt**.

### The honest reading

At ₹2.5 lakh MoSPI is **not procuring a deliverable.** Note the contrast with the DI Lab
DPR, where the scope explicitly states *"All documents, data, and code generated shall be
property of NSO"* — SIH carries no such transfer, no contract, and no obligation on
either side.

What they are buying is **option value**: parallel exploration of a use case at the
cheapest rate available to them, from which they can pick any approach and pursue it
later through a proper instrument (grant, fellowship, or procurement).

**This is the portfolio, and SIH is its widest, cheapest funnel:**

```
SIH  ₹2.5L/PS   →  hundreds of approaches, no commitment      ← we are here
Minor grant ₹15L →  one team, 12 months, a real study
Research study ₹50L → one institution, deeper
Fellowship / DPR  →  build the permanent capability
```

**What this means for the pitch:** they are not evaluating us as a vendor delivering
₹2.5 lakh of work. They are scanning for an approach worth graduating to the next rung.
So "adoptable" beats "impressive", and a `Pilot → Scale → Production` story (their own
DPR's words, §4.5) is what moves us up the ladder.

---

## 4.11 WHAT MoSPI ACTUALLY GETS — the deal structure `[VERIFIED]`

§4.10 established the price (₹2.5 lakh/PS). This is what it buys, from
**sih.gov.in/projectImplementation** — *"Guidelines for Deployment of Smart India
Hackathon Winning Projects"*, the official post-hackathon contract.

### The answer, in one clause

> *"The **Intellectual Property (IP) of the solution resides with the students** who have
> developed and deployed the solution post-Hackathon **but the concerned ministry will
> have lifetime access to the solution for free.** This has been done to encourage
> Startups to be created out of the developed solutions while also keeping in mind the
> interest of the involved ministries."*

**MoSPI is buying a perpetual free licence, not ownership.** That is the entire trade,
and it explains the price. Compare the DI Lab DPR consultancy (§4.10), where the scope
says *"all documents, data, and code generated shall be property of NSO"* — full IP,
much higher cost. SIH gives up ownership to get the price down by an order of magnitude.

### The post-win pathway is a documented programme, not a handshake

| guideline | detail |
|---|---|
| duration | **6 months to 1 year** of development after the win |
| contact | MoE/AICTE hand team details to the ministry, which initiates directly |
| plan | ministry requests a detailed project plan with tools and timelines |
| procurement | **ministry procures** the commercial software/hardware needed |
| oversight | an autonomous/technical agency, **or a panel of experts**, coordinates |
| mentor | **minimum one experienced technical expert per solution** |
| cadence | weekly/monthly video monitoring sessions |
| **stipend** | **₹10,000–15,000/month per member, minimum 6 months, max 6 students** |
| travel | ministry bears travel/stay for site visits |
| security | a cybersecurity expert engaged for software solutions |
| reporting | ministry files **quarterly status reports** to MIC and AICTE |
| institution | written consent required; **no financial burden on the college** |

MoE is also candid about the starting quality:

> *"projects developed during Hackathons are usually **very crude and absolutely not ready
> for field implementation** … They require considerable work or development before
> implementation/deployment as reliable, dependable solutions."*

### How often does adoption actually happen `[VERIFIED — PIB, MoE, 11 Dec 2024]`

PIB publishes a section titled *"Solutions Implemented by Government Ministries"*:

| | |
|---|---|
| SIH 2022 | **24 projects successfully implemented** (water, social welfare, education, Ayush, science, defence) |
| SIH 2023 | **30 projects successfully implemented** (I&B, power, Ayush, water, animal rearing, disaster management, science, technology, railway, administration) |
| Ministry of Ayush | 8 solutions accepted till 2022 — **4 funded by AICTE, 4 funded directly by the ministry** |
| ISRO | 4 accepted **for in-house development** |
| DRDO | 1 accepted |

Against roughly **250 problem statements per edition**, 24–30 implementations is on the
order of **10%**. Ecosystem-wide: **100+ startups and 9,654 SIH alumni** via the YUKTI
National Innovation Repository; 13.91 lakh students since 2017.

**The honest reading of both sides:** a widely-repeated criticism is that *"despite years
of SIH, no solution has become widely adopted — mainly due to lack of post-hackathon
support."* That is **too strong** — 24 and 30 implementations are documented in a PIB
release. But ~10% is the realistic base rate, and it requires 6–12 months of further work
after the trophy. Note also ISRO's model: solutions accepted **for in-house development**,
i.e. the ministry takes the idea, not necessarily the team.

### What this means for us

| | value |
|---|---|
| prize | ₹1.5 lakh |
| stipend if adopted | ₹10–15k/month × up to 6 members × ≥6 months ≈ **₹3.6–5.4 lakh** |
| tooling | ministry procures what the build needs |
| mentorship | a MoSPI technical expert assigned, weekly/monthly reviews |
| **IP** | **stays with us** — explicitly so a startup can be founded on it |
| ministry gets | lifetime free access |

**So the prize is the smallest part of the prize.** The real asset is a 6–12 month funded
engagement with DIID, retained IP, and a ministry that has lifetime access rather than
ownership — which is exactly the structure a product gets built on.

**Pitch consequence:** win-and-walk-away is not the game. The deck should read like the
opening of a 6–12 month engagement — which is what `Pilot → Scale → Production`
(§4.5, their own DPR's words) already frames. Slide 4's roadmap should implicitly answer
*"what would the first six months after the finale look like?"*, because that is the
decision the ministry is actually making.

---

## 4.12 DOES IT SAVE THEM MONEY? — tested, and mostly NO `[MEASURED]`

The tempting pitch is *"₹3.4 lakh crore of overrun — we save a slice of it."* We tested
the mechanism that claim depends on. **It does not hold in our data.**

### The test: does a schedule slip lead to a cost increase?

The chain the ROI claim needs is: *we flag → intervention → less delay → less cost
escalation.* So: after a project's deadline moves, does a cost revision follow?

| | rate of a cost revision within 6 months |
|---|---|
| after a schedule slip (n=1,904) | **1.94%** |
| no slip (n=14,454) | **5.05%** |
| relative risk | **0.38× — the OPPOSITE direction** |

**A slip is associated with *fewer* subsequent cost revisions, not more.** Plausibly a
project that just had its schedule revised has been through an administrative review that
settled cost at the same time; or 13 months is too short to see the long-run relationship
the literature describes across full project lifecycles.

Either way: **we cannot claim savings through avoided cost escalation.** Do not put a
rupee ROI figure on a slide. It would be the easiest thing in the deck to destroy.

### Three more reasons a savings claim would be dishonest

1. **We predict revisions; we do not prevent them.** Between our flag and a rupee saved
   sit three links we do not control — escalation, ministerial attention, and whether the
   blocker is even actionable (§4.4: the *why* field is empty).
2. **No counterfactual exists.** Nobody has ever acted on our shortlist. Demonstrating
   savings needs flagged-and-escalated projects compared against matched controls.
3. **A slip is not automatically a cost.** Many revisions are schedule-only. Conflating
   time overrun with cost overrun is the same category error as §2.1.

### What IS defensible

| claim | status |
|---|---|
| "Saves ₹X crore" | **NO** — untestable here, and the mechanism failed |
| Triage: 1,981 → 50 at 94% precision | **YES**, measured |
| Redirects the scarcest resource — PMO/PRAGATI attention — off a signal that scores 0.472 | **YES**, measured |
| Surfaces 768 data-quality findings in a series that feeds Parliamentary Questions and RTI replies | **YES**, measured |
| Delivers assets earlier (public value, not a "saving") | plausible, **unquantified** |

### The right answer when a judge asks "how much will this save?"

> *"We can't responsibly quantify that yet — and we tested the obvious mechanism. In our
> panel a schedule slip is followed by* fewer *cost revisions, not more, so we won't
> claim savings through avoided escalation. What we can show is that the shortlist is
> right 47 times out of 50, and that the signal being used today scores worse than a coin
> flip. Measuring the rupee value needs a pilot: run the shortlist for six months, track
> which flagged projects were escalated, and compare their slip against matched controls.
> That is exactly what the first six months of deployment should be designed to answer."*

That answer is stronger than a fabricated ROI, and it converts the question into a
proposal for the 6–12 month engagement (§4.11).

---

## 4.13 EXACT MATCH AGAINST THE PROBLEM STATEMENT `[VERIFIED]`

The PS states: *"As of April 2026, the PAIMANA project-monitoring framework tracks 1,981
ongoing infrastructure projects … aggregate original cost of approximately ₹37.13 lakh
crore, revised cost of approximately ₹42.78 lakh crore and cumulative expenditure of
approximately ₹20.36 lakh crore."*

Computed from our own 2026-04 snapshot:

| quantity | PS text | our panel |
|---|---|---|
| projects | 1,981 | **1,981** |
| original cost | ₹37.13 lakh cr | **₹37.13 lakh cr** |
| revised cost | ₹42.78 lakh cr | **₹42.78 lakh cr** |
| cumulative expenditure | ₹20.36 lakh cr | **₹20.36 lakh cr** |

**Four independent quantities, exact to two decimals.** We are demonstrably reading the
same source the ministry wrote the problem statement from. One line on the feasibility
slide; it pre-empts every question about data provenance at once.

---

## 5. Where we are weak — stated up front `[MEASURED]`

**Cost revisions are rare and we predict them poorly.**

| event | count | rate of transitions |
|---|---|---|
| schedule revision | 2,253 | 13.81% |
| **cost revision** | **163** | **1.00%** |

163 positives is thin. Any cost-overrun classifier we present will have wide
uncertainty. **We will report it with calibrated confidence and an abstention band
rather than a headline accuracy number.** See `01_SOLUTION_SPEC.md` §4.

Do not let the PPT imply cost and schedule prediction are equally solved. They are not.

---

## 6. Reproduction

```bash
cd "SIH RESEARCH/paimana"
python3 harvest.py          # re-pull all 13 snapshots (idempotent, rate-limited)
python3 panel.py            # -> data/panel.parquet
python3 train.py --report   # reproduces every number in §2
python3 audit.py            # reproduces §3.2, §3.3
python3 ablation.py         # reproduces §4
```

Raw snapshots already on disk: `data/raw/2025-07.json` … `data/raw/2026-07.json`

---

## 7. The five things to remember

1. **We have a 13-month panel of 2,243 central infrastructure projects that the portal
   itself does not retain.** 18,601 project-months. Nobody else will have it.
2. **The obvious model is subtraction** — R²=1.0, coefficients −1 and +1. We can prove
   it on stage in one slide.
3. **The honest model works**: AUC 0.883 (0.892 within-regime), 94% precision on the
   top-50 watchlist, forward time split.
4. **The heuristic in use today is worse than random** (overdue: AUC 0.472).
5. **We found a 12× structural break and 758 integrity anomalies in a live national
   statistical series** — and MoSPI is the ministry whose job is data quality.
