# MoSPI Flash Report Corpus - `files.zip`

Monthly **Flash Reports on Central Sector Infrastructure Projects (Rs. 150 crore and above)** published by the Infrastructure & Project Monitoring Division (IPMD), Ministry of Statistics and Programme Implementation, plus the quarterly Project Implementation Status Reports.

Assembled for **SIH 2026, PS 26103 (PAIMANA)**. Every figure below is computed from the archive and the extraction output by `scripts/make_corpus_doc.py`. Nothing is typed by hand.

## What is in the zip

| | count | size |
|---|---:|---:|
| Monthly Flash Reports (`FR_*.pdf`) | 207 | 1.79 GB |
| Quarterly PISR (`quarterly/`) | 7 | 129 MB |
| **Total** | **214** | **1.91 GB** |

Filenames are normalised to `FR_<year>_<month>_<monthname>.pdf`. **MoSPI's own naming is not consistent** - one directory holds `FRMARCH2025.pdf`, `FR_may2025.pdf`, `FlashReport_JULY_2025.pdf` and `FlashReport_august_2025.pdf`. `manifest_all.csv` maps every normalised name back to the exact URL it came from (232 mapped).

## Coverage

```
        Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec    n
2001     .   .   .   #   #   #   #   #   #   #   #   #    9/12
2002     #   #   #   #   #   #   #   #   #   #   #   #   12/12
2003     #   #   #   .   .   .   .   .   .   .   .   .    3/12
2004     .   .   .   .   .   .   .   .   .   .   .   .    0/12
2005     .   .   .   .   .   .   .   .   .   .   .   .    0/12
2006     .   .   .   .   .   .   .   .   .   .   .   .    0/12
2007     .   .   .   .   #   .   .   .   .   #   .   .    2/12
2008     .   .   .   .   .   .   .   .   .   .   .   .    0/12
2009     .   .   #   .   .   #   #   #   #   #   #   #    8/12
2010     #   #   #   #   #   #   #   #   #   #   #   #   12/12
2011     #   #   #   #   #   #   #   #   #   #   #   #   12/12
2012     #   #   #   #   #   #   #   #   #   #   #   #   12/12
2013     .   #   #   #   #   #   #   #   #   #   #   #   11/12
2014     #   #   #   #   #   #   #   #   #   #   #   #   12/12
2015     #   #   #   #   #   #   #   #   #   #   #   #   12/12
2016     #   #   #   #   #   #   #   #   #   #   #   #   12/12
2017     #   #   #   #   #   #   #   #   #   #   #   #   12/12
2018     #   #   #   #   #   #   #   .   .   .   .   .    7/12
2019     .   .   .   .   .   .   .   .   .   .   .   .    0/12
2020     .   #   #   #   #   #   .   #   #   #   #   #   10/12
2021     #   #   #   #   #   #   #   #   #   #   #   #   12/12
2022     #   #   #   #   #   #   #   #   #   #   #   #   12/12
2023     #   #   #   #   #   #   #   #   #   #   #   #   12/12
2024     #   #   #   #   #   .   #   #   #   #   #   #   11/12
2025     #   #   #   #   #   #   #   #   #   #   #   #   12/12
2026     #   .   #   .   .   .   .   .   .   .   .   .    2/12
```

**207 monthly reports spanning 2001-2026.**

| period | status |
|---|---|
| 2004-2006, 2008 | not present in MoSPI's archive |
| **2019** | **entirely absent.** 272-404 filename variants were probed across both archive hosts and both financial-year folder conventions. The files are not there - this is not a naming problem. |
| 2010-2017 | complete and unbroken |
| 2020-2025 | near-complete |

## What extraction actually recovered

Parsed **207 of 207** monthly reports so far, yielding **592,608 project-level rows** plus 287,035 aggregate/summary rows (separated, not counted as projects).

| year | project rows | with ID code | slip events |
|---|---:|---:|---:|
| 2001 | 1,831 | 0 | 39 |
| 2002 | 3,091 | 0 | 95 |
| 2003 | 868 | 0 | 32 |
| 2007 | 1,094 | 0 | 39 |
| 2009 | 1,939 | 0 | 85 |
| 2012 | 217 | 159 | 0 |
| 2013 | 20,787 | 15,852 | 354 |
| 2014 | 34,795 | 26,763 | 586 |
| 2015 | 39,338 | 30,589 | 461 |
| 2016 | 54,305 | 47,362 | 683 |
| 2017 | 58,882 | 53,329 | 541 |
| 2018 | 37,523 | 34,297 | 285 |
| 2020 | 63,992 | 59,652 | 597 |
| 2021 | 95,004 | 88,488 | 1,357 |
| 2022 | 77,726 | 71,696 | 2,021 |
| 2023 | 66,995 | 59,778 | 2,365 |
| 2024 | 33,795 | 30,586 | 1,489 |
| 2025 | 318 | 0 | 0 |
| 2026 | 108 | 0 | 0 |

