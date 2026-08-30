# PAIMANA Foresight — Solution Specification

**PS:** SIH26103 · MoSPI (Data Informatics & Innovation Division) · deadline 20 Sep 2026
**Priority:** team's **pick 2** (pick 1 = PS 26018 Land Records) — see `04_RISKS_AND_GAPS.md` §6.2
**One line:** *We rebuild the project history PAIMANA doesn't keep, and use it to flag
revisions before they are filed — with calibrated confidence and an audit trail.*

---

## 1. The framing decision (everything follows from this)

The PS says *"predict cost overruns and time overruns."* Read literally, that is a
column the portal already displays, and modelling it yields R²=1.0 by subtraction
(`00_FINDINGS.md` §2.1).

We reframe to the decision the ministry actually faces each month:

| | today | with Foresight |
|---|---|---|
| question | "which projects are late?" | "which projects are **about to slip**?" |
| answer source | the portal already shows it | ranked watchlist, 94% precision @ top-50 |
| timing | after the revision is filed | **before** |
| action | record it | intervene |

**We state the reframe explicitly on the slide and justify it with the R²=1.0 proof.**
That converts our biggest risk (judges thinking we ignored the brief) into our
strongest moment.

> Guardrail: we still ship the literal deliverables (a) and (b) from the PS outcome
> list. We do not substitute — we deliver both, and show why one of them is degenerate.

---

## 2. System architecture

```
┌─ INGEST ───────────────────────────────────────────────────────┐
│  harvest.py   monthly snapshot puller (CSRF session, 2.5s rate │
│               limit, robots-respecting, full request log)      │
│                          ↓                                      │
│               data/raw/YYYY-MM.json   (immutable, hash-logged)  │
└────────────────────────────────────────────────────────────────┘
                           ↓
┌─ DETERMINISTIC CORE  (no LLM touches anything in this box) ────┐
│  panel.py      snapshots → project-month panel (SQLite+parquet)│
│  features.py   point-in-time features  ⟵ LEAKAGE LINTER        │
│  train.py      HistGB + isotonic calibration + time-split eval │
│  score.py      monthly risk scores + abstention band           │
│  audit.py      data-integrity monitor (§3.2 anomalies)         │
│  ablation.py   CUF sufficiency protocol (PS clause c)          │
└────────────────────────────────────────────────────────────────┘
                           ↓
┌─ SERVE ────────────────────────────────────────────────────────┐
│  api.py        FastAPI: /watchlist /project/{id} /explain      │
│                /audit /ablation                                 │
│  assistant.py  LLM: NL → parameterised SQL over the panel.      │
│                Reads numbers, never computes them.              │
│  ui/           Next.js + D3: watchlist, project timeline,       │
│                SHAP waterfall, integrity feed, ablation view    │
└────────────────────────────────────────────────────────────────┘
```

