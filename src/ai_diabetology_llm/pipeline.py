from __future__ import annotations

import ast
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

import httpx
import networkx as nx
import pandas as pd
from pydantic import BaseModel, ValidationError, field_validator
from tqdm import tqdm

from ai_diabetology.classification import (
    category_color_map,
    category_labels,
    compile_category_patterns,
    fallback_label,
    make_classifier,
)
from ai_diabetology.config import Period, load_protocol
from ai_diabetology.network_metrics import top_centrality_table
from ai_diabetology.pipeline import _analyze_publication_subset, _write_csv
from ai_diabetology.role_flow import build_role_transition_counts, write_role_sankey_html

from ai_diabetology_llm.config import load_sidecar_config, resolve_sidecar_paths


OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
OPENAI_FILES_URL = "https://api.openai.com/v1/files"
OPENAI_BATCHES_URL = "https://api.openai.com/v1/batches"
DEFAULT_STATUS_FAILED = "failed"
DEFAULT_STATUS_OK = "ok"
BATCH_REGISTRY_COLUMNS = [
    "chunk_id",
    "batch_status",
    "openai_batch_id",
    "input_file_id",
    "submitted_at",
    "completed_at",
    "request_count",
    "success_count",
    "error_count",
    "request_file",
    "manifest_file",
    "result_file",
    "error_file",
]
FINAL_BATCH_STATUSES = {"completed", "failed", "cancelled", "expired"}
ACTIVE_BATCH_STATUSES = {"validating", "in_progress", "finalizing", "cancelling"}
RETRYABLE_BATCH_STATUSES = {"failed", "cancelled", "expired", "error"}


class ParsedClassification(BaseModel):
    label: str
    confidence: float
    confusion_note: str = ""

    @field_validator("label")
    @classmethod
    def _normalize_label(cls, value: str) -> str:
        return str(value).strip()

    @field_validator("confidence")
    @classmethod
    def _validate_confidence(cls, value: float) -> float:
        numeric = float(value)
        if numeric < 0.0 or numeric > 1.0:
            raise ValueError("confidence must be between 0 and 1.")
        return numeric

    @field_validator("confusion_note")
    @classmethod
    def _normalize_note(cls, value: str) -> str:
        return str(value).strip()


def parse_jsonish(value: Any) -> Any:
    if isinstance(value, (list, dict)):
        return value
    if value is None:
        return []
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text:
        return []
    for parser in (json.loads, ast.literal_eval):
        try:
            return parser(text)
        except Exception:
            continue
    return [text]


def normalize_affiliation_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text).strip())


def make_cache_key(
    affiliation_text: str,
    *,
    model: str,
    prompt_version: str,
    schema_version: str,
) -> str:
    normalized = normalize_affiliation_text(affiliation_text)
    digest = hashlib.sha256(
        f"{model}|||{prompt_version}|||{schema_version}|||{normalized}".encode("utf-8")
    ).hexdigest()
    return digest


def load_publications_df(parquet_path: str | Path) -> pd.DataFrame:
    df = pd.read_parquet(parquet_path).copy()
    jsonish_columns = [
        "affiliation_raw",
        "institutions",
        "countries",
        "institution_country_pairs",
        "grant_entries",
        "funding_flags",
        "mesh_terms",
    ]
    for column in jsonish_columns:
        if column in df.columns:
            df[column] = df[column].apply(parse_jsonish)
    if "period" in df.columns:
        df["period"] = df["period"].astype(str)
    return df


def extract_affiliation_occurrences(publications_df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, row in publications_df.iterrows():
        raw_affiliations = row.get("affiliation_raw", [])
        if not isinstance(raw_affiliations, list):
            raw_affiliations = []
        for raw in raw_affiliations:
            text = normalize_affiliation_text(raw)
            if not text:
                continue
            rows.append(
                {
                    "pmid": str(row.get("pmid", "")).strip(),
                    "publication_year": int(row.get("publication_year", 0) or 0),
                    "period": str(row.get("period", "")).strip(),
                    "funding_category": str(row.get("funding_category", "")).strip(),
                    "affiliation_text": text,
                }
            )
    return pd.DataFrame(
        rows,
        columns=["pmid", "publication_year", "period", "funding_category", "affiliation_text"],
    )


def build_unique_affiliation_table(occurrences_df: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    if occurrences_df.empty:
        return pd.DataFrame(
            columns=["affiliation_text", "occurrence_count", "pmid_count", "cache_key"]
        )
    grouped = (
        occurrences_df.groupby("affiliation_text", as_index=False)
        .agg(
            occurrence_count=("affiliation_text", "count"),
            pmid_count=("pmid", "nunique"),
        )
        .sort_values(["occurrence_count", "affiliation_text"], ascending=[False, True])
        .reset_index(drop=True)
    )
    grouped["cache_key"] = grouped["affiliation_text"].apply(
        lambda text: make_cache_key(
            text,
            model=config["model"],
            prompt_version=config["prompt_version"],
            schema_version=config["schema_version"],
        )
    )
    return grouped


def build_structured_schema(config: dict[str, Any]) -> dict[str, Any]:
    allowed_labels = list(config["category_labels"]) + [config["fallback_label"]]
    return {
        "name": "affiliation_classification",
        "type": "json_schema",
        "strict": True,
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "label": {
                    "type": "string",
                    "enum": allowed_labels,
                },
                "confidence": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1,
                },
                "confusion_note": {
                    "type": "string",
                },
            },
            "required": ["label", "confidence", "confusion_note"],
        },
    }


def build_prompt_text(config: dict[str, Any]) -> str:
    lines = [
        "You classify biomedical raw affiliation strings into exactly one institution-domain label.",
        "Base the decision on the department, institution, or organization named in the affiliation.",
        "Do not classify by paper topic unless it is needed to disambiguate the institution type.",
        "Return exactly one label from the allowed list.",
        f"Use {config['fallback_label']} only when none of the labels fit well.",
        "Return a confidence score between 0 and 1.",
        "Keep confusion_note empty when confident.",
        "If uncertain, keep confusion_note short and specific.",
        "Allowed labels:",
    ]
    for label in config["category_labels"]:
        lines.append(f"- {label}: {config['label_descriptions'][label]}")
    lines.append(f"- {config['fallback_label']}: no label is a good fit.")
    return "\n".join(lines)


def build_request_payload(affiliation_text: str, config: dict[str, Any]) -> dict[str, Any]:
    return {
        "model": config["model"],
        "input": [
            {"role": "system", "content": build_prompt_text(config)},
            {
                "role": "user",
                "content": (
                    "Classify this raw affiliation string.\n"
                    f"Affiliation: {affiliation_text}"
                ),
            },
        ],
        "text": {"format": build_structured_schema(config)},
        "max_output_tokens": int(config["max_output_tokens"]),
    }


def _openai_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
    }


