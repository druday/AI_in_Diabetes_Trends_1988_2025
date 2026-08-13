from __future__ import annotations

from pathlib import Path
import re
from typing import Any, Callable

import pandas as pd

from ai_diabetology.classification import (
    compile_category_patterns,
    fallback_label,
    make_classifier,
)


def normalize_affiliation_lookup_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text).strip())


def classification_source(protocol: dict[str, Any]) -> str:
    analysis_cfg = protocol.get("analysis", {})
    return str(analysis_cfg.get("classification_source", "keyword")).strip().lower()


def llm_classifications_path(protocol: dict[str, Any], project_root: Path) -> Path:
    analysis_cfg = protocol.get("analysis", {})
    configured = str(
        analysis_cfg.get(
            "llm_classifications_parquet",
            "data/llm/results/affiliation_classifications.parquet",
        )
    )
    path = Path(configured)
    return path if path.is_absolute() else (project_root / path).resolve()


def build_protocol_classifier(
    protocol: dict[str, Any],
    *,
    project_root: str | Path,
) -> tuple[Callable[[str], str], str]:
    source = classification_source(protocol)
    fallback = fallback_label(protocol["classification"])

    if source == "keyword":
        patterns = compile_category_patterns(protocol["classification"])
        return make_classifier(patterns, fallback=fallback), fallback

    if source != "llm":
        raise ValueError(
            f"Unsupported analysis.classification_source '{source}'. Expected 'keyword' or 'llm'."
        )

    project_root_path = Path(project_root).resolve()
    parquet_path = llm_classifications_path(protocol, project_root_path)
    if not parquet_path.exists():
        raise FileNotFoundError(
            f"LLM classifications parquet not found: {parquet_path}. "
            "Run the LLM sidecar classification first or switch analysis.classification_source."
        )

    df = pd.read_parquet(parquet_path)
    if "affiliation_text" not in df.columns or "label" not in df.columns:
        raise ValueError(
            "LLM classifications parquet must contain 'affiliation_text' and 'label' columns."
        )

    if "classified_at" in df.columns:
        df = df.sort_values(["classified_at", "affiliation_text"], ascending=[True, True])
    lookup: dict[str, str] = {}
    for _, row in df.iterrows():
        normalized = normalize_affiliation_lookup_text(str(row.get("affiliation_text", "")))
        if not normalized:
            continue
        label = str(row.get("label", "")).strip() or fallback
        lookup[normalized] = label

    def _classify(name: str) -> str:
        normalized = normalize_affiliation_lookup_text(name)
        if normalized not in lookup:
            raise KeyError(
                "No canonical LLM classification found for affiliation: "
                f"{name!r}. Canonical reruns do not fall back to keyword matching."
            )
        return lookup[normalized]

    return _classify, fallback