**Stack** (all open-source, as the PS requires; all already in the team's stack):
Python · pandas · scikit-learn · SQLite · FastAPI · Next.js/React/D3 · Docker.
LLM: self-hosted quantised model via vLLM (no external API — matters for a ministry).

---

## 3. Modules → PS expected outcomes

The PS lists nine indicative outcomes (a–i). **We cover all nine.** Most teams will
cover three or four.

| PS outcome | our module | status |
|---|---|---|
| (a) Cost Overrun Prediction Model | `train.py --target cost` | ships, **with honest weak-signal reporting** (163 events) |
| (b) Time Overrun Prediction Model | `train.py --target schedule` | ships, AUC 0.883 |
| (c) Project Risk Scoring Framework | `score.py` — calibrated 0–100 composite | ships |
| (d) Early Warning Alert System | `/watchlist` + abstention band | ships |
| (e) Benchmarking & Comparative Analytics | sector/agency peer percentiles | ships |
| (f) Cost Escalation Driver Analysis | SHAP waterfall per project | ships |
| (g) AI-powered Monitoring Dashboard | `ui/` | ships |
| (h) LLM Project Intelligence Assistant | `assistant.py`, grounded | ships |
| (i) Documentation & deployment framework | Docker + this repo | ships |
| **+ not asked for** | **Data Integrity Monitor** (`audit.py`) | our addition |
| **+ not asked for** | **CUF Sufficiency Protocol** (`ablation.py`) | our addition |
| **+ not asked for** | **Leakage Linter** | our addition |

---

## 4. The three things that are actually ours

Everything above the line is table stakes — a competent team ships a dashboard and a
gradient booster. These three are the differentiators.

### 4.1 The Leakage Linter

A guard that refuses to train on any feature not computable from information available
at time *t*. Implemented as a hard assertion in `features.py`: every feature declares
the snapshot months it reads; the linter fails the build if any feature reads *t+k*.

Why it matters: it is the *institutional* version of our §2.1 finding. MoSPI will
receive many student models claiming >0.9 accuracy. **We hand them a tool to tell which
ones are real.** For a ministry whose product is trustworthy statistics, a
methodology-checking tool is more valuable than one more model.

*On stage:* "We ran your data through our own linter first. The obvious model fails it."

### 4.2 Calibrated confidence with abstention

The score is not a raw probability from a classifier. It is:
- **isotonic-calibrated** on a held-out fold, reported with **ECE** and a reliability diagram
- **banded**: high-confidence flag → watchlist; **low-confidence → abstain and route to
  a human**, never a silent guess
- for cost revisions (163 events) the abstention band is *wide, on purpose, and shown*

Why it matters: an early-warning system that cries wolf is switched off within a
quarter. Precision@top-50 = 94% is the number an officer cares about, not AUC.
Abstention is what makes that number hold.

*This is the same architectural moat the team is using on PS 26018 — deterministic core,
calibrated confidence, human-in-the-loop, hash-chained audit log. Reuse it.*

### 4.3 The CUF Sufficiency Protocol (PS clause c, answered properly)

A repeatable test for *"does this proposed new field earn its place on the form?"*:

1. establish the CUF-only baseline (time-split AUC/PR)
2. add the candidate variable
3. measure **incremental** performance, sector-controlled
4. report the delta with a confidence interval — including when it is **negative**

We already ran it once and got a negative result (agency portfolio load: 0.883 → 0.863,
`00_FINDINGS.md` §4.2). We present that negative result deliberately.

*On stage:* "The variable that looked most promising failed. That is the protocol
working. This is what you need before you add a field to a national form."


---

## 4.4 How the shortlist is actually decided (the triage score)

`00_FINDINGS.md` §4.7 established that IPMD's real job is choosing which projects get
escalated to PMO/PRAGATI. **"Probability of slipping" is not the same as "worth
escalating."** The scoring must reflect that.

### Three ingredients we can compute

| ingredient | question | source |
|---|---|---|
| **Risk** | will it be revised in the next 3 months? | calibrated model, AUC 0.883 |
| **Stakes** | how much money is exposed? | `(cost − expenditure)` still unspent |
| **Salvageability** | is there still time for intervention to land? | `0 < months_to_due ≤ 12` and not already stuck > 3 years |

```
exposure  = P(revision) × unspent_cost
shortlist = top-N by exposure, among savable projects only
```

### The one ingredient we cannot compute — and must not fake

**Actionability:** would PM attention actually unblock this? A project stalled on a court
case is not fixed by a review meeting; one stalled on a state land clearance very much is.

That distinction lives in `RevisedDateReason`, which is **0% populated** in the public
feed (`00_FINDINGS.md` §3.4). **We cannot rank on it.** The human at IPMD can — they sit
in the review meetings and know which blockers are political rather than legal.

**So the division of labour is:** the system takes 1,981 → ~50, ranked and evidenced.
The officer takes 50 → 5. That is not a limitation we're apologising for; it is the
human-in-the-loop design, and it is why the tool is adoptable.

### Measured trade-off — report it honestly

April 2026 pool, 1,952 projects:

| ranking | precision @ top-8 | what it picks |
|---|---|---|
| pure model risk | **1.00** | certain to slip, but small (₹394–2,374 cr unspent) |
| exposure, unfiltered | — | big money, but 2 of top 3 **already past due** — too late to act |
| **exposure + savable filter** | **0.75** | ₹2,600–3,500 cr, due in 2–9 months, still actionable |

**Precision drops from 1.00 to 0.75, deliberately.** We trade prediction accuracy for
stakes and timing, because a perfect list of trivial or already-lost projects is worth
less to IPMD than a good list of large savable ones. Say this out loud — it shows the
objective was chosen, not stumbled into.

### Two design cautions

1. **Sector concentration.** The triage top-8 is almost entirely Roads & Highways —
   plausibly just NHAI's portfolio size (521 concurrent projects). A shortlist that hands
   the PM the same sector every month is not useful. **Add per-sector caps or
   within-sector ranking** before this is presented as an agenda.
2. **"False positives" may be filed late, not wrong.** One flagged project (Vadodara–Mumbai
   Jujuwa–Gandhar, 5% built, 7.5 months to due, p=0.92) was *not* revised in the window.
   At 5% built it almost certainly should have been. We score it as a miss and cannot
   prove otherwise — but do not over-tune against cases like this.

---

## 5. What the demo looks like (90 seconds)

1. **The trap.** One chart: R² = 1.0, coefficients −1.000 and +1.000. "This is the model
   we did not build."
2. **The panel.** 13 snapshots stacking into a timeline for one real project —
   Imphal Airport, expenditure going *down* between two months.
3. **The watchlist.** July 2026, top 50 projects by revision risk. Reveal: 47 of 50 were
   in fact revised. Officer-facing, sorted, with a reason per row.
4. **One project drill-down.** SHAP waterfall: why this project is flagged.
5. **The integrity feed.** 427 expenditure reversals, the −₹175,291 crore outlier, the
   March 2026 structural break.
6. **The abstention.** A cost-revision case where the system says *"insufficient
   confidence — routing to analyst"* instead of guessing.

Step 6 is the one that wins it. Everyone shows accuracy; almost nobody shows restraint.

---

## 6. Non-goals (say these out loud; they buy credibility)

- **We do not mine free-text delay reasons.** `RevisedCostReason`, `RevisedDateReason`
  and `Remarks` are empty in the public feed. With MoSPI's internal data the module
  drops in; we will not claim it works today.
- **We do not have two decades of OCMS history.** The PS mentions it; the public
  endpoint exposes 13 months. Our method scales to the archive — we say so, and we do
  not pretend to have it.
- **We do not predict *why* a project will slip.** We predict *that* it will, and show
  which observable factors drove the score. Causal attribution needs the fields the CUF
  does not collect (§4.3).
- **We do not replace the officer.** Abstention and human routing are designed in.

---

## 7. Ethics & compliance

- Public data, no authentication bypassed, no login used.
- 2.5s inter-request delay; 13 requests total per full harvest; full request log with
  timestamps retained and shown on request.
- `robots.txt` returns 404 (no policy published); we still throttle conservatively.
- No personal data involved — projects and agencies, not individuals.
- Every published figure traceable to a raw snapshot file by content hash.