def _load_env_value_from_file(env_file: Path, key: str) -> str:
    if not env_file.exists():
        return ""
    pattern = re.compile(rf"^{re.escape(key)}\s*=\s*(.+?)\s*$")
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = pattern.match(line)
        if not match:
            continue
        value = match.group(1).strip()
        if value[:1] in {"\"", "'"} and value[-1:] == value[:1] and len(value) >= 2:
            value = value[1:-1]
        return value.strip()
    return ""


def _resolve_openai_api_key(config: dict[str, Any]) -> str:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if api_key:
        return api_key
    project_root = Path(str(config.get("project_root", "."))).resolve()
    for candidate in (project_root / ".env", project_root / ".env.example"):
        file_value = _load_env_value_from_file(candidate, "OPENAI_API_KEY")
        if file_value:
            os.environ["OPENAI_API_KEY"] = file_value
            return file_value
    return ""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_batch_registry(paths: dict[str, Path]) -> pd.DataFrame:
    registry_path = paths["batch_registry_csv"]
    if not registry_path.exists():
        return pd.DataFrame(columns=BATCH_REGISTRY_COLUMNS)
    registry = pd.read_csv(registry_path)
    for column in BATCH_REGISTRY_COLUMNS:
        if column not in registry.columns:
            registry[column] = ""
    return registry[BATCH_REGISTRY_COLUMNS].copy()


def _save_batch_registry(paths: dict[str, Path], registry: pd.DataFrame) -> None:
    paths["batch_manifest_root"].mkdir(parents=True, exist_ok=True)
    output = registry.copy()
    for column in BATCH_REGISTRY_COLUMNS:
        if column not in output.columns:
            output[column] = ""
    output[BATCH_REGISTRY_COLUMNS].to_csv(paths["batch_registry_csv"], index=False)


def _batch_request_file_path(paths: dict[str, Path], chunk_id: str) -> Path:
    return paths["batch_input_root"] / f"{chunk_id}.jsonl"


def _batch_manifest_file_path(paths: dict[str, Path], chunk_id: str) -> Path:
    return paths["batch_manifest_root"] / f"{chunk_id}.json"


def _batch_result_file_path(paths: dict[str, Path], chunk_id: str) -> Path:
    return paths["batch_result_root"] / f"{chunk_id}.jsonl"


def _batch_error_file_path(paths: dict[str, Path], chunk_id: str) -> Path:
    return paths["batch_error_root"] / f"{chunk_id}.jsonl"


def _read_request_entries(request_file: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    if not request_file.exists():
        return entries
    with request_file.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            entries.append(json.loads(text))
    return entries


def _read_batch_custom_ids(request_file: Path) -> set[str]:
    return {
        str(entry.get("custom_id", "")).strip()
        for entry in _read_request_entries(request_file)
        if str(entry.get("custom_id", "")).strip()
    }


def _represented_cache_keys(
    registry: pd.DataFrame,
    *,
    retry_failed: bool,
) -> set[str]:
    represented: set[str] = set()
    for _, row in registry.iterrows():
        status = str(row.get("batch_status", "")).strip().lower()
        if retry_failed and status in RETRYABLE_BATCH_STATUSES:
            continue
        request_file = str(row.get("request_file", "")).strip()
        if not request_file:
            continue
        represented |= _read_batch_custom_ids(Path(request_file))
    return represented


def _cache_keys_from_classification_df(df: pd.DataFrame) -> set[str]:
    if df.empty:
        return set()
    working = df.copy()
    if "status" in working.columns:
        status_series = working["status"].astype(str).str.strip().str.lower()
        working = working[status_series == DEFAULT_STATUS_OK]
    return set(working.get("cache_key", pd.Series(dtype=str)).astype(str).tolist())


def extract_response_text(response_json: dict[str, Any]) -> str:
    output_text = response_json.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    output = response_json.get("output", [])
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict):
                continue
            for content in item.get("content", []):
                if not isinstance(content, dict):
                    continue
                text = content.get("text")
                if isinstance(text, str) and text.strip():
                    return text.strip()
                inner = content.get("output_text")
                if isinstance(inner, str) and inner.strip():
                    return inner.strip()
    raise ValueError("No structured text content was returned by the OpenAI response.")


def validate_classification_payload(payload: dict[str, Any], config: dict[str, Any]) -> ParsedClassification:
    parsed = ParsedClassification.model_validate(payload)
    allowed_labels = set(config["category_labels"]) | {config["fallback_label"]}
    if parsed.label not in allowed_labels:
        raise ValueError(
            f"Label '{parsed.label}' is not in the allowed sidecar label set."
        )
    return parsed


