from __future__ import annotations

import re
from typing import Any, Callable


DEFAULT_FALLBACK_LABEL = "Other"
DEFAULT_FALLBACK_COLOR = "#bdbdbd"
LEGACY_CATEGORY_MAP = {
    "dental": {"label": "Dental", "color": "#e31a1c"},
    "medical": {"label": "Medical", "color": "#1f78b4"},
    "technical": {"label": "Technical", "color": "#33a02c"},
}


def _build_pattern(terms: list[str]) -> re.Pattern[str]:
    escaped = [re.escape(term).replace(r"\ ", r"\s+") for term in terms]
    joined = "|".join(escaped)
    return re.compile(rf"\b({joined})\b", re.IGNORECASE)


def normalize_classification_config(classification_cfg: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(classification_cfg, dict):
        raise ValueError("classification must be a mapping.")

    if isinstance(classification_cfg.get("categories"), list):
        categories = classification_cfg.get("categories", [])
        fallback_label = str(
            classification_cfg.get("fallback_label", DEFAULT_FALLBACK_LABEL)
        ).strip() or DEFAULT_FALLBACK_LABEL
        fallback_color = str(
            classification_cfg.get("fallback_color", DEFAULT_FALLBACK_COLOR)
        ).strip() or DEFAULT_FALLBACK_COLOR
        normalized: list[dict[str, Any]] = []
        labels_seen: set[str] = set()
        colors_seen: set[str] = set()

        for index, raw in enumerate(categories):
            if not isinstance(raw, dict):
                raise ValueError(
                    f"classification.categories[{index}] must be a mapping with label/keywords/color."
                )
            label = str(raw.get("label", "")).strip()
            if not label:
                raise ValueError(f"classification.categories[{index}] is missing a non-empty label.")
            if label == fallback_label:
                raise ValueError(
                    f"classification.categories[{index}] label '{label}' duplicates fallback_label."
                )
            if label in labels_seen:
                raise ValueError(f"classification contains duplicate category label '{label}'.")

            keywords = [
                str(value).strip()
                for value in raw.get("keywords", [])
                if str(value).strip()
            ]
            if not keywords:
                raise ValueError(
                    f"classification category '{label}' must define at least one keyword."
                )

            color = str(raw.get("color", "")).strip()
            if not color:
                raise ValueError(
                    f"classification category '{label}' must define a non-empty color."
                )
            if color in colors_seen:
                raise ValueError(f"classification contains duplicate category color '{color}'.")

            labels_seen.add(label)
            colors_seen.add(color)
            normalized.append({"label": label, "keywords": keywords, "color": color})

        return {
            "categories": normalized,
            "fallback_label": fallback_label,
            "fallback_color": fallback_color,
        }

    legacy_categories: list[dict[str, Any]] = []
    for key, meta in LEGACY_CATEGORY_MAP.items():
        keywords = [
            str(value).strip() for value in classification_cfg.get(key, []) if str(value).strip()
        ]
        if keywords:
            legacy_categories.append(
                {
                    "label": meta["label"],
                    "keywords": keywords,
                    "color": meta["color"],
                }
            )
    if not legacy_categories:
        raise ValueError(
            "classification must define either categories[] or legacy dental/medical/technical keywords."
        )
    return {
        "categories": legacy_categories,
        "fallback_label": DEFAULT_FALLBACK_LABEL,
        "fallback_color": DEFAULT_FALLBACK_COLOR,
    }


def category_labels(classification_cfg: dict[str, Any], include_fallback: bool = True) -> list[str]:
    normalized = normalize_classification_config(classification_cfg)
    labels = [str(category["label"]) for category in normalized["categories"]]
    if include_fallback:
        labels.append(str(normalized["fallback_label"]))
    return labels


def category_color_map(
    classification_cfg: dict[str, Any],
    extra_colors: dict[str, str] | None = None,
) -> dict[str, str]:
    normalized = normalize_classification_config(classification_cfg)
    color_map = {
        str(category["label"]): str(category["color"])
        for category in normalized["categories"]
    }
    color_map[str(normalized["fallback_label"])] = str(normalized["fallback_color"])
    if extra_colors:
        color_map.update({str(key): str(value) for key, value in extra_colors.items()})
    return color_map


def compile_category_patterns(classification_cfg: dict[str, Any]) -> list[tuple[str, re.Pattern[str]]]:
    normalized = normalize_classification_config(classification_cfg)
    return [
        (str(category["label"]), _build_pattern(list(category["keywords"])))
        for category in normalized["categories"]
    ]


def fallback_label(classification_cfg: dict[str, Any]) -> str:
    normalized = normalize_classification_config(classification_cfg)
    return str(normalized["fallback_label"])


def classify_institution(
    name: str,
    patterns: list[tuple[str, re.Pattern[str]]],
    fallback: str = DEFAULT_FALLBACK_LABEL,
) -> str:
    for category, pattern in patterns:
        if pattern.search(name):
            return category
    return fallback


def make_classifier(
    patterns: list[tuple[str, re.Pattern[str]]],
    fallback: str = DEFAULT_FALLBACK_LABEL,
) -> Callable[[str], str]:
    def _classifier(name: str) -> str:
        return classify_institution(name, patterns, fallback=fallback)

    return _classifier
