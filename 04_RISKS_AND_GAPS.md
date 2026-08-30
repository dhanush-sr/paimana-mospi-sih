# Risks, Gaps, and Open Questions

Written adversarially against our own work. Anything here that is not resolved before
20 Sep 2026 must still be *said out loud* in the deck rather than hidden.

---

## 1. Things that could break the headline number

### 1.1 The March 2026 structural break — PARTLY RESOLVED
Revision rate jumps 1.95% → 23.96% between Feb and Mar 2026 and never reverts.

- **Mitigated:** we retrained entirely inside the post-break regime
  (train Mar+Apr → test Jun+Jul) and got **AUC 0.892**. The result is not an artifact.
- **Largely explained `[VERIFIED, 2026-08-27]`:** PAIMANA replaced OCMS-2006 on
  **25 September 2025** (PIB), with the project-monitoring module operationalised in
  **February 2026**. Our project count ramps 791 (Jul 25) → 1,948 (Feb 26) → 1,987
  (May 26), and the revision-rate break lands in **March 2026 — the first full monthly
  cycle after operationalisation.** The break is almost certainly the migration settling,
  not a change in real-world project behaviour.
- **Still `[OPEN]`:** we cannot prove that from public data alone. **Present it as a
  detected break with a documented candidate cause and ask them to confirm.** Do not
  assert it.
- **Why it matters:** if a judge from MoSPI knows the cause and we guess wrong on stage,
  we lose credibility. Say: *"the break coincides with the first full cycle after PAIMANA
  was operationalised in February 2026 — we believe it is the migration, and we'd like
  you to confirm."* Offering a researched hypothesis **and** inviting correction is the
  strongest posture.

### 1.2 The onboarding ramp confounds the early panel
Project count runs 791 → 800 → 794 → 820 → 823 → 1,392 → 1,702 → 1,948 → 1,941 →
1,981 → 1,987 → 1,847 → 1,775.

A project **appearing** is onboarding, not a new project. A project **disappearing** is
not necessarily completion — it may be de-scoped, re-classified, or dropped.

- Mitigated by including `nobs` (months observed) as a feature. **Keep it.**
- `[OPEN]` We have not established what the 1,987 → 1,775 decline (May → Jul) represents.
  **Check before the deck is final.** If those are completions, there is a second,
  valuable label available (completion prediction). If they are data drops, it is
  another integrity finding. Either outcome is useful; guessing is not.

### 1.3 Label definition is "date field changed", not "project actually slipped"
We detect a **filing event**, not physical reality. 5.3% of revisions pull the date
*earlier*, which is not a slip at all.

- Honest framing: we predict **administrative revision events**. That is genuinely what
  IPMD processes each month, so it is decision-relevant — but do not call it
  "predicting delays" when a judge is listening carefully.
- **Possible refinement if time allows:** restrict the label to *positive* slips
  > 30 days. Costs sample size (~2,253 → ~1,500), buys a cleaner claim. Test it; keep
  whichever is more defensible, and report both.

### 1.4 Cost model is thin — ACCEPTED, NOT FIXED
163 cost-revision events across 16,315 transitions (1.0%). Any classifier will have
wide error bars.

- Do not put a cost AUC on the slide as a headline.
- **Do** show the abstention band doing its job on this target. Turn the weakness into
  the demonstration of the moat.

---

## 2. Things we cannot do and must not claim

| we cannot | because | what we say instead |
|---|---|---|
| mine free-text delay reasons | `RevisedCostReason`, `RevisedDateReason`, `Remarks` are **0% populated** in the public feed | "the module drops in on your internal data; we will not claim it works today" |
| use 2 decades of OCMS history | public freeze range is 2025-07 → 2026-07 only | "the method scales to your archive" |
| ~~do state/geographic analysis~~ | **RESOLVED** — recovered via StateId filter, 99.0% coverage | now a strength: we show geography their own payload reports as null |
| attribute causes | causal fields are not in the CUF (Ram Singh) | this *is* our clause (c) answer |
| use `DELAYED_TIME`, `COST_OVERRUN`, `COR_PERC`, `TOR_PERC` | all **0%** populated | we derive overruns ourselves — which is how we control leakage |

**The temptation to resist:** an "LLM analyses delay narratives" slide would be the most
impressive-sounding claim in the deck, and it is not deliverable from public data. If a
judge asks for a live demo of it, we are finished. Leave it out.

---

## 3. Open questions worth a few hours each — ranked

*(3.1 resolved 2026-08-27; remaining items still open.)*