def prepare_batch_requests(
    config_path: str | Path,
    project_root: str | Path = ".",
    *,
    limit: int | None = None,
    retry_failed: bool = False,
) -> dict[str, Any]:
    config = load_sidecar_config(config_path, project_root=project_root)
    if not bool(config["batch_enabled"]):
        raise ValueError("Batch preparation requested, but sidecar.batch_enabled is false.")
    paths = resolve_sidecar_paths(config)
    prepare_affiliation_inputs(config_path, project_root=project_root)
    existing_summary = rebuild_cache_index(config_path, project_root=project_root)
    unique_df = pd.read_parquet(paths["unique_affiliations_parquet"])
    existing_df = (
        pd.read_parquet(paths["classification_index_parquet"])
        if paths["classification_index_parquet"].exists()
        else pd.DataFrame(columns=["cache_key"])
    )
    if retry_failed and "status" in existing_df.columns:
        cached_keys = set(
            existing_df[existing_df["status"].astype(str) == DEFAULT_STATUS_OK]
            .get("cache_key", pd.Series(dtype=str))
            .astype(str)
            .tolist()
        )
    else:
        cached_keys = set(existing_df.get("cache_key", pd.Series(dtype=str)).astype(str).tolist())
    registry = _load_batch_registry(paths)
    represented_keys = _represented_cache_keys(registry, retry_failed=retry_failed)

    pending_df = unique_df[
        ~unique_df["cache_key"].isin(cached_keys)
        & ~unique_df["cache_key"].isin(represented_keys)
    ].copy()
    pending_df = pending_df.sort_values(
        ["occurrence_count", "cache_key"],
        ascending=[False, True],
    ).reset_index(drop=True)
    if limit is not None:
        pending_df = pending_df.head(int(limit)).reset_index(drop=True)

    paths["batch_input_root"].mkdir(parents=True, exist_ok=True)
    paths["batch_manifest_root"].mkdir(parents=True, exist_ok=True)
    created_chunks = 0
    created_rows = 0
    next_chunk_number = int(len(registry)) + 1
    chunk_size = max(1, int(config["batch_chunk_size"]))

    for start in range(0, len(pending_df), chunk_size):
        chunk_df = pending_df.iloc[start : start + chunk_size].copy()
        chunk_id = f"batch_chunk_{next_chunk_number:05d}"
        next_chunk_number += 1
        request_file = _batch_request_file_path(paths, chunk_id)
        manifest_file = _batch_manifest_file_path(paths, chunk_id)
        request_lines: list[str] = []
        for _, row in chunk_df.iterrows():
            body = build_request_payload(str(row["affiliation_text"]).strip(), config)
            request_lines.append(
                json.dumps(
                    {
                        "custom_id": str(row["cache_key"]).strip(),
                        "method": "POST",
                        "url": "/v1/responses",
                        "body": body,
                    },
                    ensure_ascii=False,
                )
            )
        request_file.write_text("\n".join(request_lines) + ("\n" if request_lines else ""), encoding="utf-8")
        manifest_payload = {
            "chunk_id": chunk_id,
            "created_at": _now_iso(),
            "request_count": int(len(chunk_df)),
            "request_file": str(request_file.resolve()),
            "cache_keys": chunk_df["cache_key"].astype(str).tolist(),
            "model": config["model"],
            "prompt_version": config["prompt_version"],
            "schema_version": config["schema_version"],
        }
        manifest_file.write_text(json.dumps(manifest_payload, indent=2), encoding="utf-8")
        registry = pd.concat(
            [
                registry,
                pd.DataFrame(
                    [
                        {
                            "chunk_id": chunk_id,
                            "batch_status": "prepared",
                            "openai_batch_id": "",
                            "input_file_id": "",
                            "submitted_at": "",
                            "completed_at": "",
                            "request_count": int(len(chunk_df)),
                            "success_count": 0,
                            "error_count": 0,
                            "request_file": str(request_file.resolve()),
                            "manifest_file": str(manifest_file.resolve()),
                            "result_file": str(_batch_result_file_path(paths, chunk_id).resolve()),
                            "error_file": str(_batch_error_file_path(paths, chunk_id).resolve()),
                        }
                    ]
                ),
            ],
            ignore_index=True,
        )
        created_chunks += 1
        created_rows += int(len(chunk_df))

    _save_batch_registry(paths, registry)
    return {
        "existing_rows_before": int(existing_summary["rows"]),
        "pending_rows": int(len(pending_df)),
        "created_chunks": int(created_chunks),
        "created_rows": int(created_rows),
        "batch_registry_csv": str(paths["batch_registry_csv"]),
    }


def _extract_usage(response_json: dict[str, Any]) -> dict[str, int]:
    usage = response_json.get("usage", {})
    if not isinstance(usage, dict):
        return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    return {
        "input_tokens": int(usage.get("input_tokens", 0) or 0),
        "output_tokens": int(usage.get("output_tokens", 0) or 0),
        "total_tokens": int(usage.get("total_tokens", 0) or 0),
    }


def classify_single_affiliation(
    affiliation_text: str,
    config: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any] | None, dict[str, int]]:
    api_key = _resolve_openai_api_key(config)
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is required to classify uncached affiliations."
        )

    request_payload = build_request_payload(affiliation_text, config)
    timeout = int(config["request_timeout_seconds"])
    last_error = ""
    last_response_json: dict[str, Any] | None = None

    with httpx.Client(timeout=timeout) as client:
        for attempt in range(int(config["max_retries"]) + 1):
            response = client.post(
                OPENAI_RESPONSES_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=request_payload,
            )
            response.raise_for_status()
            response_json = response.json()
            last_response_json = response_json
            usage = _extract_usage(response_json)
            try:
                text = extract_response_text(response_json)
                payload = json.loads(text)
                parsed = validate_classification_payload(payload, config)
                return parsed.model_dump(), response_json, usage
            except (ValidationError, ValueError, json.JSONDecodeError) as exc:
                last_error = str(exc)
                if attempt >= int(config["max_retries"]):
                    break

    failure = {
        "label": config["fallback_label"],
        "confidence": 0.0,
        "confusion_note": f"classification_failed_after_retries: {last_error}".strip(),
    }
    return failure, last_response_json, _extract_usage(last_response_json or {})


def _response_file_path(paths: dict[str, Path], config: dict[str, Any], cache_key: str) -> Path:
    model_slug = str(config["model"]).replace("/", "_")
    return (
        paths["responses_root"]
        / model_slug
        / str(config["prompt_version"])
        / str(config["schema_version"])
        / f"{cache_key}.json"
    )


def submit_pending_batches(
    config_path: str | Path,
    project_root: str | Path = ".",
    *,
    limit_chunks: int | None = None,
) -> dict[str, Any]:
    config = load_sidecar_config(config_path, project_root=project_root)
    if not bool(config["batch_enabled"]):
        raise ValueError("Batch submission requested, but sidecar.batch_enabled is false.")
    api_key = _resolve_openai_api_key(config)
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required to submit batch jobs.")
    paths = resolve_sidecar_paths(config)
    registry = _load_batch_registry(paths)
    pending = registry[registry["batch_status"].astype(str) == "prepared"].copy().reset_index(drop=True)
    if limit_chunks is not None:
        pending = pending.head(int(limit_chunks)).reset_index(drop=True)

    submitted = 0
    with httpx.Client(timeout=int(config["request_timeout_seconds"])) as client:
        for _, row in pending.iterrows():
            request_file = Path(str(row["request_file"]))
            with request_file.open("rb") as handle:
                upload = client.post(
                    OPENAI_FILES_URL,
                    headers=_openai_headers(api_key),
                    data={"purpose": "batch"},
                    files={"file": (request_file.name, handle, "application/jsonl")},
                )
            upload.raise_for_status()
            file_payload = upload.json()
            input_file_id = str(file_payload.get("id", "")).strip()
            batch_create = client.post(
                OPENAI_BATCHES_URL,
                headers={
                    **_openai_headers(api_key),
                    "Content-Type": "application/json",
                },
                json={
                    "input_file_id": input_file_id,
                    "endpoint": "/v1/responses",
                    "completion_window": config["batch_completion_window"],
                    "metadata": {
                        "chunk_id": str(row["chunk_id"]),
                        "prompt_version": config["prompt_version"],
                        "schema_version": config["schema_version"],
                        "model": config["model"],
                    },
                },
            )
            batch_create.raise_for_status()
            batch_payload = batch_create.json()
            idx = registry.index[registry["chunk_id"] == row["chunk_id"]]
            registry.loc[idx, "openai_batch_id"] = str(batch_payload.get("id", "")).strip()
            registry.loc[idx, "input_file_id"] = input_file_id
            registry.loc[idx, "batch_status"] = str(batch_payload.get("status", "submitted")).strip()
            registry.loc[idx, "submitted_at"] = str(batch_payload.get("created_at", "")).strip() or _now_iso()
            submitted += 1

    _save_batch_registry(paths, registry)
    return {
        "submitted_chunks": int(submitted),
        "batch_registry_csv": str(paths["batch_registry_csv"]),
    }


