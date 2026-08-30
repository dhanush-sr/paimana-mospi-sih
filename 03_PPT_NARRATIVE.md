# PPT Narrative — 6 slides

**Format rules (from the official template):** max 6 slides *including* title · no
paragraphs, use points/diagrams/infographics · must use the provided template unchanged ·
submit as **PDF only**.

**The through-line, one sentence:**
> *The portal already tells you which projects are late. We tell you which ones are
> about to become late — and we can prove the obvious way of doing that is arithmetic.*

---

## Slide 1 — Title

Fill exactly as the template requires: PS ID **SIH26103** · title *"Use case on
web-based integrated project-monitoring platform"* · Theme **Smart Automation** ·
Category **Software** · Team ID · Team Name.

Nothing else. Do not decorate the title slide.

---

## Slide 2 — Proposed Solution

**Headline: "The model everyone will build is subtraction."**

Left half — the trap, as a single figure:
```
Time Overrun  =  RevisedDate − OriginalEndDate

Predict it from those same two columns:
      R² = 1.0000
      coefficient(OriginalEndDate) = −1.000
      coefficient(RevisedDate)     = +1.000
```
Caption: *A perfect score, and no information. The portal already displays this number.*

Right half — the reframe:

| | today | PAIMANA Foresight |
|---|---|---|
| question | which projects **are** late? | which are **about to slip**? |
| timing | after the revision is filed | **before** |
| output | a record | a ranked watchlist, 94% precision @ top-50 |

Bottom strip — **innovation & uniqueness** (the template asks for this explicitly):
1. We reconstructed a **13-month panel of 2,243 projects (18,601 project-months)** that
   the portal does not retain.
2. **Calibrated confidence with abstention** — the system refuses to guess.
3. A **leakage linter** MoSPI can run on *any* submitted model.

> Presenter line: *"We built the naive model first, on purpose, so we could show you
> why we threw it away."*

---

## Slide 3 — Technical Approach

Flow diagram (from `01_SOLUTION_SPEC.md` §2), four boxes left to right:

```
INGEST                DETERMINISTIC CORE           SERVE
13 monthly     →  panel → features → model  →  watchlist / drill-down
snapshots         ↑ LEAKAGE LINTER              integrity feed
(CSRF POST,       ↓ isotonic calibration         grounded assistant
 2.5s throttle)     + abstention band
```

Stack strip: Python · scikit-learn · SQLite · FastAPI · Next.js + D3 · Docker ·
self-hosted LLM (vLLM). **All open-source — as the PS requires.**

Results box — put the real numbers on the slide:

| | |
|---|---|
| ROC-AUC (forward time split) | **0.883** |
| within-regime re-test | **0.892** |
| PR-AUC | 0.726 vs 0.263 base |
| **precision @ top-50** | **0.94** |
| "is it overdue?" heuristic | **0.472 — worse than random** |

> That last row is the slide's best moment. Say it out loud: *"The signal your
> dashboard highlights today is worse than a coin flip for predicting the next revision."*

---

## Slide 4 — Feasibility and Viability

**Feasibility — it already runs.** This is not a proposal:
- 13 snapshots harvested, 18,601 project-months, model trained and evaluated
- 2026-04 snapshot returns **exactly 1,981 projects** — the figure quoted in the PS
  itself, so our pipeline demonstrably reads MoSPI's own source
- zero-cost: public endpoint, open-source stack, runs on a laptop

**Risks, and what we did about them** — state them, do not hide them:

| risk | our response |
|---|---|
| Free-text delay reasons are empty in the public feed | We **do not** claim text mining. Module drops in on MoSPI's internal data. |
| Cost revisions are rare (163 events) | Reported with a **wide abstention band**, not a headline accuracy |
| A **12× structural break** at March 2026 | Detected it; re-validated entirely inside the new regime (AUC 0.892) |
| Only 13 months public, not the 2 decades of OCMS | Method scales to the archive; we do not pretend to hold it |
| Portal is a government host | 2.5s throttle, 13 requests/harvest, full logged audit trail |

> Presenter line: *"Every one of these we found by checking our own work. The last row
> is why the risk table is on the slide at all."*

---

## Slide 5 — Impact and Benefits

**The portfolio being monitored:** 1,981 projects · ₹37.13 lakh crore original cost ·
₹42.78 lakh crore revised · **₹5.65 lakh crore of overrun already on the books.**

Three benefits, each tied to something we measured:

1. **Earlier intervention.** A 94%-precision top-50 watchlist gives IPMD a monthly
   list of 50 projects to act on, ahead of the filing. Not "monitor everything" —
   *monitor these fifty.*

