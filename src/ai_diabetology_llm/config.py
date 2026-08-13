from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ai_diabetology.classification import category_labels, fallback_label
from ai_diabetology.config import load_protocol


DEFAULT_MODEL = "gpt-5-mini"
DEFAULT_PROMPT_VERSION = "v1"
DEFAULT_SCHEMA_VERSION = "v1"
DEFAULT_REVIEW_THRESHOLD = 0.70
DEFAULT_MAX_OUTPUT_TOKENS = 160
DEFAULT_MAX_RETRIES = 2
DEFAULT_REQUEST_TIMEOUT_SECONDS = 60
DEFAULT_EXPORT_HTML = True
DEFAULT_WITH_FUNDING = True
DEFAULT_MATCH_PROTOCOL_LABELS = True
DEFAULT_EXECUTION_MODE = "sync"
DEFAULT_SYNC_MAX_CONCURRENCY = 8
DEFAULT_BATCH_ENABLED = True
DEFAULT_BATCH_CHUNK_SIZE = 5000
DEFAULT_BATCH_POLL_INTERVAL_SECONDS = 60
DEFAULT_BATCH_COMPLETION_WINDOW = "24h"
DEFAULT_ALLOW_PARTIAL_RUN = False


DEFAULT_LABEL_DESCRIPTIONS = {
    "Technical_AI_Informatics": "Computer science, informatics, engineering, AI, data science, or computational groups.",
    "Endocrinology_Diabetes": "Endocrinology, diabetology, metabolism, or diabetes specialty clinical groups.",
    "Ophthalmology_Vision": "Ophthalmology, retina, optometry, or vision science groups.",
    "Complications_Cardiometabolic_Nephrology_Neurology": "Diabetes complication specialties such as nephrology, cardiology, vascular medicine, neurology, or renal/cardiometabolic medicine.",
    "Pediatrics_Maternal_Health": "Pediatrics, children's hospitals, obstetrics, gynecology, maternal-fetal medicine, or gestational diabetes groups.",
    "General_Clinical_Medicine": "General/internal/family/primary care or broad clinical/hospital medicine groups.",
    "Public_Health_Epidemiology": "Public health, epidemiology, preventive medicine, population health, community health, or policy groups.",
    "Nutrition": "Nutrition, dietetics, food science, or clinical nutrition groups.",
    "Nursing_Diabetes_Education": "Nursing schools, nursing practice, or diabetes education groups.",
    "Behavioral_Psychological": "Psychology, psychiatry, behavioral medicine, or mental health groups.",
    "Exercise_Lifestyle": "Exercise science, physical activity, sports medicine, lifestyle medicine, or rehabilitation groups.",
    "Industry_Digital_Health_Device": "Commercial, biotech, pharma, digital health, therapeutics, or medical device organizations.",
}


def _resolve_path(path_like: str, project_root: Path) -> Path:
    path = Path(path_like)
    return path if path.is_absolute() else (project_root / path)


def resolve_latest_main_run_manifest(project_root: Path) -> Path | None:
    runs_dir = project_root / "outputs" / "runs"
    manifests = sorted(runs_dir.glob("*/run_manifest.json"))
    return manifests[-1] if manifests else None


