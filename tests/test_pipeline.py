import json
from pathlib import Path

import networkx as nx
import pandas as pd

from ai_diabetology import pipeline as pipeline_module
from ai_diabetology.pipeline import _load_all_raw_records
from ai_diabetology.pipeline import run_complete_analysis, run_pipeline


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row))
            handle.write("\n")


def test_load_all_raw_records_supports_absolute_glob(tmp_path: Path) -> None:
    raw_dir = tmp_path / "data" / "raw"
    file_path = raw_dir / "pubmed_records_test.jsonl"
    _write_jsonl(file_path, [{"PMID": "1"}, {"PMID": "2"}])

    absolute_pattern = str(raw_dir / "pubmed_records_*.jsonl")
    rows = _load_all_raw_records(absolute_pattern, project_root=tmp_path)

    assert len(rows) == 2


def test_run_pipeline_enforces_study_year_ceiling(tmp_path: Path) -> None:
    raw_dir = tmp_path / "data" / "raw"
    output_dir = tmp_path / "outputs" / "tables"
    networks_dir = tmp_path / "outputs" / "networks"
    html_dir = tmp_path / "outputs" / "networks_html"
    processed_dir = tmp_path / "data" / "processed"
    raw_file = raw_dir / "pubmed_records_test.jsonl"

    records = [
        {
            "PMID": "100",
            "TI": "In range",
            "AB": "Artificial intelligence for diabetes care and prediction.",
            "DP": "2025",
            "AD": ["Department of Endocrinology, University A, United States."],
            "GR": ["R01 DK000001/DK/NIDDK NIH HHS/United States"],
        },
        {
            "PMID": "200",
            "TI": "Out of range",
            "AB": "Artificial intelligence for diabetes care.",
            "DP": "2026",
            "AD": ["Department of Medicine, University B, United States."],
        },
        {
            "PMID": "300",
            "TI": "False positive engineering record",
            "AB": "Artificial intelligence workflow for dental imaging.",
            "DP": "2025",
            "AD": ["School of Engineering, University C, United States."],
        },
    ]
    _write_jsonl(raw_file, records)

    protocol = {
        "study": {
            "manuscript_period_start": 1946,
            "manuscript_period_end": 2025,
        },
        "queries": [{"id": "q1", "query": "dummy"}],
        "temporal_segmentation": {
            "mode": "fixed",
            "fixed_periods": [
                {"label": "2024-2025", "start_year": 2024, "end_year": 2025},
            ],
        },
        "preprocessing": {
            "remove_punctuation": True,
            "institution_keyword_hints": ["university", "school", "department"],
        },
        "screening": {
            "enabled": True,
            "include_terms": ["diabetes", "diabetic", "diabetology"],
            "exclude_terms": [],
        },
        "classification": {
            "fallback_label": "Other",
            "fallback_color": "#bdbdbd",
            "categories": [
                {
                    "label": "Technical_AI_Informatics",
                    "keywords": ["engineering", "computer science"],
                    "color": "#1d4ed8",
                },
                {
                    "label": "Endocrinology_Diabetes",
                    "keywords": ["endocrinology", "diabetes center"],
                    "color": "#dc2626",
                },
                {
                    "label": "General_Clinical_Medicine",
                    "keywords": ["medical", "medicine", "hospital"],
                    "color": "#0f766e",
                },
            ],
        },
        "outputs": {
            "publications_table": str(processed_dir / "publications.parquet"),
            "publication_summary": str(output_dir / "publication_counts.csv"),
            "period_definitions": str(output_dir / "period_definitions.csv"),
            "global_metrics": str(output_dir / "global.csv"),
            "core_newcomer_metrics": str(output_dir / "core.csv"),
            "cluster_metrics": str(output_dir / "cluster.csv"),
            "region_summary": str(output_dir / "region.csv"),
            "centrality_dir": str(output_dir / "centrality"),
            "graph_dir": str(networks_dir),
            "graph_html_dir": str(html_dir),
        },
        "visualization": {"export_html": False},
    }
    protocol_file = tmp_path / "config.yaml"
    protocol_file.write_text(json.dumps(protocol), encoding="utf-8")

    summary = run_pipeline(
        protocol_path=protocol_file,
        raw_glob=str(raw_file),
        project_root=tmp_path,
        clean_output_dirs=True,
    )

    assert summary["raw_records"] == 3
    assert summary["publications_after_preprocessing"] == 1

    publications_df = pd.read_parquet(processed_dir / "publications.parquet")
    assert len(publications_df) == 1
    institutions_cell = str(publications_df.iloc[0]["institutions"])
    assert "Department of Endocrinology, University A, United States." in institutions_cell
    assert publications_df.iloc[0]["funding_category"] == "US_FEDERAL_FUNDED"
    assert bool(publications_df.iloc[0]["has_grant_support"])

    funding_global = tmp_path / "outputs" / "tables" / "funding_global_network_metrics.csv"
    funding_core = tmp_path / "outputs" / "tables" / "funding_core_newcomer_metrics.csv"
    funding_transition = tmp_path / "outputs" / "tables" / "funding_role_transition_counts.csv"
    period_definitions = tmp_path / "outputs" / "tables" / "period_definitions.csv"
    base_transition = tmp_path / "outputs" / "tables" / "role_transition_counts.csv"
    base_comparison = tmp_path / "outputs" / "tables" / "structural_comparison_summary.csv"
    assert funding_global.exists()
    assert funding_core.exists()
    assert funding_transition.exists()
    assert period_definitions.exists()
    assert base_transition.exists()
    assert base_comparison.exists()


