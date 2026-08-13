import pandas as pd
import pytest

from ai_diabetology.affiliations import (
    approximate_publication_date,
    dedupe_preserve_order,
    extract_institution_from_affiliation,
    normalize_affiliation_text,
    record_passes_screening,
)


def test_normalize_affiliation_text() -> None:
    value = normalize_affiliation_text("Department of Prosthodontics, Universitas Gadjah Mada.")
    assert value == "department of prosthodontics universitas gadjah mada"


def test_extract_institution_prefers_keyword_hint() -> None:
    raw = "Division of Surgery, Massachusetts General Hospital, Boston, MA, United States."
    institution = extract_institution_from_affiliation(
        raw,
        keyword_hints=["university", "hospital", "institute"],
        extraction_mode="keyword_hint_segment",
    )
    assert institution == "massachusetts general hospital"


def test_extract_institution_exact_affiliation_preserves_raw_text() -> None:
    raw = "Division of Surgery, Massachusetts General Hospital, Boston, MA, United States."
    institution = extract_institution_from_affiliation(
        raw,
        keyword_hints=["university", "hospital", "institute"],
        extraction_mode="exact_affiliation",
    )
    assert institution == raw


def test_extract_institution_rejects_unknown_mode() -> None:
    with pytest.raises(ValueError, match="Unsupported institution extraction mode"):
        extract_institution_from_affiliation(
            "Division of Surgery, Massachusetts General Hospital",
            keyword_hints=["hospital"],
            extraction_mode="invalid",
        )


def test_approximate_publication_date_year_only() -> None:
    dt = approximate_publication_date("2024")
    assert isinstance(dt, pd.Timestamp)
    assert int(dt.year) == 2024


def test_dedupe_preserve_order() -> None:
    assert dedupe_preserve_order(["a", "b", "a", "c"]) == ["a", "b", "c"]


def test_record_passes_screening_uses_title_abstract_and_mesh() -> None:
    screening_cfg = {
        "enabled": True,
        "include_terms": ["diabetes", "diabetic", "diabetology"],
    }
    diabetes_record = {"TI": "Artificial intelligence in diabetology", "AB": "", "MH": []}
    non_diabetes_record = {"TI": "Artificial intelligence in radiology", "AB": "", "MH": []}
    mesh_only_record = {"TI": "Artificial intelligence", "AB": "", "MH": ["Diabetes Mellitus"]}

    assert record_passes_screening(diabetes_record, screening_cfg) is True
    assert record_passes_screening(mesh_only_record, screening_cfg) is True
    assert record_passes_screening(non_diabetes_record, screening_cfg) is False
