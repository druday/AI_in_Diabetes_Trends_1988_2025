#!/usr/bin/env python3
from __future__ import annotations

from datetime import date
from pathlib import Path

from docx import Document
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


ROOT = Path("/Users/uday/AI in Diabetology")
DOCS_DIR = ROOT / "docs"
DOCX_OUT = DOCS_DIR / "AI_Diabetes_Dual_Track_Publication_Blueprint_V1.docx"
MD_OUT = DOCS_DIR / "AI_Diabetes_Dual_Track_Publication_Blueprint_V1.md"

TITLE = "Dual-Track Publication Blueprint for AI in Diabetes Research"
SUBTITLE = (
    "Main informatics manuscript plus diabetes-journal letter/commentary options "
    "based on collaborator feedback"
)


MAPPING_ROWS = [
    (
        "Growth in publications, institutional nodes, and collaboration edges",
        "The field expanded rapidly in both output and participating institutions.",
        "AI in diabetes is no longer a niche topic; it is now a broad multi-institutional research area.",
        "Main informatics paper",
        "JAMIA / npj Digital Medicine / JBI",
    ),
    (
        "Interdisciplinarity increased over time",
        "AI-and-diabetes work increasingly brings together clinical, technical, public-health, complications, and device groups.",
        "The field is becoming more translational and less siloed.",
        "Main paper + short clinical piece",
        "JAMIA + DOM / Diabetic Medicine",
    ),
    (
        "2016-2019 collaboration surge includes a mega-collaboration outlier",
        "One extremely large collaboration episode inflated some cohesion metrics.",
        "A spike in network cohesion does not automatically mean routine clinical integration.",
        "Main paper only",
        "JAMIA / JBI",
    ),
    (
        "Shift from Tech/AI-centered ties toward clinically anchored and complications-linked ties",
        "AI is increasingly embedded inside clinical and complications-focused work instead of sitting outside as a purely technical partner.",
        "The field appears to be moving closer to real-world diabetes care questions.",
        "Main paper + strong clinical short piece",
        "npj Digital Medicine + DOM / Diabetic Medicine",
    ),
    (
        "Geographic expansion with uneven international integration",
        "Research output spread globally, but not all growth reflects cross-border collaboration.",
        "Rising research volume does not necessarily mean globally integrated diabetes AI development.",
        "Best short clinical piece + main paper",
        "DOM / Primary Care Diabetes / main paper geography section",
    ),
    (
        "China/WPRO growth versus cross-border integration",
        "China became a major volume contributor, but much of that growth remained domestically concentrated.",
        "Geographic leadership and international integration are not the same thing.",
        "Best letter/commentary candidate",
        "DOM / Primary Care Diabetes / BMJ Open DRC if short format fits",
    ),
    (
        "Funding-stratified structural differences",
        "Funded and non-funded work show different collaboration shapes and partner profiles.",
        "Funding may influence whether AI-in-diabetes work remains narrow or becomes more multidisciplinary.",
        "Main paper, with possible secondary short piece",
        "JAMIA / npj Digital Medicine / DTT",
    ),
]

MAIN_PAPER_POINTS = [
    "Position the paper as a full original research article for a medical informatics or digital medicine audience rather than a clinically simplified bibliometric note.",
    "Use one repeated central message: AI-in-diabetes research has grown from a small, relatively siloed literature into a broader, more interdisciplinary, clinically embedded, and globally distributed collaboration ecosystem, but that maturation remains uneven.",
    "Make the method itself part of the contribution: reproducible PubMed retrieval, affiliation-level institutional mapping, LLM-assisted domain grouping, and interpretable temporal network analysis.",
    "Translate every major network result into plain-language clinical meaning in the Discussion so the paper stays accessible outside a pure informatics audience.",
]

