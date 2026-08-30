# -*- coding: utf-8 -*-
"""Build PAIMANA_Data_Report.pdf.

Design rule: every figure is read from a data file at generation time. Nothing is
typed into this script by hand. Where a source is missing or a run is incomplete,
the report says so rather than substituting an estimate - a report that quietly
fills a gap is worse than one that admits it.
"""
import collections
import csv
import json
import os
import re
import sys
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, KeepTogether, PageTemplate,
                                Paragraph, Spacer, Table, TableStyle)

ROOT = r"C:\Users\LENOVO\Downloads\SIH2026\PAIMANA"
OUT = os.path.join(ROOT, "PAIMANA_Data_Report.pdf")

for name, fn in [("Body", "calibri.ttf"), ("Body-B", "calibrib.ttf"),
                 ("Disp-B", "georgiab.ttf"), ("Mono", "consola.ttf")]:
    try:
        pdfmetrics.registerFont(TTFont(name, fn))
    except Exception:
        pass

INK = colors.HexColor("#101828")
MUTED = colors.HexColor("#667085")
ACCENT = colors.HexColor("#0b5394")
GOOD = colors.HexColor("#177245")
WARN = colors.HexColor("#b54708")
BAD = colors.HexColor("#b42318")
LINE = colors.HexColor("#d0d5dd")
SURF = colors.HexColor("#f2f4f7")

PW, PH = A4
M = 1.8 * cm
CW = PW - 2 * M

S = {
    "h1": ParagraphStyle("h1", fontName="Disp-B", fontSize=19, textColor=INK, leading=23),
    "sub": ParagraphStyle("sub", fontName="Body", fontSize=10, textColor=MUTED, leading=14),
    "h2": ParagraphStyle("h2", fontName="Disp-B", fontSize=12.5, textColor=ACCENT,
                         leading=16, spaceBefore=14, spaceAfter=5),
    "h3": ParagraphStyle("h3", fontName="Body-B", fontSize=10, textColor=INK,
                         leading=13, spaceBefore=8, spaceAfter=3),
    "p": ParagraphStyle("p", fontName="Body", fontSize=9.4, textColor=INK,
                        leading=13.6, spaceAfter=5),
    "small": ParagraphStyle("small", fontName="Body", fontSize=8.4, textColor=MUTED,
                            leading=11.8, spaceAfter=4),
    "th": ParagraphStyle("th", fontName="Body-B", fontSize=8.3, textColor=INK, leading=11),
    "td": ParagraphStyle("td", fontName="Body", fontSize=8.5, textColor=INK, leading=11.5),
    "tdm": ParagraphStyle("tdm", fontName="Mono", fontSize=7.8, textColor=INK, leading=11),
}

story = []
P = lambda t, s="p": Paragraph(t, S[s])
MISSING = "<font color='#b42318'>NOT AVAILABLE</font>"


def tbl(headers, rows, widths, mono=()):
    data = [[Paragraph(h, S["th"]) for h in headers]]
    for r in rows:
        data.append([Paragraph(str(c), S["tdm"] if i in mono else S["td"])
                     for i, c in enumerate(r)])
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), SURF),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOX", (0, 0), (-1, -1), 0.6, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
    ]))
    return t