def test_run_pipeline_uses_llm_classifications_and_resets_outputs(tmp_path: Path) -> None:
    raw_dir = tmp_path / "data" / "raw"
    output_dir = tmp_path / "outputs" / "tables"
    networks_dir = tmp_path / "outputs" / "networks"
    html_dir = tmp_path / "outputs" / "networks_html"
    processed_dir = tmp_path / "data" / "processed"
    llm_dir = tmp_path / "data" / "llm" / "results"
    raw_file = raw_dir / "pubmed_records_test.jsonl"

    records = [
        {
            "PMID": "100",
            "TI": "In range",
            "AB": "Artificial intelligence for diabetes care and prediction.",
            "DP": "2025",
            "AD": [
                "Department of Medicine, University A, United States.",
                "Department of Endocrinology, University B, United States.",
            ],
        },
    ]
    _write_jsonl(raw_file, records)

    stale_table = tmp_path / "outputs" / "tables" / "stale.csv"
    stale_figure = tmp_path / "outputs" / "figures" / "flow_options" / "stale.html"
    stale_table.parent.mkdir(parents=True, exist_ok=True)
    stale_figure.parent.mkdir(parents=True, exist_ok=True)
    stale_table.write_text("old", encoding="utf-8")
    stale_figure.write_text("old", encoding="utf-8")

    llm_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "affiliation_text": "Department of Medicine, University A, United States.",
                "label": "Technical_AI_Informatics",
                "classified_at": "2026-05-22T00:00:00Z",
            },
            {
                "affiliation_text": "Department of Endocrinology, University B, United States.",
                "label": "Endocrinology_Diabetes",
                "classified_at": "2026-05-22T00:00:01Z",
            },
        ]
    ).to_parquet(llm_dir / "affiliation_classifications.parquet", index=False)

    protocol = {
        "study": {
            "manuscript_period_start": 1946,
            "manuscript_period_end": 2025,
        },
        "queries": [{"id": "q1", "query": "dummy"}],
        "temporal_segmentation": {
            "mode": "fixed",
            "fixed_periods": [
                {"label": "2025-2025", "start_year": 2025, "end_year": 2025},
            ],
        },
        "preprocessing": {
            "remove_punctuation": True,
            "institution_keyword_hints": ["university", "school", "department"],
        },
        "screening": {
            "enabled": True,
            "include_terms": ["diabetes", "diabetic", "diabetology"],
            "exclude_terms": [],
        },
        "analysis": {
            "classification_source": "llm",
            "llm_classifications_parquet": str(llm_dir / "affiliation_classifications.parquet"),
        },
        "classification": {
            "fallback_label": "Other",
            "fallback_color": "#bdbdbd",
            "categories": [
                {
                    "label": "Technical_AI_Informatics",
                    "keywords": ["engineering", "computer science"],
                    "color": "#1d4ed8",
                },
                {
                    "label": "Endocrinology_Diabetes",
                    "keywords": ["endocrinology", "diabetes center"],
                    "color": "#dc2626",
                },
                {
                    "label": "General_Clinical_Medicine",
                    "keywords": ["medical", "medicine", "hospital"],
                    "color": "#0f766e",
                },
            ],
        },
        "outputs": {
            "publications_table": str(processed_dir / "publications.parquet"),
            "publication_summary": str(output_dir / "publication_counts.csv"),
            "period_definitions": str(output_dir / "period_definitions.csv"),
            "global_metrics": str(output_dir / "global.csv"),
            "core_newcomer_metrics": str(output_dir / "core.csv"),
            "cluster_metrics": str(output_dir / "cluster.csv"),
            "region_summary": str(output_dir / "region.csv"),
            "centrality_dir": str(output_dir / "centrality"),
            "graph_dir": str(networks_dir),
            "graph_html_dir": str(html_dir),
        },
        "visualization": {"export_html": False},
        "funding": {"enabled": False},
    }
    protocol_file = tmp_path / "config.yaml"
    protocol_file.write_text(json.dumps(protocol), encoding="utf-8")

    summary = run_pipeline(
        protocol_path=protocol_file,
        raw_glob=str(raw_file),
        project_root=tmp_path,
        clean_output_dirs=True,
        with_funding=False,
    )

    assert summary["publications_after_preprocessing"] == 1
    assert not stale_table.exists()
    assert not stale_figure.exists()

    graph = nx.read_graphml(networks_dir / "institutions_2025_2025.graphml")
    assert graph.nodes["Department of Medicine, University A, United States."]["type"] == (
        "Technical_AI_Informatics"
    )
    assert graph.nodes["Department of Endocrinology, University B, United States."]["type"] == (
        "Endocrinology_Diabetes"
    )
    assert (output_dir / "period_definitions.csv").exists()
    assert (output_dir / "role_transition_counts.csv").exists()
    assert (output_dir / "structural_comparison_summary.csv").exists()


