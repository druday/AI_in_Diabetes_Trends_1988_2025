#!/usr/bin/env python3
"""Build a manuscript-ready detailed diabetology methods and results report in DOCX format."""

from __future__ import annotations

import ast
from pathlib import Path

import pandas as pd
import yaml
from docx import Document
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt

from build_results_report_assets import (
    FIELD_SHORT_LABELS,
    FOCAL_DOMAINS,
    FUNDING_LABELS,
    FUNDING_ORDER,
    ensure_report_assets,
)


ROOT = Path("/Users/uday/AI in Diabetology")
TEMPLATE = ROOT / "docs" / "AI_Diabetology_Collaborator_Brief_v2.docx"
OUTPUT = ROOT / "docs" / "AI_Diabetology_Detailed_Results_Report_V1.docx"

PERIODS = ["1988-2015", "2016-2019", "2020-2021", "2022-2023", "2024-2024", "2025-2025"]
GLOSSARY_ROWS = [
    (
        "Node",
        "A node is one institution or affiliation in the network, such as a university department, hospital, or research center.",
    ),
    (
        "Edge",
        "An edge is a collaboration link showing that two institutions appeared together on at least one paper in that period.",
    ),
    (
        "Density",
        "Density describes how full the collaboration network is, with higher values meaning a larger share of all possible institution-to-institution ties are present.",
    ),
    (
        "Degree",
        "Degree is the number of other institutions connected to a given institution within the period-specific collaboration network.",
    ),
    (
        "Median degree",
        "Median degree shows the connectivity of the typical institution and is less distorted by unusually large consortium-style collaborations than the average degree.",
    ),
    (
        "Clustering coefficient",
        "The clustering coefficient indicates how often an institution's collaborators also collaborate with one another, which helps show whether ties form tight local groups.",
    ),
    (
        "Connected component",
        "A connected component is a cluster of institutions that can all be reached through chains of collaboration links, even if they are not directly linked to every other member.",
    ),
    (
        "Largest connected component",
        "The largest connected component is the single biggest collaboration cluster in a period and reflects how much of the field is tied into one main network.",
    ),
    (
        "Centrality",
        "Centrality measures how prominent or strategically important an institution is in the network, such as being widely connected or acting as a bridge between groups.",
    ),
    (
        "Interdisciplinarity",
        "Interdisciplinarity here means that connected collaboration clusters contain institutions from multiple field categories rather than staying within one specialty alone.",
    ),
]


def clear_document_body(doc: Document) -> None:
    body = doc._element.body
    sect_pr = body.sectPr
    for child in list(body):
        if child is not sect_pr:
            body.remove(child)


