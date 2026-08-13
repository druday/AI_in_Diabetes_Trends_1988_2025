import json
from pathlib import Path

import pandas as pd

from ai_diabetology_llm.config import load_sidecar_config
from ai_diabetology_llm.pipeline import (
    build_unique_affiliation_table,
    compare_keyword_vs_llm,
    extract_affiliation_occurrences,
    ingest_completed_batches,
    load_publications_df,
    make_cache_key,
    parse_jsonish,
    prepare_batch_requests,
    prepare_affiliation_inputs,
    rebuild_cache_index,
    run_parallel_analysis,
    run_sidecar,
    validate_classification_payload,
)


def test_parse_jsonish_handles_serialized_list() -> None:
    parsed = parse_jsonish('["A", "B"]')
    assert parsed == ["A", "B"]


def test_extract_unique_affiliations_dedupes_globally() -> None:
    df = pd.DataFrame(
        [
            {
                "pmid": "1",
                "publication_year": 2024,
                "period": "2024-2025",
                "funding_category": "NO_GRANT_LISTED",
                "affiliation_raw": ["A", "B", "A"],
            },
            {
                "pmid": "2",
                "publication_year": 2025,
                "period": "2024-2025",
                "funding_category": "US_FEDERAL_FUNDED",
                "affiliation_raw": ["B", "C"],
            },
        ]
    )
    occurrences = extract_affiliation_occurrences(df)
    config = {
        "model": "gpt-5-mini",
        "prompt_version": "v1",
        "schema_version": "v1",
    }
    unique = build_unique_affiliation_table(occurrences, config)
    assert set(unique["affiliation_text"]) == {"A", "B", "C"}
    assert int(unique.loc[unique["affiliation_text"] == "B", "occurrence_count"].iloc[0]) == 2


def test_validate_classification_payload_rejects_bad_label() -> None:
    cfg = {
        "category_labels": ["Technical_AI_Informatics"],
        "fallback_label": "Other",
    }
    try:
        validate_classification_payload(
            {"label": "Bad", "confidence": 0.8, "confusion_note": ""},
            cfg,
        )
    except ValueError as exc:
        assert "allowed sidecar label set" in str(exc)
    else:
        raise AssertionError("Expected ValueError for invalid label")


def test_rebuild_cache_index_creates_review_queue(tmp_path: Path) -> None:
    project_root = tmp_path
    (project_root / "config").mkdir(parents=True)
    (project_root / "outputs" / "runs" / "20260101T000000Z").mkdir(parents=True)
    protocol = {
        "queries": [{"id": "q1", "query": "dummy"}],
        "classification": {
            "fallback_label": "Other",
            "fallback_color": "#bdbdbd",
            "categories": [
                {"label": "Technical_AI_Informatics", "keywords": ["engineering"], "color": "#111111"},
            ],
        },
        "preprocessing": {"institution_extraction_mode": "exact_affiliation"},
        "outputs": {"publications_table": "x"},
        "temporal_segmentation": {
            "mode": "fixed",
            "fixed_periods": [{"label": "2024-2025", "start_year": 2024, "end_year": 2025}],
        },
    }
    (project_root / "config" / "protocol.yaml").write_text(json.dumps(protocol), encoding="utf-8")
    (project_root / "outputs" / "runs" / "20260101T000000Z" / "run_manifest.json").write_text(
        json.dumps({"outputs": {"period_definitions": str(project_root / "outputs" / "tables" / "period_definitions.csv")}}),
        encoding="utf-8",
    )
    (project_root / "outputs" / "tables").mkdir(parents=True)
    pd.DataFrame([{"label": "2024-2025", "start_year": 2024, "end_year": 2025}]).to_csv(
        project_root / "outputs" / "tables" / "period_definitions.csv",
        index=False,
    )
    sidecar_dir = project_root / "sidecars" / "llm_affiliation_classification" / "config"
    sidecar_dir.mkdir(parents=True)
    sidecar_config = {
        "main_protocol_path": "config/protocol.yaml",
        "main_run_manifest_path": "outputs/runs/20260101T000000Z/run_manifest.json",
        "input_publications_parquet": "data/processed/publications.parquet",
        "output_root": "outputs_llm",
        "cache_root": "data/llm/cache",
        "intermediate_root": "data/llm",
        "model": "gpt-5-mini",
        "prompt_version": "v1",
        "schema_version": "v1",
        "review_confidence_threshold": 0.70,
        "category_labels": ["Technical_AI_Informatics"],
        "fallback_label": "Other",
        "label_descriptions": {"Technical_AI_Informatics": "tech"},
    }
    config_path = sidecar_dir / "sidecar.yaml"
    config_path.write_text(json.dumps(sidecar_config), encoding="utf-8")
    response_dir = project_root / "data" / "llm" / "cache" / "responses" / "gpt-5-mini" / "v1" / "v1"
    response_dir.mkdir(parents=True)
    cache_key = make_cache_key(
        "A",
        model="gpt-5-mini",
        prompt_version="v1",
        schema_version="v1",
    )
    wrapper = {
        "affiliation_text": "A",
        "normalized_affiliation_text": "A",
        "cache_key": cache_key,
        "model": "gpt-5-mini",
        "prompt_version": "v1",
        "schema_version": "v1",
        "classified_at": "2026-01-01T00:00:00+00:00",
        "status": "ok",
        "error": "",
        "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
        "parsed": {"label": "Technical_AI_Informatics", "confidence": 0.5, "confusion_note": "uncertain"},
        "response": {"id": "resp_123"},
        "request": {"model": "gpt-5-mini"},
    }
    (response_dir / f"{cache_key}.json").write_text(json.dumps(wrapper), encoding="utf-8")

    summary = rebuild_cache_index(config_path, project_root=project_root)
    assert summary["rows"] == 1
    review = pd.read_csv(project_root / "data" / "llm" / "review" / "low_confidence_review_queue.csv")
    assert len(review) == 1