MAIN_STRUCTURE_ROWS = [
    (
        "Introduction",
        "Why collaboration structure matters in AI-in-diabetes research, why publication counts alone are insufficient, and why institutional mapping is relevant for translational maturity.",
    ),
    (
        "Methods",
        "PubMed search strategy, screening, affiliation extraction, LLM-assisted grouping, validation subset plan, temporal bins, network construction, interdisciplinarity, geography, funding, and sensitivity analyses.",
    ),
    (
        "Results",
        "Corpus growth, network cohesion, institutional roles and transitions, interdisciplinarity, central institutions, geography, and funding-stratified differences.",
    ),
    (
        "Discussion",
        "What maturation means in practical translational terms, why growth does not always mean integration, and why geographic/funding differences matter for diabetes AI translation.",
    ),
    (
        "Limitations",
        "Affiliation-classification limits, accepted Other pool, disambiguation constraints, outlier effects, and the fact that network metrics describe collaboration structure rather than clinical effectiveness.",
    ),
]

MAIN_KEEP_ROWS = [
    ("Corpus/period summary", "Main paper", "Keep as a compact grounding table."),
    ("Network cohesion table", "Main paper", "Keep, but pair averages with median degree and outlier caution."),
    ("One role-flow figure", "Main paper", "Use the clearest role-transition visual only."),
    ("One interdisciplinarity figure", "Main paper", "Prefer the pairwise heatmap plus focused interpretation."),
    ("One geography figure", "Main paper + strongest short piece", "Use the geography story to separate volume from integration."),
    ("One funding figure", "Main paper", "Use the funded vs no-grant partner-profile comparison."),
    ("Dense exploratory visuals", "Supplement only", "Move HTML interactives and dense tables to supplementary material."),
]

MAIN_MANDATORY_REVISIONS = [
    "Add explicit manual-validation and inter-rater agreement reporting for the LLM affiliation grouping.",
    "Add a sensitivity analysis that removes the 2016-2019 mega-collaboration outlier and shows which conclusions are stable.",
    "Use plain-language section leads and avoid framing the paper as 'AI in diabetology'; prefer 'AI in diabetes research' or 'AI-and-diabetes research'.",
    "Keep geography interpretation focused on both volume and cross-border structure so China/WPRO growth is not over-read as equivalent international integration.",
]

LETTER_OPTIONS = [
    {
        "title": "Option 1. Geography and international integration",
        "recommendation": "Recommended first clinical short piece",
        "theme": "Global growth does not equal global integration in AI-and-diabetes research.",
        "findings": [
            "WHO-region shift toward the Western Pacific Region after 2015",
            "China's rapid post-2015 growth in publication volume",
            "Domestic concentration versus cross-country integration",
            "Country and WHO-region collaboration heatmaps as the main evidence",
        ],
        "why": "This story is easy to understand clinically, policy-relevant, and does not require readers to absorb much network-science vocabulary.",
        "targets": [
            "Diabetes, Obesity and Metabolism letter",
            "Primary Care Diabetes letter/commentary route",
            "BMJ Open Diabetes Research & Care only if the short-format fit is confirmed at submission time",
        ],
    },
    {
        "title": "Option 2. Clinical embedding and interdisciplinarity",
        "recommendation": "Strong backup short piece",
        "theme": "AI-in-diabetes research is becoming more clinically embedded and multidisciplinary.",
        "findings": [
            "Growth in multi-field connected components",
            "Shift from pure Tech/AI dominance toward Clinical Medicine and complications-linked collaboration",
            "Selected exact two-field profiles translated into a simple clinical story",
        ],
        "why": "This gives the clearest translational narrative: AI is moving closer to real clinical diabetes care questions.",
        "targets": [
            "Diabetes, Obesity and Metabolism commentary/letter",
            "Diabetic Medicine correspondence/brief format",
            "Primary Care Diabetes if framed around translation and care delivery",
        ],
    },
    {
        "title": "Option 3. Funding and collaboration structure",
        "recommendation": "Niche but plausible secondary short piece",
        "theme": "Funding appears to shape how narrowly or broadly AI-in-diabetes collaborations are organized.",
        "findings": [
            "Funded versus no-grant exact two-field partner-profile differences",
            "Differences in diversification and clinical anchoring",
            "Potential policy implications for translational research support",
        ],
        "why": "This is interesting and policy-facing, but it is less immediately intuitive to a broad clinical audience than geography or interdisciplinarity.",
        "targets": [
            "Diabetes Technology & Therapeutics commentary or observational letter",
            "Possibly a technology-facing diabetes journal rather than a broad clinical journal",
        ],
    },
]