2. **Data quality, surfaced.** We found **768 integrity anomalies** in the live public
   series — 427 expenditure reversals, 212 progress reversals, 119 completion dates
   pulled earlier — plus a **−₹175,291 crore** single-month cost entry, and an
   unflagged **12× structural break**. For the Ministry of Statistics, this is the
   product, not a side effect.

3. **A better form (PS clause c, answered).** The canonical Indian study
   (Ram Singh, *EPW*, 894 projects) finds the dominant causes are land acquisition,
   clearances, and contractual disputes — **none of which are CUF fields.** The CUF
   records symptoms, not causes. And we tested one candidate new field
   (agency portfolio load: 4.8% → 20.8% revision rate, looked excellent) and
   **rejected it** — no incremental value once sector is controlled.

> Presenter line: *"We are handing you a protocol for deciding what belongs on a
> national statistical form — including the discipline to say no."*

---

## Slide 6 — Research and References

- **Ram Singh**, *"Delays and Cost Overruns in Infrastructure Projects: Extent, Causes
  and Remedies"*, **Economic & Political Weekly** — 894 projects, 17 sectors, built on
  this MoSPI series. `econdse.org/wp-content/uploads/2016/03/Delays-Cost-overruns-EPW.pdf`
- **PAIMANA public dashboard**, MoSPI — `paimana-proj.mospi.gov.in/Home/PublicDashboardNew`
  (project-level feed; 13 monthly frozen snapshots, 2025-07 → 2026-07)
- **Chen et al. (2025)**, *"Transparent and reliable construction cost prediction using
  advanced machine learning and explainable AI"*, *Engineering Science and Technology*
  70:102159 — HistGradientBoosting + SHAP + confidence intervals; our modelling baseline
- **MoSPI Flash Reports on Central Sector Infrastructure Projects** (₹150 cr and above)
- Methods: Fellegi–Sunter-style calibration · isotonic regression · SHAP · time-series
  cross-validation with strict forward splits

**Reproducibility line at the foot of the slide:**
*Every figure in this deck is reproducible from 13 raw JSON snapshots and five scripts.
Harvest log with SHA-256 per snapshot available on request.*

---

## Live-demo safety

**Click project #3 — "Integrated Para Xylene [PX] ... Paradip Refinery" (pid 604859).**
It has the full 13 months on all three series, so every chart in the drill-down fills.

Avoid clicking #1 or #7 live: **21 of the 50 shortlisted projects have fewer than two
revised-cost points**, because that field is only 53% populated portal-wide. Those charts
now read *"not reported in this period"* rather than rendering blank — which is honest,
and is itself the clause-(c) point if a judge asks.

Progress and expenditure series are complete for all 50.

---

## Rehearsal notes

**The three sentences that must land:**
1. *"R² of 1.0, with coefficients of exactly −1 and +1. That is subtraction, not prediction."*
2. *"Of the 50 projects we flagged in July, 47 were revised."*
3. *"The most promising new variable we tested, we rejected."*

**Anticipated questions:**

- *"Why only 13 months?"* — That is what the public endpoint exposes; we verified the
  freeze range. With your internal OCMS archive the same pipeline extends to two decades.
- *"Isn't `months_to_due` obvious?"* — Yes, and it is legitimately known at prediction
  time. Removing it costs 5 AUC points; the model still scores 0.832. No single feature
  carries it, and we published the ablation.
- *"Did you scrape us?"* — Public endpoint, no login, 13 requests per harvest, 2.5-second
  throttle, full logged audit trail with content hashes.
- *"Is 94% precision real?"* — Strict forward time split, and re-validated entirely
  inside the post-March regime at AUC 0.892. Never a random split.
- *"What about cost overruns?"* — Weaker, and we say so: 163 events. That is where the
  abstention band is widest. We would rather show you the limit than hide it.

---

# The spoken pitch — say it in this order

Roughly 3 minutes. Nine beats. The order matters more than the wording: each beat only
lands because the one before it set it up.

---

**1 — Open with their own words. (10 sec)**

> "Your problem statement says you want to move *beyond descriptive monitoring towards
> predictive monitoring.* We took that literally — so the first thing we did was ask what
> 'predictive' actually means for this data."

*Why:* signals we read the brief, and makes everything that follows sound like service
rather than cleverness.

---

**2 — Set the trap. (25 sec)**

> "Every project on your portal carries two dates: when it was supposed to finish, and
> when it now says it will finish. The delay is the gap between them — and it is already
> printed on your screen.
>
> We built the model that predicts that gap. It scored a perfect 1.0. Then we opened it
> up. It had learned exactly two numbers: **minus one, and plus one.** It was doing
> subtraction.
>
> That is not a prediction. It is a calculator. And we think you are going to receive a
> lot of submissions with a very impressive accuracy figure, built exactly this way."