def _download_openai_file(client: httpx.Client, api_key: str, file_id: str, out_path: Path) -> None:
    if not file_id:
        return
    out_path.parent.mkdir(parents=True, exist_ok=True)
    response = client.get(
        f"{OPENAI_FILES_URL}/{file_id}/content",
        headers=_openai_headers(api_key),
    )
    response.raise_for_status()
    out_path.write_bytes(response.content)


def sync_batch_status(
    config_path: str | Path,
    project_root: str | Path = ".",
    *,
    download_files: bool = True,
) -> dict[str, Any]:
    config = load_sidecar_config(config_path, project_root=project_root)
    api_key = _resolve_openai_api_key(config)
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required to sync batch jobs.")
    paths = resolve_sidecar_paths(config)
    registry = _load_batch_registry(paths)
    tracked = registry[
        registry["openai_batch_id"].astype(str).str.len() > 0
    ].copy()

    status_counts: dict[str, int] = {}
    with httpx.Client(timeout=int(config["request_timeout_seconds"])) as client:
        for _, row in tracked.iterrows():
            batch_id = str(row["openai_batch_id"]).strip()
            batch_resp = client.get(
                f"{OPENAI_BATCHES_URL}/{batch_id}",
                headers=_openai_headers(api_key),
            )
            batch_resp.raise_for_status()
            payload = batch_resp.json()
            status = str(payload.get("status", "")).strip()
            idx = registry.index[registry["chunk_id"] == row["chunk_id"]]
            registry.loc[idx, "batch_status"] = status
            if status in FINAL_BATCH_STATUSES:
                completed_at = (
                    str(payload.get("completed_at", "")).strip()
                    or str(payload.get("failed_at", "")).strip()
                    or str(payload.get("expired_at", "")).strip()
                    or _now_iso()
                )
                registry.loc[idx, "completed_at"] = completed_at
            result_file_id = str(payload.get("output_file_id", "")).strip()
            error_file_id = str(payload.get("error_file_id", "")).strip()
            result_path = Path(str(row["result_file"]))
            error_path = Path(str(row["error_file"]))
            if download_files and result_file_id and not result_path.exists():
                _download_openai_file(client, api_key, result_file_id, result_path)
            if download_files and error_file_id and not error_path.exists():
                _download_openai_file(client, api_key, error_file_id, error_path)
            status_counts[status] = status_counts.get(status, 0) + 1

    _save_batch_registry(paths, registry)
    return {
        "tracked_chunks": int(len(tracked)),
        "status_counts": status_counts,
        "batch_registry_csv": str(paths["batch_registry_csv"]),
    }


def _ingest_batch_line(
    *,
    line_payload: dict[str, Any],
    request_map: dict[str, dict[str, Any]],
    unique_lookup: dict[str, str],
    config: dict[str, Any],
    paths: dict[str, Path],
    classified_at: str,
) -> tuple[str, str]:
    cache_key = str(line_payload.get("custom_id", "")).strip()
    request_entry = request_map.get(cache_key, {})
    affiliation_text = unique_lookup.get(cache_key, "")
    response_path = _response_file_path(paths, config, cache_key)
    response_path.parent.mkdir(parents=True, exist_ok=True)

    response_block = line_payload.get("response")
    error_block = line_payload.get("error")
    status = DEFAULT_STATUS_OK
    error_text = ""
    parsed: dict[str, Any]
    raw_response: dict[str, Any] | None = None
    usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

    try:
        if isinstance(response_block, dict) and int(response_block.get("status_code", 0) or 0) == 200:
            raw_response = response_block.get("body") if isinstance(response_block.get("body"), dict) else {}
            usage = _extract_usage(raw_response or {})
            text = extract_response_text(raw_response or {})
            payload = json.loads(text)
            parsed_model = validate_classification_payload(payload, config)
            parsed = parsed_model.model_dump()
        else:
            raise ValueError(json.dumps(error_block or response_block or {"error": "missing_response"}))
    except Exception as exc:  # noqa: BLE001
        status = DEFAULT_STATUS_FAILED
        error_text = str(exc)
        parsed = {
            "label": config["fallback_label"],
            "confidence": 0.0,
            "confusion_note": f"batch_ingest_failed: {error_text}".strip(),
        }

    wrapper = {
        "affiliation_text": affiliation_text,
        "normalized_affiliation_text": normalize_affiliation_text(affiliation_text),
        "cache_key": cache_key,
        "model": config["model"],
        "prompt_version": config["prompt_version"],
        "schema_version": config["schema_version"],
        "classified_at": classified_at,
        "status": status,
        "error": error_text,
        "usage": usage,
        "parsed": parsed,
        "response": raw_response,
        "request": request_entry.get("body", build_request_payload(affiliation_text, config)),
        "batch_result": line_payload,
    }
    response_path.write_text(json.dumps(wrapper, indent=2), encoding="utf-8")
    return status, str(response_path.resolve())


def ingest_completed_batches(
    config_path: str | Path,
    project_root: str | Path = ".",
) -> dict[str, Any]:
    config = load_sidecar_config(config_path, project_root=project_root)
    paths = resolve_sidecar_paths(config)
    prepare_affiliation_inputs(config_path, project_root=project_root)
    unique_df = pd.read_parquet(paths["unique_affiliations_parquet"])
    unique_lookup = {
        str(row["cache_key"]).strip(): str(row["affiliation_text"]).strip()
        for _, row in unique_df.iterrows()
    }
    registry = _load_batch_registry(paths)
    target = registry[
        registry["batch_status"].astype(str).isin(["completed", "failed", "cancelled", "expired"])
    ].copy()

    ingested_chunks = 0
    ingested_rows = 0
    for _, row in target.iterrows():
        if str(row["batch_status"]).strip() == "ingested":
            continue
        request_file = Path(str(row["request_file"]))
        request_map = {
            str(entry.get("custom_id", "")).strip(): entry
            for entry in _read_request_entries(request_file)
        }
        success_count = 0
        error_count = 0
        classified_at = str(row.get("completed_at", "")).strip() or _now_iso()

        for file_key in ("result_file", "error_file"):
            file_path = Path(str(row.get(file_key, "")).strip())
            if not file_path.exists():
                continue
            with file_path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    text = line.strip()
                    if not text:
                        continue
                    payload = json.loads(text)
                    status, _ = _ingest_batch_line(
                        line_payload=payload,
                        request_map=request_map,
                        unique_lookup=unique_lookup,
                        config=config,
                        paths=paths,
                        classified_at=classified_at,
                    )
                    if status == DEFAULT_STATUS_OK:
                        success_count += 1
                    else:
                        error_count += 1
                    ingested_rows += 1

        idx = registry.index[registry["chunk_id"] == row["chunk_id"]]
        registry.loc[idx, "success_count"] = int(success_count)
        registry.loc[idx, "error_count"] = int(error_count)
        registry.loc[idx, "batch_status"] = "ingested"
        ingested_chunks += 1

    _save_batch_registry(paths, registry)
    rebuilt = rebuild_cache_index(config_path, project_root=project_root)
    return {
        "ingested_chunks": int(ingested_chunks),
        "ingested_rows": int(ingested_rows),
        **rebuilt,
    }