JOURNAL_ROWS = [
    (
        "JAMIA",
        "Primary main-paper target",
        "Original Research / Applications",
        "Strong fit for reproducible informatics methods, LLM-assisted classification, and translational ecosystem framing.",
        "Best if the manuscript clearly owns the method and keeps plain-language interpretation strong.",
    ),
    (
        "npj Digital Medicine",
        "High-visibility main-paper target",
        "Article",
        "Strong fit if the paper is framed as digital-medicine maturation, clinical embedding, and global system-level change.",
        "Best when the narrative is broader than bibliometrics and clearly connected to translational implications.",
    ),
    (
        "Journal of Biomedical Informatics",
        "Pragmatic main-paper backup",
        "Original Article",
        "Good fit for a methods-forward manuscript if the paper remains more technical and evaluation-centric.",
        "Useful backup if the framing lands more on framework development than on big-picture digital medicine.",
    ),
    (
        "Diabetes, Obesity and Metabolism",
        "Best clinical short-piece target",
        "Letter to the Editor or Commentary",
        "Current author guidance indicates letters up to 1,200 words with up to 2 small figures/tables, and commentaries up to 1,500 words.",
        "Best venue for a concise geography or interdisciplinarity story with direct translational relevance.",
    ),
    (
        "Diabetic Medicine",
        "Strong backup clinical target",
        "Letter / correspondence",
        "Current author guidance indicates letters up to 800 words with 1 figure/table and 10 references.",
        "Good fit for a tightly framed clinical-translation message with less methods detail.",
    ),
    (
        "Primary Care Diabetes",
        "Practical backup for geography or translation angle",
        "Letter/commentary path to verify",
        "The journal clearly publishes letters, but exact format requirements should be checked directly at submission stage.",
        "Potentially attractive if the message is framed around real-world diffusion, care delivery, and translational gaps.",
    ),
    (
        "Diabetes Technology & Therapeutics",
        "Best niche funding/technology short-piece target",
        "Commentary / Observational Letter",
        "Current author guidance supports Commentary at 1,000 words and Observational Letter at 750 words.",
        "Better for the funding or device/technology story than for a broad clinical-global integration piece.",
    ),
]

REPLY_DRAFT = [
    "Dear Prof. Khunti,",
    (
        "Thank you very much for the careful and constructive comments. We agree with your overall assessment that the current draft is written too heavily in network-science and AI language for a clinical diabetes audience, and that the main next step is to simplify the framing and translate the findings into clearer clinical and translational implications."
    ),
    (
        "Based on your feedback and further discussion with Prof. Jiang, we plan to take a dual-track approach. First, we will develop the present work into a full informatics-oriented original research paper that can properly present the methods, validation, and collaboration-mapping framework. In parallel, we will develop a shorter clinically focused piece that highlights the most diabetes-facing findings in simpler language."
    ),
    (
        "At present, the strongest candidate for the shorter clinical piece appears to be the geography and international-collaboration story, particularly the distinction between rising publication volume and true cross-border integration. We also see the interdisciplinarity and clinical-embedding findings as strong secondary options."
    ),
    (
        "If you agree, would you see the geography and collaboration findings as the best candidate for a short diabetes-journal letter or commentary? We would be very grateful for your view on that specific direction as we prepare the next revision."
    ),
    "With thanks again for your guidance,",
    "Uday",
]

SOURCE_NOTES = [
    (
        "Journal fit notes were checked against current official journal pages on June 11, 2026. "
        "These should still be rechecked immediately before submission."
    ),
    (
        "The main paper should not be diluted into multiple overlapping short papers. The cleanest strategy is one strong informatics paper plus one clinically focused short piece drafted in parallel."
    ),
]


