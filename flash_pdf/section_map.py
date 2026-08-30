# -*- coding: utf-8 -*-
"""Explicit classification of every section heading in the flash-report corpus.

Built by enumerating all 89 distinct heading strings rather than by substring
guessing, which is what produced the earlier mis-labelling.

The critical distinction the first attempt missed:

  EVENT  sections list what happened THIS MONTH. TABLE-16, "List of projects
         reporting additional delayed", has columns
             DOC reported: Original | Last month | This month | Delay (in months)
         so each row is a project whose commissioning date moved since the last
         report. This is a timestamped slip event WITH magnitude, published by
         MoSPI - the best label in the corpus, and no transition inference is
         needed to use it.

  STATE  sections list current status ("Delayed Projects w.r.t. Original
         Schedule"). A project sits in these every month it stays late.

Mixing the two made almost every project-month read as DELAYED, which collapsed
transition counts to zero in several months.

Headings are messy across 17 years: case varies, words are truncated by the
column width, and there is at least one typo in the source ("Dealy Project").
Rules are ordered most-specific first.
"""
import re

# (label, pattern) - order matters, first match wins
RULES = [
    # ---- events: something changed this month ----
    ("EVENT_SLIP",              r"additional\s+delay"),

    # ---- non-data pages ----
    ("JUNK",                    r"^\s*$"),
    ("JUNK",                    r"^tables?$"),
    ("JUNK",                    r"list of tables"),
    ("JUNK",                    r"milestones for each project"),
    ("JUNK",                    r"as reported by line ministries"),
    ("JUNK",                    r"earliest \(oldest\) projects"),

    # ---- lifecycle (portfolio churn, not project status) ----
    ("LIFECYCLE_CHURN",         r"completed\s*/\s*dropped|dropped\s*/\s*frozen"),
    ("LIFECYCLE_ADDED",         r"projects added"),
    ("LIFECYCLE_COMPLETED",     r"completed projects?"),
    ("LIFECYCLE_DELETED",       r"deleted projects?"),

    # ---- delivery mode ----
    ("MODE_PPP",                r"public\s+privat"),

    # ---- data-quality flags (absence of information, not project status) ----
    ("ADMIN_NO_MILESTONE",      r"without\s+milestone"),
    ("ADMIN_NO_DOC",            r"without\s+(original\s+)?date of"),
    # Headings are truncated at the column width, so "...having Without Original"
    # is "Without Original Date of Commissioning" with the tail cut off.
    ("ADMIN_NO_DOC",            r"without\s+original\s*$"),

    # ---- financial state ----
    ("STATE_EXPENDITURE_OVER",  r"expenditure is more than approved"),
    # "overru" not "overrun": same truncation.
    ("STATE_TIME_AND_COST",     r"(both\s+)?time and cost\s+overru"),
    ("STATE_COST_OVERRUN",      r"cost\s+overru"),

    # MoSPI's own watchlist - projects the ministry itself flags as needing
    # attention. That is a human-curated priority label, not a derived one.
    ("STATE_FOCUS_ATTENTION",   r"requiring focused attention|focussed attention"),

    # ---- schedule state ----
    ("STATE_AHEAD",             r"ahead of schedule"),
    ("STATE_ON_SCHEDULE",       r"on\s+schedule"),
    # Both spellings occur: "Delay Project" and the source typo "Dealy Project".
    # de[al]{2}y covers delay/dealy; an earlier `deal?y` silently matched only
    # the typo and dropped 3,507 genuine records into UNCLASSIFIED.
    ("STATE_DELAYED",           r"de[al]{2}y\s+project|delayed|time\s+overru"),

    # ---- master lists (denominators) ----
    ("LIST_NORTH_EAST",         r"north\s*east\s*projects?"),
    ("LIST_ONGOING",            r"ongoing projects?\s+costing|details of ongoing projects?"),
    ("LIST_ALL",                r"central sector projects?\s+costing"),
    ("LIST_ALL",                r"projects?\s+\(costing"),
]

_COMPILED = [(lab, re.compile(pat, re.I)) for lab, pat in RULES]


def classify(section):
    s = " ".join((section or "").split())
    for lab, rx in _COMPILED:
        if rx.search(s):
            return lab
    return "UNCLASSIFIED"


# Which labels are usable as supervised signal, and of what kind
KIND = {
    "EVENT_SLIP":             "event",
    "STATE_DELAYED":          "state",
    "STATE_ON_SCHEDULE":      "state",
    "STATE_AHEAD":            "state",
    "STATE_COST_OVERRUN":     "state",
    "STATE_TIME_AND_COST":    "state",
    "STATE_EXPENDITURE_OVER": "state",
    "STATE_FOCUS_ATTENTION":  "state",
    "LIFECYCLE_COMPLETED":    "lifecycle",
    "LIFECYCLE_DELETED":      "lifecycle",
    "LIFECYCLE_CHURN":        "lifecycle",
    "LIFECYCLE_ADDED":        "lifecycle",
    "LIST_NORTH_EAST":        "denominator",
    "ADMIN_NO_MILESTONE":     "admin",
    "ADMIN_NO_DOC":           "admin",
    "MODE_PPP":               "attribute",
    "LIST_ONGOING":           "denominator",
    "LIST_ALL":               "denominator",
    "JUNK":                   "drop",
    "UNCLASSIFIED":           "drop",
}


if __name__ == "__main__":
    import sys, io, csv, collections
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    REC = r"C:\Users\LENOVO\Downloads\SIH2026\PAIMANA\extracted\records.csv"
    counts = collections.Counter()
    with open(REC, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["section"] != "__ERROR__":
                counts[" ".join(r["section"].split())] += 1

    by_label = collections.defaultdict(list)
    for s, n in counts.items():
        by_label[classify(s)].append((n, s))

    print("FULL MAPPING FOR REVIEW  (%d headings, %d records)\n"
          % (len(counts), sum(counts.values())))
    total = sum(counts.values())
    for lab in sorted(by_label, key=lambda l: -sum(n for n, _ in by_label[l])):
        recs = sum(n for n, _ in by_label[lab])
        print("=" * 78)
        print("%-24s %9s records  %5.1f%%   kind=%s"
              % (lab, "{:,}".format(recs), 100 * recs / total, KIND.get(lab, "?")))
        print("=" * 78)
        for n, s in sorted(by_label[lab], reverse=True):
            print("   %8d  |%s|" % (n, s[:74]))
        print()