*Why:* this is the whole pitch in one beat. It is generous rather than superior — we
built the bad model ourselves before criticising it. Never name other teams.

---

**3 — The reframe. (15 sec)**

> "So we asked a different question. Not *how late is this project* — you already know
> that. Instead: **which projects are about to have their deadline moved, before the
> revision is filed?**
>
> That answer is not on your screen. It is not written down anywhere yet. That is a real
> prediction."

---

**4 — How we could even ask it. (25 sec)**

> "To answer that we needed something your portal does not keep. PAIMANA shows the
> *current* state of every project — and next month, the previous state is gone.
>
> So we took a copy every month for thirteen months and stacked them. **2,243 projects,
> 18,601 monthly observations.** That history exists because we saved it.
>
> As a check that we were reading your data correctly: our April 2026 copy contains
> exactly **1,981 projects** — the number written in your own problem statement."

*Why:* the 1,981 cross-check is the cheapest credibility in the deck. Do not skip it.

---

**5 — The proof. (20 sec)**

> "We trained on the earlier months and tested on months the model had never seen — never
> a random split, always forward in time.
>
> **Of the 50 projects it flagged in July, 47 were revised.**"

---

**6 — The twist. (20 sec)**

> "Then we checked the shortcut anyone would reach for first — just look at what is
> already overdue. **That scores worse than a coin flip.**
>
> The signal your dashboard highlights most prominently is the wrong one. A project
> carrying a big visible delay has usually just been revised. The one at risk is the one
> approaching a deadline it will not meet — and today, that project looks healthy."

*Why:* this is the moment a judge sits forward. It is counterintuitive, it is measured,
and it is about *their* system rather than our model.

---

**7 — What we found in their data. (30 sec)**

> "Along the way we found things in your own series. **430 cases** where cumulative
> spending went *down*. **216** where physical progress went *backwards*.
> One single-month cost entry of **minus ₹175,291 crore.** And a **twelve-fold jump** in
> the revision rate in March 2026 that we could not explain from public data.
>
> We are not claiming these are errors. We are saying they are visible only if someone
> keeps the history.
>
> On that March jump — it lands on the first full monthly cycle after PAIMANA was
> operationalised in February. We think it is the migration settling. We would like you
> to confirm that.""

*Why:* MoSPI is the Ministry of *Statistics*. Data quality is their identity. Ending on a
question rather than an accusation is what makes this land as help.

---

**8 — Restraint. (20 sec)**

> "One more thing. For **cost** revisions we only have 163 examples. That is not enough to
> be confident, so the system does not guess — it returns *'insufficient confidence,
> route to an analyst.'*
>
> We would rather show you where the limit is than hide it behind a number."

*Why:* almost every other team will present only strengths. Naming your own ceiling, on
stage, unprompted, is the single most credible thing you can do.

---

**9 — Close on the form. (25 sec)**

> "Your form records **symptoms** — cost, date, progress. The causes the research
> identifies — land acquisition, clearances, contractual disputes — are not on it.
>
> So we built a test for whether a proposed new field earns its place. We ran it on the
> most promising candidate we could think of, agency workload. It looked excellent —
> a four-fold difference. **We rejected it.** It added nothing once sector was accounted for.
>
> That is the discipline we think you need before adding a field to a national form."

*Why:* ends on measurement design, which is MoSPI's actual profession — not on our model.

---

**10 — The closer, if the room is still with you. (25 sec)**

> "One last thing. Your Data Innovation Lab scope of work says the governance framework
> needs **model validation, audit, versioning, explainability and transparency**, and a
> path from **pilot to scale to production.**
>
> We read that document *after* we had built this. Our leakage linter is model
> validation. Our hash-chained harvest log is audit. Our model manifest is versioning.
> SHAP is explainability. Calibration and abstention are how it earns trust.
>
> We did not build a model for you. We built it the way your own lab says it should be
> built."

*Why:* this is the single strongest thing we can say, it is verifiable from their own
published document, and it reframes us from *contestants* to *people who could be
adopted*. Their scheme is explicitly a proof-of-concept pipeline — so "adoptable" is the
winning quality, not "most accurate."

*Caution:* say it as alignment, never as "we did your homework."*

---

## If you only get 60 seconds

Beats **2 → 3 → 5 → 6**. The trap, the reframe, 47 of 50, worse than a coin flip.
Everything else is supporting material.

## Three things never to say

- Never name or imply other teams. It is always *"submissions you will receive."*
- Never say "errors in your data." It is *"visible only if someone keeps the history."*
- Never claim we analyse delay reasons. Those fields are empty and a judge may ask for a
  live demo.