def rebuild_cache_index(config_path: str | Path, project_root: str | Path = ".") -> dict[str, Any]:
    config = load_sidecar_config(config_path, project_root=project_root)
    paths = resolve_sidecar_paths(config)
    rows: list[dict[str, Any]] = []
    for file_path in sorted(paths["responses_root"].glob("**/*.json")):
        payload = json.loads(file_path.read_text(encoding="utf-8"))
        parsed = payload.get("parsed", {}) or {}
        usage = payload.get("usage", {}) or {}
        rows.append(
            {
                "affiliation_text": str(payload.get("affiliation_text", "")).strip(),
                "normalized_affiliation_text": str(
                    payload.get("normalized_affiliation_text", "")
                ).strip(),
                "label": str(parsed.get("label", config["fallback_label"])).strip()
                or config["fallback_label"],
                "confidence": float(parsed.get("confidence", 0.0) or 0.0),
                "confusion_note": str(parsed.get("confusion_note", "")).strip(),
                "model": str(payload.get("model", config["model"])).strip() or config["model"],
                "prompt_version": str(
                    payload.get("prompt_version", config["prompt_version"])
                ).strip()
                or config["prompt_version"],
                "schema_version": str(
                    payload.get("schema_version", config["schema_version"])
                ).strip()
                or config["schema_version"],
                "cache_key": str(payload.get("cache_key", "")).strip(),
                "response_path": str(file_path.resolve()),
                "classified_at": str(payload.get("classified_at", "")).strip(),
                "status": str(payload.get("status", DEFAULT_STATUS_OK)).strip()
                or DEFAULT_STATUS_OK,
                "error": str(payload.get("error", "")).strip(),
                "input_tokens": int(usage.get("input_tokens", 0) or 0),
                "output_tokens": int(usage.get("output_tokens", 0) or 0),
                "total_tokens": int(usage.get("total_tokens", 0) or 0),
            }
        )

    index_df = pd.DataFrame(
        rows,
        columns=[
            "affiliation_text",
            "normalized_affiliation_text",
            "label",
            "confidence",
            "confusion_note",
            "model",
            "prompt_version",
            "schema_version",
            "cache_key",
            "response_path",
            "classified_at",
            "status",
            "error",
            "input_tokens",
            "output_tokens",
            "total_tokens",
        ],
    )
    if not index_df.empty:
        index_df = (
            index_df.sort_values(["classified_at", "affiliation_text"], ascending=[True, True])
            .drop_duplicates(subset=["cache_key"], keep="last")
            .reset_index(drop=True)
        )
    for directory_key in ("cache_root", "results_root", "review_root"):
        paths[directory_key].mkdir(parents=True, exist_ok=True)
    index_df.to_parquet(paths["classification_index_parquet"], index=False)
    index_df.to_parquet(paths["classifications_parquet"], index=False)
    index_df.to_csv(paths["classifications_csv"], index=False)

    review_df = index_df[
        (index_df["confidence"] < float(config["review_confidence_threshold"]))
        | (index_df["confusion_note"].astype(str).str.len() > 0)
    ].copy()
    review_df.to_csv(paths["review_queue_csv"], index=False)

    return {
        "rows": int(len(index_df)),
        "review_rows": int(len(review_df)),
        "classifications_parquet": str(paths["classifications_parquet"]),
        "review_queue_csv": str(paths["review_queue_csv"]),
    }


def prepare_affiliation_inputs(config_path: str | Path, project_root: str | Path = ".") -> dict[str, Any]:
    config = load_sidecar_config(config_path, project_root=project_root)
    paths = resolve_sidecar_paths(config)
    publications_df = load_publications_df(paths["input_publications_parquet"])
    occurrences_df = extract_affiliation_occurrences(publications_df)
    unique_df = build_unique_affiliation_table(occurrences_df, config)

    paths["inputs_root"].mkdir(parents=True, exist_ok=True)
    occurrences_df.to_parquet(paths["affiliation_occurrences_parquet"], index=False)
    unique_df.to_parquet(paths["unique_affiliations_parquet"], index=False)
    return {
        "occurrence_rows": int(len(occurrences_df)),
        "unique_rows": int(len(unique_df)),
        "affiliation_occurrences_parquet": str(paths["affiliation_occurrences_parquet"]),
        "unique_affiliations_parquet": str(paths["unique_affiliations_parquet"]),
    }


def classify_affiliations_sync(
    config_path: str | Path,
    project_root: str | Path = ".",
    limit: int | None = None,
    *,
    retry_failed: bool = False,
) -> dict[str, Any]:
    config = load_sidecar_config(config_path, project_root=project_root)
    paths = resolve_sidecar_paths(config)
    prepare_affiliation_inputs(config_path, project_root=project_root)

    unique_df = pd.read_parquet(paths["unique_affiliations_parquet"])
    existing_summary = rebuild_cache_index(config_path, project_root=project_root)
    existing_df = (
        pd.read_parquet(paths["classification_index_parquet"])
        if paths["classification_index_parquet"].exists()
        else pd.DataFrame(columns=["cache_key"])
    )
    if retry_failed and "status" in existing_df.columns:
        cached_keys = set(
            existing_df[existing_df["status"].astype(str) == DEFAULT_STATUS_OK]
            .get("cache_key", pd.Series(dtype=str))
            .astype(str)
            .tolist()
        )
    else:
        cached_keys = set(existing_df.get("cache_key", pd.Series(dtype=str)).astype(str).tolist())
    pending_df = unique_df[~unique_df["cache_key"].isin(cached_keys)].copy().reset_index(drop=True)
    if limit is not None:
        pending_df = pending_df.head(int(limit)).reset_index(drop=True)

    max_workers = int(config["sync_max_concurrency"])
    new_rows = 0
    pending_rows = [
        {
            "affiliation_text": str(row["affiliation_text"]).strip(),
            "cache_key": str(row["cache_key"]).strip(),
        }
        for _, row in pending_df.iterrows()
    ]
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {
            executor.submit(classify_single_affiliation, row["affiliation_text"], config): row
            for row in pending_rows
        }
        for future in tqdm(
            as_completed(future_map),
            total=len(future_map),
            desc=f"Classifying affiliations ({max_workers} workers)",
        ):
            row = future_map[future]
            affiliation_text = str(row["affiliation_text"]).strip()
            cache_key = str(row["cache_key"]).strip()
            response_path = _response_file_path(paths, config, cache_key)
            response_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                parsed, raw_response, usage = future.result()
            except Exception as exc:
                parsed = {
                    "label": config["fallback_label"],
                    "confidence": 0.0,
                    "confusion_note": f"classification_failed_with_exception: {exc}",
                }
                raw_response = None
                usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
            status = (
                DEFAULT_STATUS_OK
                if float(parsed.get("confidence", 0.0) or 0.0) > 0
                and not str(parsed.get("confusion_note", "")).startswith("classification_failed")
                else DEFAULT_STATUS_FAILED
            )
            wrapper = {
                "affiliation_text": affiliation_text,
                "normalized_affiliation_text": normalize_affiliation_text(affiliation_text),
                "cache_key": cache_key,
                "model": config["model"],
                "prompt_version": config["prompt_version"],
                "schema_version": config["schema_version"],
                "classified_at": datetime.now(timezone.utc).isoformat(),
                "status": status,
                "error": "" if status == DEFAULT_STATUS_OK else parsed.get("confusion_note", ""),
                "usage": usage,
                "parsed": parsed,
                "response": raw_response,
                "request": build_request_payload(affiliation_text, config),
            }
            response_path.write_text(json.dumps(wrapper, indent=2), encoding="utf-8")
            new_rows += 1

    rebuilt = rebuild_cache_index(config_path, project_root=project_root)
    return {
        "existing_rows_before": int(existing_summary["rows"]),
        "pending_rows": int(len(pending_df)),
        "new_rows_written": int(new_rows),
        "execution_mode": "sync",
        "sync_max_concurrency": int(max_workers),
        **rebuilt,
    }