def test_prepare_batch_requests_excludes_cached_and_creates_registry(tmp_path: Path) -> None:
    project_root = tmp_path
    (project_root / "config").mkdir(parents=True)
    (project_root / "outputs" / "runs" / "20260101T000000Z").mkdir(parents=True)
    (project_root / "outputs" / "tables").mkdir(parents=True)
    (project_root / "data" / "processed").mkdir(parents=True)
    protocol = {
        "queries": [{"id": "q1", "query": "dummy"}],
        "classification": {
            "fallback_label": "Other",
            "fallback_color": "#bdbdbd",
            "categories": [
                {"label": "Technical_AI_Informatics", "keywords": ["engineering"], "color": "#111111"},
            ],
        },
        "preprocessing": {"institution_extraction_mode": "exact_affiliation"},
        "outputs": {"publications_table": "x"},
        "temporal_segmentation": {
            "mode": "fixed",
            "fixed_periods": [{"label": "2024-2025", "start_year": 2024, "end_year": 2025}],
        },
    }
    (project_root / "config" / "protocol.yaml").write_text(json.dumps(protocol), encoding="utf-8")
    (project_root / "outputs" / "runs" / "20260101T000000Z" / "run_manifest.json").write_text(
        json.dumps({"outputs": {"period_definitions": str(project_root / "outputs" / "tables" / "period_definitions.csv")}}),
        encoding="utf-8",
    )
    pd.DataFrame([{"label": "2024-2025", "start_year": 2024, "end_year": 2025}]).to_csv(
        project_root / "outputs" / "tables" / "period_definitions.csv",
        index=False,
    )
    pd.DataFrame(
        [
            {
                "pmid": "1",
                "title": "A",
                "abstract": "a",
                "mesh_terms": json.dumps(["diabetes"]),
                "publication_date_raw": "2024",
                "publication_year": 2024,
                "affiliation_raw": json.dumps(["Aff A", "Aff B"]),
                "institutions": json.dumps(["Aff A", "Aff B"]),
                "countries": json.dumps(["United States"]),
                "institution_country_pairs": json.dumps([]),
                "grant_entries": json.dumps([]),
                "funding_category": "NO_GRANT_LISTED",
                "funding_flags": json.dumps({}),
                "has_grant_support": False,
                "period": "2024-2025",
            }
        ]
    ).to_parquet(project_root / "data" / "processed" / "publications.parquet", index=False)
    config_dir = project_root / "sidecars" / "llm_affiliation_classification" / "config"
    config_dir.mkdir(parents=True)
    sidecar_config = {
        "main_protocol_path": "config/protocol.yaml",
        "main_run_manifest_path": "outputs/runs/20260101T000000Z/run_manifest.json",
        "input_publications_parquet": "data/processed/publications.parquet",
        "output_root": "outputs_llm",
        "cache_root": "data/llm/cache",
        "intermediate_root": "data/llm",
        "execution_mode": "batch",
        "batch_chunk_size": 1,
        "model": "gpt-5-mini",
        "prompt_version": "v1",
        "schema_version": "v1",
        "review_confidence_threshold": 0.70,
        "category_labels": ["Technical_AI_Informatics"],
        "fallback_label": "Other",
        "label_descriptions": {"Technical_AI_Informatics": "tech"},
    }
    config_path = config_dir / "sidecar.yaml"
    config_path.write_text(json.dumps(sidecar_config), encoding="utf-8")

    cache_dir = project_root / "data" / "llm" / "cache" / "responses" / "gpt-5-mini" / "v1" / "v1"
    cache_dir.mkdir(parents=True)
    cache_key_a = make_cache_key("Aff A", model="gpt-5-mini", prompt_version="v1", schema_version="v1")
    cached_wrapper = {
        "affiliation_text": "Aff A",
        "normalized_affiliation_text": "Aff A",
        "cache_key": cache_key_a,
        "model": "gpt-5-mini",
        "prompt_version": "v1",
        "schema_version": "v1",
        "classified_at": "2026-01-01T00:00:00+00:00",
        "status": "ok",
        "error": "",
        "usage": {},
        "parsed": {"label": "Technical_AI_Informatics", "confidence": 0.9, "confusion_note": ""},
        "response": {"id": "resp_1"},
        "request": {"model": "gpt-5-mini"},
    }
    (cache_dir / f"{cache_key_a}.json").write_text(json.dumps(cached_wrapper), encoding="utf-8")

    summary = prepare_batch_requests(config_path, project_root=project_root)
    assert summary["created_chunks"] == 1
    registry = pd.read_csv(project_root / "data" / "llm" / "batch" / "manifests" / "batch_registry.csv")
    assert len(registry) == 1
    request_file = Path(registry.iloc[0]["request_file"])
    lines = [json.loads(line) for line in request_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 1
    assert lines[0]["custom_id"] != cache_key_a


def test_ingest_completed_batches_writes_cache_wrappers(tmp_path: Path) -> None:
    project_root = tmp_path
    (project_root / "config").mkdir(parents=True)
    (project_root / "outputs" / "runs" / "20260101T000000Z").mkdir(parents=True)
    (project_root / "outputs" / "tables").mkdir(parents=True)
    (project_root / "data" / "processed").mkdir(parents=True)
    protocol = {
        "queries": [{"id": "q1", "query": "dummy"}],
        "classification": {
            "fallback_label": "Other",
            "fallback_color": "#bdbdbd",
            "categories": [
                {"label": "Technical_AI_Informatics", "keywords": ["engineering"], "color": "#111111"},
            ],
        },
        "preprocessing": {"institution_extraction_mode": "exact_affiliation"},
        "outputs": {"publications_table": "x"},
        "temporal_segmentation": {
            "mode": "fixed",
            "fixed_periods": [{"label": "2024-2025", "start_year": 2024, "end_year": 2025}],
        },
    }
    (project_root / "config" / "protocol.yaml").write_text(json.dumps(protocol), encoding="utf-8")
    (project_root / "outputs" / "runs" / "20260101T000000Z" / "run_manifest.json").write_text(
        json.dumps({"outputs": {"period_definitions": str(project_root / "outputs" / "tables" / "period_definitions.csv")}}),
        encoding="utf-8",
    )
    pd.DataFrame([{"label": "2024-2025", "start_year": 2024, "end_year": 2025}]).to_csv(
        project_root / "outputs" / "tables" / "period_definitions.csv",
        index=False,
    )
    pd.DataFrame(
        [
            {
                "pmid": "1",
                "title": "A",
                "abstract": "a",
                "mesh_terms": json.dumps(["diabetes"]),
                "publication_date_raw": "2024",
                "publication_year": 2024,
                "affiliation_raw": json.dumps(["Aff B"]),
                "institutions": json.dumps(["Aff B"]),
                "countries": json.dumps(["United States"]),
                "institution_country_pairs": json.dumps([]),
                "grant_entries": json.dumps([]),
                "funding_category": "NO_GRANT_LISTED",
                "funding_flags": json.dumps({}),
                "has_grant_support": False,
                "period": "2024-2025",
            }
        ]
    ).to_parquet(project_root / "data" / "processed" / "publications.parquet", index=False)
    config_dir = project_root / "sidecars" / "llm_affiliation_classification" / "config"
    config_dir.mkdir(parents=True)
    sidecar_config = {
        "main_protocol_path": "config/protocol.yaml",
        "main_run_manifest_path": "outputs/runs/20260101T000000Z/run_manifest.json",
        "input_publications_parquet": "data/processed/publications.parquet",
        "output_root": "outputs_llm",
        "cache_root": "data/llm/cache",
        "intermediate_root": "data/llm",
        "execution_mode": "batch",
        "batch_chunk_size": 1,
        "model": "gpt-5-mini",
        "prompt_version": "v1",
        "schema_version": "v1",
        "review_confidence_threshold": 0.70,
        "category_labels": ["Technical_AI_Informatics"],
        "fallback_label": "Other",
        "label_descriptions": {"Technical_AI_Informatics": "tech"},
    }
    config_path = config_dir / "sidecar.yaml"
    config_path.write_text(json.dumps(sidecar_config), encoding="utf-8")
    prepare_affiliation_inputs(config_path, project_root=project_root)
    cache_key_b = make_cache_key("Aff B", model="gpt-5-mini", prompt_version="v1", schema_version="v1")

    request_root = project_root / "data" / "llm" / "batch" / "requests"
    manifest_root = project_root / "data" / "llm" / "batch" / "manifests"
    result_root = project_root / "data" / "llm" / "batch" / "results"
    error_root = project_root / "data" / "llm" / "batch" / "errors"
    request_root.mkdir(parents=True)
    manifest_root.mkdir(parents=True)
    result_root.mkdir(parents=True)
    error_root.mkdir(parents=True)
    request_file = request_root / "batch_chunk_00001.jsonl"
    request_file.write_text(
        json.dumps(
            {
                "custom_id": cache_key_b,
                "method": "POST",
                "url": "/v1/responses",
                "body": {"model": "gpt-5-mini"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    result_file = result_root / "batch_chunk_00001.jsonl"
    result_file.write_text(
        json.dumps(
            {
                "custom_id": cache_key_b,
                "response": {
                    "status_code": 200,
                    "body": {
                        "output_text": json.dumps(
                            {
                                "label": "Technical_AI_Informatics",
                                "confidence": 0.88,
                                "confusion_note": "",
                            }
                        ),
                        "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
                    },
                },
                "error": None,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    registry = pd.DataFrame(
        [
            {
                "chunk_id": "batch_chunk_00001",
                "batch_status": "completed",
                "openai_batch_id": "batch_123",
                "input_file_id": "file_123",
                "submitted_at": "2026-01-01T00:00:00+00:00",
                "completed_at": "2026-01-01T00:10:00+00:00",
                "request_count": 1,
                "success_count": 0,
                "error_count": 0,
                "request_file": str(request_file.resolve()),
                "manifest_file": str((manifest_root / "batch_chunk_00001.json").resolve()),
                "result_file": str(result_file.resolve()),
                "error_file": str((error_root / "batch_chunk_00001.jsonl").resolve()),
            }
        ]
    )
    registry.to_csv(manifest_root / "batch_registry.csv", index=False)

    summary = ingest_completed_batches(config_path, project_root=project_root)
    assert summary["ingested_chunks"] == 1
    index_df = pd.read_parquet(project_root / "data" / "llm" / "cache" / "cache_index.parquet")
    assert len(index_df) == 1
    assert index_df.iloc[0]["label"] == "Technical_AI_Informatics"


def test_run_sidecar_batch_blocks_until_cache_complete(tmp_path: Path) -> None:
    project_root = tmp_path
    (project_root / "config").mkdir(parents=True)
    (project_root / "outputs" / "runs" / "20260101T000000Z").mkdir(parents=True)
    (project_root / "outputs" / "tables").mkdir(parents=True)
    (project_root / "data" / "processed").mkdir(parents=True)
    protocol = {
        "queries": [{"id": "q1", "query": "dummy"}],
        "classification": {
            "fallback_label": "Other",
            "fallback_color": "#bdbdbd",
            "categories": [
                {"label": "Technical_AI_Informatics", "keywords": ["engineering"], "color": "#111111"},
            ],
        },
        "preprocessing": {"institution_extraction_mode": "exact_affiliation"},
        "outputs": {"publications_table": "x"},
        "temporal_segmentation": {
            "mode": "fixed",
            "fixed_periods": [{"label": "2024-2025", "start_year": 2024, "end_year": 2025}],
        },
    }
    (project_root / "config" / "protocol.yaml").write_text(json.dumps(protocol), encoding="utf-8")
    (project_root / "outputs" / "runs" / "20260101T000000Z" / "run_manifest.json").write_text(
        json.dumps({"outputs": {"period_definitions": str(project_root / "outputs" / "tables" / "period_definitions.csv")}}),
        encoding="utf-8",
    )
    pd.DataFrame([{"label": "2024-2025", "start_year": 2024, "end_year": 2025}]).to_csv(
        project_root / "outputs" / "tables" / "period_definitions.csv",
        index=False,
    )
    pd.DataFrame(
        [
            {
                "pmid": "1",
                "title": "A",
                "abstract": "a",
                "mesh_terms": json.dumps(["diabetes"]),
                "publication_date_raw": "2024",
                "publication_year": 2024,
                "affiliation_raw": json.dumps(["Aff A"]),
                "institutions": json.dumps(["Aff A"]),
                "countries": json.dumps(["United States"]),
                "institution_country_pairs": json.dumps([]),
                "grant_entries": json.dumps([]),
                "funding_category": "NO_GRANT_LISTED",
                "funding_flags": json.dumps({}),
                "has_grant_support": False,
                "period": "2024-2025",
            }
        ]
    ).to_parquet(project_root / "data" / "processed" / "publications.parquet", index=False)
    config_dir = project_root / "sidecars" / "llm_affiliation_classification" / "config"
    config_dir.mkdir(parents=True)
    sidecar_config = {
        "main_protocol_path": "config/protocol.yaml",
        "main_run_manifest_path": "outputs/runs/20260101T000000Z/run_manifest.json",
        "input_publications_parquet": "data/processed/publications.parquet",
        "output_root": "outputs_llm",
        "cache_root": "data/llm/cache",
        "intermediate_root": "data/llm",
        "execution_mode": "batch",
        "batch_chunk_size": 1,
        "allow_partial_run": False,
        "model": "gpt-5-mini",
        "prompt_version": "v1",
        "schema_version": "v1",
        "review_confidence_threshold": 0.70,
        "category_labels": ["Technical_AI_Informatics"],
        "fallback_label": "Other",
        "label_descriptions": {"Technical_AI_Informatics": "tech"},
    }
    config_path = config_dir / "sidecar.yaml"
    config_path.write_text(json.dumps(sidecar_config), encoding="utf-8")

    summary = run_sidecar(
        config_path,
        project_root=project_root,
        skip_classification=True,
    )
    assert "analysis_skipped_reason" in summary
    assert "uncached affiliations remain" in summary["analysis_skipped_reason"]


def test_parallel_analysis_and_comparison_outputs(tmp_path: Path) -> None:
    project_root = tmp_path
    (project_root / "config").mkdir(parents=True)
    (project_root / "outputs" / "runs" / "20260101T000000Z").mkdir(parents=True)
    (project_root / "outputs" / "tables").mkdir(parents=True)
    (project_root / "data" / "processed").mkdir(parents=True)
    protocol = {
        "queries": [{"id": "q1", "query": "dummy"}],
        "classification": {
            "fallback_label": "Other",
            "fallback_color": "#bdbdbd",
            "categories": [
                {"label": "Technical_AI_Informatics", "keywords": ["engineering"], "color": "#111111"},
                {"label": "Endocrinology_Diabetes", "keywords": ["endocrinology"], "color": "#222222"},
            ],
        },
        "preprocessing": {"institution_extraction_mode": "exact_affiliation"},
        "outputs": {"publications_table": "x"},
        "visualization": {"export_html": False},
        "temporal_segmentation": {
            "mode": "fixed",
            "fixed_periods": [
                {"label": "2024-2024", "start_year": 2024, "end_year": 2024},
                {"label": "2025-2025", "start_year": 2025, "end_year": 2025},
            ],
        },
    }
    (project_root / "config" / "protocol.yaml").write_text(json.dumps(protocol), encoding="utf-8")
    pd.DataFrame(
        [
            {
                "pmid": "1",
                "title": "A",
                "abstract": "a",
                "mesh_terms": json.dumps(["diabetes"]),
                "publication_date_raw": "2024",
                "publication_year": 2024,
                "affiliation_raw": json.dumps(["Department of Endocrinology, Hospital A"]),
                "institutions": json.dumps(["Department of Endocrinology, Hospital A"]),
                "countries": json.dumps(["United States"]),
                "institution_country_pairs": json.dumps(
                    [{"institution": "Department of Endocrinology, Hospital A", "country": "United States"}]
                ),
                "grant_entries": json.dumps([]),
                "funding_category": "NO_GRANT_LISTED",
                "funding_flags": json.dumps({}),
                "has_grant_support": False,
                "period": "2024-2024",
            },
            {
                "pmid": "2",
                "title": "B",
                "abstract": "b",
                "mesh_terms": json.dumps(["diabetes"]),
                "publication_date_raw": "2025",
                "publication_year": 2025,
                "affiliation_raw": json.dumps(
                    [
                        "Department of Endocrinology, Hospital A",
                        "School of Engineering, University B",
                    ]
                ),
                "institutions": json.dumps(
                    [
                        "Department of Endocrinology, Hospital A",
                        "School of Engineering, University B",
                    ]
                ),
                "countries": json.dumps(["United States"]),
                "institution_country_pairs": json.dumps(
                    [
                        {"institution": "Department of Endocrinology, Hospital A", "country": "United States"},
                        {"institution": "School of Engineering, University B", "country": "United States"},
                    ]
                ),
                "grant_entries": json.dumps([]),
                "funding_category": "US_FEDERAL_FUNDED",
                "funding_flags": json.dumps({}),
                "has_grant_support": False,
                "period": "2025-2025",
            },
        ]
    ).to_parquet(project_root / "data" / "processed" / "publications.parquet", index=False)
    pd.DataFrame(
        [
            {"label": "2024-2024", "start_year": 2024, "end_year": 2024},
            {"label": "2025-2025", "start_year": 2025, "end_year": 2025},
        ]
    ).to_csv(project_root / "outputs" / "tables" / "period_definitions.csv", index=False)
    pd.DataFrame(
        [
            {"period": "2024-2024", "nodes": 1, "edges": 0, "density": 0.0, "avg_degree": 0.0, "avg_clustering_weighted": 0.0, "largest_connected_component_size": 1},
            {"period": "2025-2025", "nodes": 2, "edges": 1, "density": 1.0, "avg_degree": 1.0, "avg_clustering_weighted": 0.0, "largest_connected_component_size": 2},
        ]
    ).to_csv(project_root / "outputs" / "tables" / "global_network_metrics.csv", index=False)
    pd.DataFrame(
        [
            {"period": "2024-2024", "num_components": 1, "single_field_components": 1, "two_field_components": 0, "three_field_components": 0, "three_or_more_field_components": 0, "single_field_ratio": 1.0, "two_field_ratio": 0.0, "three_field_ratio": 0.0, "three_or_more_field_ratio": 0.0, "mean_distinct_key_fields_per_component": 1.0, "max_distinct_key_fields_in_component": 1},
            {"period": "2025-2025", "num_components": 1, "single_field_components": 0, "two_field_components": 1, "three_field_components": 0, "three_or_more_field_components": 0, "single_field_ratio": 0.0, "two_field_ratio": 1.0, "three_field_ratio": 0.0, "three_or_more_field_ratio": 0.0, "mean_distinct_key_fields_per_component": 2.0, "max_distinct_key_fields_in_component": 2},
        ]
    ).to_csv(project_root / "outputs" / "tables" / "cluster_interdisciplinarity_metrics.csv", index=False)
    (project_root / "outputs" / "runs" / "20260101T000000Z" / "run_manifest.json").write_text(
        json.dumps(
            {
                "outputs": {
                    "period_definitions": str(project_root / "outputs" / "tables" / "period_definitions.csv"),
                }
            }
        ),
        encoding="utf-8",
    )

    config_dir = project_root / "sidecars" / "llm_affiliation_classification" / "config"
    config_dir.mkdir(parents=True)
    sidecar_config = {
        "main_protocol_path": "config/protocol.yaml",
        "main_run_manifest_path": "outputs/runs/20260101T000000Z/run_manifest.json",
        "input_publications_parquet": "data/processed/publications.parquet",
        "output_root": "outputs_llm",
        "cache_root": "data/llm/cache",
        "intermediate_root": "data/llm",
        "model": "gpt-5-mini",
        "prompt_version": "v1",
        "schema_version": "v1",
        "review_confidence_threshold": 0.70,
        "export_html": False,
        "category_labels": ["Technical_AI_Informatics", "Endocrinology_Diabetes"],
        "fallback_label": "Other",
        "label_descriptions": {
            "Technical_AI_Informatics": "tech",
            "Endocrinology_Diabetes": "endo",
        },
    }
    config_path = config_dir / "sidecar.yaml"
    config_path.write_text(json.dumps(sidecar_config), encoding="utf-8")

    prepare_affiliation_inputs(config_path, project_root=project_root)
    classes = pd.DataFrame(
        [
            {
                "affiliation_text": "Department of Endocrinology, Hospital A",
                "normalized_affiliation_text": "Department of Endocrinology, Hospital A",
                "label": "Endocrinology_Diabetes",
                "confidence": 0.95,
                "confusion_note": "",
                "model": "gpt-5-mini",
                "prompt_version": "v1",
                "schema_version": "v1",
                "cache_key": make_cache_key("Department of Endocrinology, Hospital A", model="gpt-5-mini", prompt_version="v1", schema_version="v1"),
                "response_path": "/tmp/a.json",
                "classified_at": "2026-01-01T00:00:00+00:00",
                "status": "ok",
                "error": "",
                "input_tokens": 10,
                "output_tokens": 5,
                "total_tokens": 15,
            },
            {
                "affiliation_text": "School of Engineering, University B",
                "normalized_affiliation_text": "School of Engineering, University B",
                "label": "Technical_AI_Informatics",
                "confidence": 0.93,
                "confusion_note": "",
                "model": "gpt-5-mini",
                "prompt_version": "v1",
                "schema_version": "v1",
                "cache_key": make_cache_key("School of Engineering, University B", model="gpt-5-mini", prompt_version="v1", schema_version="v1"),
                "response_path": "/tmp/b.json",
                "classified_at": "2026-01-01T00:00:00+00:00",
                "status": "ok",
                "error": "",
                "input_tokens": 10,
                "output_tokens": 5,
                "total_tokens": 15,
            },
        ]
    )
    (project_root / "data" / "llm" / "results").mkdir(parents=True, exist_ok=True)
    classes.to_parquet(project_root / "data" / "llm" / "results" / "affiliation_classifications.parquet", index=False)

    summary = run_parallel_analysis(config_path, project_root=project_root, clean_output=True)
    assert Path(summary["run_manifest"]).exists()
    assert (project_root / "outputs_llm" / "tables" / "global_network_metrics.csv").exists()

    comparison = compare_keyword_vs_llm(config_path, project_root=project_root)
    assert Path(comparison["comparison_table"]).exists()
    assert Path(comparison["shift_matrix"]).exists()