def test_run_complete_analysis_updates_manifest_with_postprocessing_outputs(
    tmp_path: Path, monkeypatch
) -> None:
    raw_dir = tmp_path / "data" / "raw"
    output_dir = tmp_path / "outputs" / "tables"
    networks_dir = tmp_path / "outputs" / "networks"
    html_dir = tmp_path / "outputs" / "networks_html"
    processed_dir = tmp_path / "data" / "processed"
    raw_file = raw_dir / "pubmed_records_test.jsonl"

    records = [
        {
            "PMID": "100",
            "TI": "In range",
            "AB": "Artificial intelligence for diabetes care and prediction.",
            "DP": "2025",
            "AD": ["Department of Endocrinology, University A, United States."],
        },
    ]
    _write_jsonl(raw_file, records)

    protocol = {
        "study": {
            "manuscript_period_start": 1946,
            "manuscript_period_end": 2025,
        },
        "queries": [{"id": "q1", "query": "dummy"}],
        "temporal_segmentation": {
            "mode": "fixed",
            "fixed_periods": [
                {"label": "2025-2025", "start_year": 2025, "end_year": 2025},
            ],
        },
        "preprocessing": {
            "remove_punctuation": True,
            "institution_keyword_hints": ["university", "school", "department"],
        },
        "screening": {
            "enabled": True,
            "include_terms": ["diabetes", "diabetic", "diabetology"],
            "exclude_terms": [],
        },
        "classification": {
            "fallback_label": "Other",
            "fallback_color": "#bdbdbd",
            "categories": [
                {
                    "label": "Endocrinology_Diabetes",
                    "keywords": ["endocrinology", "diabetes center"],
                    "color": "#dc2626",
                },
            ],
        },
        "outputs": {
            "publications_table": str(processed_dir / "publications.parquet"),
            "publication_summary": str(output_dir / "publication_counts.csv"),
            "period_definitions": str(output_dir / "period_definitions.csv"),
            "global_metrics": str(output_dir / "global.csv"),
            "core_newcomer_metrics": str(output_dir / "core.csv"),
            "cluster_metrics": str(output_dir / "cluster.csv"),
            "region_summary": str(output_dir / "region.csv"),
            "role_transition_counts": str(output_dir / "role_transition_counts.csv"),
            "structural_comparison_summary": str(output_dir / "structural_comparison_summary.csv"),
            "centrality_dir": str(output_dir / "centrality"),
            "graph_dir": str(networks_dir),
            "graph_html_dir": str(html_dir),
        },
        "visualization": {"export_html": False},
        "funding": {"enabled": False},
    }
    protocol_file = tmp_path / "config.yaml"
    protocol_file.write_text(json.dumps(protocol), encoding="utf-8")

    def fake_postprocess(*, command, stage, logger=None):
        if logger:
            logger(stage, "ok")
        flow_dir = tmp_path / "outputs" / "figures" / "flow_options"
        flow_dir.mkdir(parents=True, exist_ok=True)
        table_dir = tmp_path / "outputs" / "tables"
        table_dir.mkdir(parents=True, exist_ok=True)
        if stage == "generate_descriptive_table":
            (table_dir / "table_descriptive_by_period.csv").write_text("period\n2025-2025\n", encoding="utf-8")
            (table_dir / "table_descriptive_by_period.md").write_text("# table\n", encoding="utf-8")
        elif stage == "generate_flow_prototypes":
            for name in [
                "option1_all_institutions_role_flow.png",
                "option1_all_institutions_role_flow.pdf",
                "option2_field_small_multiples_role_flow.png",
                "option2_field_small_multiples_role_flow.pdf",
                "option3_top_institution_trajectories.png",
                "option3_top_institution_trajectories.pdf",
                "flow_transition_counts.csv",
            ]:
                (flow_dir / name).write_text("x", encoding="utf-8")
        elif stage == "generate_interactive_sankey":
            (flow_dir / "role_flow_sankey.html").write_text("<html></html>", encoding="utf-8")
            (flow_dir / "role_flow_sankey_fields.html").write_text("<html></html>", encoding="utf-8")

    monkeypatch.setattr(pipeline_module, "_run_postprocess_command", fake_postprocess)

    summary = run_complete_analysis(
        protocol_path=protocol_file,
        raw_glob=str(raw_file),
        project_root=tmp_path,
        clean_output_dirs=True,
        with_funding=False,
        python_executable="python3",
    )

    manifest_path = Path(summary["run_manifest"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["status"] == "analysis_completed"
    assert "postprocessing" in manifest
    assert "descriptive_table_csv" in manifest["outputs"]
    assert "role_flow_sankey_html" in manifest["outputs"]
    assert "flow_transition_counts" in manifest["outputs"]