def classify_affiliations(
    config_path: str | Path,
    project_root: str | Path = ".",
    limit: int | None = None,
    *,
    execution_mode: str | None = None,
    retry_failed: bool = False,
) -> dict[str, Any]:
    config = load_sidecar_config(config_path, project_root=project_root)
    mode = str(execution_mode or config["execution_mode"]).strip().lower()
    if mode == "sync":
        return classify_affiliations_sync(
            config_path=config_path,
            project_root=project_root,
            limit=limit,
            retry_failed=retry_failed,
        )

    prepare = prepare_batch_requests(
        config_path=config_path,
        project_root=project_root,
        limit=limit,
        retry_failed=retry_failed,
    )
    submit = submit_pending_batches(
        config_path=config_path,
        project_root=project_root,
    )
    sync = sync_batch_status(
        config_path=config_path,
        project_root=project_root,
        download_files=True,
    )
    ingest = ingest_completed_batches(
        config_path=config_path,
        project_root=project_root,
    )
    return {
        "execution_mode": "batch",
        "prepare": prepare,
        "submit": submit,
        "sync": sync,
        "ingest": ingest,
    }


def _missing_cache_keys(config_path: str | Path, project_root: str | Path = ".") -> set[str]:
    config = load_sidecar_config(config_path, project_root=project_root)
    paths = resolve_sidecar_paths(config)
    if not paths["unique_affiliations_parquet"].exists():
        prepare_affiliation_inputs(config_path, project_root=project_root)
    unique_df = pd.read_parquet(paths["unique_affiliations_parquet"])
    cached: set[str] = set()
    if paths["classification_index_parquet"].exists():
        cached |= _cache_keys_from_classification_df(pd.read_parquet(paths["classification_index_parquet"]))
    if paths["classifications_parquet"].exists():
        cached |= _cache_keys_from_classification_df(pd.read_parquet(paths["classifications_parquet"]))
    return set(unique_df["cache_key"].astype(str).tolist()) - cached


def _load_periods_from_main_run(config: dict[str, Any], paths: dict[str, Path]) -> list[Period]:
    period_path: Path | None = None
    manifest_path = paths.get("main_run_manifest_path")
    if manifest_path and manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        outputs = manifest.get("outputs", {})
        candidate = outputs.get("period_definitions")
        if candidate:
            period_path = Path(candidate)
    if period_path is None:
        period_path = paths["project_root"] / "outputs" / "tables" / "period_definitions.csv"
    df = pd.read_csv(period_path)
    periods = [
        Period(
            label=str(row["label"]),
            start_year=int(row["start_year"]),
            end_year=int(row["end_year"]),
        )
        for _, row in df.iterrows()
    ]
    return periods


def _lookup_classifier_from_index(index_df: pd.DataFrame, fallback: str):
    lookup = {
        normalize_affiliation_text(str(row["affiliation_text"])): str(row["label"]).strip() or fallback
        for _, row in index_df.iterrows()
    }

    def _classify(name: str) -> str:
        return lookup.get(normalize_affiliation_text(name), fallback)

    return _classify


def _llm_manifest_path(paths: dict[str, Path]) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = paths["runs_root"] / timestamp
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / "run_manifest.json"