def load_sidecar_config(config_path: str | Path, project_root: str | Path = ".") -> dict[str, Any]:
    project_root_path = Path(project_root).resolve()
    config_file = _resolve_path(str(config_path), project_root_path).resolve()
    raw = yaml.safe_load(config_file.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError("Sidecar config must be a mapping.")

    cfg: dict[str, Any] = {
        "main_protocol_path": raw.get("main_protocol_path", "config/protocol.yaml"),
        "main_run_manifest_path": raw.get("main_run_manifest_path"),
        "input_publications_parquet": raw.get(
            "input_publications_parquet",
            "data/processed/publications.parquet",
        ),
        "output_root": raw.get("output_root", "outputs_llm"),
        "cache_root": raw.get("cache_root", "data/llm/cache"),
        "intermediate_root": raw.get("intermediate_root", "data/llm"),
        "model": str(raw.get("model", DEFAULT_MODEL)).strip() or DEFAULT_MODEL,
        "prompt_version": str(raw.get("prompt_version", DEFAULT_PROMPT_VERSION)).strip()
        or DEFAULT_PROMPT_VERSION,
        "schema_version": str(raw.get("schema_version", DEFAULT_SCHEMA_VERSION)).strip()
        or DEFAULT_SCHEMA_VERSION,
        "review_confidence_threshold": float(
            raw.get("review_confidence_threshold", DEFAULT_REVIEW_THRESHOLD)
        ),
        "max_output_tokens": int(raw.get("max_output_tokens", DEFAULT_MAX_OUTPUT_TOKENS)),
        "max_retries": int(raw.get("max_retries", DEFAULT_MAX_RETRIES)),
        "request_timeout_seconds": int(
            raw.get("request_timeout_seconds", DEFAULT_REQUEST_TIMEOUT_SECONDS)
        ),
        "execution_mode": str(raw.get("execution_mode", DEFAULT_EXECUTION_MODE)).strip().lower()
        or DEFAULT_EXECUTION_MODE,
        "sync_max_concurrency": int(
            raw.get("sync_max_concurrency", DEFAULT_SYNC_MAX_CONCURRENCY)
        ),
        "batch_enabled": bool(raw.get("batch_enabled", DEFAULT_BATCH_ENABLED)),
        "batch_chunk_size": int(raw.get("batch_chunk_size", DEFAULT_BATCH_CHUNK_SIZE)),
        "batch_poll_interval_seconds": int(
            raw.get("batch_poll_interval_seconds", DEFAULT_BATCH_POLL_INTERVAL_SECONDS)
        ),
        "batch_completion_window": str(
            raw.get("batch_completion_window", DEFAULT_BATCH_COMPLETION_WINDOW)
        ).strip()
        or DEFAULT_BATCH_COMPLETION_WINDOW,
        "allow_partial_run": bool(raw.get("allow_partial_run", DEFAULT_ALLOW_PARTIAL_RUN)),
        "batch_input_root": raw.get("batch_input_root", "data/llm/batch/requests"),
        "batch_result_root": raw.get("batch_result_root", "data/llm/batch/results"),
        "batch_error_root": raw.get("batch_error_root", "data/llm/batch/errors"),
        "batch_manifest_root": raw.get("batch_manifest_root", "data/llm/batch/manifests"),
        "export_html": bool(raw.get("export_html", DEFAULT_EXPORT_HTML)),
        "with_funding": bool(raw.get("with_funding", DEFAULT_WITH_FUNDING)),
        "match_protocol_labels": bool(
            raw.get("match_protocol_labels", DEFAULT_MATCH_PROTOCOL_LABELS)
        ),
        "category_labels": [
            str(value).strip()
            for value in raw.get("category_labels", [])
            if str(value).strip()
        ],
        "fallback_label": str(raw.get("fallback_label", "Other")).strip() or "Other",
        "label_descriptions": {
            **DEFAULT_LABEL_DESCRIPTIONS,
            **{
                str(key): str(value).strip()
                for key, value in (raw.get("label_descriptions", {}) or {}).items()
                if str(key).strip() and str(value).strip()
            },
        },
        "config_path": str(config_file),
        "project_root": str(project_root_path),
    }

    protocol = load_protocol(_resolve_path(cfg["main_protocol_path"], project_root_path))
    protocol_labels = category_labels(protocol["classification"], include_fallback=False)
    protocol_fallback = fallback_label(protocol["classification"])

    if not cfg["category_labels"]:
        cfg["category_labels"] = list(protocol_labels)

    if cfg["match_protocol_labels"]:
        if cfg["category_labels"] != protocol_labels:
            raise ValueError(
                "sidecar.category_labels must match the main protocol classification labels exactly."
            )
        if cfg["fallback_label"] != protocol_fallback:
            raise ValueError(
                "sidecar.fallback_label must match the main protocol fallback label."
            )

    if len(cfg["category_labels"]) != len(set(cfg["category_labels"])):
        raise ValueError("sidecar.category_labels contains duplicates.")

    if cfg["execution_mode"] not in {"batch", "sync"}:
        raise ValueError("sidecar.execution_mode must be 'batch' or 'sync'.")
    if cfg["sync_max_concurrency"] < 1:
        raise ValueError("sidecar.sync_max_concurrency must be at least 1.")

    missing_descriptions = [
        label
        for label in cfg["category_labels"]
        if label not in cfg["label_descriptions"]
    ]
    if missing_descriptions:
        raise ValueError(
            f"Missing label_descriptions for sidecar labels: {missing_descriptions}"
        )

    main_run_manifest_path = cfg["main_run_manifest_path"]
    if main_run_manifest_path:
        manifest_path = _resolve_path(main_run_manifest_path, project_root_path)
    else:
        manifest_path = resolve_latest_main_run_manifest(project_root_path)
    cfg["main_run_manifest_path"] = str(manifest_path) if manifest_path else None
    return cfg


def resolve_sidecar_paths(config: dict[str, Any]) -> dict[str, Path]:
    project_root = Path(config["project_root"]).resolve()
    intermediate_root = _resolve_path(config["intermediate_root"], project_root).resolve()
    cache_root = _resolve_path(config["cache_root"], project_root).resolve()
    output_root = _resolve_path(config["output_root"], project_root).resolve()
    batch_input_root = _resolve_path(config["batch_input_root"], project_root).resolve()
    batch_result_root = _resolve_path(config["batch_result_root"], project_root).resolve()
    batch_error_root = _resolve_path(config["batch_error_root"], project_root).resolve()
    batch_manifest_root = _resolve_path(config["batch_manifest_root"], project_root).resolve()

    paths = {
        "project_root": project_root,
        "main_protocol_path": _resolve_path(config["main_protocol_path"], project_root).resolve(),
        "input_publications_parquet": _resolve_path(
            config["input_publications_parquet"], project_root
        ).resolve(),
        "output_root": output_root,
        "cache_root": cache_root,
        "intermediate_root": intermediate_root,
        "inputs_root": intermediate_root / "inputs",
        "results_root": intermediate_root / "results",
        "review_root": intermediate_root / "review",
        "responses_root": cache_root / "responses",
        "batch_input_root": batch_input_root,
        "batch_result_root": batch_result_root,
        "batch_error_root": batch_error_root,
        "batch_manifest_root": batch_manifest_root,
        "unique_affiliations_parquet": intermediate_root / "inputs" / "unique_affiliations.parquet",
        "affiliation_occurrences_parquet": intermediate_root
        / "inputs"
        / "affiliation_occurrences.parquet",
        "classification_index_parquet": cache_root / "cache_index.parquet",
        "classifications_parquet": intermediate_root
        / "results"
        / "affiliation_classifications.parquet",
        "classifications_csv": intermediate_root / "results" / "affiliation_classifications.csv",
        "review_queue_csv": intermediate_root / "review" / "low_confidence_review_queue.csv",
        "batch_registry_csv": batch_manifest_root / "batch_registry.csv",
        "tables_root": output_root / "tables",
        "networks_root": output_root / "networks",
        "networks_html_root": output_root / "networks_html",
        "figures_root": output_root / "figures" / "flow_options",
        "runs_root": output_root / "runs",
    }
    main_run_manifest_path = config.get("main_run_manifest_path")
    if main_run_manifest_path:
        paths["main_run_manifest_path"] = _resolve_path(
            main_run_manifest_path, project_root
        ).resolve()
    return paths
