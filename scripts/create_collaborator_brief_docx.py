#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


TITLE = "Mapping Collaboration in AI and Diabetes Research: A Temporal Institutional Network Bibliometric Analysis"
SUBTITLE = "Collaborator Concept Brief"

CATEGORIES = [
    (
        "Technical / AI / Informatics",
        "Computer science, engineering, biomedical informatics, data science, and computational medicine groups developing AI methods or digital infrastructure.",
        "Computer science, AI, machine learning, engineering, informatics, data science, biomedical informatics, bioinformatics",
    ),
    (
        "Endocrinology / Diabetes",
        "Core clinical and translational diabetes specialty groups central to diabetology practice and disease management.",
        "Endocrinology, diabetology, metabolism, diabetes center, diabetes institute, insulin",
    ),
    (
        "Ophthalmology / Vision",
        "Vision-focused groups, especially relevant for diabetic retinopathy, retinal imaging, and AI-enabled screening.",
        "Ophthalmology, retina, vision sciences, eye institute, optometry",
    ),
    (
        "Complications / Cardiometabolic / Nephrology / Neurology",
        "Clinical specialties focused on major diabetes complications and downstream multimorbidity.",
        "Nephrology, cardiology, vascular medicine, neurology, renal medicine, cardiovascular medicine",
    ),
    (
        "Pediatrics / Maternal Health",
        "Groups focused on pediatric diabetes, transition care, pregnancy, and gestational diabetes.",
        "Pediatrics, children's hospital, obstetrics, gynecology, maternal-fetal medicine, gestational diabetes",
    ),
    (
        "General Clinical Medicine",
        "Broad hospital-based or clinical medicine groups contributing to diabetes care pathways, screening, and implementation.",
        "Internal medicine, family medicine, primary care, hospital medicine, clinical medicine, medical center",
    ),
    (
        "Public Health / Epidemiology",
        "Population-level, prevention, policy, and health systems groups examining AI use beyond single institutions or clinics.",
        "Public health, epidemiology, preventive medicine, population health, community health, global health",
    ),
    (
        "Nutrition",
        "Groups focused on diet, metabolism, lifestyle intervention, and clinical nutrition in diabetes care.",
        "Nutrition, dietetics, nutritional sciences, food science, clinical nutrition",
    ),
    (
        "Nursing / Diabetes Education",
        "Practice and education groups supporting chronic disease management, patient education, and care coordination.",
        "Nursing, diabetes educator, school of nursing, nurse practitioner",
    ),
    (
        "Behavioral / Psychological",
        "Mental health and behavior-change groups relevant to adherence, self-management, and patient-centered diabetes care.",
        "Psychology, psychiatry, behavioral medicine, mental health, health behavior",
    ),
    (
        "Exercise / Lifestyle",
        "Lifestyle medicine and physical activity groups studying intervention, prevention, and rehabilitation pathways.",
        "Kinesiology, exercise science, sports medicine, physical activity, lifestyle medicine, rehabilitation",
    ),
    (
        "Industry / Digital Health / Device",
        "Commercial, device, pharma, and digital-health organizations shaping translational and deployment-oriented research.",
        "Biotech, pharma, medical device, digital health, therapeutics, Abbott, Dexcom, Medtronic, Novo Nordisk",
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


def style_run(run, *, font: str = "Calibri", size: float = 11, bold: bool = False, color: str = "1f2937", italic: bool = False) -> None:
    run.font.name = font
    run._element.rPr.rFonts.set(qn("w:ascii"), font)
    run._element.rPr.rFonts.set(qn("w:hAnsi"), font)
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = RGBColor.from_string(color)


def add_paragraph(document: Document, text: str = "", *, style: str | None = None, align: WD_ALIGN_PARAGRAPH | None = None):
    para = document.add_paragraph(style=style)
    if align is not None:
        para.alignment = align
    if text:
        run = para.add_run(text)
        style_run(run)
    return para


def apply_base_styles(document: Document) -> None:
    section = document.sections[0]
    section.top_margin = Inches(0.8)
    section.bottom_margin = Inches(0.75)
    section.left_margin = Inches(0.9)
    section.right_margin = Inches(0.9)
    section.header_distance = Inches(0.35)
    section.footer_distance = Inches(0.35)

    styles = document.styles

    normal = styles["Normal"]
    normal.font.name = "Calibri"
    normal._element.rPr.rFonts.set(qn("w:ascii"), "Calibri")
    normal._element.rPr.rFonts.set(qn("w:hAnsi"), "Calibri")
    normal.font.size = Pt(11)
    normal.font.color.rgb = RGBColor.from_string("1f2937")
    normal.paragraph_format.space_after = Pt(7)
    normal.paragraph_format.line_spacing = 1.25

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
        pf = style.paragraph_format
        pf.space_before = Pt(12 if "Heading" in name else 0)
        pf.space_after = Pt(6)


def add_header_footer(document: Document) -> None:
    for section in document.sections:
        header = section.header
        p = header.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        run = p.add_run("AI in Diabetology Collaboration Brief")
        style_run(run, size=8.5, color="64748b")

        footer = section.footer
        fp = footer.paragraphs[0]
        fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        fr = fp.add_run("Proposed reproducible collaboration study | PubMed through December 31, 2025")
        style_run(fr, size=8.5, color="64748b")


def add_title_block(document: Document) -> None:
    p = document.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(3)
    r = p.add_run("COLLABORATOR CONCEPT BRIEF")
    style_run(r, size=10.5, bold=True, color="2563eb")

    p = document.add_paragraph(style="Title")
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(4)
    r = p.add_run(TITLE)
    style_run(r, size=24, bold=True, color="0f172a")

    p = document.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(14)
    r = p.add_run(SUBTITLE)
    style_run(r, size=12, color="475569", italic=True)

    meta = document.add_table(rows=1, cols=2)
    meta.alignment = WD_TABLE_ALIGNMENT.CENTER
    meta.autofit = False
    meta.columns[0].width = Inches(3.1)
    meta.columns[1].width = Inches(3.1)
    left, right = meta.rows[0].cells
    for cell in (left, right):
        set_cell_shading(cell, "EFF6FF")
        set_cell_margins(cell, top=110, bottom=110, start=120, end=120)
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
    left_p = left.paragraphs[0]
    left_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    left_p.add_run("Proposed study type\n")
    style_run(left_p.runs[0], size=9, bold=True, color="1e3a8a")
    left_run = left_p.add_run("Temporal institutional network analysis")
    style_run(left_run, size=10.5, color="0f172a")
    right_p = right.paragraphs[0]
    right_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    right_p.add_run("Primary data source\n")
    style_run(right_p.runs[0], size=9, bold=True, color="1e3a8a")
    right_run = right_p.add_run("PubMed-indexed AI and diabetes literature")
    style_run(right_run, size=10.5, color="0f172a")


def add_callout(document: Document, title: str, body: str, *, fill: str = "F8FAFC") -> None:
    table = document.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    table.columns[0].width = Inches(6.25)
    cell = table.rows[0].cells[0]
    set_cell_shading(cell, fill)
    set_cell_margins(cell, top=130, bottom=130, start=140, end=140)
    cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    run = p.add_run(f"{title}\n")
    style_run(run, size=10.5, bold=True, color="0f172a")
    run2 = p.add_run(body)
    style_run(run2, size=10.5, color="334155")


def add_framework_table(document: Document) -> None:
    document.add_paragraph("Study Architecture", style="Heading 1")
    table = document.add_table(rows=2, cols=4)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    widths = [Inches(1.56), Inches(1.56), Inches(1.56), Inches(1.56)]
    titles = ["1. Retrieval", "2. Network Building", "3. Domain Typing", "4. Structural Insight"]
    descriptions = [
        "PubMed search on AI and diabetes through 2025 with reproducible query blocks and screening rules.",
        "Period-specific institutional co-authorship networks using exact affiliation entities as nodes.",
        "Rule-based and LLM-assisted classification of institutional domains across the diabetology ecosystem.",
        "Longitudinal analysis of cohesion, interdisciplinarity, geography, central actors, and funding structure.",
    ]
    fills = ["DBEAFE", "E0E7FF", "F3E8FF", "DCFCE7"]
    for idx, width in enumerate(widths):
        table.columns[idx].width = width
        top = table.rows[0].cells[idx]
        bottom = table.rows[1].cells[idx]
        for cell, fill in ((top, fills[idx]), (bottom, "FFFFFF")):
            set_cell_margins(cell, top=100, bottom=100, start=110, end=110)
            set_cell_shading(cell, fill)
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        tp = top.paragraphs[0]
        tp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        tr = tp.add_run(titles[idx])
        style_run(tr, size=10, bold=True, color="0f172a")
        bp = bottom.paragraphs[0]
        bp.alignment = WD_ALIGN_PARAGRAPH.LEFT
        br = bp.add_run(descriptions[idx])
        style_run(br, size=9.5, color="334155")


def add_body_content(document: Document) -> None:
    document.add_paragraph("Project Overview", style="Heading 1")
    p = document.add_paragraph()
    p.add_run(
        "Artificial intelligence is rapidly expanding across diabetes research and care, with applications spanning "
        "risk prediction, glucose monitoring, diabetic retinopathy screening, clinical decision support, and digital health. "
        "Yet the growth of this literature does not necessarily mean that the field has matured into a cohesive, interdisciplinary, "
        "and globally integrated research ecosystem. This project proposes a reproducible temporal institutional network study of "
        "AI in diabetology using PubMed-indexed publications to examine how collaboration has evolved across institutions, countries, "
        "disciplines, and funding contexts over time."
    )

    add_callout(
        document,
        "Why this study matters",
        "The key question is not only how much AI-in-diabetes research exists, but whether the field is becoming structurally integrated, "
        "interdisciplinary, and globally connected enough to support scalable clinical translation.",
        fill="F8FAFC",
    )

    document.add_paragraph("Rationale and Collaborator Value", style="Heading 1")
    p = document.add_paragraph()
    p.add_run(
        "Our prior AI-in-dentistry work showed that temporal institutional networks can reveal how emerging clinical AI fields evolve "
        "from fragmented efforts toward more sustained cross-domain collaboration. AI in diabetes is an especially compelling next case: "
        "the disease burden is global, the technology stack is broad, and innovation spans prediction, imaging, devices, education, and care delivery. "
        "A collaboration-focused analysis can therefore illuminate not just productivity, but field maturity."
    )
    p = document.add_paragraph()
    p.add_run(
        "This framing creates a strong opportunity for multidisciplinary collaborators. Clinical investigators can help interpret whether the network core reflects "
        'true diabetology leadership or adjacent specialties; informatics and AI collaborators can strengthen the technical framing; population health and policy collaborators '
        "can help interpret geographic distribution and implementation relevance; and bibliometric or network-science collaborators can refine the structural analyses and manuscript positioning."
    )

    add_framework_table(document)

    document.add_paragraph("Methods in Brief", style="Heading 1")
    methods = [
        "PubMed retrieval: We will use a structured, reproducible PubMed search strategy combining AI-related and diabetes-related terms, capped at December 31, 2025.",
        "Unit of analysis: Institutions, derived from author affiliation strings, will serve as the primary unit rather than individual authors.",
        "Network construction: For each temporal period, nodes will represent unique institutional entities and edges will represent co-occurrence on the same publication.",
        "Temporal design: The corpus will be segmented into balanced or fixed six-period cohorts to enable stable comparison across the field's long-term growth curve.",
        "Network metrics: We will quantify growth, density, average degree, clustering, largest connected component share, and node centrality.",
        "Dynamic structure: We will examine returning versus newcomer institutions, role mobility, interdisciplinarity, geography, and funding-stratified structures.",
        "Reproducibility layer: In addition to rule-based domain typing, we are building an LLM-assisted affiliation-classification sidecar to improve domain labeling while keeping the workflow auditable.",
    ]
    for item in methods:
        p = document.add_paragraph(style="Normal")
        p.paragraph_format.left_indent = Inches(0.18)
        p.paragraph_format.first_line_indent = Inches(-0.18)
        p.paragraph_format.space_after = Pt(5)
        r1 = p.add_run("• ")
        style_run(r1, size=11, bold=True, color="2563eb")
        r2 = p.add_run(item)
        style_run(r2, size=10.8, color="1f2937")


def add_categories_section(document: Document) -> None:
    document.add_page_break()
    document.add_paragraph("Institutional Domain Categories", style="Heading 1")
    p = document.add_paragraph()
    p.add_run(
        "To interpret interdisciplinarity in a clinically meaningful way, we will classify institutions into a diabetology-specific domain framework. "
        "This extends the broader dental project taxonomy and gives us a structured way to examine where collaborations are concentrated, where bridges emerge, "
        "and which domains are underrepresented in the evolving AI-in-diabetes ecosystem."
    )

    table = document.add_table(rows=1, cols=3)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    table.columns[0].width = Inches(1.55)
    table.columns[1].width = Inches(2.15)
    table.columns[2].width = Inches(2.55)
    header_cells = table.rows[0].cells
    headers = ["Category", "Primary role in the study", "Illustrative keywords / institutional signals"]
    for idx, cell in enumerate(header_cells):
        set_cell_shading(cell, "DBEAFE")
        set_cell_margins(cell, top=90, bottom=90, start=100, end=100)
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(headers[idx])
        style_run(run, size=9.5, bold=True, color="0f172a")

    for name, role, examples in CATEGORIES:
        row = table.add_row().cells
        values = [name, role, examples]
        for idx, cell in enumerate(row):
            set_cell_margins(cell, top=80, bottom=80, start=100, end=100)
            set_cell_shading(cell, "FFFFFF" if len(table.rows) % 2 == 0 else "F8FAFC")
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            run = p.add_run(values[idx])
            style_run(run, size=9.2 if idx else 9.5, bold=(idx == 0), color="1f2937")

    add_callout(
        document,
        "Classification strategy",
        "The primary paper will use single-label institutional assignment for clarity and comparability, while an optional LLM-assisted classification workflow can be used as a sensitivity analysis or methodological extension.",
        fill="EFF6FF",
    )


def add_expected_insights(document: Document) -> None:
    document.add_paragraph("Expected Insights", style="Heading 1")
    insights = [
        "Which institutions and regions form the collaboration core of AI in diabetes research.",
        "Whether recent growth reflects durable network cohesion or continued fragmentation driven by transient entrants.",
        "How strongly clinical, technical, public health, industry, and complication-focused communities are converging.",
        "Whether funded studies are structurally more cohesive or more internationally distributed than unfunded studies.",
        "How this field compares conceptually with other AI-enabled biomedical domains in terms of collaboration maturity.",
    ]
    for item in insights:
        p = document.add_paragraph()
        p.paragraph_format.left_indent = Inches(0.2)
        p.paragraph_format.first_line_indent = Inches(-0.2)
        p.paragraph_format.space_after = Pt(4)
        p.add_run("• ")
        style_run(p.runs[0], size=11, bold=True, color="16a34a")
        r = p.add_run(item)
        style_run(r, size=10.8, color="1f2937")

    document.add_paragraph("Potential Collaborator Contributions", style="Heading 1")
    p = document.add_paragraph()
    p.add_run(
        "We see room for collaborators in clinical interpretation, query refinement, network and bibliometric analysis, visualization, manuscript writing, "
        "and diabetes-specific framing. The project is designed as a reproducible methods paper as much as a field-mapping study, so collaborators can contribute "
        "both domain expertise and methodological depth."
    )

    add_callout(
        document,
        "Planned deliverables",
        "A cleaned PubMed-derived publication dataset, period-specific collaboration networks, descriptive and structural tables, geographic and funding-stratified summaries, "
        "interactive network outputs, and a manuscript positioned around the maturation of AI-enabled diabetology as an interdisciplinary research ecosystem.",
        fill="F0FDF4",
    )


def build_document(output_path: Path) -> None:
    document = Document()
    apply_base_styles(document)
    add_header_footer(document)
    add_title_block(document)
    add_body_content(document)
    add_categories_section(document)
    add_expected_insights(document)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    document.save(output_path)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    output_path = root / "docs" / "AI_Diabetology_Collaborator_Brief.docx"
    build_document(output_path)
    print(output_path)


if __name__ == "__main__":
    main()
