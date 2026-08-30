# What we've built — plain version

**SIH 2026 · PS 26103 · MoSPI · our pick 2 · deadline 20 September**

---

## 1. We found data nobody else will have

The problem statement points at a link on the government's portal. **That link is empty.**
It literally says "Coming Soon". Most teams will hit that wall and fall back to scraping
news articles for headline totals.

We read the dashboard's own code and found an undocumented door — a hidden request that
returns **every project, one row each, 26 fields**.

Then the important bit. The portal only ever shows you *today*. Next month it updates and
the old version is gone forever. It's a photo, not a video.

**So we took a photo every month for 13 months and stacked them into a flipbook.**

- 2,243 projects
- 18,601 monthly rows
- Nobody else has this, because it doesn't exist anywhere — you had to save it as it happened

One more thing: the site can't be reached from foreign servers. Cloud scraping tools fail
on it. **It has to be pulled from an Indian machine.**

---

## 2. We proved the obvious approach is fake

The portal shows two dates: *"was supposed to finish"* and *"now says it'll finish."*
The delay is the gap between them.

If you ask a computer to "predict delay" and give it both dates, **it just subtracts
them.** It scores a perfect 100% and has learned nothing. Like guessing someone's age
after being told their birth year and today's date.

We built that model on purpose. Perfect score. Looked inside — the only two numbers it
had learned were **minus one and plus one**.

**A lot of the 500 teams will build this by accident and present the perfect score as a
win.** We can show why it's meaningless in one slide.

---

## 3. What we built instead — and it works

We ask a question whose answer **isn't written down anywhere yet**:

> *Which projects are about to have their deadline pushed — before anyone files it?*

How it works is not magic. It's the same as predicting a student will fail:
**how much is left, how long till the deadline, how fast are they going?**

> Pune–Hyderabad highway: 46% built. 1 month left. Needs 50% this month. Doing 2.7%.
> It cannot finish. The paperwork admitting it hadn't been filed yet.

We tested it properly — learned from the early months, then tested on months it had never
seen. **Of the 50 projects it flagged, 47 really did get pushed.**

And the shortcut everyone uses today — *"just look at what's already late"* — scores
**worse than a coin flip.** The most visible signal is the wrong one.

---

## 4. Two things nobody asked for

**A data-quality checker.** Going month to month, we found **768 problems in the
government's live data** — 430 cases where spending went *down*, 216 where progress went
*backwards*, and one cost entry of **minus ₹1.75 lakh crore** sitting on the public site.
None of this is visible from a single snapshot. MoSPI is the *statistics* ministry —
data quality is their identity.

**A test for adding fields to their form.** We had a great idea: agency workload. Agencies
running 150+ projects slip 4× more often. Looked brilliant. **We tested it properly and
it added nothing** once you account for the sector. So we rejected it — and we present
that rejection, because knowing how to say no is the actual skill.

---

## 5. We found out who this is really for

MoSPI doesn't build roads. **MoSPI decides which projects get named in front of the Prime
Minister.**

Their own site says the data feeds *"the PRAGATI monthly review, the Prime Minister's
State visits, Parliamentary Questions and RTI."*

- **1,129 of 1,775 projects are already behind schedule** (79%)
- PRAGATI reviews about **five** per meeting

So the real job is: **which five, out of 1,981?** That's exactly what our list of 50 is
for. Not "who is late" — nearly everyone is late — but *"who is about to get worse while
someone can still do something."*

---

## 6. We checked our own claims and killed the ones that failed

- **"We'll save them crores."** Tested it. In our data a delay is followed by *fewer*
  cost increases, not more. **We won't claim savings.** A MoSPI statistician would
  destroy that number in ten seconds.
- **"Agency workload is a great new signal."** Tested. Rejected.
- **"Our numbers match our teammate's independently."** They don't — it was the same data
  twice. Withdrawn.

What survived: our figures **exactly match all four numbers quoted in MoSPI's own problem
statement** — 1,981 projects, ₹37.13 / ₹42.78 / ₹20.36 lakh crore. To two decimals.

---

## 7. What the winner actually gets

Worth knowing, because it changes how we pitch. From the official rules:

- Prize is ₹1.5 lakh
- **But if they adopt it: ₹10,000–15,000/month each, for 6–12 months**, ministry buys the
  software, assigns a technical mentor, pays travel
- **We keep the IP.** The ministry gets free lifetime access. This is deliberate — the
  rules say it's to let startups grow out of it
- About **10%** of problem statements end in a real implementation (24 in 2022, 30 in 2023)

**So the deck shouldn't read like a hackathon submission. It should read like the opening
of a six-month engagement.**

---

## Where we stand

**Working right now** — run `./dev.sh`, open the dashboard:
Shortlist (top 50, click any project for its 13-month story) · Portfolio by state and
sector · Data quality · Method.

Everything reproduces from raw files with one command.

**Still open:**
1. Teammate's 200+ historical PDF reports — waiting on one answer: *do they contain
   physical progress %?* Without it we can't rank, only predict.
2. Three small unknowns, about an hour each
3. Turning all of this into six slides

**Nobody needs to fear a question in the room.** Every number traces back to a raw file
with a fingerprint, and the things we couldn't prove, we've written down as things we
couldn't prove.
