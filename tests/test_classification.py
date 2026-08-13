from ai_diabetology.classification import classify_institution, compile_category_patterns


def test_classification_patterns_respect_ordered_categories_and_fallback() -> None:
    cfg = {
        "fallback_label": "Other",
        "categories": [
            {
                "label": "Technical_AI_Informatics",
                "keywords": ["computer science", "bioengineering"],
                "color": "#1d4ed8",
            },
            {
                "label": "Endocrinology_Diabetes",
                "keywords": ["diabetes center", "endocrinology"],
                "color": "#dc2626",
            },
        ],
    }
    patterns = compile_category_patterns(cfg)

    assert (
        classify_institution(
            "school of bioengineering and computer science, diabetes center",
            patterns,
            fallback="Other",
        )
        == "Technical_AI_Informatics"
    )
    assert (
        classify_institution("department of endocrinology, diabetes center", patterns, fallback="Other")
        == "Endocrinology_Diabetes"
    )
    assert classify_institution("school of humanities", patterns, fallback="Other") == "Other"