def run_parallel_analysis(
    config_path: str | Path,
    project_root: str | Path = ".",
    clean_output: bool = False,
) -> dict[str, Any]:
    config = load_sidecar_config(config_path, project_root=project_root)
    paths = resolve_sidecar_paths(config)
    missing_cache_keys = _missing_cache_keys(config_path, project_root=project_root)
    if missing_cache_keys and not bool(config["allow_partial_run"]):
        raise ValueError(
            f"LLM classifications are incomplete: {len(missing_cache_keys)} uncached affiliations remain."
        )
    if not paths["classifications_parquet"].exists():
        raise FileNotFoundError(
            "LLM classifications parquet is missing. Run the classification step first."
        )

    protocol = load_protocol(paths["main_protocol_path"])
    periods = _load_periods_from_main_run(config, paths)
    period_labels = [period.label for period in periods]
    publications_df = load_publications_df(paths["input_publications_parquet"])
    publications_df["period"] = publications_df["period"].astype(str)
    publications_df = publications_df[publications_df["period"].isin(period_labels)].copy()

    index_df = pd.read_parquet(paths["classifications_parquet"])
    llm_fallback = str(config["fallback_label"]).strip() or "Other"
    classifier = _lookup_classifier_from_index(index_df, fallback=llm_fallback)
    vis_cfg = protocol.get("visualization", {})
    node_colors = category_color_map(
        protocol["classification"],
        extra_colors=vis_cfg.get("node_colors", {}),
    )
    field_order = category_labels(protocol["classification"], include_fallback=True)

    paths["tables_root"].mkdir(parents=True, exist_ok=True)
    base = _analyze_publication_subset(
        publications_df=publications_df,
        periods=periods,
        classifier=classifier,
        graph_dir=paths["networks_root"],
        graph_html_dir=paths["networks_html_root"],
        export_html=bool(config["export_html"]),
        node_colors=node_colors,
        category_order=field_order,
        fallback_category=llm_fallback,
        centrality_dir=paths["tables_root"] / "centrality",
        clean_output_dirs=clean_output,
    )

    output_registry: dict[str, str] = {}
    base_table_map = {
        "publication_summary": "publication_counts_by_period.csv",
        "global_metrics": "global_network_metrics.csv",
        "cluster_metrics": "cluster_interdisciplinarity_metrics.csv",
        "core_newcomer_metrics": "core_newcomer_metrics.csv",
        "region_summary": "who_region_summary.csv",
    }
    for key, filename in base_table_map.items():
        out_path = paths["tables_root"] / filename
        _write_csv(base[key], out_path)
        output_registry[key] = str(out_path.resolve())

    period_def_out = paths["tables_root"] / "period_definitions.csv"
    pd.DataFrame(
        [{"label": p.label, "start_year": p.start_year, "end_year": p.end_year} for p in periods]
    ).to_csv(period_def_out, index=False)
    output_registry["period_definitions"] = str(period_def_out.resolve())

    for period in periods:
        centrality = top_centrality_table(
            base["period_graphs"][period.label],
            top_n=10,
            use_lcc_for_path_metrics=True,
        )
        centrality_path = paths["tables_root"] / "centrality" / f"centrality_top10_{period.label.replace('-', '_')}.csv"
        centrality.to_csv(centrality_path, index=False)

    if bool(config["with_funding"]):
        funding_categories = sorted(
            {str(value).strip() for value in publications_df["funding_category"].dropna().tolist() if str(value).strip()}
        )
        funding_figure_root = paths["figures_root"] / "funding"
        funding_figure_root.mkdir(parents=True, exist_ok=True)

        funding_pub_rows: list[pd.DataFrame] = []
        funding_global_rows: list[pd.DataFrame] = []
        funding_cluster_rows: list[pd.DataFrame] = []
        funding_core_rows: list[pd.DataFrame] = []
        funding_region_rows: list[pd.DataFrame] = []
        funding_transition_rows: list[pd.DataFrame] = []
        comparison_rows: list[pd.DataFrame] = []

        for category in funding_categories:
            subset = publications_df[publications_df["funding_category"] == category].copy()
            slug = str(category).strip().lower().replace("-", "_").replace(" ", "_")
            analyzed = _analyze_publication_subset(
                publications_df=subset,
                periods=periods,
                classifier=classifier,
                graph_dir=paths["output_root"] / "networks_funding" / slug,
                graph_html_dir=paths["output_root"] / "networks_html_funding" / slug,
                export_html=bool(config["export_html"]),
                node_colors=node_colors,
                category_order=field_order,
                fallback_category=llm_fallback,
                centrality_dir=None,
                clean_output_dirs=False,
            )

            pub_df = analyzed["publication_summary"].copy()
            pub_df["funding_category"] = category
            funding_pub_rows.append(pub_df)

            global_df = analyzed["global_metrics"].copy()
            global_df["funding_category"] = category
            funding_global_rows.append(global_df)

            cluster_df = analyzed["cluster_metrics"].copy()
            cluster_df["funding_category"] = category
            funding_cluster_rows.append(cluster_df)

            core_df = analyzed["core_newcomer_metrics"].copy()
            core_df["funding_category"] = category
            funding_core_rows.append(core_df)

            region_df = analyzed["region_summary"].copy()
            region_df["funding_category"] = category
            funding_region_rows.append(region_df)

            transitions = build_role_transition_counts(
                period_graphs=analyzed["period_graphs"],
                period_labels=period_labels,
                include_absent=True,
            )
            transitions["funding_category"] = category
            funding_transition_rows.append(transitions)

            sankey_path = funding_figure_root / f"{slug}_role_flow_sankey.html"
            write_role_sankey_html(
                transitions=transitions,
                period_labels=period_labels,
                out_html=sankey_path,
                title=f"LLM Institution Role Flow Across Periods ({category})",
                subtitle="Funding-stratified transitions with Absent entry/exit states.",
                include_absent=True,
                include_period_annotations=True,
            )
            output_registry[f"funding_sankey_{slug}"] = str(sankey_path.resolve())

            merged = pub_df.merge(global_df, on=["period", "funding_category"], how="left")
            if not core_df.empty:
                core_copy = core_df.rename(columns={"to": "period"}).drop(columns=["from"])
                merged = merged.merge(core_copy, on=["period", "funding_category"], how="left")
            merged["lcc_share_pct"] = merged.apply(
                lambda r: (100.0 * float(r["largest_connected_component_size"]) / float(r["nodes"]))
                if float(r["nodes"]) > 0
                else 0.0,
                axis=1,
            )
            comparison_rows.append(merged)

        funding_outputs = {
            "funding_publication_summary": pd.concat(funding_pub_rows, ignore_index=True),
            "funding_global_metrics": pd.concat(funding_global_rows, ignore_index=True),
            "funding_cluster_metrics": pd.concat(funding_cluster_rows, ignore_index=True),
            "funding_core_newcomer_metrics": pd.concat(funding_core_rows, ignore_index=True),
            "funding_region_summary": pd.concat(funding_region_rows, ignore_index=True),
            "funding_role_transition_counts": pd.concat(funding_transition_rows, ignore_index=True),
            "funding_structural_comparison_summary": pd.concat(comparison_rows, ignore_index=True),
        }
        funding_names = {
            "funding_publication_summary": "funding_publication_counts_by_period.csv",
            "funding_global_metrics": "funding_global_network_metrics.csv",
            "funding_cluster_metrics": "funding_cluster_interdisciplinarity_metrics.csv",
            "funding_core_newcomer_metrics": "funding_core_newcomer_metrics.csv",
            "funding_region_summary": "funding_who_region_summary.csv",
            "funding_role_transition_counts": "funding_role_transition_counts.csv",
            "funding_structural_comparison_summary": "funding_structural_comparison_summary.csv",
        }
        for key, frame in funding_outputs.items():
            out_path = paths["tables_root"] / funding_names[key]
            _write_csv(frame, out_path)
            output_registry[key] = str(out_path.resolve())

    manifest_path = _llm_manifest_path(paths)
    summary = {
        "source_main_run_manifest_path": str(paths.get("main_run_manifest_path", "")),
        "source_parquet_path": str(paths["input_publications_parquet"]),
        "model": config["model"],
        "prompt_version": config["prompt_version"],
        "schema_version": config["schema_version"],
        "review_confidence_threshold": float(config["review_confidence_threshold"]),
        "publications": int(len(publications_df)),
        "periods": int(len(periods)),
        "classified_affiliations": int(len(index_df)),
        "outputs": output_registry,
    }
    manifest_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    summary["run_manifest"] = str(manifest_path.resolve())
    return summary