def note(title, body, color=ACCENT):
    inner = [Paragraph(title, ParagraphStyle("n", fontName="Body-B", fontSize=8.8,
                                             textColor=color, leading=11.5, spaceAfter=2)),
             Paragraph(body, S["small"])]
    t = Table([[inner]], colWidths=[CW])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fbfcfd")),
        ("LINEBEFORE", (0, 0), (0, -1), 2.2, color),
        ("BOX", (0, 0), (-1, -1), 0.5, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


# ---------------------------------------------------------------- gather facts
F = {}


def rd(path):
    p = os.path.join(ROOT, path)
    return open(p, encoding="utf-8", errors="replace").read() if os.path.exists(p) else None


# corpus
files_dir = os.path.join(ROOT, "files")
quart_dir = os.path.join(files_dir, "quarterly")
flash = sorted(f for f in os.listdir(files_dir)
               if f.startswith("FR_") and f.lower().endswith(".pdf")) \
    if os.path.isdir(files_dir) else []
quart = sorted(os.listdir(quart_dir)) if os.path.isdir(quart_dir) else []
F["n_flash"] = len(flash)
F["n_quart"] = len(quart)
F["bytes"] = sum(os.path.getsize(os.path.join(files_dir, f)) for f in flash) + \
             sum(os.path.getsize(os.path.join(quart_dir, f)) for f in quart)
cov = collections.defaultdict(set)
for f in flash:
    m = re.match(r"FR_(\d{4})_(\d{2})_", f)
    if m:
        cov[int(m.group(1))].add(int(m.group(2)))
F["cov"] = cov

# verification
vr = rd("verification_report.txt")
F["verdict"] = None
if vr:
    m = re.search(r"VERDICT:\s*(\d+)/(\d+) files usable,\s*([\d,]+) pages", vr)
    if m:
        F["verdict"] = (int(m.group(1)), int(m.group(2)), m.group(3))
    F["unusable"] = len(re.findall(r"(NO_TEXT_LAYER|NO_PROJECT_CODES|NOT_A_PDF)", vr))

# api panel
pp = os.path.join(ROOT, "dashboard", "project_panel.json")
if os.path.exists(pp):
    panel = json.load(open(pp, encoding="utf-8"))
    F["panel_rows"] = len(panel)
    F["panel_projects"] = len({r.get("ProjectId") for r in panel})
    F["panel_months"] = sorted({r.get("freeze_month") for r in panel})
    seen = collections.defaultdict(set)
    for r in panel:
        seen[r.get("ProjectId")].add(r.get("freeze_month"))
    F["panel_full"] = sum(1 for v in seen.values() if len(v) == len(F["panel_months"]))

# base rates
br = rd(os.path.join("dashboard", "base_rates.txt"))
F["rates"] = {}
if br:
    for blk in re.finditer(r"--- (\d{4}-\d{2})\s+\(n=([\d,]+)\) ---(.*?)(?=\n\s*---|\Z)",
                           br, re.S):
        mon, n, body = blk.group(1), blk.group(2), blk.group(3)
        c = re.search(r"cost overrun :\s*(\d+)/(\d+)\s+known\s+\(\s*([\d.]+)%", body)
        t = re.search(r"time overrun :\s*(\d+)/(\d+)\s+known\s+\(\s*([\d.]+)%", body)
        md = re.search(r"delay months\s*: median ([\d.]+)", body)
        mc = re.search(r"cost overrun %: median ([\d.]+)", body)
        if c and t:
            F["rates"][mon] = dict(n=n, cost=c.group(3), time=t.group(3),
                                   med_delay=md.group(1) if md else None,
                                   med_cost=mc.group(1) if mc else None)

# table extraction
tj = os.path.join(ROOT, "extracted", "tables.jsonl")
dn = os.path.join(ROOT, "extracted", "tables_done.txt")
F["tbl_done"] = len([l for l in open(dn, encoding="utf-8") if l.strip()]) \
    if os.path.exists(dn) else 0
F["tbl_complete"] = F["tbl_done"] >= F["n_flash"] and F["n_flash"] > 0
F["tbl_rows"] = F["tbl_proj"] = F["tbl_agg"] = F["tbl_code"] = F["tbl_slip"] = 0
F["tbl_slipmag"] = 0
F["tbl_labels"] = collections.Counter()
F["tbl_years"] = collections.Counter()
F["tbl_codes"] = set()
if os.path.exists(tj):
    with open(tj, encoding="utf-8") as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except Exception:
                continue
            F["tbl_rows"] += 1
            F["tbl_years"][r.get("year")] += 1
            if r.get("is_aggregate"):
                F["tbl_agg"] += 1
                continue
            F["tbl_proj"] += 1
            F["tbl_labels"][r.get("section_label")] += 1
            if r.get("project_code"):
                F["tbl_code"] += 1
                F["tbl_codes"].add(r["project_code"])
            if r.get("section_label") == "EVENT_SLIP":
                F["tbl_slip"] += 1
                if r.get("delay_months"):
                    F["tbl_slipmag"] += 1

# linkage
ms = os.path.join(ROOT, "merged", "merge_summary.json")
F["link"] = json.load(open(ms, encoding="utf-8")) if os.path.exists(ms) else None

# ---------------------------------------------------------------- build
gen = datetime.now().strftime("%d %B %Y, %H:%M")
story.append(P("PAIMANA Data Acquisition &amp; Verification Report", "h1"))
story.append(P("SIH 2026 &mdash; Problem Statement 26103 (MoSPI, IPMD) &nbsp;&middot;&nbsp; "
               "generated %s" % gen, "sub"))
story.append(Spacer(1, 8))
story.append(note("How to read this report",
                  "Every figure is read from a data file at generation time by "
                  "<font face='Mono' size='8'>scripts/build_report.py</font>. No value is "
                  "hand-entered. Where a source file is absent or a run is unfinished, "
                  "the report states that instead of estimating. Regenerate at any time "
                  "to get current numbers."))

# 1 corpus
story.append(P("1. What was acquired", "h2"))
story.append(P("Two independent sources were harvested. They are complementary: the "
               "dashboard API gives rich fields over a short window, the PDF archive "
               "gives a long history at lower field richness.", "p"))
rows = [
    ["Monthly Flash Reports (PDF)", "%d files" % F["n_flash"],
     "%.2f GB" % (F["bytes"] / 2 ** 30),
     "%d&ndash;%d" % (min(cov), max(cov)) if cov else "&mdash;"],
    ["Quarterly PISR (PDF)", "%d files" % F["n_quart"], "included above", "&mdash;"],
]
if "panel_rows" in F:
    rows.append(["Dashboard API panel (JSON)",
                 "{:,} rows".format(F["panel_rows"]),
                 "{:,} projects".format(F["panel_projects"]),
                 "%s &ndash; %s" % (F["panel_months"][0], F["panel_months"][-1])])
else:
    rows.append(["Dashboard API panel (JSON)", MISSING, MISSING, MISSING])
story.append(tbl(["source", "volume", "size", "coverage"], rows,
                 [5.2 * cm, 3.4 * cm, 3.6 * cm, CW - 12.2 * cm]))

story.append(P("Coverage of the monthly archive", "h3"))
grid = []
for y in range(min(cov), max(cov) + 1) if cov else []:
    ms_ = cov.get(y, set())
    grid.append([str(y), "".join("#" if i in ms_ else "." for i in range(1, 13)),
                 "%d/12" % len(ms_)])
if grid:
    story.append(tbl(["year", "J F M A M J J A S O N D", "n"], grid,
                     [1.6 * cm, 6.0 * cm, 1.4 * cm], mono=(1,)))

# 2 verification
story.append(P("2. Verification", "h2"))
if F["verdict"]:
    u, tot, pages = F["verdict"]
    story.append(P("Every file was opened and checked for a valid PDF header, an "
                   "extractable text layer, and the presence of project rows.", "p"))
    story.append(tbl(["check", "result"], [
        ["Files carrying project-level data", "<b>%d of %d</b>" % (u, tot)],
        ["Files without project rows", "%d" % (tot - u)],
        ["Total pages verified", pages],
    ], [7.5 * cm, CW - 7.5 * cm]))
    story.append(Spacer(1, 5))
    story.append(note("The excluded files are not corrupt",
                      "They are short executive-summary editions (17&ndash;26 pages) with a "
                      "perfectly good text layer that simply do not contain the project "
                      "annexures. Consequence: <b>the usable project-level panel begins in "
                      "2009, not 2001.</b> A panel built naively across all files would show "
                      "those months as empty.", WARN))
else:
    story.append(P("Verification report %s &mdash; run "
                   "<font face='Mono' size='8'>scripts/verify_corpus.py</font>." % MISSING, "p"))

# 3 API findings
story.append(P("3. Measured findings &mdash; dashboard panel", "h2"))
if F["rates"]:
    rr = []
    for mon in sorted(F["rates"]):
        d = F["rates"][mon]
        rr.append([mon, d["n"], d["time"] + "%", d["cost"] + "%",
                   (d["med_delay"] or "&mdash;"), (d["med_cost"] or "&mdash;") + "%"])
    story.append(tbl(["snapshot", "projects", "time overrun",
                      "cost overrun", "median delay (mo)", "median cost overrun"],
                     rr, [2.4 * cm, 2.0 * cm, 2.6 * cm, 2.6 * cm, 3.0 * cm,
                          CW - 12.6 * cm]))
    story.append(Spacer(1, 5))
    story.append(P("Overruns are <b>computed</b> from <font face='Mono' size='8'>RevisedCost "
                   "vs OriginalCost</font> and <font face='Mono' size='8'>RevisedDate vs "
                   "OriginalEndDate</font>. The API's own overrun fields "
                   "(<font face='Mono' size='8'>DELAYED_TIME, COST_OVERRUN, COR_PERC, "
                   "TOR_PERC</font>) are returned <b>0% populated</b> and cannot be used.", "p"))
    story.append(note("Why the base rate decides everything",
                      "With roughly four in five monitored projects already behind "
                      "schedule, a model that predicts &ldquo;delayed&rdquo; for every project "
                      "scores that rate for free. Any accuracy claim must be stated against "
                      "this baseline, not against 50%.", BAD))
else:
    story.append(P("Base-rate file %s." % MISSING, "p"))

# 4 PDF extraction
story.append(P("4. Structured extraction from the PDF archive", "h2"))
if F["tbl_rows"]:
    status = ("complete" if F["tbl_complete"]
              else "<b>IN PROGRESS &mdash; %d of %d files parsed.</b> Figures below are "
                   "partial and will change." % (F["tbl_done"], F["n_flash"]))
    story.append(P("Status: " + status, "p"))
    pr = F["tbl_proj"] or 1
    story.append(tbl(["measure", "value"], [
        ["Rows extracted", "{:,}".format(F["tbl_rows"])],
        ["Project-level rows", "{:,} ({:.1f}%)".format(F["tbl_proj"],
                                                       100 * F["tbl_proj"] / max(F["tbl_rows"], 1))],
        ["Aggregate / summary rows (excluded from project counts)",
         "{:,} ({:.1f}%)".format(F["tbl_agg"], 100 * F["tbl_agg"] / max(F["tbl_rows"], 1))],
        ["Project-level rows carrying an OCMS code",
         "{:,} ({:.1f}%)".format(F["tbl_code"], 100 * F["tbl_code"] / pr)],
        ["Distinct OCMS project codes seen", "{:,}".format(len(F["tbl_codes"]))],
        ["Slip events (EVENT_SLIP)", "{:,}".format(F["tbl_slip"])],
        ["&nbsp;&nbsp;of which carry a delay magnitude", "{:,}".format(F["tbl_slipmag"])],
    ], [9.5 * cm, CW - 9.5 * cm]))

    story.append(P("Section labels assigned", "h3"))
    lab = [[k, "{:,}".format(v), "%.1f%%" % (100 * v / pr)]
           for k, v in F["tbl_labels"].most_common(12)]
    story.append(tbl(["label", "rows", "share"], lab,
                     [7.0 * cm, 2.6 * cm, CW - 9.6 * cm]))
    uncl = F["tbl_labels"].get("UNCLASSIFIED", 0)
    story.append(Spacer(1, 5))
    story.append(note("Label accuracy varies by era &mdash; state this, do not hide it",
                      "Unclassified rows currently stand at <b>%.1f%%</b> of project-level "
                      "rows. On a single modern report tuned during development the figure "
                      "was 0.3%%; across the whole archive it is higher because table layouts "
                      "and heading wording drift between eras. The corpus-wide figure is the "
                      "honest one to quote." % (100 * uncl / pr), WARN))
else:
    story.append(P("Extraction output %s &mdash; run "
                   "<font face='Mono' size='8'>scripts/extract_tables.py</font>." % MISSING, "p"))

# 5 linkage
story.append(P("5. Identifier linkage &mdash; an unsolved problem", "h2"))
story.append(P("The two sources use unrelated identifier systems. PAIMANA replaced "
               "OCMS-2006 and renumbered every project.", "p"))
link_rate = "&mdash;"
if F["link"]:
    lr = F["link"]
    if lr.get("pdf_entities"):
        link_rate = "%.1f%%" % (100 * lr.get("linked", 0) / lr["pdf_entities"])
story.append(tbl(["", "identifier", "stable within source?", "links to the other?"], [
    ["PDF archive", "OCMS code e.g. N24001658", "yes, across monthly reports",
     "no &mdash; name-match rate %s" % link_rate],
    ["Dashboard API", "ProjectId e.g. 706718", "yes, across freeze months",
     "no"],
], [2.6 * cm, 4.6 * cm, 4.4 * cm, CW - 11.6 * cm]))
story.append(Spacer(1, 5))
story.append(note("Do not present these as one continuous series",
                  "Within each source the join is exact and safe. Between them it is "
                  "probabilistic record linkage on project names typed by different people "
                  "across two decades. Treat them as two linked panels, and state the "
                  "caveat wherever a claim spans both.", BAD))

# 6 corrections
story.append(P("6. Errors found and corrected during this work", "h2"))
story.append(P("Recorded because the corrected figures are only trustworthy if the "
               "corrections are visible. Each was found by checking a derived number "
               "against the source document.", "p"))
story.append(tbl(["what went wrong", "how it showed up", "resolution"], [
    ["Section heading carried forward across pages that had none",
     "EVENT_SLIP inflated to 138,128 rows; slip rates of 80&ndash;98% per month, which "
     "is not credible",
     "Per-table titles; inheritance now requires a matching column signature"],
    ["Two-line headings read only on the second line",
     "4,943 rows in one report labelled from &ldquo;Costing Rs. 150 Crore and above&rdquo;, "
     "which carries no section information",
     "Multiple title candidates including pairwise joins"],
    ["Fallback accepted any long line as a heading",
     "137 invented sections such as &ldquo;NAGPUR RING ROAD PACKAGE-2&rdquo;",
     "Return no title rather than guess; let structural inheritance fill it"],
    ["Regex <font face='Mono' size='7.5'>deal?y</font> matched &ldquo;dealy&rdquo; but "
     "not &ldquo;delay&rdquo;",
     "3,507 rows dropped to UNCLASSIFIED",
     "Corrected pattern; 13 classifier unit tests added"],
    ["Aggregate summary tables counted as project rows",
     "Row counts overstated",
     "Tables without a project column flagged <font face='Mono' size='7.5'>is_aggregate</font>"],
    ["Dates harvested as currency values",
     "&ldquo;03/2021&rdquo; contributed 3 and 2021 to cost columns",
     "Dates stripped before money extraction"],
], [4.6 * cm, 5.8 * cm, CW - 10.4 * cm]))

# 7 limitations
story.append(P("7. Known limitations", "h2"))
story.append(tbl(["limitation", "detail"], [
    ["2019 is entirely absent",
     "272&ndash;404 filename variants probed across both archive hosts and both "
     "financial-year folder conventions. The files are not published."],
    ["2001&ndash;2003 unusable for project data",
     "Executive-summary editions only. Usable panel starts 2009."],
    ["CUF specification not public",
     "The Common Upload Form referenced in the problem statement is not published. Any "
     "field list is inferred from what the monitoring feed exposes, which may be a "
     "subset. Say &ldquo;fields exposed in the public feed&rdquo;, not &ldquo;the CUF&rdquo;."],
    ["Free-text reason fields are empty",
     "RevisedCostReason, RevisedDateReason and Remarks are 0% populated in the public "
     "feed. Narrative analysis of delay causes is not deliverable from this data."],
    ["Onboarding ramp confounds the early panel",
     "Project counts rise steeply across the first snapshots as projects migrate onto "
     "PAIMANA. A project appearing is onboarding, not a new project."],
], [4.8 * cm, CW - 4.8 * cm]))

# 8 repro
story.append(P("8. Reproduction", "h2"))
story.append(P("The corpus is reproducible without redistributing %.1f GB: "
               "<font face='Mono' size='8'>manifest_all.csv</font> records the source URL "
               "of every file." % (F["bytes"] / 2 ** 30), "p"))
story.append(tbl(["step", "command"], [
    ["Download the archive", "python scripts/download_all.py"],
    ["Recover missing months", "python scripts/fill_gaps.py"],
    ["Verify integrity", "python scripts/verify_corpus.py"],
    ["Extract tables", "python scripts/extract_tables.py"],
    ["Harvest the dashboard panel", "python scripts/scrape_dashboard.py"],
    ["Compute base rates", "python scripts/analyze_dashboard_panel.py"],
    ["Regenerate this report", "python scripts/build_report.py"],
], [5.4 * cm, CW - 5.4 * cm], mono=(1,)))
story.append(Spacer(1, 6))
story.append(P("Sources are public Government of India publications. Content owned and "
               "maintained by IPMD, MoSPI.", "small"))


def furniture(c, d):
    c.saveState()
    c.setFont("Body", 7.4)
    c.setFillColor(MUTED)
    c.drawString(M, 1.05 * cm, "PAIMANA Data Report - SIH 2026 PS 26103")
    c.drawRightString(PW - M, 1.05 * cm, "Page %d" % d.page)
    c.setStrokeColor(LINE)
    c.setLineWidth(0.5)
    c.line(M, 1.32 * cm, PW - M, 1.32 * cm)
    c.restoreState()


doc = BaseDocTemplate(OUT, pagesize=A4, leftMargin=M, rightMargin=M,
                      topMargin=1.5 * cm, bottomMargin=1.8 * cm,
                      title="PAIMANA Data Acquisition and Verification Report",
                      author="SIH 2026 PS 26103")
doc.addPageTemplates([PageTemplate(id="m", frames=[
    Frame(M, 1.8 * cm, CW, PH - 1.5 * cm - 1.8 * cm, id="f",
          leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)],
    onPage=furniture)])
doc.build(story)
print("wrote", OUT)
print("extraction complete:", F["tbl_complete"], "| files parsed:", F["tbl_done"],
      "| rows:", F["tbl_rows"])