Files parsed but yielding **no** project rows (50): `FR_2009_03_march.pdf`, `FR_2009_09_september.pdf`, `FR_2009_10_october.pdf`, `FR_2009_11_november.pdf`, `FR_2009_12_december.pdf`, `FR_2010_01_january.pdf`, `FR_2010_02_february.pdf`, `FR_2010_03_march.pdf`, `FR_2010_04_april.pdf`, `FR_2010_05_may.pdf`, `FR_2010_06_june.pdf`, `FR_2010_07_july.pdf` ...

## Identifiers - read this before joining anything

There are **two eras**, and conflating them is the easiest mistake to make here.

| era | project rows | tracking ID |
|---|---|---|
| **pre-2012** | 8,823 | **none.** MoSPI had not introduced the `N########` scheme. Rows are real observations but can only be linked across months by NAME |
| **2012 onward** | 583,785 | `N########` embedded in the project-name cell, stable across monthly reports |

So: **project-level observations run from 2001; reliable per-project tracking runs from 2013.** State both facts together - the first without the second overstates what the early years support.

The OCMS `N########` code is also **unrelated to the PAIMANA dashboard's `ProjectId`.** PAIMANA replaced OCMS and renumbered. A name-based bridge between the two scored **1.1%** and should be treated as an unsolved record-linkage problem, not a working join.

## What a full report contains

A modern edition runs 500-600 pages. Rows are grouped into sections, and the sections are themselves labels assigned by MoSPI:

| section family | what it means |
|---|---|
| `projects reporting additional delays` | **the slip event.** Columns are `DOC reported: Original / Last month / This month` and `Delay (in months)` - a project whose commissioning date moved since the previous report, with magnitude |
| `Delayed Projects w.r.t. Original Schedule` | state: behind original schedule |
| `On Schedule Projects` | state: on time |
| `Ongoing Projects having Cost Overruns` | state: over cost |
| `Projects Requiring Focused Attention` | **MoSPI's own watchlist** |
| `Projects Without Milestones` / `Without Date of Commissioning` | data-quality flags |
| `Completed` / `Deleted` / `added` / `dropped-Frozen` | portfolio churn |

The distinction between an **event** section (something changed this month) and a **state** section (status as of this month) is the one that matters. Conflating them inflates apparent slip rates by an order of magnitude.

Label distribution across extracted project rows:

| label | rows | share |
|---|---:|---:|
| `ADMIN_NO_MILESTONE` | 89,916 | 15.2% |
| `STATE_DELAYED` | 89,145 | 15.0% |
| `ADMIN_NO_DOC` | 82,728 | 14.0% |
| `STATE_ON_SCHEDULE` | 71,323 | 12.0% |
| `LIST_ONGOING` | 67,977 | 11.5% |
| `STATE_COST_OVERRUN` | 67,599 | 11.4% |
| `UNCLASSIFIED` | 42,883 | 7.2% |
| `STATE_TIME_AND_COST` | 30,188 | 5.1% |
| `STATE_EXPENDITURE_OVER` | 12,167 | 2.1% |
| `EVENT_SLIP` | 11,029 | 1.9% |

Unclassified sits at **7.2%**. Heading wording drifts between eras, so this is higher than on any single modern report - quote the corpus-wide figure.

## Provenance

| host | role |
|---|---|
| `ipm.mospi.gov.in` | legacy OCMS-era archive (serves an **expired TLS certificate**) |
| `paimana-proj.mospi.gov.in` | live successor portal, recent months |
| `mospi.gov.in/sites/default/files/publication_reports` | some editions |

All public - no login, no paywall. There is **no directory index** on any of them: archive folders return HTTP 200 with an empty body, so every file was located by enumerating candidate URLs.

The corpus is reproducible without redistributing 1.9 GB:

```bash
python scripts/download_all.py     # fetch from the manifest URLs
python scripts/fill_gaps.py        # recover awkwardly-named months
python scripts/extract_tables.py   # rebuild the structured rows
```

## Licence and attribution

Government of India publications, redistributed unmodified. Content owned and maintained by IPMD, MoSPI. Portal contact: `dir-ipmd[at]mospi[dot]gov[dot]in`.
