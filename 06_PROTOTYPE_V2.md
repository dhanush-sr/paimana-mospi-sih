# Prototype v2 — from dashboard to instrument

**Why:** v1 is a competent analyst's dashboard. It is not yet the thing IPMD would
actually *use*, because IPMD's job is not to browse — it is to **escalate**. Their own
mandate: *"identifying projects falling behind schedule … and **apprises to PMO/CabSec/
NITI Aayog** through **periodic communications**."*

We built the analysis. We did not build the communication.

---

## The gap, named honestly

| what a judge sees in v1 | what would make them say "this is it" |
|---|---|
| a ranked list on a screen | **a brief they could send to the PMO today** |
| "the model scored it 0.68" | **"here is why this project, in four lines"** |
| a snapshot of July | **"here is what changed since June"** |
| top 50 only | **look up any of the 1,981** |

Everything below closes one of those rows. Nothing below is new modelling — the model is
done and validated. This is about making its output *usable by the person who has to act*.

---

## Build list, in priority order

### 1. `(f)` Driver analysis — *PS outcome (f), currently unbuilt*
**What:** per-project, which factors pushed the score up or down, in rupee/percent terms
a non-modeller can read.
**How:** SHAP `TreeExplainer` over the trained model. Cache contributions per
(pid, month) at score time so the API is a lookup, not a computation.
**Endpoint:** `GET /explain/{pid}?month=`
**UI:** a contribution bar list inside the drill-down drawer.
**Why it matters:** *"why was MY project escalated?"* is the first question a line
ministry asks. That is the defensibility the whole pitch rests on.

### 2. Escalation brief — *the missing instrument*
**What:** one click on any shortlisted project → a formatted, printable note containing:
- project identity, agency, state, sector, cost/spend
- the finding in one sentence (*46% built, 1.1 months to deadline, needs 50%/month, doing 2.7%*)
- the drivers from (1)
- the 13-month history table
- data provenance: snapshot month, model version, source file hash
- an explicit **"what we do not know"** line (the reason field is empty portal-wide)

**Endpoint:** `GET /brief/{pid}?month=`
**UI:** "Generate brief" button in the drawer; opens a clean print view.
**Why it matters:** this converts the demo from *"look at our dashboard"* to *"here is
the note that goes out on Monday."* It is the single highest-leverage thing left.

### 3. What changed this month — *the monitoring workflow*
**What:** month-over-month delta —
- **entered** the shortlist (new risk)
- **left** it (resolved, or revised and no longer savable)
- **worsened** — pace shortfall grew
- deadline moved since last month

**Endpoint:** `GET /changes?month=`
**UI:** a fifth view, or a strip at the top of the shortlist.
**Why it matters:** a monthly system that cannot answer *"what's new since last month?"*
is a report, not a monitor. This also demonstrates the panel doing work no snapshot can.

### 4. Search any project
**What:** type-ahead over all 2,243 projects; open the same drill-down for any of them,
shortlisted or not.
**Why it matters:** the first thing an officer does is look up a project they already
care about. Without it we can only show our own top 50 — which reads as a canned demo.

### 5. (deferred) `(h)` LLM assistant
Not required for the pitch. Build only if 1–4 land and time remains.

---

## What we are deliberately NOT doing

- **No new model.** The numbers are validated; changing them now invalidates the docs.
- **No auth/RBAC.** Demo, not deployment — stated as a deliberate omission.
- **No map view.** Tempting with 99% state coverage, but Portfolio already answers the
  geography question and a map is decoration next to items 1–3.

---

## Acceptance

Each item ships only when it works end-to-end from `./dev.sh` with live data and no
console errors, verified in a real browser — not assumed.

The demo after v2 should read as a sequence, not a tour:

> *this project → why → the brief → what changed since last month.*

Four clicks, one story.