def compare_keyword_vs_llm(
    config_path: str | Path,
    project_root: str | Path = ".",
) -> dict[str, Any]:
    config = load_sidecar_config(config_path, project_root=project_root)
    paths = resolve_sidecar_paths(config)
    prepare_affiliation_inputs(config_path, project_root=project_root)
    if not paths["classifications_parquet"].exists():
        raise FileNotFoundError("LLM classifications parquet is missing.")

    protocol = load_protocol(paths["main_protocol_path"])
    patterns = compile_category_patterns(protocol["classification"])
    keyword_fallback = fallback_label(protocol["classification"])
    keyword_classifier = make_classifier(patterns, fallback=keyword_fallback)

    unique_df = pd.read_parquet(paths["unique_affiliations_parquet"])
    llm_df = pd.read_parquet(paths["classifications_parquet"])
    merged = unique_df.merge(
        llm_df,
        on="cache_key",
        how="left",
        suffixes=("_input", ""),
    )
    merged["keyword_label"] = merged["affiliation_text_input"].apply(keyword_classifier)
    merged["llm_label"] = merged["label"].astype(str)
    merged["agree"] = merged["keyword_label"] == merged["llm_label"]
    merged["affiliation_text"] = merged["affiliation_text_input"].astype(str)

    comparison_cols = [
        "affiliation_text",
        "occurrence_count",
        "pmid_count",
        "keyword_label",
        "llm_label",
        "confidence",
        "confusion_note",
        "model",
        "prompt_version",
        "schema_version",
        "cache_key",
        "response_path",
        "status",
        "error",
        "agree",
    ]
    comparison_df = merged[comparison_cols].copy().sort_values(
        ["agree", "occurrence_count", "affiliation_text"],
        ascending=[True, False, True],
    )
    comparison_path = paths["tables_root"] / "affiliation_keyword_vs_llm.csv"
    _write_csv(comparison_df, comparison_path)

    summary_df = (
        comparison_df.groupby("keyword_label", as_index=False)
        .agg(
            unique_affiliations=("affiliation_text", "count"),
            occurrence_count=("occurrence_count", "sum"),
            agree_count=("agree", "sum"),
        )
        .assign(
            disagree_count=lambda x: x["unique_affiliations"] - x["agree_count"],
            agree_rate=lambda x: x["agree_count"] / x["unique_affiliations"],
        )
        .sort_values(["keyword_label"], ascending=[True])
    )
    overall = pd.DataFrame(
        [
            {
                "keyword_label": "__overall__",
                "unique_affiliations": int(len(comparison_df)),
                "occurrence_count": int(comparison_df["occurrence_count"].sum()),
                "agree_count": int(comparison_df["agree"].sum()),
                "disagree_count": int((~comparison_df["agree"]).sum()),
                "agree_rate": float(comparison_df["agree"].mean()) if len(comparison_df) else 0.0,
            }
        ]
    )
    summary_df = pd.concat([overall, summary_df], ignore_index=True)
    summary_path = paths["tables_root"] / "agreement_summary_by_keyword_label.csv"
    _write_csv(summary_df, summary_path)

    disagreements_df = comparison_df[~comparison_df["agree"]].copy()
    disagreements_path = paths["tables_root"] / "affiliation_label_disagreements.csv"
    _write_csv(disagreements_df, disagreements_path)

    shift_df = pd.crosstab(
        comparison_df["keyword_label"],
        comparison_df["llm_label"],
        dropna=False,
    ).reset_index()
    shift_path = paths["tables_root"] / "label_shift_matrix.csv"
    _write_csv(shift_df, shift_path)

    keyword_global_path = paths["project_root"] / "outputs" / "tables" / "global_network_metrics.csv"
    keyword_cluster_path = paths["project_root"] / "outputs" / "tables" / "cluster_interdisciplinarity_metrics.csv"
    llm_global_path = paths["tables_root"] / "global_network_metrics.csv"
    llm_cluster_path = paths["tables_root"] / "cluster_interdisciplinarity_metrics.csv"

    keyword_global = pd.read_csv(keyword_global_path).add_prefix("keyword_").rename(columns={"keyword_period": "period"})
    llm_global = pd.read_csv(llm_global_path).add_prefix("llm_").rename(columns={"llm_period": "period"})
    keyword_cluster = pd.read_csv(keyword_cluster_path).add_prefix("keyword_").rename(columns={"keyword_period": "period"})
    llm_cluster = pd.read_csv(llm_cluster_path).add_prefix("llm_").rename(columns={"llm_period": "period"})
    metrics_df = keyword_global.merge(llm_global, on="period", how="outer").merge(
        keyword_cluster,
        on="period",
        how="outer",
        suffixes=("", "_clusterdup"),
    ).merge(
        llm_cluster,
        on="period",
        how="outer",
        suffixes=("", "_clusterdup2"),
    )
    for column in list(metrics_df.columns):
        if column.startswith("keyword_"):
            candidate = column.replace("keyword_", "llm_", 1)
            if candidate in metrics_df.columns and pd.api.types.is_numeric_dtype(metrics_df[column]):
                metrics_df[f"delta_{column.removeprefix('keyword_')}"] = (
                    metrics_df[candidate] - metrics_df[column]
                )
    metrics_path = paths["tables_root"] / "network_metric_delta_summary.csv"
    _write_csv(metrics_df, metrics_path)

    return {
        "comparison_rows": int(len(comparison_df)),
        "disagreement_rows": int(len(disagreements_df)),
        "comparison_table": str(comparison_path.resolve()),
        "agreement_summary": str(summary_path.resolve()),
        "disagreements_table": str(disagreements_path.resolve()),
        "shift_matrix": str(shift_path.resolve()),
        "metric_deltas": str(metrics_path.resolve()),
    }


def run_sidecar(
    config_path: str | Path,
    project_root: str | Path = ".",
    *,
    limit: int | None = None,
    clean_output: bool = False,
    skip_classification: bool = False,
) -> dict[str, Any]:
    extraction = prepare_affiliation_inputs(config_path, project_root=project_root)
    config = load_sidecar_config(config_path, project_root=project_root)
    classification: dict[str, Any] = {"skipped": bool(skip_classification)}
    if not skip_classification:
        classification = classify_affiliations(
            config_path=config_path,
            project_root=project_root,
            limit=limit,
            execution_mode=config["execution_mode"],
        )
    missing_cache_keys = _missing_cache_keys(config_path, project_root=project_root)
    if missing_cache_keys and not bool(config["allow_partial_run"]):
        return {
            "extraction": extraction,
            "classification": classification,
            "analysis_skipped_reason": (
                f"{len(missing_cache_keys)} uncached affiliations remain; "
                "downstream analysis is blocked until classification is complete."
            ),
        }

    analysis = run_parallel_analysis(
        config_path=config_path,
        project_root=project_root,
        clean_output=clean_output,
    )
    comparison = compare_keyword_vs_llm(
        config_path=config_path,
        project_root=project_root,
    )
    return {
        "extraction": extraction,
        "classification": classification,
        "analysis": analysis,
        "comparison": comparison,
    }