def set_cell_shading(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_cell_margins(cell, top=85, start=115, bottom=85, end=115) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_mar = tc_pr.find(qn("w:tcMar"))
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for tag, value in [("top", top), ("start", start), ("bottom", bottom), ("end", end)]:
        node = tc_mar.find(qn(f"w:{tag}"))
        if node is None:
            node = OxmlElement(f"w:{tag}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def format_table(table, widths=None, font_size=8.8) -> None:
    table.style = "Table Grid"
    table.autofit = False
    for row_idx, row in enumerate(table.rows):
        for col_idx, cell in enumerate(row.cells):
            set_cell_margins(cell)
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            for paragraph in cell.paragraphs:
                for run in paragraph.runs:
                    run.font.size = Pt(font_size)
                    if row_idx == 0:
                        run.bold = True
                if row_idx == 0:
                    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
                elif col_idx == 0:
                    paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
                else:
                    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            if row_idx == 0:
                set_cell_shading(cell, "D9E6F2")
            elif row_idx % 2 == 1:
                set_cell_shading(cell, "F8FBFD")
    if widths:
        for row in table.rows:
            for idx, width in enumerate(widths):
                row.cells[idx].width = width


def add_spacer(doc: Document, size: int = 4) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(size)


def short_label(text: str, limit: int = 72) -> str:
    text = " ".join(str(text).split()).split(";")[0].strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def short_field_name(text: str) -> str:
    return FIELD_SHORT_LABELS.get(str(text), str(text).replace("_", " "))


def short_combination_label(text: str) -> str:
    parts = [short_field_name(part.strip()) for part in str(text).split(" + ")]
    return " + ".join(parts)


def pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def update_template_running_text(doc: Document) -> None:
    for section in doc.sections:
        if section.header.paragraphs:
            section.header.paragraphs[0].text = "AI in Diabetology Detailed Results Report"
        if section.footer.paragraphs:
            section.footer.paragraphs[0].text = (
                "Canonical LLM-based temporal institutional network analysis | Completed manuscript-ready results report"
            )


def add_table_caption(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    run = p.add_run(text)
    run.bold = True
    run.italic = True
    run.font.size = Pt(9.5)
    p.paragraph_format.space_after = Pt(4)


def add_figure(doc: Document, image_path: Path, caption: str, width: Inches = Inches(6.15)) -> None:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run()
    run.add_picture(str(image_path), width=width)
    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap_run = cap.add_run(caption)
    cap_run.italic = True
    cap_run.font.size = Pt(9)
    cap.paragraph_format.space_after = Pt(8)


def note_box(doc: Document, text: str) -> None:
    table = doc.add_table(rows=1, cols=1)
    table.style = "Table Grid"
    cell = table.cell(0, 0)
    set_cell_shading(cell, "EEF4F8")
    set_cell_margins(cell, top=140, start=140, bottom=140, end=140)
    p = cell.paragraphs[0]
    p.paragraph_format.space_after = Pt(0)
    p.add_run("Interpretive status note. ").bold = True
    p.add_run(text)


def methods_box(doc: Document, title: str, bullets: list[str]) -> None:
    table = doc.add_table(rows=1, cols=1)
    table.style = "Table Grid"
    cell = table.cell(0, 0)
    set_cell_shading(cell, "EEF4F8")
    set_cell_margins(cell, top=140, start=140, bottom=140, end=140)
    first = cell.paragraphs[0]
    first.paragraph_format.space_after = Pt(3)
    run = first.add_run(f"{title}. ")
    run.bold = True
    first.add_run("Plain-language summary of the institutional grouping instructions used in the canonical classification workflow.")
    for bullet in bullets:
        p = cell.add_paragraph(style=None)
        p.paragraph_format.left_indent = Inches(0.2)
        p.paragraph_format.space_after = Pt(0)
        p.add_run("• ").bold = True
        p.add_run(bullet)


def methods_text_box(doc: Document, title: str, paragraphs: list[str], font_size: float = 7.6) -> None:
    table = doc.add_table(rows=1, cols=1)
    table.style = "Table Grid"
    cell = table.cell(0, 0)
    set_cell_shading(cell, "F6FAFD")
    set_cell_margins(cell, top=125, start=135, bottom=125, end=135)
    first = cell.paragraphs[0]
    first.paragraph_format.space_after = Pt(4)
    run = first.add_run(title)
    run.bold = True
    run.font.size = Pt(8.8)
    for idx, paragraph_text in enumerate(paragraphs):
        p = cell.add_paragraph() if idx > 0 else cell.add_paragraph()
        p.paragraph_format.space_after = Pt(2)
        r = p.add_run(paragraph_text)
        r.font.size = Pt(font_size)


def _extract_query_window(query_text: str) -> str:
    import re

    matches = re.findall(r'"(\d{4}/\d{2}/\d{2})"\[Date - Publication\]', str(query_text))
    if len(matches) >= 2:
        return f"{matches[0]} to {matches[1]}"
    return "Configured in protocol"


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _count_jsonl_rows(path: Path) -> int:
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())


def _methods_prompt_bullets() -> list[str]:
    return [
        "Classify the organization or department named in each raw affiliation string, rather than classifying the paper topic itself.",
        "Choose exactly one institutional-domain label from the allowed list for every affiliation.",
        "Use Other only when no domain is a good fit for the named institution.",
        "Return a confidence score for every decision and add a short uncertainty note only when the classification is not straightforward.",
    ]


def load_data() -> dict[str, object]:
    tables = ROOT / "outputs" / "tables"
    protocol = _load_yaml(ROOT / "config" / "protocol.yaml")
    sidecar = _load_yaml(ROOT / "sidecars" / "llm_affiliation_classification" / "config" / "sidecar.yaml")

    pub = pd.read_csv(tables / "publication_counts_by_period.csv")
    glob = pd.read_csv(tables / "global_network_metrics.csv")
    inter = pd.read_csv(tables / "cluster_interdisciplinarity_metrics.csv")
    core = pd.read_csv(tables / "core_newcomer_metrics.csv")
    who = pd.read_csv(tables / "who_region_summary.csv")
    descriptive = pd.read_csv(tables / "table_descriptive_by_period.csv")
    pairwise = pd.read_csv(tables / "component_field_pairwise_collaboration_by_period.csv")
    combinations = pd.read_csv(tables / "component_field_combination_summary_by_period.csv")
    focal_profiles = pd.read_csv(tables / "focal_domain_exact_two_field_profiles_by_period.csv")
    three_field_timelapse = pd.read_csv(tables / "exact_three_field_timelapse_profiles.csv")
    prominent_transitions = pd.read_csv(tables / "prominent_institution_role_transition_counts.csv")
    who_pairwise = pd.read_csv(tables / "who_region_pairwise_collaboration_by_period.csv")
    country_pairwise = pd.read_csv(tables / "country_pairwise_collaboration_by_period.csv")
    country_display = pd.read_csv(tables / "country_pairwise_collaboration_display_by_period.csv")
    funding_domain_profiles = pd.read_csv(tables / "funding_domain_exact_two_field_profiles_by_period.csv")
    llm = pd.read_parquet(ROOT / "data" / "llm" / "results" / "affiliation_classifications.parquet")
    review_queue = pd.read_csv(ROOT / "data" / "llm" / "review" / "low_confidence_review_queue.csv")
    processed = pd.read_parquet(
        ROOT / "data" / "processed" / "publications.parquet",
        columns=[
            "pmid",
            "title",
            "publication_year",
            "period",
            "institutions",
            "funding_category",
            "has_grant_support",
        ],
    )

    funding_pub = pd.read_csv(tables / "funding_publication_counts_by_period.csv")
    funding_glob = pd.read_csv(tables / "funding_global_network_metrics.csv")
    funding_inter = pd.read_csv(tables / "funding_cluster_interdisciplinarity_metrics.csv")
    funding_core = pd.read_csv(tables / "funding_core_newcomer_metrics.csv")
    funding_who = pd.read_csv(tables / "funding_who_region_summary.csv")
    funding_struct = pd.read_csv(tables / "funding_structural_comparison_summary.csv")

    merged = pub.merge(glob, on="period").merge(inter, on="period")
    merged["mentions_per_publication"] = merged["institution_mentions"] / merged["publication_count"]
    merged["lcc_share"] = merged["largest_connected_component_size"] / merged["nodes"]

    processed["period"] = processed["period"].astype(str)
    processed["institution_count"] = processed["institutions"].apply(
        lambda value: len(ast.literal_eval(value)) if isinstance(value, str) and value else 0
    )
    raw_query_rows = []
    raw_dir = ROOT / "data" / "raw"
    for query in protocol.get("queries", []):
        query_id = str(query.get("id", "")).strip()
        snapshot_path = raw_dir / f"pubmed_records_{query_id}.jsonl"
        raw_query_rows.append(
            {
                "query_id": query_id,
                "date_window": str(query.get("query", "")).split("AND ((")[-1].rstrip(")"),
                "raw_record_count": _count_jsonl_rows(snapshot_path) if snapshot_path.exists() else 0,
            }
        )
    raw_query_summary = pd.DataFrame(raw_query_rows)
    funding_counts = (
        processed["funding_category"]
        .value_counts()
        .rename_axis("funding_category")
        .reset_index(name="publication_count")
    )
    methods_category_rows = [
        {
            "label": str(item.get("label", "")).strip(),
            "description": str(sidecar.get("label_descriptions", {}).get(str(item.get("label", "")).strip(), "")).strip(),
        }
        for item in protocol.get("classification", {}).get("categories", [])
    ]
    methods_category_rows.append(
        {
            "label": str(protocol.get("classification", {}).get("fallback_label", "Other")).strip(),
            "description": "Affiliations that did not fit any of the predefined institutional-domain groups closely enough for a more specific assignment.",
        }
    )
    methods_categories = pd.DataFrame(methods_category_rows)

    outlier_record = (
        processed.loc[processed["period"] == "2016-2019"]
        .sort_values(["institution_count", "pmid"], ascending=[False, True])
        .iloc[0]
        .to_dict()
    )

    top_regions = (
        who.sort_values(["period", "publication_count", "institution_count"], ascending=[True, False, False])
        .groupby("period", as_index=False)
        .head(1)
        .reset_index(drop=True)
    )

    latest_regions = (
        who[who["period"] == "2025-2025"]
        .sort_values(["publication_count", "institution_count"], ascending=[False, False])
        .reset_index(drop=True)
    )

    centrality = {}
    for path in sorted((tables / "centrality").glob("centrality_top10_*.csv")):
        period = path.stem.replace("centrality_top10_", "")
        df = pd.read_csv(path)
        centrality[period] = {
            "degree_node": str(df.loc[0, "degree_node"]),
            "degree_score": float(df.loc[0, "degree_score"]),
            "betweenness_node": str(df.loc[0, "betweenness_node"]),
            "betweenness_score": float(df.loc[0, "betweenness_score"]),
        }

    def value_for(metric: str, period: str) -> str:
        row = descriptive.loc[descriptive["Metric"] == metric]
        if row.empty:
            return ""
        return str(row.iloc[0][period])

    role_composition = pd.DataFrame(
        {
            "Period": PERIODS,
            "High-centrality": [value_for("  B1 High-centrality institutions, n (%)", p) for p in PERIODS],
            "Mid-centrality": [value_for("  B2 Mid-centrality institutions, n (%)", p) for p in PERIODS],
            "Low-centrality": [value_for("  B3 Low-centrality institutions, n (%)", p) for p in PERIODS],
            "Zero-centrality": [value_for("  B4 Zero-centrality institutions, n (%)", p) for p in PERIODS],
        }
    )

    transition_metrics = pd.DataFrame(
        {
            "Transition": PERIODS[1:],
            "Active in both periods": [value_for("  H1 Active institutions in both periods, n", p) for p in PERIODS[1:]],
            "Role changes": [value_for("  H2 Role changes among active institutions, n", p) for p in PERIODS[1:]],
            "Low→Mid": [value_for("  H3 Upward Low-centrality institutions -> Mid-centrality institutions, n", p) for p in PERIODS[1:]],
            "Mid→High": [value_for("  H4 Upward Mid-centrality institutions -> High-centrality institutions, n", p) for p in PERIODS[1:]],
            "Entries": [value_for("  H8 Entries (Absent -> active tiers), n", p) for p in PERIODS[1:]],
            "Exits": [value_for("  H9 Exits (active tiers -> Absent), n", p) for p in PERIODS[1:]],
        }
    )

    descriptive_compact = pd.DataFrame(
        {
            "Period": PERIODS,
            "Publications": [int(pub.loc[pub["period"] == p, "publication_count"].iloc[0]) for p in PERIODS],
            "Institution mentions": [int(pub.loc[pub["period"] == p, "institution_mentions"].iloc[0]) for p in PERIODS],
            "Nodes": [int(glob.loc[glob["period"] == p, "nodes"].iloc[0]) for p in PERIODS],
            "Edges": [int(glob.loc[glob["period"] == p, "edges"].iloc[0]) for p in PERIODS],
        }
    )

    funding_summary = (
        funding_pub.groupby("funding_category", as_index=False)[["publication_count", "institution_mentions"]]
        .sum()
        .merge(
            funding_glob.groupby("funding_category", as_index=False)[["density", "avg_degree", "median_degree"]].mean(),
            on="funding_category",
        )
        .merge(
            funding_inter.groupby("funding_category", as_index=False)[["three_or_more_field_ratio"]].mean(),
            on="funding_category",
        )
        .merge(
            funding_struct.groupby("funding_category", as_index=False)[["lcc_share_pct"]].mean(),
            on="funding_category",
        )
    )
    funding_summary["Funding category"] = funding_summary["funding_category"].map(FUNDING_LABELS)
    funding_summary = funding_summary.set_index("funding_category").loc[FUNDING_ORDER].reset_index(drop=True)

    funding_region_leaders = (
        funding_who.sort_values(
            ["funding_category", "period", "publication_count", "institution_count"],
            ascending=[True, True, False, False],
        )
        .groupby(["funding_category", "period"], as_index=False)
        .head(1)
    )

    return {
        "pub": pub,
        "glob": glob,
        "inter": inter,
        "core": core,
        "who": who,
        "descriptive": descriptive,
        "pairwise": pairwise,
        "combinations": combinations,
        "focal_profiles": focal_profiles,
        "three_field_timelapse": three_field_timelapse,
        "prominent_transitions": prominent_transitions,
        "who_pairwise": who_pairwise,
        "country_pairwise": country_pairwise,
        "country_display": country_display,
        "funding_domain_profiles": funding_domain_profiles,
        "llm": llm,
        "review_queue": review_queue,
        "processed": processed,
        "protocol": protocol,
        "sidecar": sidecar,
        "raw_query_summary": raw_query_summary,
        "funding_counts": funding_counts,
        "methods_categories": methods_categories,
        "outlier_record": outlier_record,
        "merged": merged,
        "top_regions": top_regions,
        "latest_regions": latest_regions,
        "centrality": centrality,
        "role_composition": role_composition,
        "transition_metrics": transition_metrics,
        "descriptive_compact": descriptive_compact,
        "funding_pub": funding_pub,
        "funding_glob": funding_glob,
        "funding_inter": funding_inter,
        "funding_core": funding_core,
        "funding_who": funding_who,
        "funding_struct": funding_struct,
        "funding_summary": funding_summary,
        "funding_region_leaders": funding_region_leaders,
    }


def add_front_matter(doc: Document, data: dict[str, object]) -> None:
    pub = data["pub"]
    llm = data["llm"]
    merged = data["merged"]
    total_publications = int(pub["publication_count"].sum())
    total_mentions = int(pub["institution_mentions"].sum())
    total_nodes = int(merged["nodes"].sum())
    total_affiliations = int(len(llm))
    ok_count = int((llm["status"] == "ok").sum())
    failed_count = int((llm["status"] == "failed").sum())
    other_count = int((llm["label"] == "Other").sum())

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run("MANUSCRIPT-READY METHODS AND RESULTS REPORT")
    run.bold = True
    run.font.size = Pt(11)

    title = doc.add_paragraph(style="Title")
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.add_run("Mapping Collaboration in AI and Diabetes Research: Detailed Methods and Results Report")

    subtitle = doc.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subrun = subtitle.add_run("Canonical LLM-based temporal institutional network analysis | Methods and results update | V1 | May 2026")
    subrun.italic = True
    subrun.font.size = Pt(10.5)

    note_box(
        doc,
        "This report is based on the completed canonical output tree and is intended for collaborator circulation "
        "as a near-manuscript methods-and-results document. The final affiliation-classification basis accepts all "
        f"{total_affiliations:,} unique affiliation strings, including {ok_count:,} structured assignments and "
        f"{failed_count:,} rows that were accepted canonically as Other. Across the full corpus, the analysis spans "
        f"{total_publications:,} screened publications, {total_mentions:,} institution mentions, and {total_nodes:,} "
        "period-specific institutional nodes. The current Other pool contains "
        f"{other_count:,} unique affiliations and is treated as a final analytic category in this report."
    )
    add_spacer(doc, 8)


def add_methods_section(doc: Document, data: dict[str, object]) -> None:
    protocol = data["protocol"]
    sidecar = data["sidecar"]
    processed = data["processed"]
    llm = data["llm"]
    review_queue = data["review_queue"]
    raw_query_summary = data["raw_query_summary"]
    funding_counts = data["funding_counts"]
    methods_categories = data["methods_categories"]

    retrieval_date = str(protocol["study"]["retrieval_date"])
    publication_end = str(protocol["study"]["hard_publication_end_date"])
    periods = protocol["temporal_segmentation"]["fixed_periods"]
    period_text = "; ".join(
        f"{item['label']} ({item['start_year']}-{item['end_year']})" for item in periods
    )
    total_raw = int(raw_query_summary["raw_record_count"].sum())
    total_publications = int(len(processed))
    min_year = int(processed["publication_year"].min())
    max_year = int(processed["publication_year"].max())
    grant_supported = int(processed["has_grant_support"].sum())
    no_grant = int(funding_counts.loc[funding_counts["funding_category"] == "NO_GRANT_LISTED", "publication_count"].iloc[0])
    us_federal = int(funding_counts.loc[funding_counts["funding_category"] == "US_FEDERAL_FUNDED", "publication_count"].iloc[0])
    non_us = int(funding_counts.loc[funding_counts["funding_category"] == "NON_US_OR_INTL_FUNDED", "publication_count"].iloc[0])
    unique_affiliations = int(len(llm))
    ok_count = int((llm["status"] == "ok").sum())
    failed_count = int((llm["status"] == "failed").sum())
    review_count = int(len(review_queue))
    fallback_label = str(protocol["classification"]["fallback_label"])
    category_names = ", ".join(str(label).replace("_", " ") for label in methods_categories["label"].tolist())
    query_1 = str(protocol["queries"][0]["query"]).strip()
    query_2 = str(protocol["queries"][1]["query"]).strip()
    label_lines = [
        f"- {str(row.label)}: {str(row.description)}"
        for row in methods_categories.itertuples(index=False)
    ]
    prompt_lines = [
        "System prompt:",
        "You classify biomedical raw affiliation strings into exactly one institution-domain label.",
        "Base the decision on the department, institution, or organization named in the affiliation.",
        "Do not classify by paper topic unless it is needed to disambiguate the institution type.",
        "Return exactly one label from the allowed list.",
        f"Use {fallback_label} only when none of the labels fit well.",
        "Return a confidence score between 0 and 1.",
        "Keep confusion_note empty when confident.",
        "If uncertain, keep confusion_note short and specific.",
        "Allowed labels:",
        *label_lines,
        "User prompt template:",
        "Classify this raw affiliation string.",
        "Affiliation: <raw affiliation text>",
        "Structured response fields: label, confidence, confusion_note",
    ]

    doc.add_heading("Methods", level=1)

    doc.add_heading("Study design and data source", level=2)
    p = doc.add_paragraph()
    p.add_run(
        "This study used a PubMed-based temporal institutional collaboration design to examine how AI-and-diabetes research has evolved over time. "
        "The analytic unit was the institutional affiliation listed on each publication rather than the individual author. "
        f"PubMed records were retrieved on {retrieval_date}, and the search was hard-capped at a publication date of {publication_end} so that 2026 papers were not included."
    )

    doc.add_heading("PubMed search strategy", level=2)
    p = doc.add_paragraph()
    p.add_run(
        "The search used two protocol-defined PubMed query blocks. Together, they combined artificial intelligence, machine learning, computational, decision-support, digital health, and remote monitoring terms with diabetes-specific disease, monitoring, and complication terms. "
        "The scope was intentionally centered on diabetes and diabetes-related care rather than a broader obesity or general metabolic-disease corpus."
    )
    p = doc.add_paragraph()
    p.add_run(
        "The first query block covered the earlier literature window and the second query block covered the recent period through the final publication ceiling. "
        "This split was used to keep retrieval manageable while preserving one consistent study definition."
    )
    methods_text_box(
        doc,
        "Exact PubMed search block 1",
        [
            "Query identifier: ai_diabetes_1972_2012",
            query_1,
        ],
        font_size=7.0,
    )
    add_spacer(doc, 3)
    methods_text_box(
        doc,
        "Exact PubMed search block 2",
        [
            "Query identifier: ai_diabetes_2022_2025",
            query_2,
        ],
        font_size=7.0,
    )
    add_spacer(doc, 4)

    doc.add_heading("Screening and final analytic cohort", level=2)
    p = doc.add_paragraph()
    p.add_run(
        f"A total of {total_raw:,} PubMed records were retrieved across the two query blocks. Records were then screened using protocol-defined diabetes inclusion terms applied to the title, abstract, and MeSH text. "
        "Records without usable affiliation information were excluded, and publication-level duplicates were removed before analysis."
    )
    p = doc.add_paragraph()
    p.add_run(
        f"The final analytic cohort contained {total_publications:,} screened publications spanning {min_year} through {max_year}. "
        f"Of these, {grant_supported:,} publications had at least one grant entry, while {no_grant:,} had no grant listed. "
        f"The funded subset comprised {us_federal:,} US federally funded publications and {non_us:,} non-US or internationally funded publications."
    )

    doc.add_heading("Affiliation extraction and institutional unit definition", level=2)
    p = doc.add_paragraph()
    p.add_run(
        "The default extraction mode treated each exact raw affiliation string as the institutional unit. In practice, this means the named department, hospital, institute, university unit, or company affiliation was carried forward directly rather than being aggressively collapsed into a manually harmonized master list."
    )
    p = doc.add_paragraph()
    p.add_run(
        "To keep the workflow reproducible, affiliation text was normalized in a limited way before downstream processing: punctuation was cleaned, text was standardized for case, and repeated institution-country pairs were deduplicated within each publication. "
        "This approach intentionally favors a transparent, rerunnable pipeline over deeper hand-curated institutional disambiguation."
    )

    doc.add_heading("LLM-based institutional domain grouping", level=2)
    p = doc.add_paragraph()
    p.add_run(
        "The canonical analysis used the LLM-based institutional grouping workflow rather than the older keyword-only classifier. Each unique raw affiliation string was classified one at a time, with the model asked to identify the kind of organization or department named in the affiliation. "
        f"The model was instructed to choose exactly one allowed domain label and to use {fallback_label} only when none of the predefined domains fit well."
    )
    p = doc.add_paragraph()
    p.add_run(
        f"The implemented classification workflow used model {sidecar['model']}, prompt version {sidecar['prompt_version']}, and schema version {sidecar['schema_version']}. "
        f"Every classification required a confidence score, and rows with confidence below {float(sidecar['review_confidence_threshold']):.2f} were also written to a low-confidence review queue. "
        "Responses were cached so that classification was reproducible and resumable rather than being regenerated from scratch each time."
    )
    p = doc.add_paragraph()
    p.add_run(
        f"In the final accepted classification set, {unique_affiliations:,} unique affiliation strings were processed. "
        f"This yielded {ok_count:,} structured classifications with valid model output and {failed_count:,} rows whose final accepted label was retained as {fallback_label}. "
        f"The low-confidence review queue contained {review_count:,} rows. In manuscript terms, accepted failed rows were not dropped; they were kept in the canonical analysis as {fallback_label} so every unique affiliation remained represented."
    )

    methods_text_box(
        doc,
        "Methods box: Near-verbatim LLM prompt structure used for institutional grouping",
        prompt_lines,
        font_size=7.2,
    )
    add_spacer(doc, 5)

    doc.add_heading("Institutional grouping framework", level=2)
    p = doc.add_paragraph()
    p.add_run(
        "Institutions were assigned to a single diabetology-oriented domain framework rather than being multi-tagged across several domains. "
        f"The full grouping framework used in this report was: {category_names}. "
        f"{fallback_label} was the catch-all category for affiliations that did not fit the predefined groups closely enough for a more specific assignment."
    )

    doc.add_heading("Temporal segmentation, network construction, and role assignment", level=2)
    p = doc.add_paragraph()
    p.add_run(
        f"The manuscript periods were fixed in advance as follows: {period_text}. Within each period, an undirected institution-to-institution collaboration network was constructed from co-occurrence within publications. "
        "In plain language, each node represents one institutional affiliation and each edge represents a paper on which two institutions appeared together."
    )
    p = doc.add_paragraph()
    p.add_run(
        "Institutions were then summarized into role tiers to make network position easier to interpret clinically. Core institutions were the most central and connective actors, semi-peripheral institutions remained active but somewhat less dominant, peripheral institutions were more modestly embedded, and isolates were present in the period but had no collaboration link to another institution in that period-specific network."
    )

    doc.add_heading("Additional analytic layers", level=2)
    p = doc.add_paragraph()
    p.add_run(
        "Beyond overall growth and connectivity, the analysis examined several additional layers. Interdisciplinarity analyses asked whether collaboration clusters stayed within one institutional domain or mixed several domains together. Geography analyses mapped affiliations to countries and then to WHO regions to describe both distribution and cross-region collaboration patterns. Funding analyses applied a three-level hierarchy separating US federally funded, non-US or internationally funded, and no-grant-listed publications. Centrality and transition analyses were used to identify prominent institutions and to describe how collaboration roles changed from one manuscript period to the next."
    )

    doc.add_heading("Primary analytic focus", level=2)
    p = doc.add_paragraph()
    p.add_run(
        "The main analytic questions were whether AI-and-diabetes research grew in scale, whether the collaboration network became more cohesive over time, how institutional interdisciplinarity changed, how the field spread geographically, and whether funded and non-funded research showed different collaboration structures."
    )

    add_table_caption(doc, "Table M1. Study cohort and data-processing summary.")
    table = doc.add_table(rows=1, cols=3)
    headers = ["Element", "Value", "Plain-language note"]
    for idx, label in enumerate(headers):
        table.rows[0].cells[idx].text = label
    rows = []
    for row in raw_query_summary.itertuples(index=False):
        window = _extract_query_window(protocol["queries"][len(rows)]["query"])
        rows.append((f"PubMed query block: {row.query_id}", f"{int(row.raw_record_count):,}", f"Configured publication-date window: {window}."))
    rows.extend(
        [
            ("Combined raw PubMed records", f"{total_raw:,}", "All records retrieved across both protocol-defined PubMed query blocks before screening."),
            ("Final included screened publications", f"{total_publications:,}", "Unique publications retained after screening, affiliation checks, and deduplication."),
            ("Publication year span", f"{min_year}-{max_year}", "Observed year range in the final screened cohort."),
            ("Unique affiliation strings classified", f"{unique_affiliations:,}", "Distinct raw affiliation strings sent through the canonical LLM-based grouping workflow."),
            ("LLM structured classifications", f"{ok_count:,}", "Rows with valid structured model output in the final accepted classification set."),
            (f"Accepted {fallback_label} fallback rows", f"{failed_count:,}", f"Rows kept canonically as {fallback_label} after unsuccessful structured output recovery."),
            ("Low-confidence review rows", f"{review_count:,}", "Rows copied to the review queue because confidence was below the protocol threshold."),
            ("Publications with any grant support", f"{grant_supported:,}", "Publications with at least one PubMed grant entry."),
            ("US federally funded publications", f"{us_federal:,}", "Publications with at least one detected US federal grant signal."),
            ("Non-US or internationally funded publications", f"{non_us:,}", "Grant-supported publications without a US federal signal."),
            ("No-grant-listed publications", f"{no_grant:,}", "Publications without any grant entry in PubMed."),
        ]
    )
    for element, value, note in rows:
        cells = table.add_row().cells
        cells[0].text = element
        cells[1].text = value
        cells[2].text = note
    format_table(table, widths=[Inches(2.25), Inches(1.0), Inches(3.0)], font_size=8.2)

    add_spacer(doc, 5)
    add_table_caption(doc, "Table M2. Institutional grouping framework used in the canonical LLM-based analysis.")
    table = doc.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = "Institutional domain label"
    table.rows[0].cells[1].text = "Plain-language scope"
    for row in methods_categories.itertuples(index=False):
        cells = table.add_row().cells
        cells[0].text = str(row.label)
        cells[1].text = str(row.description)
    format_table(table, widths=[Inches(2.15), Inches(4.1)], font_size=8.2)
    add_spacer(doc, 8)


def add_results_overview(doc: Document, data: dict[str, object]) -> None:
    pub = data["pub"]
    merged = data["merged"]
    total_publications = int(pub["publication_count"].sum())
    total_mentions = int(pub["institution_mentions"].sum())
    peak_pub = pub.loc[pub["publication_count"].idxmax()]
    peak_mentions = pub.loc[pub["institution_mentions"].idxmax()]

    doc.add_heading("Results Overview", level=1)
    p = doc.add_paragraph()
    p.add_run(
        f"The completed analysis covers {total_publications:,} PubMed-indexed publications distributed across six "
        "fixed manuscript periods spanning 1988 through 2025. Institutional participation scaled sharply over time, "
        f"with {total_mentions:,} institution mentions overall. Publication volume peaked in {peak_pub.period} at "
        f"{int(peak_pub.publication_count):,} publications, while institution mentions peaked in {peak_mentions.period} "
        f"at {int(peak_mentions.institution_mentions):,}. Across periods, the network moved from a relatively sparse "
        "clinical collaboration environment into a much larger multi-institutional ecosystem whose growth was "
        "accompanied by stronger interdisciplinarity, broader geographic diffusion, and a more mixed clinical-technical "
        "collaboration core."
    )
    p = doc.add_paragraph()
    p.add_run(
        "The descriptive and structural tables below should be interpreted together. Publication growth alone does "
        "not imply maturation; a more persuasive sign of maturation is whether later periods also show sustained "
        "increases in institutional participation, richer connected-component diversity, and more coherent role-flow "
        "patterns across the collaboration hierarchy."
    )
    add_spacer(doc, 4)
    add_table_caption(doc, "Clinician glossary. Plain-language explanations for the main network terms used in this report.")
    table = doc.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = "Term"
    table.rows[0].cells[1].text = "Plain-language explanation"
    for term, explanation in GLOSSARY_ROWS:
        cells = table.add_row().cells
        cells[0].text = term
        cells[1].text = explanation
    format_table(table, widths=[Inches(1.3), Inches(5.3)], font_size=8.6)


def add_corpus_growth_section(doc: Document, data: dict[str, object], assets: dict[str, Path]) -> None:
    pub = data["pub"]
    compact = data["descriptive_compact"]
    merged = data["merged"]

    doc.add_heading("1. Corpus Growth and Descriptive Summary", level=1)
    p = doc.add_paragraph()
    p.add_run(
        f"Field expansion is visible in both publication counts and institutional scale. The corpus grew from "
        f"{int(pub.iloc[0].publication_count):,} publications in 1988-2015 to {int(pub.iloc[-1].publication_count):,} "
        f"publications in 2025-2025, while institution mentions increased from {int(pub.iloc[0].institution_mentions):,} "
        f"to {int(pub.iloc[-1].institution_mentions):,}. The 2022-2023 period was the largest by publication volume "
        f"({int(pub.loc[pub['publication_count'].idxmax(), 'publication_count']):,}), and 2022-2023 as well as 2025-2025 "
        "showed especially large institutional footprints. This pattern indicates that AI-and-diabetes research is "
        "not only producing more papers, but also assembling broader institutional constellations around individual studies."
    )
    p = doc.add_paragraph()
    p.add_run(
        f"The change in network scale is equally pronounced. Period-specific node counts rose from {int(merged.iloc[0].nodes):,} "
        f"to {int(merged.iloc[-1].nodes):,}, and edge counts expanded from {int(merged.iloc[0].edges):,} to "
        f"{int(merged.iloc[-1].edges):,}. Figure 1 provides the manuscript-ready overview of institutional role flow "
        "across the completed time horizon, while Table 1 condenses the key descriptive measures that anchor the rest "
        "of the report."
    )

    add_table_caption(doc, "Table 1. High-level descriptive summary by manuscript period.")
    table = doc.add_table(rows=1, cols=5)
    headers = ["Period", "Publications", "Institution mentions", "Nodes", "Edges"]
    for idx, label in enumerate(headers):
        table.rows[0].cells[idx].text = label
    for _, row in compact.iterrows():
        cells = table.add_row().cells
        cells[0].text = str(row["Period"])
        cells[1].text = f"{int(row['Publications']):,}"
        cells[2].text = f"{int(row['Institution mentions']):,}"
        cells[3].text = f"{int(row['Nodes']):,}"
        cells[4].text = f"{int(row['Edges']):,}"
    format_table(table, widths=[Inches(1.15), Inches(1.1), Inches(1.45), Inches(1.1), Inches(1.1)], font_size=9.0)
    add_spacer(doc, 6)

    add_figure(
        doc,
        assets["all_institutions_role_flow"],
        "Figure 1. Static overview of institutional role flow across all manuscript periods.",
        width=Inches(6.2),
    )


def add_network_growth_section(doc: Document, data: dict[str, object]) -> None:
    merged = data["merged"]
    outlier = data["outlier_record"]
    doc.add_heading("2. Network Growth and Cohesion", level=1)
    anomalous = merged.loc[merged["period"] == "2016-2019"].iloc[0]
    latest = merged.iloc[-1]
    p = doc.add_paragraph()
    p.add_run(
        f"The collaboration system expanded faster than it consolidated. Density measured {merged.iloc[0].density:.6f} "
        f"in 1988-2015, rose anomalously to {anomalous.density:.6f} in 2016-2019, and then returned to a lower late-period "
        f"range between {merged.iloc[2:]['density'].min():.6f} and {merged.iloc[2:]['density'].max():.6f}. The same pattern "
        f"appears in average degree, which rose from {merged.iloc[0].avg_degree:.2f} to an outlying {anomalous.avg_degree:.2f} "
        f"in 2016-2019 before settling into a later range of roughly {merged.iloc[2:]['avg_degree'].min():.2f}-{merged.iloc[2:]['avg_degree'].max():.2f}. "
        f"By contrast, median degree rose more modestly from {merged.iloc[0].median_degree:.2f} to {anomalous.median_degree:.2f} "
        f"and remained between {merged.iloc[2:]['median_degree'].min():.2f} and {merged.iloc[2:]['median_degree'].max():.2f} afterward, "
        "showing that the typical institution was not experiencing the same explosive connectivity implied by the mean."
    )
    p = doc.add_paragraph()
    p.add_run(
        f"The 2016-2019 interval is therefore best interpreted as a structurally exceptional collaboration episode rather "
        f"than a simple field-wide increase in everyday cohesion. That period combined {int(anomalous.nodes):,} nodes with "
        f"{int(anomalous.edges):,} edges, far exceeding neighboring periods despite not being the largest by publication count. "
        f"By contrast, 2025-2025 had more than {int(latest.nodes):,} nodes but only {int(latest.edges):,} edges, indicating a "
        "broader yet less explosively connected network. Largest connected component shares also remained modest, underscoring "
        "that the field continues to expand through many partially disconnected collaboration clusters rather than one fully "
        "integrated global core."
    )
    p = doc.add_paragraph()
    p.add_run(
        f"One concrete outlier helps explain this spike. In the processed 2016-2019 cohort, PMID {outlier['pmid']} "
        f"({int(outlier['publication_year'])}) carried {int(outlier['institution_count']):,} unique institutions: "
        f"\"{short_label(outlier['title'], limit=120)}\". A record of that scale behaves more like a proceedings-style or consortium-style "
        "mega-collaboration than a typical multi-institution paper, and it likely inflated pairwise edge creation substantially during that period. "
        "This does not fully explain the entire 2016-2019 pattern on its own, but it makes clear why mean connectivity measures should be interpreted "
        "alongside median degree and publication context."
    )

    add_table_caption(doc, "Table 2. Network cohesion and largest-component metrics by period.")
    table = doc.add_table(rows=1, cols=8)
    headers = ["Period", "Nodes", "Edges", "Density", "Avg degree", "Median degree", "Weighted clustering", "LCC share"]
    for idx, label in enumerate(headers):
        table.rows[0].cells[idx].text = label
    for row in merged.itertuples(index=False):
        cells = table.add_row().cells
        cells[0].text = row.period
        cells[1].text = f"{int(row.nodes):,}"
        cells[2].text = f"{int(row.edges):,}"
        cells[3].text = f"{row.density:.6f}"
        cells[4].text = f"{row.avg_degree:.2f}"
        cells[5].text = f"{row.median_degree:.2f}"
        cells[6].text = f"{row.avg_clustering_weighted:.3f}"
        cells[7].text = pct(row.lcc_share)
    format_table(
        table,
        widths=[Inches(0.95), Inches(0.75), Inches(0.88), Inches(0.72), Inches(0.8), Inches(0.9), Inches(1.0), Inches(0.75)],
        font_size=8.2,
    )


def add_role_flow_section(doc: Document, data: dict[str, object], assets: dict[str, Path]) -> None:
    role_comp = data["role_composition"]
    transitions = data["transition_metrics"]
    doc.add_heading("3. Institutional Role Composition and Transitions", level=1)
    p = doc.add_paragraph()
    p.add_run(
        f"The institutional role mix changed markedly after the earliest period. Zero-centrality institutions accounted "
        f"for {role_comp.iloc[0]['Zero-centrality']} in 1988-2015, but fell to a narrow late-period band around "
        f"{role_comp.iloc[-1]['Zero-centrality']} by 2025-2025. At the same time, mid-centrality and low-centrality "
        "institutions became the modal forms of participation, indicating that later collaboration systems were populated "
        "less by isolated one-off nodes and more by institutions occupying active but non-dominant positions in the network."
    )
    p = doc.add_paragraph()
    p.add_run(
        f"Role transitions among institutions active in adjacent periods remained substantial. Across the five inter-period "
        f"transitions, active institutions present in both periods totaled {sum(int(str(v).replace(',', '')) for v in transitions['Active in both periods']):,}, "
        f"and role changes totaled {sum(int(str(v).replace(',', '')) for v in transitions['Role changes']):,}. Entries vastly "
        "outnumbered retained active institutions in every interval, reinforcing that field expansion continues to be driven "
        "by large waves of new institutional participation layered onto a smaller but denser returning core."
    )

    add_table_caption(doc, "Table 3. Role composition by period.")
    table = doc.add_table(rows=1, cols=5)
    for idx, label in enumerate(role_comp.columns):
        table.rows[0].cells[idx].text = label
    for row in role_comp.itertuples(index=False):
        cells = table.add_row().cells
        for idx, value in enumerate(row):
            cells[idx].text = str(value)
    format_table(table, widths=[Inches(1.0), Inches(1.25), Inches(1.25), Inches(1.25), Inches(1.25)], font_size=8.4)
    add_spacer(doc, 4)

    add_table_caption(doc, "Table 4. Selected role-transition indicators across adjacent period pairs.")
    table = doc.add_table(rows=1, cols=7)
    for idx, label in enumerate(transitions.columns):
        table.rows[0].cells[idx].text = label
    for row in transitions.itertuples(index=False):
        cells = table.add_row().cells
        for idx, value in enumerate(row):
            cells[idx].text = str(value)
    format_table(
        table,
        widths=[Inches(0.95), Inches(0.95), Inches(0.85), Inches(0.8), Inches(0.8), Inches(0.95), Inches(0.95)],
        font_size=8.0,
    )
    add_spacer(doc, 6)

    add_figure(
        doc,
        assets["role_flow_overview"],
        "Figure 2. Static Sankey-style rendering of role flow among institutions active in adjacent periods.",
        width=Inches(6.2),
    )


def add_interdisciplinarity_section(doc: Document, data: dict[str, object], assets: dict[str, Path]) -> None:
    inter = data["inter"]
    pairwise = data["pairwise"]
    combinations = data["combinations"]
    focal_profiles = data["focal_profiles"]
    doc.add_heading("4. Interdisciplinarity and Component Structure", level=1)
    doc.add_heading("4A. High-Level Interdisciplinarity Summary", level=2)
    early = inter.iloc[0]
    late = inter.iloc[-1]
    peak = inter.loc[inter["three_or_more_field_ratio"].idxmax()]
    p = doc.add_paragraph()
    p.add_run(
        f"Component-level interdisciplinarity increased sharply after the formative phase. In 1988-2015, "
        f"{pct(early.single_field_ratio)} of components were single-field and the mean number of distinct key fields per "
        f"component was only {early.mean_distinct_key_fields_per_component:.2f}. By 2025-2025, the single-field share "
        f"had declined to {pct(late.single_field_ratio)}, while the mean number of distinct key fields per component had "
        f"risen to {late.mean_distinct_key_fields_per_component:.2f}."
    )
    p = doc.add_paragraph()
    p.add_run(
        f"The highest three-or-more-field share was observed in {peak.period}, when {pct(peak.three_or_more_field_ratio)} "
        f"of components crossed at least three key domains. The maximum domain span within a single component grew from "
        f"{int(early.max_distinct_key_fields_in_component)} fields in the earliest period to {int(late.max_distinct_key_fields_in_component)} "
        "fields in the latest period. These results suggest that later collaboration clusters increasingly integrate clinical, "
        "technical, epidemiologic, and complication-focused groups within the same connected structures."
    )

    add_table_caption(doc, "Table 5. Interdisciplinarity and component-composition metrics by period.")
    table = doc.add_table(rows=1, cols=6)
    headers = ["Period", "Single-field", "Two-field", "Three+ field", "Mean fields/component", "Max fields/component"]
    for idx, label in enumerate(headers):
        table.rows[0].cells[idx].text = label
    for row in inter.itertuples(index=False):
        cells = table.add_row().cells
        cells[0].text = row.period
        cells[1].text = pct(row.single_field_ratio)
        cells[2].text = pct(row.two_field_ratio)
        cells[3].text = pct(row.three_or_more_field_ratio)
        cells[4].text = f"{row.mean_distinct_key_fields_per_component:.2f}"
        cells[5].text = f"{int(row.max_distinct_key_fields_in_component)}"
    format_table(table, widths=[Inches(1.0), Inches(1.0), Inches(0.95), Inches(0.95), Inches(1.3), Inches(1.2)], font_size=8.5)
    add_spacer(doc, 6)

    add_figure(
        doc,
        assets["field_small_multiples"],
        "Figure 3. Field-stratified role-flow small multiples showing how institutional positions evolve across manuscript periods, with explicit panel titles for each field grouping.",
        width=Inches(6.15),
    )
    doc.add_heading("4B. Pairwise Field Collaboration Patterns", level=2)
    cross_pairwise = pairwise[pairwise["field_a"] != pairwise["field_b"]].copy()
    pairwise_top = (
        cross_pairwise.sort_values(["period", "component_count", "field_a", "field_b"], ascending=[True, False, True, True])
        .groupby("period", as_index=False)
        .head(1)
        .reset_index(drop=True)
    )
    early_pair = pairwise_top[pairwise_top["period"] == PERIODS[0]].iloc[0]
    late_pair = pairwise_top[pairwise_top["period"] == PERIODS[-1]].iloc[0]
    peak_pair = cross_pairwise.sort_values(["component_count", "period"], ascending=[False, True]).iloc[0]
    diagonal_top = pairwise[pairwise["field_a"] == pairwise["field_b"]].copy()
    diagonal_top = diagonal_top.sort_values(["period", "component_count", "field_a"], ascending=[True, False, True])
    latest_diagonal = diagonal_top[diagonal_top["period"] == PERIODS[-1]].iloc[0]

    field_order = list(FIELD_SHORT_LABELS.keys())
    pair_index = cross_pairwise.set_index(["period", "field_a", "field_b"])["component_count"].to_dict()
    full_rows = []
    for idx, field_a in enumerate(field_order):
        for field_b in field_order[idx + 1 :]:
            row = {"field_a": field_a, "field_b": field_b}
            for period in PERIODS:
                key = (period, field_a, field_b)
                rev_key = (period, field_b, field_a)
                row[period] = int(pair_index.get(key, pair_index.get(rev_key, 0)))
            full_rows.append(row)
    full_pairs = pd.DataFrame(full_rows)
    full_pairs["early_count"] = full_pairs[PERIODS[0]]
    full_pairs["late_count"] = full_pairs[PERIODS[-1]]
    full_pairs["late_minus_early"] = full_pairs["late_count"] - full_pairs["early_count"]
    growth_pairs = full_pairs.sort_values(
        ["late_minus_early", "late_count", "field_a", "field_b"], ascending=[False, False, True, True]
    )
    top_growth = growth_pairs.iloc[0]
    emergent_pairs = full_pairs[(full_pairs["early_count"] == 0) & (full_pairs["late_count"] > 0)].sort_values(
        ["late_count", "field_a", "field_b"], ascending=[False, True, True]
    )
    top_emergent = emergent_pairs.head(3)
    never_pairs = full_pairs[full_pairs[PERIODS].sum(axis=1) == 0].copy()
    persistently_rare = full_pairs[
        (full_pairs[PERIODS].sum(axis=1) > 0) & (full_pairs[PERIODS].max(axis=1) <= 2)
    ].sort_values(["field_a", "field_b"])
    p = doc.add_paragraph()
    p.add_run(
        "Figure 4 moves beyond counting how many disciplines are present in a component and instead counts how often specific field combinations occur inside connected collaboration structures. "
        "Off-diagonal cells represent cross-field component counts, whereas diagonal cells represent same-field components containing at least two institutions from that field. "
        f"In the latest period, the strongest same-field pattern is {FIELD_SHORT_LABELS.get(latest_diagonal.field_a, latest_diagonal.field_a)}, "
        f"which appears in {int(latest_diagonal.component_count):,} multi-institution same-field components."
    )
    p = doc.add_paragraph()
    p.add_run(
        f"Among cross-field bridges, {FIELD_SHORT_LABELS.get(early_pair.field_a, early_pair.field_a)} + "
        f"{FIELD_SHORT_LABELS.get(early_pair.field_b, early_pair.field_b)} was already the leading pair in {PERIODS[0]} "
        f"at {int(early_pair.component_count):,} connected components, and it remained the leading pair in {PERIODS[-1]} at "
        f"{int(late_pair.component_count):,}. The dominant bridge therefore did not shift; instead, the same clinical-technical interface became far more common as the collaboration system grew."
    )
    p = doc.add_paragraph()
    p.add_run(
        f"The strongest absolute growth from the first to the last period is also "
        f"{FIELD_SHORT_LABELS.get(top_growth.field_a, top_growth.field_a)} + {FIELD_SHORT_LABELS.get(top_growth.field_b, top_growth.field_b)}, "
        f"which rose from {int(top_growth.early_count):,} to {int(top_growth.late_count):,} connected components "
        f"(+{int(top_growth.late_minus_early):,}). The strongest single-period cross-field footprint anywhere in the study occurred in {peak_pair.period}, when "
        f"{FIELD_SHORT_LABELS.get(peak_pair.field_a, peak_pair.field_a)} + {FIELD_SHORT_LABELS.get(peak_pair.field_b, peak_pair.field_b)} "
        f"appeared in {int(peak_pair.component_count):,} components. Secondary late-period bridges increasingly cluster around clinical medicine, especially its repeated co-occurrence with endocrinology, public health, and complications-focused domains."
    )
    if not top_emergent.empty:
        emergent_text = "; ".join(
            f"{FIELD_SHORT_LABELS.get(row.field_a, row.field_a)} + {FIELD_SHORT_LABELS.get(row.field_b, row.field_b)} "
            f"(0 to {int(row.late_count):,})"
            for row in top_emergent.itertuples(index=False)
        )
        p = doc.add_paragraph()
        p.add_run(
            f"Some interfaces appear more genuinely late-emerging than simply intensifying from a visible early base. The clearest examples are {emergent_text}. "
            "These newer bridges suggest that recent interdisciplinarity has broadened outward from the established clinical core rather than replacing that core with a different organizing structure."
        )
    p = doc.add_paragraph()
    if len(never_pairs) > 0:
        never_text = "; ".join(
            f"{FIELD_SHORT_LABELS.get(row.field_a, row.field_a)} + {FIELD_SHORT_LABELS.get(row.field_b, row.field_b)}"
            for row in never_pairs.head(5).itertuples(index=False)
        )
        p.add_run(
            f"Some cross-field pairs were never observed in the same connected component anywhere in this analysis, including {never_text}. "
            "This should be read as an absence of observed connected-component co-occurrence in the current dataset, not as evidence that those domains are scientifically incompatible."
        )
    elif len(persistently_rare) > 0:
        rare_text = "; ".join(
            f"{FIELD_SHORT_LABELS.get(row.field_a, row.field_a)} + {FIELD_SHORT_LABELS.get(row.field_b, row.field_b)} "
            f"(maximum {int(row[PERIODS].max()):,})"
            for row in persistently_rare.head(5).itertuples(index=False)
        )
        p.add_run(
            f"No cross-field pair was completely absent across all periods, but some remained persistently rare, including {rare_text}. "
            "These low-frequency interfaces likely reflect either narrow specialty niches or domain pairings that seldom become part of the same broader connected component."
        )
    else:
        p.add_run(
            "No cross-field pair remained completely absent or uniformly rare across the full study window, reinforcing that the later collaboration system spans a broad range of disciplinary interfaces."
        )
    add_figure(
        doc,
        assets["interdisciplinarity_heatmap"],
        "Figure 4. Count-based pairwise field co-occurrence heatmap by manuscript period; off-diagonal cells represent cross-field connected-component counts, diagonal cells represent same-field multi-institution components, and colors use a shared log scale.",
        width=Inches(6.2),
    )

    doc.add_heading("4C. Exact Two-Field Collaboration Profiles", level=2)
    selected_profiles = focal_profiles[focal_profiles["focal_domain"].isin(FOCAL_DOMAINS)].copy()
    profile_lookup = selected_profiles.set_index(["period", "focal_domain", "partner_domain"])

    def profile_value(period: str, focal_domain: str, partner_domain: str, column: str) -> float:
        key = (period, focal_domain, partner_domain)
        if key not in profile_lookup.index:
            return 0.0
        return float(profile_lookup.loc[key, column])

    def profile_count(period: str, focal_domain: str, partner_domain: str) -> int:
        return int(round(profile_value(period, focal_domain, partner_domain, "component_count")))

    def profile_share(period: str, focal_domain: str, partner_domain: str) -> float:
        return profile_value(period, focal_domain, partner_domain, "partner_share_within_focal_domain")

    def profile_total(period: str, focal_domain: str) -> int:
        subset = selected_profiles[
            (selected_profiles["period"] == period) & (selected_profiles["focal_domain"] == focal_domain)
        ]
        return int(subset["focal_domain_total_exact_two_field_components"].iloc[0])

    latest_profiles = selected_profiles[selected_profiles["period"] == PERIODS[-1]].copy()
    latest_top = (
        latest_profiles.sort_values(
            ["focal_domain", "partner_share_within_focal_domain", "component_count", "partner_domain"],
            ascending=[True, False, False, True],
        )
        .groupby("focal_domain", as_index=False)
        .head(1)
        .reset_index(drop=True)
    )
    most_diversified = latest_top.sort_values(
        ["partner_share_within_focal_domain", "component_count"], ascending=[True, False]
    ).iloc[0]
    most_concentrated = latest_top.sort_values(
        ["partner_share_within_focal_domain", "component_count"], ascending=[False, False]
    ).iloc[0]

    p = doc.add_paragraph()
    p.add_run(
        "Figure 5 reframes exact two-field combinations from the perspective of selected anchor domains. Each panel shows how a focal domain distributes its exact two-field collaboration profile across partner domains in each manuscript period, with radial values expressed as within-domain shares so that changes in partner emphasis remain visible even as total counts grow."
    )

    p = doc.add_paragraph()
    p.add_run(
        f"Taken together, the spider profiles suggest that exact two-field collaboration in AI-and-diabetes research has shifted from a more visibly technical structure toward a more clinically anchored and translational one. Technical/AI partnerships remain important, but their relative share recedes in several focal domains, while clinical medicine, complications-focused work, device-linked endocrinology, and lifestyle or education-oriented collaborations become more prominent."
    )

    p = doc.add_paragraph()
    p.add_run(
        f"For Tech/AI, Clinical Med remained the dominant partner throughout the study window, accounting for "
        f"{profile_share(PERIODS[0], 'Technical_AI_Informatics', 'General_Clinical_Medicine') * 100:.1f}% "
        f"({profile_count(PERIODS[0], 'Technical_AI_Informatics', 'General_Clinical_Medicine'):,} of {profile_total(PERIODS[0], 'Technical_AI_Informatics'):,}) "
        f"of the exact two-field profile in {PERIODS[0]} and "
        f"{profile_share(PERIODS[-1], 'Technical_AI_Informatics', 'General_Clinical_Medicine') * 100:.1f}% "
        f"({profile_count(PERIODS[-1], 'Technical_AI_Informatics', 'General_Clinical_Medicine'):,} of {profile_total(PERIODS[-1], 'Technical_AI_Informatics'):,}) "
        f"in {PERIODS[-1]}. By contrast, direct Tech/AI pairing with Endocrino declined from "
        f"{profile_share(PERIODS[0], 'Technical_AI_Informatics', 'Endocrinology_Diabetes') * 100:.1f}% to "
        f"{profile_share(PERIODS[-1], 'Technical_AI_Informatics', 'Endocrinology_Diabetes') * 100:.1f}%, and pairing with Public Health fell from "
        f"{profile_share(PERIODS[0], 'Technical_AI_Informatics', 'Public_Health_Epidemiology') * 100:.1f}% to "
        f"{profile_share(PERIODS[-1], 'Technical_AI_Informatics', 'Public_Health_Epidemiology') * 100:.1f}%. Ophthalmology became a major applied bridge, peaking at "
        f"{profile_share('2022-2023', 'Technical_AI_Informatics', 'Ophthalmology_Vision') * 100:.1f}% in 2022-2023 before easing to "
        f"{profile_share(PERIODS[-1], 'Technical_AI_Informatics', 'Ophthalmology_Vision') * 100:.1f}% in {PERIODS[-1]}, consistent with the strong historical role of image-based diabetes applications. Smaller but meaningful late growth also appears in Behavioral/Psychological "
        f"({profile_share(PERIODS[0], 'Technical_AI_Informatics', 'Behavioral_Psychological') * 100:.1f}% to "
        f"{profile_share(PERIODS[-1], 'Technical_AI_Informatics', 'Behavioral_Psychological') * 100:.1f}%) and Pediatrics/Maternal Health "
        f"({profile_share(PERIODS[0], 'Technical_AI_Informatics', 'Pediatrics_Maternal_Health') * 100:.1f}% to "
        f"{profile_share(PERIODS[-1], 'Technical_AI_Informatics', 'Pediatrics_Maternal_Health') * 100:.1f}%), suggesting gradual expansion beyond core technical-clinical dyads into more patient-centered settings."
    )

    p = doc.add_paragraph()
    p.add_run(
        f"Endocrino became progressively more anchored to Clinical Med. The Clinical Med share rose from "
        f"{profile_share(PERIODS[0], 'Endocrinology_Diabetes', 'General_Clinical_Medicine') * 100:.1f}% "
        f"({profile_count(PERIODS[0], 'Endocrinology_Diabetes', 'General_Clinical_Medicine'):,} of {profile_total(PERIODS[0], 'Endocrinology_Diabetes'):,}) in {PERIODS[0]} to "
        f"{profile_share(PERIODS[-1], 'Endocrinology_Diabetes', 'General_Clinical_Medicine') * 100:.1f}% "
        f"({profile_count(PERIODS[-1], 'Endocrinology_Diabetes', 'General_Clinical_Medicine'):,} of {profile_total(PERIODS[-1], 'Endocrinology_Diabetes'):,}) in {PERIODS[-1]}, while its direct Tech/AI share fell from "
        f"{profile_share(PERIODS[0], 'Endocrinology_Diabetes', 'Technical_AI_Informatics') * 100:.1f}% to "
        f"{profile_share(PERIODS[-1], 'Endocrinology_Diabetes', 'Technical_AI_Informatics') * 100:.1f}%. Public Health remained present but secondary "
        f"({profile_share(PERIODS[0], 'Endocrinology_Diabetes', 'Public_Health_Epidemiology') * 100:.1f}% to "
        f"{profile_share(PERIODS[-1], 'Endocrinology_Diabetes', 'Public_Health_Epidemiology') * 100:.1f}%), whereas Industry/Device links grew from "
        f"{profile_share(PERIODS[0], 'Endocrinology_Diabetes', 'Industry_Digital_Health_Device') * 100:.1f}% to "
        f"{profile_share(PERIODS[-1], 'Endocrinology_Diabetes', 'Industry_Digital_Health_Device') * 100:.1f}%. This pattern suggests that endocrinology-focused AI work is becoming less defined by a simple Endocrino-Plus-Tech pairing and more embedded in broader clinical care and diabetes technology ecosystems."
    )

    p = doc.add_paragraph()
    p.add_run(
        f"Clinical Med shows the clearest redistribution of partner structure. In {PERIODS[0]}, its largest exact two-field partner was Tech/AI at "
        f"{profile_share(PERIODS[0], 'General_Clinical_Medicine', 'Technical_AI_Informatics') * 100:.1f}% "
        f"({profile_count(PERIODS[0], 'General_Clinical_Medicine', 'Technical_AI_Informatics'):,} of {profile_total(PERIODS[0], 'General_Clinical_Medicine'):,}), but by {PERIODS[-1]} the Tech/AI share had fallen to "
        f"{profile_share(PERIODS[-1], 'General_Clinical_Medicine', 'Technical_AI_Informatics') * 100:.1f}%. Over the same span, Complications rose from "
        f"{profile_share(PERIODS[0], 'General_Clinical_Medicine', 'Complications_Cardiometabolic_Nephrology_Neurology') * 100:.1f}% to "
        f"{profile_share(PERIODS[-1], 'General_Clinical_Medicine', 'Complications_Cardiometabolic_Nephrology_Neurology') * 100:.1f}%, overtaking every other partner in the latest period. Endocrino remained strikingly stable at "
        f"{profile_share(PERIODS[0], 'General_Clinical_Medicine', 'Endocrinology_Diabetes') * 100:.1f}% in the earliest period and "
        f"{profile_share(PERIODS[-1], 'General_Clinical_Medicine', 'Endocrinology_Diabetes') * 100:.1f}% in the latest, while Public Health fell from "
        f"{profile_share(PERIODS[0], 'General_Clinical_Medicine', 'Public_Health_Epidemiology') * 100:.1f}% to "
        f"{profile_share(PERIODS[-1], 'General_Clinical_Medicine', 'Public_Health_Epidemiology') * 100:.1f}%. Pediatrics/Maternal Health and Ophthalmology both grew as secondary partners, but the most important late shift is clearly toward complications and comorbidity-focused collaboration."
    )

    p = doc.add_paragraph()
    p.add_run(
        f"Public Health remained consistently anchored to Clinical Med, with that partner accounting for "
        f"{profile_share(PERIODS[0], 'Public_Health_Epidemiology', 'General_Clinical_Medicine') * 100:.1f}% "
        f"({profile_count(PERIODS[0], 'Public_Health_Epidemiology', 'General_Clinical_Medicine'):,} of {profile_total(PERIODS[0], 'Public_Health_Epidemiology'):,}) in {PERIODS[0]} and "
        f"{profile_share(PERIODS[-1], 'Public_Health_Epidemiology', 'General_Clinical_Medicine') * 100:.1f}% "
        f"({profile_count(PERIODS[-1], 'Public_Health_Epidemiology', 'General_Clinical_Medicine'):,} of {profile_total(PERIODS[-1], 'Public_Health_Epidemiology'):,}) in {PERIODS[-1]}. Tech/AI remained the second major partner, but its share declined from "
        f"{profile_share(PERIODS[0], 'Public_Health_Epidemiology', 'Technical_AI_Informatics') * 100:.1f}% to "
        f"{profile_share(PERIODS[-1], 'Public_Health_Epidemiology', 'Technical_AI_Informatics') * 100:.1f}%, while Endocrino remained meaningful but subordinate at "
        f"{profile_share(PERIODS[-1], 'Public_Health_Epidemiology', 'Endocrinology_Diabetes') * 100:.1f}% in the latest period. A notable late broadening appears in lifestyle and implementation-adjacent partnerships: Exercise rose from "
        f"{profile_share(PERIODS[0], 'Public_Health_Epidemiology', 'Exercise_Lifestyle') * 100:.1f}% to "
        f"{profile_share(PERIODS[-1], 'Public_Health_Epidemiology', 'Exercise_Lifestyle') * 100:.1f}%, Nutrition from "
        f"{profile_share(PERIODS[0], 'Public_Health_Epidemiology', 'Nutrition') * 100:.1f}% to "
        f"{profile_share(PERIODS[-1], 'Public_Health_Epidemiology', 'Nutrition') * 100:.1f}%, and Nursing/Diabetes Education from "
        f"{profile_share(PERIODS[0], 'Public_Health_Epidemiology', 'Nursing_Diabetes_Education') * 100:.1f}% to "
        f"{profile_share(PERIODS[-1], 'Public_Health_Epidemiology', 'Nursing_Diabetes_Education') * 100:.1f}%. By contrast, Industry/Device collaboration fell from "
        f"{profile_share(PERIODS[0], 'Public_Health_Epidemiology', 'Industry_Digital_Health_Device') * 100:.1f}% to "
        f"{profile_share(PERIODS[-1], 'Public_Health_Epidemiology', 'Industry_Digital_Health_Device') * 100:.1f}%, highlighting a growing difference between endocrinology-centered and public-health-centered two-field structures."
    )

    p = doc.add_paragraph()
    p.add_run(
        f"Comparing the four focal domains directly, the most diversified late-period partner profile is "
        f"{FIELD_SHORT_LABELS.get(most_diversified['focal_domain'], most_diversified['focal_domain'])}, because its largest partner accounts for only "
        f"{float(most_diversified['partner_share_within_focal_domain']) * 100:.1f}% of the exact two-field profile. The most concentrated late-period profile is "
        f"{FIELD_SHORT_LABELS.get(most_concentrated['focal_domain'], most_concentrated['focal_domain'])}, where the leading partner still accounts for "
        f"{float(most_concentrated['partner_share_within_focal_domain']) * 100:.1f}%. Across the four panels, the broader directional pattern is a relative de-emphasis of explicit Tech/AI dyads in Endocrino, Clinical Med, and Public Health, paired with stronger anchoring in clinical medicine, rising complication-focused clinical ties, and selective growth in device-linked or lifestyle-oriented partnerships. This pattern is consistent with a field that is becoming more clinically embedded and translational rather than remaining primarily organized around a stand-alone technical core."
    )
    add_figure(
        doc,
        assets["two_field_spider_profiles"],
        "Figure 5. Spider-chart profiles for exact two-field collaboration structure in four focal domains, with periods overlaid and radial values showing within-domain partner shares.",
        width=Inches(6.3),
    )

    three_field = data["three_field_timelapse"].copy()
    three_field["period"] = pd.Categorical(three_field["period"], categories=PERIODS, ordered=True)
    top_by_period = (
        three_field.sort_values(["period", "component_count", "combination_label"], ascending=[True, False, True])
        .groupby("period", as_index=False, observed=False)
        .head(1)
        .reset_index(drop=True)
    )
    combo_period_stats = (
        three_field[three_field["component_count"] > 0]
        .groupby("combination_label", as_index=False)
        .agg(
            active_periods=("period", "nunique"),
            cumulative_count=("component_count", "sum"),
            first_period_seen=("first_period_seen", "first"),
            last_period_seen=("last_period_seen", "first"),
        )
    )
    stable_core = combo_period_stats[combo_period_stats["active_periods"] == len(PERIODS)].sort_values(
        ["cumulative_count", "combination_label"], ascending=[False, True]
    )
    early_counts = (
        three_field[three_field["period"] == PERIODS[0]][["combination_label", "component_count"]]
        .rename(columns={"component_count": "early_count"})
    )
    late_counts = (
        three_field[three_field["period"] == PERIODS[-1]][["combination_label", "component_count"]]
        .rename(columns={"component_count": "late_count"})
    )
    growth = early_counts.merge(late_counts, on="combination_label", how="outer").fillna(0)
    growth["growth"] = growth["late_count"] - growth["early_count"]
    growth = growth.sort_values(["growth", "late_count", "combination_label"], ascending=[False, False, True])
    late_emerging = three_field[
        (three_field["component_count"] > 0) & (three_field["first_period_seen"] != PERIODS[0])
    ][["combination_label", "short_combination_label", "first_period_seen", "period", "component_count"]]
    late_emerging = (
        late_emerging.sort_values(
            ["first_period_seen", "component_count", "combination_label"],
            ascending=[True, False, True],
        )
        .drop_duplicates(subset=["combination_label"])
        .sort_values(["component_count", "combination_label"], ascending=[False, True])
    )
    union_labels = three_field["combination_label"].drop_duplicates().astype(str)
    clinical_union_share = (
        float(union_labels.str.contains("General_Clinical_Medicine", regex=False).mean()) if len(union_labels) else 0.0
    )

    doc.add_heading("4D. Top Exact Three-Field Combinations", level=2)
    p = doc.add_paragraph()
    p.add_run(
        "Figure 6 converts the exact three-field layer into a period-by-period timelapse. Rather than listing triads as a static rank table, it shows which three-domain combinations persist, intensify, or newly enter the visible collaboration core as the field matures."
    )
    if not stable_core.empty:
        stable_text = "; ".join(
            short_combination_label(row.combination_label) for row in stable_core.head(3).itertuples(index=False)
        )
        p = doc.add_paragraph()
        p.add_run(
            f"The most stable core triads are {stable_text}. These combinations remain visible across all six manuscript periods, indicating that the enduring backbone of three-field collaboration is built around recurring clinical, technical, endocrinology, and public-health interfaces rather than around a constantly changing set of domain triplets."
        )
    p = doc.add_paragraph()
    p.add_run(
        f"The period leaders do change, but they do so within a narrow family of clinically anchored structures. The top triad in {PERIODS[0]} was "
        f"{short_combination_label(top_by_period.iloc[0]['combination_label'])} "
        f"({int(top_by_period.iloc[0]['component_count']):,} components), whereas the top triad in {PERIODS[-1]} was "
        f"{short_combination_label(top_by_period.iloc[-1]['combination_label'])} "
        f"({int(top_by_period.iloc[-1]['component_count']):,} components). This means the three-field layer evolves less by abandoning earlier anchors and more by reweighting which clinically centered bridge becomes most prominent at a given stage."
    )
    top_growth = growth.head(3)
    if not top_growth.empty:
        growth_text = "; ".join(
            f"{short_combination_label(row.combination_label)} ({int(row.early_count):,} to {int(row.late_count):,})"
            for row in top_growth.itertuples(index=False)
        )
        p = doc.add_paragraph()
        p.add_run(
            f"The strongest intensification is seen in {growth_text}. In practical terms, the largest late gains are concentrated in triads that keep Clinical Med at the center while adding either Tech/AI, Endocrino, or Complications, reinforcing the sense that three-field collaboration is becoming more translational and complications-aware rather than simply more methodologically technical."
        )
    if not late_emerging.empty:
        emerging_text = "; ".join(
            f"{short_combination_label(row.combination_label)} (first visible in {row.first_period_seen})"
            for row in late_emerging.head(3).itertuples(index=False)
        )
        p = doc.add_paragraph()
        p.add_run(
            f"Later-emerging triads include {emerging_text}. These combinations suggest that the recent broadening of the field is not random; it expands outward from the established clinical core into newer bridges involving complications, pediatrics, nursing or device-linked care contexts."
        )
    p = doc.add_paragraph()
    if clinical_union_share >= 0.99:
        p.add_run(
            "Notably, every triad in the top-12 display union includes Clinical Med. This makes the three-field layer even more clinically anchored than the two-field layer and suggests that, once collaboration moves beyond simple dyads, general clinical medicine becomes the organizing platform that connects technical, specialty, public-health, and complications-focused work."
        )
    else:
        p.add_run(
            f"More broadly, {clinical_union_share * 100:.1f}% of the top-12 display union includes Clinical Med. This indicates that the exact three-field layer is still overwhelmingly organized around clinically anchored bridge structures rather than around isolated technical or specialty clusters."
        )
    add_figure(
        doc,
        assets["three_field_timelapse_preview"],
        "Figure 6. Snapshot grid from the interactive exact three-field bubble-race supplement, showing how the leading triads change across manuscript periods using absolute connected-component counts.",
        width=Inches(6.35),
    )
    p = doc.add_paragraph()
    p.add_run("Interactive supplement. ").bold = True
    p.add_run(
        f"The standalone HTML timelapse for this section is saved at {assets['three_field_timelapse_html']}."
    )

    def add_combo_subsection(size_label: str, title: str, table_number: int, prose_rank: int = 3) -> None:
        subset = combinations[combinations["combination_size"] == size_label].copy()
        if subset.empty:
            return
        doc.add_heading(title, level=2)
        top_rows = (
            subset.sort_values(["period", "rank_within_size", "component_count"], ascending=[True, True, False])
            .groupby("period", as_index=False)
            .head(prose_rank)
            .reset_index(drop=True)
        )
        early_top = top_rows[top_rows["period"] == PERIODS[0]].head(1)
        late_top = top_rows[top_rows["period"] == PERIODS[-1]].head(1)
        if not early_top.empty and not late_top.empty:
            p = doc.add_paragraph()
            p.add_run(
                f"In the {title.lower()} layer, the dominant combination in {PERIODS[0]} was "
                f"{short_combination_label(early_top.iloc[0]['combination_label'])} ({int(early_top.iloc[0]['component_count']):,} components; "
                f"{early_top.iloc[0]['component_share_pct']:.1f}%), whereas the top combination in {PERIODS[-1]} was "
                f"{short_combination_label(late_top.iloc[0]['combination_label'])} ({int(late_top.iloc[0]['component_count']):,} components; "
                f"{late_top.iloc[0]['component_share_pct']:.1f}%)."
            )
        add_table_caption(doc, f"Table {table_number}. Top exact {size_label if size_label != '4+' else '4+'}-field component combinations by period.")
        table = doc.add_table(rows=1, cols=5)
        headers = ["Period", "Rank", "Combination", "Components", "Component share"]
        for idx, label in enumerate(headers):
            table.rows[0].cells[idx].text = label
        for row in top_rows.itertuples(index=False):
            cells = table.add_row().cells
            cells[0].text = str(row.period)
            cells[1].text = f"{int(row.rank_within_size)}"
            cells[2].text = short_combination_label(row.combination_label)
            cells[3].text = f"{int(row.component_count):,}"
            cells[4].text = f"{row.component_share_pct:.1f}%"
        format_table(
            table,
            widths=[Inches(1.0), Inches(0.55), Inches(3.35), Inches(0.75), Inches(0.9)],
            font_size=8.1,
        )
        add_spacer(doc, 4)

def add_centrality_section(doc: Document, data: dict[str, object], assets: dict[str, Path]) -> None:
    centrality = data["centrality"]
    prominent_transitions = data["prominent_transitions"].copy()
    doc.add_heading("5. Central Institutions and the Collaboration Core", level=1)
    p = doc.add_paragraph()
    p.add_run(
        "The centrality outputs indicate that the collaboration core is no longer confined to a narrow diabetology-only "
        "center. The earliest period is anchored primarily in European clinical diabetology and endocrinology settings, "
        "whereas the post-2020 periods show a more mixed translational core spanning ophthalmology, public health, data "
        "science, computational medicine, and major university-affiliated biomedical institutes."
    )
    p = doc.add_paragraph()
    p.add_run(
        "Representative top institutions by degree and betweenness confirm this shift. Singapore-based eye-research and "
        "medical-school ecosystems, Harvard-linked biomedical environments, the Broad Institute, Stanford-affiliated groups, "
        "Tsinghua Medicine, and major European translational centers all appear as key hubs or bridges in later periods. "
        "The field’s coordination architecture therefore looks increasingly mixed rather than purely specialty-clinical."
    )
    latest_pair = prominent_transitions[
        (prominent_transitions["period_from"] == PERIODS[-2])
        & (prominent_transitions["period_to"] == PERIODS[-1])
    ].copy()
    latest_nonzero = latest_pair[latest_pair["transition_count"] > 0].copy()
    if not latest_nonzero.empty:
        top_latest = latest_nonzero[
            ~((latest_nonzero["state_from"] == "Absent") & (latest_nonzero["state_to"] == "Absent"))
        ].sort_values(
            ["transition_count", "state_from", "state_to"], ascending=[False, True, True]
        ).iloc[0]
        upward_latest = latest_nonzero[
            ((latest_nonzero["state_from"] == "Peripheral") & (latest_nonzero["state_to"] == "Semi-Peripheral"))
            | ((latest_nonzero["state_from"] == "Semi-Peripheral") & (latest_nonzero["state_to"] == "Core"))
        ]["transition_count"].sum()
        entry_latest = latest_nonzero[latest_nonzero["state_from"] == "Absent"]["transition_count"].sum()
        exit_latest = latest_nonzero[latest_nonzero["state_to"] == "Absent"]["transition_count"].sum()
        p = doc.add_paragraph()
        p.add_run(
            f"To make role movement easier to interpret, Figure 7 summarizes adjacent-period transitions within a deterministic prominent-institution subset rather than plotting dozens of individual trajectories. In the latest transition ({PERIODS[-2]} to {PERIODS[-1]}), the single most common pattern was "
            f"{top_latest['state_from']} -> {top_latest['state_to']} ({int(top_latest['transition_count']):,} institutions). "
            f"Upward movement from Low -> Mid or Mid -> High centrality still accounted for {int(upward_latest):,} prominent institutions, while entries and exits remained visible at {int(entry_latest):,} and {int(exit_latest):,}, respectively."
        )

    add_table_caption(doc, "Table 7. Representative top institutions by degree and betweenness centrality.")
    table = doc.add_table(rows=1, cols=5)
    headers = ["Period", "Top degree institution", "Degree score", "Top betweenness institution", "Betweenness"]
    for idx, label in enumerate(headers):
        table.rows[0].cells[idx].text = label
    for period in ["1988_2015", "2016_2019", "2020_2021", "2022_2023", "2024_2024", "2025_2025"]:
        row = centrality[period]
        cells = table.add_row().cells
        cells[0].text = period.replace("_", "-")
        cells[1].text = short_label(row["degree_node"])
        cells[2].text = f"{row['degree_score']:.6f}"
        cells[3].text = short_label(row["betweenness_node"])
        cells[4].text = f"{row['betweenness_score']:.6f}"
    format_table(table, widths=[Inches(0.95), Inches(2.25), Inches(0.75), Inches(2.25), Inches(0.75)], font_size=8.1)
    add_spacer(doc, 6)

    add_figure(
        doc,
        assets["prominent_transition_heatmap"],
        "Figure 7. Prominent-institution role-transition heatmap across adjacent manuscript periods, with rows showing previous-period role and columns showing next-period role.",
        width=Inches(6.1),
    )


def add_geography_section(doc: Document, data: dict[str, object], assets: dict[str, Path]) -> None:
    top_regions = data["top_regions"]
    latest_regions = data["latest_regions"]
    who_pairwise = data["who_pairwise"].copy()
    country_display = data["country_display"].copy()
    doc.add_heading("6. Geographic Diffusion", level=1)
    p = doc.add_paragraph()
    p.add_run(
        "WHO-region summaries show substantial international broadening, but not uniform global balance. PAHO led the "
        "first three periods, after which WPRO became the dominant publication-producing region. The shift is especially "
        "visible in 2022-2023 and 2025-2025, when WPRO carried both the largest publication counts and the largest "
        "institutional footprints."
    )
    p = doc.add_paragraph()
    p.add_run(
        "The regional transition matters because it suggests that the recent expansion of AI-and-diabetes collaboration "
        "is being driven increasingly by Western Pacific institutional ecosystems rather than remaining concentrated "
        "primarily in North America and Europe. Even so, Europe retains very broad country representation, while PAHO "
        "continues to contribute substantial publication volume in every period."
    )

    add_table_caption(doc, "Table 8. Leading WHO region by publication count in each manuscript period.")
    table = doc.add_table(rows=1, cols=5)
    headers = ["Period", "Leading region", "Publications", "Countries", "Institutions"]
    for idx, label in enumerate(headers):
        table.rows[0].cells[idx].text = label
    for row in top_regions.itertuples(index=False):
        cells = table.add_row().cells
        cells[0].text = row.period
        cells[1].text = row.who_region
        cells[2].text = f"{int(row.publication_count):,}"
        cells[3].text = f"{int(row.country_count):,}"
        cells[4].text = f"{int(row.institution_count):,}"
    format_table(table, widths=[Inches(1.0), Inches(1.2), Inches(1.0), Inches(0.95), Inches(1.1)], font_size=8.7)

    add_spacer(doc, 4)
    add_table_caption(doc, "Appendix Table A1. WHO-region ranking in the latest period (2025-2025).")
    table = doc.add_table(rows=1, cols=5)
    for idx, label in enumerate(headers):
        table.rows[0].cells[idx].text = label
    for row in latest_regions.itertuples(index=False):
        cells = table.add_row().cells
        cells[0].text = row.period
        cells[1].text = row.who_region
        cells[2].text = f"{int(row.publication_count):,}"
        cells[3].text = f"{int(row.country_count):,}"
        cells[4].text = f"{int(row.institution_count):,}"
    format_table(table, widths=[Inches(1.0), Inches(1.2), Inches(1.0), Inches(0.95), Inches(1.1)], font_size=8.5)

    cross_regions = who_pairwise[who_pairwise["who_region_a"] != who_pairwise["who_region_b"]].copy()
    if not cross_regions.empty:
        early_region = cross_regions[cross_regions["period"] == PERIODS[0]].sort_values(
            ["publication_pair_count", "who_region_a", "who_region_b"], ascending=[False, True, True]
        ).iloc[0]
        late_region = cross_regions[cross_regions["period"] == PERIODS[-1]].sort_values(
            ["publication_pair_count", "who_region_a", "who_region_b"], ascending=[False, True, True]
        ).iloc[0]
        p = doc.add_paragraph()
        p.add_run(
            f"A second geography layer emerges when collaboration is counted directly between regions within individual papers. The dominant cross-region bridge in {PERIODS[0]} was "
            f"{early_region['who_region_a']} + {early_region['who_region_b']} ({int(early_region['publication_pair_count']):,} publication-level co-occurrences), and the same bridge remained dominant in {PERIODS[-1]} at "
            f"{int(late_region['publication_pair_count']):,}. This suggests that the global spread of the field has grown around a stable Euro-American backbone rather than through a complete reordering of regional linkages."
        )
        later_top = cross_regions[cross_regions["period"].isin(PERIODS[-3:])].sort_values(
            ["publication_pair_count", "period"], ascending=[False, True]
        ).head(4)
        bridges_text = "; ".join(
            f"{row.who_region_a} + {row.who_region_b} in {row.period} ({int(row.publication_pair_count):,})"
            for row in later_top.itertuples(index=False)
        )
        p = doc.add_paragraph()
        p.add_run(
            f"Later-period geography broadens beyond that core. The strongest recurring bridges after 2020 include {bridges_text}. In practical terms, Western Pacific and South-East Asia become much more visible in the collaborative structure, but they do so by attaching to an already well-established inter-regional backbone rather than displacing it."
        )

    add_figure(
        doc,
        assets["who_region_collaboration_heatmap"],
        "Figure 8. WHO-region publication-level collaboration heatmap by manuscript period; off-diagonal cells indicate cross-region co-occurrence within papers and diagonal cells indicate multi-country within-region collaboration.",
        width=Inches(6.2),
    )

    if not country_display.empty:
        late_country = country_display[
            (country_display["period"] == PERIODS[-1]) & (country_display["country_a"] != country_display["country_b"])
        ].sort_values(
            ["publication_pair_count", "country_a", "country_b"], ascending=[False, True, True]
        ).head(5)
        country_text = "; ".join(
            f"{row.country_a_display} + {row.country_b_display} ({int(row.publication_pair_count):,})"
            for row in late_country.itertuples(index=False)
        )
        p = doc.add_paragraph()
        p.add_run(
            f"Country-level collaboration is much more diffuse than the WHO-region picture, so Figure 9 uses a thresholded sparse heatmap that retains only country pairs with at least three publication-level co-occurrences in a period. In the latest period, the most visible country-pair anchors were {country_text}. The resulting pattern suggests that global expansion is real, but much of it still passes through a limited set of recurrent transnational corridors rather than through uniformly dense collaboration among all active countries."
        )

    add_figure(
        doc,
        assets["country_collaboration_heatmap"],
        "Figure 9. Thresholded country-level publication co-occurrence heatmap by manuscript period; panels retain country pairs with at least three publication-level co-occurrences in that period.",
        width=Inches(6.25),
    )


def add_funding_section(doc: Document, data: dict[str, object], assets: dict[str, Path]) -> None:
    funding_summary = data["funding_summary"]
    funding_region_leaders = data["funding_region_leaders"]
    funding_domain_profiles = data["funding_domain_profiles"].copy()
    doc.add_page_break()
    doc.add_heading("7. Funding-Stratified Analysis", level=1)

    row_us = funding_summary.iloc[0]
    row_intl = funding_summary.iloc[1]
    row_nogrant = funding_summary.iloc[2]
    p = doc.add_paragraph()
    p.add_run(
        f"The funding-stratified outputs show that the largest share of the corpus falls into the no-grant-listed category "
        f"({int(row_nogrant.publication_count):,} publications; {int(row_nogrant.institution_mentions):,} institution mentions), "
        f"followed by US federally funded studies ({int(row_us.publication_count):,} publications) and non-US/internationally funded "
        f"studies ({int(row_intl.publication_count):,} publications). Structural contrasts are still informative despite the very different "
        "volume scales."
    )
    p = doc.add_paragraph()
    p.add_run(
        f"US federally funded networks show the most moderate mean density profile ({row_us.density:.4f}) but sustained component mixing, "
        f"with a mean three-or-more-field ratio of {pct(row_us.three_or_more_field_ratio)}. Non-US/internationally funded networks are "
        f"smaller in absolute corpus size but have the highest mean density ({row_intl.density:.4f}), highest mean degree "
        f"({row_intl.avg_degree:.2f}), and largest mean LCC share ({row_intl.lcc_share_pct:.2f}%). The no-grant-listed group dominates "
        "raw publication volume yet is comparatively less interdisciplinary on average, suggesting that scale alone does not guarantee "
        "the same degree of structural concentration or domain mixing."
    )

    add_table_caption(doc, "Table 9. Funding-category comparison summary across completed manuscript periods.")
    table = doc.add_table(rows=1, cols=7)
    headers = [
        "Funding category",
        "Publications",
        "Institution mentions",
        "Mean density",
        "Mean degree",
        "Mean 3+ field share",
        "Mean LCC share",
    ]
    for idx, label in enumerate(headers):
        table.rows[0].cells[idx].text = label
    for _, row in funding_summary.iterrows():
        cells = table.add_row().cells
        cells[0].text = str(row["Funding category"])
        cells[1].text = f"{int(row['publication_count']):,}"
        cells[2].text = f"{int(row['institution_mentions']):,}"
        cells[3].text = f"{row['density']:.4f}"
        cells[4].text = f"{row['avg_degree']:.2f}"
        cells[5].text = pct(row["three_or_more_field_ratio"])
        cells[6].text = f"{row['lcc_share_pct']:.2f}%"
    format_table(
        table,
        widths=[Inches(1.55), Inches(0.9), Inches(1.05), Inches(0.8), Inches(0.8), Inches(1.0), Inches(0.85)],
        font_size=8.2,
    )
    add_spacer(doc, 6)

    add_figure(
        doc,
        assets["funding_role_flow"],
        "Figure 10. Funding-stratified role-flow comparison aggregated across adjacent-period transitions.",
        width=Inches(6.15),
    )

    if not funding_domain_profiles.empty:
        latest_profiles = funding_domain_profiles[funding_domain_profiles["period"] == PERIODS[-1]].copy()

        def top_partner_text(focal_domain: str, funding_group: str) -> tuple[str, float]:
            subset = latest_profiles[
                (latest_profiles["focal_domain"] == focal_domain)
                & (latest_profiles["funding_group"] == funding_group)
            ].sort_values(
                ["partner_share_within_focal_domain", "component_count", "partner_domain"],
                ascending=[False, False, True],
            )
            if subset.empty:
                return "None", 0.0
            row = subset.iloc[0]
            return short_field_name(str(row["partner_domain"])), float(row["partner_share_within_focal_domain"])

        clinical_funded_partner, clinical_funded_share = top_partner_text("General_Clinical_Medicine", "FUNDED")
        clinical_nogrant_partner, clinical_nogrant_share = top_partner_text("General_Clinical_Medicine", "NO_GRANT_LISTED")
        tech_funded_partner, tech_funded_share = top_partner_text("Technical_AI_Informatics", "FUNDED")
        tech_nogrant_partner, tech_nogrant_share = top_partner_text("Technical_AI_Informatics", "NO_GRANT_LISTED")
        p = doc.add_paragraph()
        p.add_run(
            "Funding status also changes the partner structure of exact two-field collaboration. Figure 11 presents side-by-side funded and no-grant partner profiles for the same four focal domains used in Section 4C, so each domain can be compared directly across the left-right panel pair while periods remain overlaid within each funding-status chart."
        )
        p = doc.add_paragraph()
        p.add_run(
            f"In the latest period, Clinical Med remained the main anchor in both funding groups, but the funded vs no-grant contrast is clearer in how other partner shares are distributed around that center. For Clinical Med itself, the top funded partner was {clinical_funded_partner} "
            f"({clinical_funded_share * 100:.1f}%), whereas the top no-grant-listed partner was {clinical_nogrant_partner} "
            f"({clinical_nogrant_share * 100:.1f}%). For Tech/AI, the top funded partner was {tech_funded_partner} "
            f"({tech_funded_share * 100:.1f}%), compared with {tech_nogrant_partner} ({tech_nogrant_share * 100:.1f}%) in the no-grant group."
        )
        funded_latest = latest_profiles[latest_profiles["funding_group"] == "FUNDED"].copy()
        nogrant_latest = latest_profiles[latest_profiles["funding_group"] == "NO_GRANT_LISTED"].copy()
        merged_profiles = funded_latest.merge(
            nogrant_latest,
            on=["period", "focal_domain", "partner_domain"],
            suffixes=("_funded", "_nogrant"),
        )
        merged_profiles["share_gap"] = (
            merged_profiles["partner_share_within_focal_domain_funded"]
            - merged_profiles["partner_share_within_focal_domain_nogrant"]
        ).abs()
        biggest_gap = merged_profiles.sort_values(
            ["share_gap", "focal_domain", "partner_domain"], ascending=[False, True, True]
        ).head(4)
        if not biggest_gap.empty:
            gap_text = "; ".join(
                f"{short_field_name(row.focal_domain)} with {short_field_name(row.partner_domain)} "
                f"({row.share_gap * 100:.1f} percentage-point gap)"
                for row in biggest_gap.itertuples(index=False)
            )
            p = doc.add_paragraph()
            p.add_run(
                f"The largest latest-period funded-versus-no-grant divergences appear in {gap_text}. Across the panels, funded profiles tend to preserve stronger ties to technical, device, and complications-linked partners, whereas no-grant-listed profiles more often collapse toward a smaller set of clinically dominant pairings."
            )

        add_figure(
            doc,
            assets["funding_exact_two_field_spider_profiles"],
            "Figure 11. Paired funded and no-grant exact two-field partner profiles for selected focal domains, with periods overlaid within each funding-status panel.",
            width=Inches(6.2),
        )

    lead_rows = (
        funding_region_leaders.sort_values(["funding_category", "period"])
        .groupby("funding_category", as_index=False)
        .tail(1)
    )
    add_table_caption(doc, "Appendix Table A2. Leading WHO region in the latest period by funding category.")
    table = doc.add_table(rows=1, cols=5)
    headers = ["Funding category", "Latest period", "Leading region", "Publications", "Institutions"]
    for idx, label in enumerate(headers):
        table.rows[0].cells[idx].text = label
    for row in lead_rows.itertuples(index=False):
        cells = table.add_row().cells
        cells[0].text = FUNDING_LABELS[row.funding_category]
        cells[1].text = row.period
        cells[2].text = row.who_region
        cells[3].text = f"{int(row.publication_count):,}"
        cells[4].text = f"{int(row.institution_count):,}"
    format_table(table, widths=[Inches(1.65), Inches(1.0), Inches(1.15), Inches(0.95), Inches(1.1)], font_size=8.4)


def add_synthesis(doc: Document, data: dict[str, object]) -> None:
    merged = data["merged"]
    doc.add_heading("Closing Synthesis", level=1)
    p = doc.add_paragraph()
    p.add_run(
        f"Taken together, the completed canonical outputs portray a field that has moved decisively beyond its earliest "
        f"siloed institutional configuration. Publication volume, institution mentions, and node counts all increased sharply, "
        f"and the mean number of distinct key fields per component roughly doubled from {merged.iloc[0].mean_distinct_key_fields_per_component:.2f} "
        f"to {merged.iloc[-1].mean_distinct_key_fields_per_component:.2f}. At the same time, maturation has not followed a simple linear path. "
        "The field remains fragmented in component terms, newcomer entry vastly outpaces the size of the returning core, and one of the most dramatic "
        "mid-period structural surges appears to reflect episodic mega-collaboration rather than uniform densification. The most defensible reading, "
        "therefore, is that AI-and-diabetes research is undergoing real institutional consolidation and interdisciplinary broadening, but that this "
        "consolidation coexists with substantial fragmentation and recurring dependence on large collaboration episodes that temporarily reshape the visible network."
    )


def build_report() -> Path:
    assets = ensure_report_assets()
    data = load_data()

    doc = Document(TEMPLATE)
    clear_document_body(doc)
    update_template_running_text(doc)
    section = doc.sections[0]
    section.top_margin = Inches(0.75)
    section.bottom_margin = Inches(0.7)

    add_front_matter(doc, data)
    add_results_overview(doc, data)
    add_corpus_growth_section(doc, data, assets)
    add_network_growth_section(doc, data)
    add_role_flow_section(doc, data, assets)
    add_interdisciplinarity_section(doc, data, assets)
    add_centrality_section(doc, data, assets)
    add_geography_section(doc, data, assets)
    add_funding_section(doc, data, assets)
    add_synthesis(doc, data)
    doc.add_page_break()
    add_methods_section(doc, data)

    doc.save(OUTPUT)
    return OUTPUT


if __name__ == "__main__":
    out = build_report()
    print(out)
