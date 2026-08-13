#!/usr/bin/env python3
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Iterable

import pandas as pd
from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = PROJECT_ROOT / "docs"
OUTPUTS_DIR = PROJECT_ROOT / "outputs" / "tables"
CENTRALITY_DIR = OUTPUTS_DIR / "centrality"
LLM_PARQUET = PROJECT_ROOT / "data" / "llm" / "results" / "affiliation_classifications.parquet"
TEMPLATE_PATH = DOCS_DIR / "AI_Diabetology_Collaborator_Brief_v2.docx"
OUT_PATH = DOCS_DIR / "AI_Diabetology_Results_Interpretation_Report.docx"

HEADER_FILL = "DCE6F1"
BAND_FILL = "EEF3F8"
TEXT_DARK = RGBColor(31, 45, 61)
MUTED = RGBColor(96, 108, 120)


def clear_body(doc: Document) -> None:
    body = doc._element.body
    for child in list(body):
        if child.tag.endswith("sectPr"):
            continue
        body.remove(child)


def set_cell_shading(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_cell_margins(cell, top=80, start=120, bottom=80, end=120) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_mar = tc_pr.find(qn("w:tcMar"))
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for key, value in {"top": top, "start": start, "bottom": bottom, "end": end}.items():
        element = tc_mar.find(qn(f"w:{key}"))
        if element is None:
            element = OxmlElement(f"w:{key}")
            tc_mar.append(element)
        element.set(qn("w:w"), str(value))
        element.set(qn("w:type"), "dxa")


def set_run_font(run, *, size: float | None = None, bold: bool | None = None, italic: bool | None = None,
                 color: RGBColor | None = None, name: str | None = None) -> None:
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold
    if italic is not None:
        run.italic = italic
    if color is not None:
        run.font.color.rgb = color
    if name is not None:
        run.font.name = name
        run._element.rPr.rFonts.set(qn("w:ascii"), name)
        run._element.rPr.rFonts.set(qn("w:hAnsi"), name)


def add_kicker(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(2)
    run = p.add_run(text.upper())
    set_run_font(run, size=10.5, bold=True, color=MUTED)


def add_title_block(doc: Document) -> None:
    title = doc.add_paragraph(style="Title")
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.add_run("Mapping Collaboration in AI and Diabetes Research: ")
    title.add_run("Results Interpretation Report")

    subtitle = doc.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subtitle.paragraph_format.space_after = Pt(10)
    run = subtitle.add_run("Detailed collaborator memo based on currently available LLM-informed outputs")
    set_run_font(run, size=12, italic=True, color=TEXT_DARK)

    meta = doc.add_paragraph()
    meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    meta.paragraph_format.space_after = Pt(14)
    run = meta.add_run(f"Prepared {date(2026, 5, 22).strftime('%B %d, %Y')}")
    set_run_font(run, size=10.5, color=MUTED)


def add_note_box(doc: Document, title: str, paragraphs: Iterable[str]) -> None:
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    cell = table.rows[0].cells[0]
    cell.width = Inches(6.5)
    set_cell_shading(cell, BAND_FILL)
    set_cell_margins(cell, top=120, start=160, bottom=120, end=160)
    cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER

    p0 = cell.paragraphs[0]
    p0.paragraph_format.space_after = Pt(4)
    r0 = p0.add_run(title)
    set_run_font(r0, size=11.5, bold=True, color=TEXT_DARK)

    for idx, text in enumerate(paragraphs):
        p = cell.add_paragraph()
        p.paragraph_format.space_after = Pt(4 if idx < len(list(paragraphs)) - 1 else 0)
        r = p.add_run(text)
        set_run_font(r, size=10.25, color=TEXT_DARK)

    doc.add_paragraph()


def add_heading(doc: Document, text: str) -> None:
    doc.add_paragraph(text, style="Heading1")


def add_body_paragraph(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.space_after = Pt(8)
    run = p.add_run(text)
    set_run_font(run, size=11, color=TEXT_DARK)


def add_caption(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(4)
    run = p.add_run(text)
    set_run_font(run, size=10, bold=True, color=TEXT_DARK)


def add_styled_table(
    doc: Document,
    title: str,
    columns: list[str],
    rows: list[list[str]],
    widths: list[float],
    alignments: list[int],
) -> None:
    add_caption(doc, title)
    table = doc.add_table(rows=1, cols=len(columns))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False

    header = table.rows[0].cells
    for i, col in enumerate(columns):
        cell = header[i]
        cell.width = Inches(widths[i])
        set_cell_shading(cell, HEADER_FILL)
        set_cell_margins(cell)
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(col)
        set_run_font(r, size=9.5, bold=True, color=TEXT_DARK)

    for row in rows:
        cells = table.add_row().cells
        for i, value in enumerate(row):
            cell = cells[i]
            cell.width = Inches(widths[i])
            set_cell_margins(cell)
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            p = cell.paragraphs[0]
            p.alignment = alignments[i]
            r = p.add_run(str(value))
            set_run_font(r, size=9.25, color=TEXT_DARK)

    doc.add_paragraph()


def compact_institution_label(text: str, max_len: int = 74) -> str:
    first = str(text).split(";")[0].strip()
    parts = [part.strip() for part in first.split(",") if part.strip()]
    if len(parts) >= 3:
        label = ", ".join(parts[:3])
    elif len(parts) >= 2:
        label = ", ".join(parts[:2])
    else:
        label = first
    if len(label) <= max_len:
        return label
    return label[: max_len - 1].rstrip() + "…"


def load_tables() -> dict[str, pd.DataFrame]:
    publication = pd.read_csv(OUTPUTS_DIR / "publication_counts_by_period.csv")
    global_metrics = pd.read_csv(OUTPUTS_DIR / "global_network_metrics.csv")
    cluster = pd.read_csv(OUTPUTS_DIR / "cluster_interdisciplinarity_metrics.csv")
    core = pd.read_csv(OUTPUTS_DIR / "core_newcomer_metrics.csv")
    region = pd.read_csv(OUTPUTS_DIR / "who_region_summary.csv")
    llm = pd.read_parquet(LLM_PARQUET)
    return {
        "publication": publication,
        "global": global_metrics,
        "cluster": cluster,
        "core": core,
        "region": region,
        "llm": llm,
    }


def build_report() -> Path:
    tables = load_tables()
    publication = tables["publication"].copy()
    global_metrics = tables["global"].copy()
    cluster = tables["cluster"].copy()
    core = tables["core"].copy()
    region = tables["region"].copy()
    llm = tables["llm"].copy()

    merged = publication.merge(global_metrics, on="period").merge(cluster, on="period")
    merged["mentions_per_paper"] = merged["institution_mentions"] / merged["publication_count"]
    merged["lcc_share_pct"] = 100 * merged["largest_connected_component_size"] / merged["nodes"]

    top_regions = (
        region.sort_values(["period", "publication_count", "institution_count"], ascending=[True, False, False])
        .groupby("period", as_index=False)
        .first()[["period", "who_region", "publication_count", "country_count", "institution_count"]]
    )

    centrality_rows: list[list[str]] = []
    for path in sorted(CENTRALITY_DIR.glob("centrality_top10_*.csv")):
        df = pd.read_csv(path)
        period = path.stem.removeprefix("centrality_top10_").replace("_", "-")
        first = df.iloc[0]
        centrality_rows.append(
            [
                period,
                compact_institution_label(first["degree_node"]),
                f"{float(first['degree_score']):.3f}",
                compact_institution_label(first["betweenness_node"]),
                f"{float(first['betweenness_score']):.3f}",
            ]
        )

    doc = Document(str(TEMPLATE_PATH))
    clear_body(doc)
    doc.core_properties.title = "AI Diabetology Results Interpretation Report"
    doc.core_properties.subject = "LLM-based diabetology collaboration analysis"
    doc.core_properties.author = "OpenAI Codex"

    add_kicker(doc, "Results Interpretation Report")
    add_title_block(doc)

    add_note_box(
        doc,
        "Interpretive Status Note",
        [
            "This report is based on the currently available diabetology outputs and is designed as a polished collaborator-facing analytical draft rather than final manuscript text.",
            f"The current LLM classification set includes {int((llm['status'] == 'ok').sum()):,} rows with status=ok and {int((llm['status'] == 'failed').sum()):,} retained failed rows; {int((llm['label'].astype(str) == 'Other').sum()):,} rows are currently labeled Other.",
            "Funding-stratified summary tables are not yet complete in the current output set, so funding interpretation is intentionally limited to a short status note rather than full narrative analysis.",
        ],
    )

    add_heading(doc, "Report Purpose")
    add_body_paragraph(
        doc,
        "This report interprets the currently completed institutional collaboration outputs for AI-and-diabetes research using the same manuscript-oriented voice that guided the earlier dentistry project, while remaining strictly results-focused. The presently available analysis spans 16,953 publications, 73,779 institution mentions, and six manuscript periods ranging from 1988–2015 through 2025. Overall, the outputs suggest a field that has expanded rapidly in scale, broadened geographically, and become more interdisciplinary over time, while still retaining substantial structural fragmentation."
    )

    add_heading(doc, "1. Publication Growth and Field Expansion")
    add_styled_table(
        doc,
        "Table 1. Publication volume and institutional participation by period",
        ["Period", "Publications", "Institution mentions", "Mentions per paper"],
        [
            [
                row.period,
                f"{int(row.publication_count):,}",
                f"{int(row.institution_mentions):,}",
                f"{float(row.mentions_per_paper):.2f}",
            ]
            for row in merged.itertuples()
        ],
        [1.2, 1.15, 1.55, 1.25],
        [WD_ALIGN_PARAGRAPH.CENTER, WD_ALIGN_PARAGRAPH.CENTER, WD_ALIGN_PARAGRAPH.CENTER, WD_ALIGN_PARAGRAPH.CENTER],
    )
    add_body_paragraph(
        doc,
        "The publication trajectory shows clear temporal growth. Period-level publication counts rose from 2,393 in 1988–2015 to 2,696 in 2020–2021, peaked at 3,674 in 2022–2023, and remained high at 3,544 in 2025–2025. Institutional participation expanded even faster than publication volume. Institution mentions increased from 3,681 in the earliest period to 17,929 in 2022–2023, which indicates that later AI-and-diabetes publications were not merely more numerous, but also substantially more multi-institutional."
    )
    add_body_paragraph(
        doc,
        "The increase in mentions per paper reinforces that interpretation. The average rose from 1.54 institution mentions per publication in 1988–2015 to a relatively stable later-period range of approximately 4.70 to 4.92. That shift suggests a field that has moved away from largely local or single-site work toward a collaboration model that routinely requires broader institutional participation."
    )

    add_heading(doc, "2. Network Growth Versus Cohesion")
    add_styled_table(
        doc,
        "Table 2. Network scale, cohesion, and fragmentation indicators by period",
        ["Period", "Nodes", "Edges", "Density", "Avg degree", "Clustering", "LCC share %"],
        [
            [
                row.period,
                f"{int(row.nodes):,}",
                f"{int(row.edges):,}",
                f"{float(row.density):.5f}",
                f"{float(row.avg_degree):.2f}",
                f"{float(row.avg_clustering_weighted):.3f}",
                f"{float(row.lcc_share_pct):.2f}",
            ]
            for row in merged.itertuples()
        ],
        [1.0, 0.85, 1.1, 0.9, 0.9, 0.9, 0.85],
        [WD_ALIGN_PARAGRAPH.CENTER] * 7,
    )
    add_body_paragraph(
        doc,
        "The collaboration networks became dramatically larger over time, with node counts increasing from 3,610 in 1988–2015 to 17,051 in 2022–2023 and 16,256 in 2025–2025. Edge counts also increased sharply, but the pattern was not smooth. The 2016–2019 period was structurally anomalous, with 439,972 edges, density of 0.00707, and average degree of 78.86. These values are far above the surrounding periods and strongly suggest the presence of one or more extremely large multi-institution collaboration events rather than a uniform increase in everyday network cohesion."
    )
    add_body_paragraph(
        doc,
        "Outside that anomalous period, the field still exhibits strong growth but more modest structural cohesion. Density remains low in every period, and the largest connected component accounts for only 0.55% to 5.70% of all nodes. The largest connected component grew in absolute terms from 20 nodes in the earliest period to 835 nodes in 2025–2025, yet the low LCC share indicates that the institutional landscape remains highly fragmented even as it expands."
    )
    add_body_paragraph(
        doc,
        "The clustering coefficient points to a more nuanced story. Weighted clustering rose from 0.135 in 1988–2015 to 0.300 in 2016–2019, then fluctuated across later periods between 0.153 and 0.305. This suggests that local triadic collaboration intensified in later eras, but not in a strictly linear way. The field seems to alternate between broad institutional expansion and pockets of denser local consolidation."
    )

    add_heading(doc, "3. Central Institutions and the Collaboration Core")
    add_styled_table(
        doc,
        "Table 3. Representative leading institutions by degree and betweenness centrality",
        ["Period", "Degree-central institution", "Degree", "Broker institution", "Betweenness"],
        centrality_rows,
        [0.95, 2.1, 0.7, 2.1, 0.7],
        [WD_ALIGN_PARAGRAPH.CENTER, WD_ALIGN_PARAGRAPH.LEFT, WD_ALIGN_PARAGRAPH.CENTER, WD_ALIGN_PARAGRAPH.LEFT, WD_ALIGN_PARAGRAPH.CENTER],
    )
    add_body_paragraph(
        doc,
        "The centrality results suggest a meaningful shift in the institutional center of gravity over time. In 1988–2015, the collaboration core was dominated by European clinical diabetology and endocrinology centers, especially French hospital-based networks. This early pattern is consistent with a field that was still clinically concentrated and relatively regionally bounded."
    )
    add_body_paragraph(
        doc,
        "By 2016–2019, the degree-central list became much more internationally dispersed, spanning Canada, Spain, Turkey, Italy, Portugal, India, Japan, and Brazil. In that period, however, the top betweenness scores were effectively zero, implying that the network was not yet organized around stable brokers connecting a cohesive global core. Instead, it appears to have consisted of multiple internally dense but weakly bridged collaboration islands."
    )
    add_body_paragraph(
        doc,
        "The later periods display a more recognizable mixed clinical-technical brokerage pattern. In 2020–2021, the Singapore Eye Research Institute and the National University of Singapore ecosystem emerged as major brokers, alongside Duke-NUS. In 2022–2023 and 2024–2024, public health, eye research, metabolic research, and large academic biomedical ecosystems in Singapore, Cambridge, Harvard-affiliated settings, and continental Europe became increasingly central. By 2025–2025, the central set included Stanford, Singapore, Tsinghua Medicine, and the Diabetes Technology Society, suggesting a collaboration core that is no longer purely anchored in narrow diabetology, but increasingly spans genomics, computational medicine, ophthalmology, digital health, and pediatric diabetes."
    )

    add_heading(doc, "4. Core–Newcomer Dynamics")
    add_styled_table(
        doc,
        "Table 4. Core–newcomer transition metrics",
        ["Transition", "New nodes", "Returning nodes", "Density existing", "Density new", "Edges per new node"],
        [
            [
                f"{row['from']} → {row['to']}",
                f"{int(row['new_nodes']):,}",
                f"{int(row['returning_nodes']):,}",
                f"{float(row['density_existing']):.4f}",
                f"{float(row['density_new']):.4f}",
                f"{float(row['edge_growth_per_new']):.2f}",
            ]
            for _, row in core.iterrows()
        ],
        [1.5, 1.0, 1.0, 0.95, 0.9, 1.15],
        [WD_ALIGN_PARAGRAPH.LEFT, WD_ALIGN_PARAGRAPH.CENTER, WD_ALIGN_PARAGRAPH.CENTER, WD_ALIGN_PARAGRAPH.CENTER, WD_ALIGN_PARAGRAPH.CENTER, WD_ALIGN_PARAGRAPH.CENTER],
    )
    add_body_paragraph(
        doc,
        "The transition metrics show that field expansion has been driven much more by continual institutional entry than by simple densification within a stable returning core. The shift from 1988–2015 to 2016–2019 brought only 66 returning institutions but 11,092 new ones. This asymmetry persisted in every later transition: newcomer counts remained above 10,000 in every step, reaching 16,426 in the transition from 2020–2021 to 2022–2023."
    )
    add_body_paragraph(
        doc,
        "Returning institutions are consistently more densely connected than newcomers. Density among returning institutions ranged from 0.00269 to 0.02378 across transitions, while density among new institutions remained lower, ranging from 0.00040 to 0.00715. This pattern indicates that the established core remains structurally tighter than the incoming periphery, even as the field broadens rapidly."
    )
    add_body_paragraph(
        doc,
        "The edges-per-new-node metric again singles out 2016–2019 as structurally exceptional. That transition generated 39.66 edges per new node, whereas the later transitions fell into a much narrower range of roughly 3.42 to 3.94. This supports the interpretation that the 2016–2019 network expansion was disproportionately influenced by large collaboration events rather than by a simple and enduring increase in routine newcomer integration."
    )

    add_heading(doc, "5. Interdisciplinarity and Component Structure")
    add_styled_table(
        doc,
        "Table 5. Interdisciplinarity indicators across connected components",
        ["Period", "Single-field %", "Two-field %", "Three+ field %", "Mean fields/component", "Max fields"],
        [
            [
                row.period,
                f"{100*float(row.single_field_ratio):.1f}",
                f"{100*float(row.two_field_ratio):.1f}",
                f"{100*float(row.three_or_more_field_ratio):.1f}",
                f"{float(row.mean_distinct_key_fields_per_component):.2f}",
                f"{int(row.max_distinct_key_fields_in_component)}",
            ]
            for row in merged.itertuples()
        ],
        [1.1, 1.0, 1.0, 1.1, 1.3, 1.0],
        [WD_ALIGN_PARAGRAPH.CENTER] * 6,
    )
    add_body_paragraph(
        doc,
        "The interdisciplinarity metrics suggest a substantial shift away from single-domain silos. In 1988–2015, 65.6% of connected components were single-field components, while only 5.6% were two-field and 2.5% were three-or-more-field components. The mean number of distinct key fields per component was only 0.85, which is characteristic of a field whose local collaboration units remain relatively narrow in their disciplinary composition."
    )
    add_body_paragraph(
        doc,
        "From 2016–2019 onward, the structure became much more mixed. The single-field share dropped to roughly 38.4–42.5% across later periods, while the two-field share settled around 28.1–30.9% and the three-or-more-field share around 19.5–22.4%. The mean number of distinct key fields per component climbed to between 1.67 and 1.82. The maximum number of key fields observed within a single component also rose from 5 in the earliest period to as high as 12 in the later periods."
    )
    add_body_paragraph(
        doc,
        "These findings strongly suggest that AI-and-diabetes collaboration became substantially more interdisciplinary once the field entered its expansion phase. Even though the overall network remains fragmented, the components that do form are increasingly likely to bridge clinical medicine, public health, technical/AI groups, and complication-focused specialties such as ophthalmology and cardiometabolic medicine."
    )

    add_heading(doc, "6. Geographic Diffusion")
    add_styled_table(
        doc,
        "Table 6. Leading WHO region by period",
        ["Period", "Leading region", "Publications", "Countries", "Institutions"],
        [
            [
                row.period,
                row.who_region,
                f"{int(row.publication_count):,}",
                f"{int(row.country_count):,}",
                f"{int(row.institution_count):,}",
            ]
            for row in top_regions.itertuples()
        ],
        [1.15, 1.05, 1.0, 1.0, 1.1],
        [WD_ALIGN_PARAGRAPH.CENTER] * 5,
    )
    add_body_paragraph(
        doc,
        "The WHO-region summaries show both geographic broadening and a notable shift in regional leadership. In the first three periods, PAHO led the field, with 422 publications in 1988–2015, 713 in 2016–2019, and 888 in 2020–2021. EURO remained the second major pole in these same periods, while WPRO grew steadily but had not yet become the dominant region."
    )
    add_body_paragraph(
        doc,
        "That pattern changes in the later periods. WPRO became the leading region in 2022–2023 with 1,163 publications and 3,743 institutions, retained the lead in 2024–2024, and extended it in 2025–2025 with 1,425 publications and 4,382 institutions. This suggests that the recent expansion of AI-and-diabetes collaboration has increasingly been driven by Western Pacific institutional ecosystems rather than remaining centered primarily in North America and Europe."
    )
    add_body_paragraph(
        doc,
        "At the same time, the field remains geographically broadening rather than merely shifting from one dominant region to another. EURO reached 47 countries in 2025–2025, and smaller regions such as AFRO and EMRO also expanded over time. AFRO rose from 8 publications in the earliest period to 63 in 2025–2025, while EMRO increased from 32 to 274. These totals remain much smaller than those of PAHO, EURO, and WPRO, but they indicate widening international participation rather than complete concentration in only a few regions."
    )

    add_heading(doc, "7. Funding Note")
    add_body_paragraph(
        doc,
        "The current output tree does not yet contain a completed set of funding-stratified summary tables sufficient for manuscript-style interpretation. Although some funding-specific network artifacts are present, the absence of a complete funding summary table family means that a rigorous funding narrative would be premature. Accordingly, funding-stratified interpretation is intentionally deferred here."
    )

    add_heading(doc, "Results Synthesis")
    add_body_paragraph(
        doc,
        "Taken together, the currently available outputs portray AI-and-diabetes research as a field that has clearly advanced beyond its earliest sparse and relatively siloed institutional configuration. Publication volume, institutional participation, and multi-institutional authorship all increased sharply. The connected components that do form are far more interdisciplinary than in the earliest period, and the geographic center of gravity appears to be shifting toward the Western Pacific region in the most recent years."
    )
    add_body_paragraph(
        doc,
        "At the same time, the collaboration system should not yet be characterized as fully integrated. The largest connected component remains small relative to total network size in every period, newcomer entry vastly outpaces the size of the returning institutional core, and the dramatic structural jump in 2016–2019 appears to have been shaped in part by episodic mega-collaboration effects rather than by stable field-wide densification. The most defensible synthesis at this stage is therefore that AI-and-diabetes research is undergoing strong institutional expansion and meaningful interdisciplinary broadening, but that this expansion still coexists with substantial fragmentation."
    )

    doc.save(str(OUT_PATH))
    return OUT_PATH


if __name__ == "__main__":
    out = build_report()
    print(out)