### 3.1 Can `StateName` be recovered? — **RESOLVED, YES** `[VERIFIED]`
Confirmed on 2026-08-27. `/Home/GetStateList` (with the `X-Requested-With` header)
returns all **36 states/UTs**; `GetTileData` with `StateId=k` returns only that state's
projects. Spot-checks match (3=Assam/Guwahati Airport, 7=Haryana/AIIMS Rewari,
6=Goa/9 rows, 10=Jharkhand/Pachwara coal).

**DONE 2026-08-27.** `harvest.py --states` implemented and run; 468/468 cached.
**99.0% state coverage.** `/benchmark?by=state` live. Remaining caveat: multi-state
corridors (9.2%) collapse to one state in the scalar column — use `project_states`.

*Note for honesty: a first probe without the `X-Requested-With` header returned an
empty body and briefly looked like a broken endpoint on MoSPI's side. It is not — our
request was malformed. **Do not claim their state filter is broken.***

### 3.2 Is there any deeper history? `[OPEN]` — ~1 hour
`GetFreezeDates` reports 2025-07 as `firstFreeze`. **Test:** request 2024 and 2025-01
anyway — the API may serve months outside the advertised range. Also probe
`/ReportPage/ArchiveProjectMonitoring` and the MoSPI publications archive for older
Flash Report PDFs with project-level tables. Every extra month is a longer test window.

### 3.3 What does the May → July decline represent? `[OPEN]` — ~1 hour
See §1.2. Sample 20 disappeared projects and check whether they reappear later, or
whether their last-seen `PhysicalProgress` was ~100 (suggesting completion).

### 3.4 Does the sanction-to-start gap predict anything? `[OPEN]` — ~30 min
`SanctionDate` is 99.3% populated and `mons_since_sanction` is in the model, but we
have not tested whether *long-dormant* projects (sanctioned years ago, low progress)
are a distinct high-risk class. Cheap to test, potentially a clean narrative segment.

### 3.5 Read the actual CUF `[OPEN]`
We are inferring the CUF field list from the API response. The real form is behind the
PMG login and we have **not** seen it. Our clause (c) answer is therefore about *the
fields exposed in the monitoring feed*, which may be a subset.
**Say "the fields exposed in the public project feed", not "the CUF", unless we obtain
the actual form.** This is a precision-of-claim issue that a MoSPI judge would catch.

---

## 4. Competitive risk

**What the other teams will build:** load the April 2026 dashboard export into pandas,
train XGBoost on the overrun column, report R² > 0.9, build a Streamlit dashboard.

**Why we beat that:** we can show, in one slide, that their number is subtraction.

**The risk in doing so:** it reads as attacking other teams rather than serving the
client. **Frame it as a service to MoSPI, never as a takedown.** The line is *"here is a
linter so you can tell which submissions are real"* — not *"the other teams are wrong."*

**Second competitive risk:** a team that also finds the panel endpoint. Unlikely — it
needs reading inline dashboard JS, and cloud scrapers cannot resolve the host — but not
impossible. Our defence is depth, not secrecy: the calibration, abstention, integrity
audit, and ablation protocol are not things you assemble in a weekend.

---

## 5. Ethics and conduct

- Public endpoint, no authentication used or bypassed, no rate abuse (2.5s throttle,
  13 requests per full harvest).
- `robots.txt` returns 404 — no published policy. We throttle conservatively anyway.
- No personal data: projects, ministries, agencies — no individuals.
- **We are publishing findings about a government system's data quality.** Frame them as
  contributions to MoSPI's own quality assurance, with reproduction steps, never as
  "we found errors in your portal." Tone matters more than content here.
- Keep the harvest log with SHA-256 per snapshot. If asked how we got the data, we show
  the log.

---

## 6. Decisions still needed from the team

1. **Owner for the PAIMANA track — DECIDED 2026-08-27: Dhanush.**
   Scope: **this PS only (26103).** Dhanush owns the PAIMANA build, the harvest schedule,
   and the PAIMANA deck. PS 26018 (Land Records) ownership is **still unassigned** and is
   explicitly *not* covered by this — it needs a different owner, since pick 1 should get
   the strongest presenter and that presenter should not be splitting attention across
   both decks.
2. **Pick order — DECIDED 2026-08-27: PAIMANA is PICK 2.** Pick 1 remains PS 26018
   (Land Records). Consequence: 26018 gets first call on team time and on the strongest
   presenter. PAIMANA must therefore be built so it can be finished by a **subset** of
   the team — which is why `02_BUILD_PLAN.md` Phases 1–4 are self-sufficient and
   Phases 5–7 are cuttable.
3. **Label definition** — filing events vs slips > 30 days (§1.3). Test both, pick one,
   report both.
4. **Re-harvest date** — put 2026-09-01 in a calendar. One more snapshot is one more
   test month.