def set_cell_shading(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_cell_margins(cell, top: int = 90, bottom: int = 90, start: int = 120, end: int = 120) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_mar = tc_pr.find(qn("w:tcMar"))
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for key, value in {"top": top, "bottom": bottom, "start": start, "end": end}.items():
        node = tc_mar.find(qn(f"w:{key}"))
        if node is None:
            node = OxmlElement(f"w:{key}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def style_run(run, *, font: str = "Calibri", size: float = 11, bold: bool = False, italic: bool = False, color: str = "1f2937") -> None:
    run.font.name = font
    run._element.rPr.rFonts.set(qn("w:ascii"), font)
    run._element.rPr.rFonts.set(qn("w:hAnsi"), font)
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = RGBColor.from_string(color)


def apply_base_styles(doc: Document) -> None:
    section = doc.sections[0]
    section.top_margin = Inches(0.8)
    section.bottom_margin = Inches(0.75)
    section.left_margin = Inches(0.9)
    section.right_margin = Inches(0.9)
    section.header_distance = Inches(0.35)
    section.footer_distance = Inches(0.35)

    styles = doc.styles
    normal = styles["Normal"]
    normal.font.name = "Calibri"
    normal._element.rPr.rFonts.set(qn("w:ascii"), "Calibri")
    normal._element.rPr.rFonts.set(qn("w:hAnsi"), "Calibri")
    normal.font.size = Pt(11)
    normal.font.color.rgb = RGBColor.from_string("1f2937")
    normal.paragraph_format.space_after = Pt(7)
    normal.paragraph_format.line_spacing = 1.22

    for name, size, color in [
        ("Title", 24, "0f172a"),
        ("Heading 1", 15.5, "1d4ed8"),
        ("Heading 2", 12.5, "1e3a8a"),
        ("Heading 3", 11.5, "0f172a"),
    ]:
        style = styles[name]
        style.font.name = "Calibri"
        style._element.rPr.rFonts.set(qn("w:ascii"), "Calibri")
        style._element.rPr.rFonts.set(qn("w:hAnsi"), "Calibri")
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = RGBColor.from_string(color)
        style.paragraph_format.space_before = Pt(12 if "Heading" in name else 0)
        style.paragraph_format.space_after = Pt(6)


def add_header_footer(doc: Document) -> None:
    for section in doc.sections:
        header = section.header.paragraphs[0]
        header.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        run = header.add_run("AI in Diabetes Publication Strategy")
        style_run(run, size=8.5, color="64748b")

        footer = section.footer.paragraphs[0]
        footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = footer.add_run("Dual-track blueprint | Main informatics paper + clinical short-piece options")
        style_run(run, size=8.5, color="64748b")


def add_title_block(doc: Document) -> None:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(3)
    r = p.add_run("PUBLICATION BLUEPRINT")
    style_run(r, size=10.5, bold=True, color="2563eb")

    p = doc.add_paragraph(style="Title")
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(4)
    r = p.add_run(TITLE)
    style_run(r, size=24, bold=True, color="0f172a")

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(12)
    r = p.add_run(SUBTITLE)
    style_run(r, size=12, italic=True, color="475569")

    meta = doc.add_table(rows=1, cols=3)
    meta.alignment = WD_TABLE_ALIGNMENT.CENTER
    meta.autofit = False
    widths = [2.0, 2.0, 2.3]
    labels = [
        ("Primary recommendation", "Main informatics paper + one clinical short piece"),
        ("Prepared", date(2026, 6, 11).strftime("%B %d, %Y")),
        ("Current basis", "Prof. Jiang guidance + Prof. Khunti feedback + V4 report"),
    ]
    for idx, (label, value) in enumerate(labels):
        cell = meta.rows[0].cells[idx]
        cell.width = Inches(widths[idx])
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        set_cell_shading(cell, "EFF6FF")
        set_cell_margins(cell, top=110, bottom=110, start=120, end=120)
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.add_run(label + "\n")
        style_run(p.runs[0], size=9, bold=True, color="1e3a8a")
        r = p.add_run(value)
        style_run(r, size=10.2, color="0f172a")
    doc.add_paragraph()


def add_note_box(doc: Document, title: str, body: str) -> None:
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    cell = table.cell(0, 0)
    cell.width = Inches(6.4)
    set_cell_shading(cell, "EEF4F8")
    set_cell_margins(cell, top=140, bottom=140, start=140, end=140)
    p = cell.paragraphs[0]
    p.paragraph_format.space_after = Pt(0)
    run = p.add_run(title + ". ")
    style_run(run, size=10.8, bold=True, color="0f172a")
    run = p.add_run(body)
    style_run(run, size=10.5, color="1f2937")
    doc.add_paragraph()


def add_paragraph(doc: Document, text: str, *, bold_lead: str | None = None) -> None:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    if bold_lead:
        lead = p.add_run(bold_lead)
        style_run(lead, bold=True)
        rest = p.add_run(text)
        style_run(rest)
    else:
        run = p.add_run(text)
        style_run(run)


def add_bullets(doc: Document, items: list[str]) -> None:
    for item in items:
        p = doc.add_paragraph(style=None)
        p.paragraph_format.left_indent = Inches(0.2)
        p.paragraph_format.space_after = Pt(3)
        r = p.add_run(f"- {item}")
        style_run(r)


def add_table_caption(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(4)
    r = p.add_run(text)
    style_run(r, size=9.5, bold=True, italic=True, color="334155")


def add_table(doc: Document, columns: list[str], rows: list[list[str]], widths: list[float], font_size: float = 8.8) -> None:
    table = doc.add_table(rows=1, cols=len(columns))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False

    for idx, col in enumerate(columns):
        cell = table.rows[0].cells[idx]
        cell.width = Inches(widths[idx])
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        set_cell_shading(cell, "DCEAF7")
        set_cell_margins(cell)
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(col)
        style_run(r, size=font_size, bold=True, color="0f172a")

    for row_idx, row in enumerate(rows):
        cells = table.add_row().cells
        for idx, val in enumerate(row):
            cell = cells[idx]
            cell.width = Inches(widths[idx])
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            set_cell_margins(cell)
            if row_idx % 2 == 0:
                set_cell_shading(cell, "F8FBFD")
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT if idx < 3 else WD_ALIGN_PARAGRAPH.CENTER
            r = p.add_run(str(val))
            style_run(r, size=font_size, color="1f2937")
    doc.add_paragraph()


def build_docx() -> None:
    doc = Document()
    apply_base_styles(doc)
    add_header_footer(doc)
    add_title_block(doc)

    add_note_box(
        doc,
        "Recommended direction",
        (
            "Use the present analysis as the basis for a full original research paper in a medical informatics or digital medicine journal, "
            "while developing one shorter clinically framed diabetes-journal piece in parallel. This preserves the methods contribution without "
            "forcing the entire project into a purely clinical narrative too early."
        ),
    )

    doc.add_paragraph("1. Executive Recommendation", style="Heading 1")
    add_paragraph(
        doc,
        (
            "Prof. Jiang's recommendation and Prof. Khunti's comments point toward a dual-track strategy rather than an either-or choice. "
            "The strongest path is to let the main paper own the framework, validation, and full collaboration analysis, then distill one "
            "clinically intuitive storyline into a short letter or commentary."
        ),
    )
    add_bullets(
        doc,
        [
            "Main paper: methods-forward original research article for an informatics or digital medicine journal.",
            "Parallel short piece: clinically framed, low-jargon story built around one high-yield finding set.",
            "Best first short-piece candidate: geography and international integration.",
            "Best backup short-piece candidate: interdisciplinarity and clinical embedding.",
        ],
    )

    doc.add_paragraph("2. Finding-to-Format Mapping Table", style="Heading 1")
    add_paragraph(
        doc,
        "This working table translates the main technical findings into plain language and assigns each one to its most natural publication format.",
    )
    add_table_caption(doc, "Working Table 1. Technical findings mapped to plain-language meaning, clinical relevance, and best publication format.")
    add_table(
        doc,
        ["Technical finding", "Plain-language interpretation", "Clinical / translational implication", "Best format", "Best journal family"],
        [list(row) for row in MAPPING_ROWS],
        [1.55, 1.65, 1.8, 1.15, 0.95],
        font_size=8.0,
    )

    doc.add_paragraph("3. Main Informatics Manuscript Blueprint", style="Heading 1")
    add_paragraph(
        doc,
        "The main paper should be framed as a reproducible collaboration-mapping study that shows how AI-in-diabetes research has grown, diversified, and clinically embedded over time.",
    )
    add_bullets(doc, MAIN_PAPER_POINTS)

    doc.add_paragraph("Recommended target-journal order", style="Heading 2")
    add_table_caption(doc, "Working Table 2. Main-paper journal positioning.")
    add_table(
        doc,
        ["Journal", "Role", "Why it fits"],
        [
            ["JAMIA", "Primary stretch option", "Best if the manuscript emphasizes reproducible informatics methods, LLM-assisted classification, and translational ecosystem measurement."],
            ["npj Digital Medicine", "High-visibility alternative", "Best if the framing is broader and more system-level, focusing on digital-medicine maturation and clinical embedding."],
            ["Journal of Biomedical Informatics", "Pragmatic backup", "Best if the paper stays more method-centric and evaluation-focused."],
        ],
        [1.35, 1.35, 3.7],
        font_size=8.5,
    )

    doc.add_paragraph("Proposed paper structure", style="Heading 2")
    add_table_caption(doc, "Working Table 3. Suggested section architecture for the main informatics manuscript.")
    add_table(
        doc,
        ["Section", "What it should do"],
        [list(row) for row in MAIN_STRUCTURE_ROWS],
        [1.2, 5.2],
        font_size=8.7,
    )

    doc.add_paragraph("Figures and tables to keep in the main paper", style="Heading 2")
    add_table_caption(doc, "Working Table 4. High-value manuscript visuals versus supplementary material.")
    add_table(
        doc,
        ["Artifact", "Placement", "Rationale"],
        [list(row) for row in MAIN_KEEP_ROWS],
        [1.8, 1.3, 3.3],
        font_size=8.6,
    )

    doc.add_paragraph("Mandatory revisions before drafting", style="Heading 2")
    add_bullets(doc, MAIN_MANDATORY_REVISIONS)

    doc.add_paragraph("4. Diabetes-Journal Letter / Commentary Options", style="Heading 1")
    add_paragraph(
        doc,
        "The short clinical piece should not try to compress the entire project. It should tell one simple story that still has clear translational meaning for a diabetes audience.",
    )
    for option in LETTER_OPTIONS:
        doc.add_paragraph(option["title"], style="Heading 2")
        add_paragraph(doc, option["recommendation"], bold_lead="Recommendation: ")
        add_paragraph(doc, option["theme"], bold_lead="Theme: ")
        add_paragraph(doc, option["why"], bold_lead="Why this works: ")
        add_paragraph(doc, " ", bold_lead="Use these findings: ")
        add_bullets(doc, option["findings"])
        add_paragraph(doc, " ", bold_lead="Potential targets: ")
        add_bullets(doc, option["targets"])

    doc.add_paragraph("5. Journal-Target Matrix", style="Heading 1")
    add_paragraph(
        doc,
        "This matrix separates the full original-research route from the shorter clinical-format options. Format notes reflect official journal pages checked on June 11, 2026 and should be reconfirmed before submission.",
    )
    add_table_caption(doc, "Working Table 5. Journal-target matrix for the main manuscript and parallel short-piece options.")
    add_table(
        doc,
        ["Journal", "Primary role", "Likely format", "Fit note", "Submission caution"],
        [list(row) for row in JOURNAL_ROWS],
        [1.2, 1.2, 1.2, 1.8, 1.2],
        font_size=7.8,
    )

    doc.add_paragraph("6. Suggested Response to Prof. Khunti", style="Heading 1")
    add_paragraph(
        doc,
        "The note below keeps the response concise, appreciative, and strategically aligned with Prof. Jiang's recommendation.",
    )
    box = doc.add_table(rows=1, cols=1)
    box.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = box.cell(0, 0)
    set_cell_shading(cell, "F8FBFD")
    set_cell_margins(cell, top=140, bottom=140, start=160, end=160)
    first = cell.paragraphs[0]
    for idx, line in enumerate(REPLY_DRAFT):
        if idx == 0:
            run = first.add_run(line)
        else:
            para = cell.add_paragraph()
            run = para.add_run(line)
        style_run(run, size=10.3, color="1f2937")
    doc.add_paragraph()

    doc.add_paragraph("7. Practical Next Steps", style="Heading 1")
    add_bullets(
        doc,
        [
            "Build the main manuscript outline first so the methods, validation, and major figures have a stable home.",
            "In parallel, draft one short geography-focused clinical piece and keep the interdisciplinarity piece as a backup, not a simultaneous second submission.",
            "Prepare the finding-to-format table as a working discussion tool for Profs. Jiang, Khunti, Misra, and Orlander.",
            "Recheck final journal instructions immediately before drafting because letter and commentary formats can change.",
        ],
    )

    add_note_box(doc, "Source note", " ".join(SOURCE_NOTES))

    DOCX_OUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(DOCX_OUT)


def build_markdown() -> None:
    lines: list[str] = []
    lines.append(f"# {TITLE}")
    lines.append("")
    lines.append(f"*{SUBTITLE}*")
    lines.append("")
    lines.append(f"Prepared: {date(2026, 6, 11).strftime('%B %d, %Y')}")
    lines.append("")
    lines.append("## Executive Recommendation")
    lines.append("")
    lines.append(
        "Use the current analysis as the basis for a full original research paper in a medical informatics or digital medicine journal, while developing one shorter clinically framed diabetes-journal piece in parallel."
    )
    lines.append("")
    lines.append("- Main paper: methods-forward original research article for an informatics or digital medicine journal.")
    lines.append("- Parallel short piece: clinically framed, low-jargon story built around one high-yield finding set.")
    lines.append("- Best first short-piece candidate: geography and international integration.")
    lines.append("- Best backup short-piece candidate: interdisciplinarity and clinical embedding.")
    lines.append("")
    lines.append("## Finding-to-Format Mapping Table")
    lines.append("")
    lines.append("| Technical finding | Plain-language interpretation | Clinical / translational implication | Best format | Best journal family |")
    lines.append("| --- | --- | --- | --- | --- |")
    for row in MAPPING_ROWS:
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")
    lines.append("## Main Informatics Manuscript Blueprint")
    lines.append("")
    for item in MAIN_PAPER_POINTS:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("### Recommended target-journal order")
    lines.append("")
    lines.append("1. JAMIA")
    lines.append("2. npj Digital Medicine")
    lines.append("3. Journal of Biomedical Informatics")
    lines.append("")
    lines.append("### Proposed paper structure")
    lines.append("")
    for section, desc in MAIN_STRUCTURE_ROWS:
        lines.append(f"- **{section}:** {desc}")
    lines.append("")
    lines.append("### Figures and tables to keep")
    lines.append("")
    for artifact, placement, rationale in MAIN_KEEP_ROWS:
        lines.append(f"- **{artifact} ({placement}):** {rationale}")
    lines.append("")
    lines.append("### Mandatory revisions before drafting")
    lines.append("")
    for item in MAIN_MANDATORY_REVISIONS:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("## Diabetes-Journal Letter / Commentary Options")
    lines.append("")
    for option in LETTER_OPTIONS:
        lines.append(f"### {option['title']}")
        lines.append("")
        lines.append(f"- **Recommendation:** {option['recommendation']}")
        lines.append(f"- **Theme:** {option['theme']}")
        lines.append(f"- **Why this works:** {option['why']}")
        lines.append("- **Use these findings:**")
        for finding in option["findings"]:
            lines.append(f"  - {finding}")
        lines.append("- **Potential targets:**")
        for target in option["targets"]:
            lines.append(f"  - {target}")
        lines.append("")
    lines.append("## Journal-Target Matrix")
    lines.append("")
    lines.append("| Journal | Primary role | Likely format | Fit note | Submission caution |")
    lines.append("| --- | --- | --- | --- | --- |")
    for row in JOURNAL_ROWS:
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")
    lines.append("## Suggested Response to Prof. Khunti")
    lines.append("")
    for line in REPLY_DRAFT:
        lines.append(line)
        lines.append("")
    lines.append("## Practical Next Steps")
    lines.append("")
    lines.append("- Build the main manuscript outline first so the methods, validation, and major figures have a stable home.")
    lines.append("- In parallel, draft one short geography-focused clinical piece and keep the interdisciplinarity piece as a backup, not a simultaneous second submission.")
    lines.append("- Prepare the finding-to-format table as a working discussion tool for Profs. Jiang, Khunti, Misra, and Orlander.")
    lines.append("- Recheck final journal instructions immediately before drafting because letter and commentary formats can change.")
    lines.append("")
    lines.append("## Source Note")
    lines.append("")
    for note in SOURCE_NOTES:
        lines.append(f"- {note}")
    lines.append("")
    MD_OUT.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    build_docx()
    build_markdown()
    print(f"Wrote {DOCX_OUT}")
    print(f"Wrote {MD_OUT}")


if __name__ == "__main__":
    main()
