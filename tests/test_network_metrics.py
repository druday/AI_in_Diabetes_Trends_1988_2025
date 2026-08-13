import pandas as pd

from ai_diabetology.network_metrics import (
    annotate_node_types,
    build_collaboration_graph,
    cluster_interdisciplinarity_metrics,
    component_field_collaboration_tables,
    core_newcomer_metrics,
    exact_three_field_timelapse_profiles,
    focal_domain_exact_two_field_profiles,
    global_metrics,
)


def test_build_collaboration_graph_counts_weighted_edges() -> None:
    publications = [
        ["a", "b", "c"],
        ["a", "b"],
        ["d"],
    ]
    graph = build_collaboration_graph(publications)
    assert graph.number_of_nodes() == 4
    assert graph.number_of_edges() == 3
    assert graph["a"]["b"]["weight"] == 2


def test_core_newcomer_metrics_basic_case() -> None:
    previous = build_collaboration_graph([["a", "b"], ["b", "c"]])
    current = build_collaboration_graph([["a", "b"], ["a", "d"], ["d", "e"]])
    metrics = core_newcomer_metrics(previous, current)
    assert metrics["returning_nodes"] == 2
    assert metrics["new_nodes"] == 2
    assert metrics["edge_growth_per_new"] > 0


def test_global_metrics_non_empty_graph() -> None:
    graph = build_collaboration_graph([["a", "b"], ["b", "c"]])
    metrics = global_metrics(graph)
    assert metrics["nodes"] == 3
    assert metrics["edges"] == 2
    assert metrics["median_degree"] == 1.0
    assert metrics["largest_connected_component_size"] == 3


def test_cluster_interdisciplinarity_metrics_supports_more_than_three_fields() -> None:
    graph = build_collaboration_graph([["a", "b", "c", "d"], ["e"]])
    field_map = {
        "a": "Technical_AI_Informatics",
        "b": "Endocrinology_Diabetes",
        "c": "Ophthalmology_Vision",
        "d": "General_Clinical_Medicine",
        "e": "Other",
    }
    annotate_node_types(graph, lambda node: field_map[node])
    metrics = cluster_interdisciplinarity_metrics(graph)
    assert metrics["three_or_more_field_components"] == 1
    assert metrics["three_field_components"] == 1
    assert metrics["max_distinct_key_fields_in_component"] == 4


def test_component_field_collaboration_tables_capture_pairs_and_exact_combinations() -> None:
    graph = build_collaboration_graph([["a", "b", "c"], ["d", "e", "g"], ["f"]])
    field_map = {
        "a": "Technical_AI_Informatics",
        "b": "Endocrinology_Diabetes",
        "c": "General_Clinical_Medicine",
        "d": "Technical_AI_Informatics",
        "e": "Ophthalmology_Vision",
        "g": "Technical_AI_Informatics",
        "f": "Other",
    }
    annotate_node_types(graph, lambda node: field_map[node])

    pairwise_df, combo_df = component_field_collaboration_tables(graph, fallback_label="Other")

    assert len(pairwise_df) == 5
    tech_endo = pairwise_df[
        (pairwise_df["field_a"] == "Endocrinology_Diabetes")
        & (pairwise_df["field_b"] == "Technical_AI_Informatics")
    ]
    assert int(tech_endo["component_count"].iloc[0]) == 1
    tech_diagonal = pairwise_df[
        (pairwise_df["field_a"] == "Technical_AI_Informatics")
        & (pairwise_df["field_b"] == "Technical_AI_Informatics")
    ]
    assert int(tech_diagonal["component_count"].iloc[0]) == 1
    assert bool(tech_diagonal["is_diagonal"].iloc[0]) is True
    assert float(tech_diagonal["log_component_count"].iloc[0]) > 0.0

    combo_3 = combo_df[combo_df["combination_size"] == "3"]
    assert len(combo_3) == 1
    assert combo_3["combination_label"].iloc[0] == (
        "Endocrinology_Diabetes + General_Clinical_Medicine + Technical_AI_Informatics"
    )


def test_focal_domain_exact_two_field_profiles_builds_directional_partner_shares() -> None:
    combos = pd.DataFrame(
        [
            {
                "period": "2025-2025",
                "combination_size": "2",
                "combination_size_exact": 2,
                "combination_label": "General_Clinical_Medicine + Technical_AI_Informatics",
                "component_count": 30,
            },
            {
                "period": "2025-2025",
                "combination_size": "2",
                "combination_size_exact": 2,
                "combination_label": "General_Clinical_Medicine + Public_Health_Epidemiology",
                "component_count": 10,
            },
            {
                "period": "2025-2025",
                "combination_size": "3",
                "combination_size_exact": 3,
                "combination_label": "General_Clinical_Medicine + Public_Health_Epidemiology + Technical_AI_Informatics",
                "component_count": 99,
            },
        ]
    )

    profile = focal_domain_exact_two_field_profiles(
        combos,
        focal_domains=[
            "Technical_AI_Informatics",
            "General_Clinical_Medicine",
            "Public_Health_Epidemiology",
        ],
    )

    clinical_rows = profile[profile["focal_domain"] == "General_Clinical_Medicine"].sort_values(
        "partner_rank_within_focal_domain"
    )
    assert clinical_rows["partner_domain"].tolist() == [
        "Technical_AI_Informatics",
        "Public_Health_Epidemiology",
    ]
    assert clinical_rows["component_count"].tolist() == [30, 10]
    assert clinical_rows["focal_domain_total_exact_two_field_components"].tolist() == [40, 40]
    assert clinical_rows["partner_share_within_focal_domain"].tolist() == [0.75, 0.25]

    tech_rows = profile[profile["focal_domain"] == "Technical_AI_Informatics"]
    assert len(tech_rows) == 1
    assert tech_rows.iloc[0]["partner_domain"] == "General_Clinical_Medicine"
    assert tech_rows.iloc[0]["partner_share_within_focal_domain"] == 1.0


def test_exact_three_field_timelapse_profiles_builds_stable_display_union() -> None:
    combos = pd.DataFrame(
        [
            {
                "period": "1988-2015",
                "combination_size": "3",
                "combination_label": "A + B + C",
                "component_count": 5,
                "component_share_pct": 1.0,
            },
            {
                "period": "1988-2015",
                "combination_size": "3",
                "combination_label": "A + B + D",
                "component_count": 4,
                "component_share_pct": 0.8,
            },
            {
                "period": "2016-2019",
                "combination_size": "3",
                "combination_label": "A + B + C",
                "component_count": 8,
                "component_share_pct": 1.2,
            },
            {
                "period": "2016-2019",
                "combination_size": "3",
                "combination_label": "A + C + D",
                "component_count": 6,
                "component_share_pct": 1.0,
            },
            {
                "period": "2016-2019",
                "combination_size": "2",
                "combination_label": "A + B",
                "component_count": 99,
                "component_share_pct": 9.9,
            },
        ]
    )

    timelapse = exact_three_field_timelapse_profiles(combos, top_k=2)

    assert set(timelapse["combination_label"]) == {"A + B + C", "A + C + D"}
    assert len(timelapse) == 4

    early_rows = timelapse[timelapse["period"] == "1988-2015"].sort_values("rank_within_period")
    assert early_rows["combination_label"].tolist() == ["A + B + C", "A + C + D"]
    assert early_rows["component_count"].tolist() == [5, 0]

    late_rows = timelapse[timelapse["period"] == "2016-2019"].sort_values("rank_within_period")
    assert late_rows["combination_label"].tolist() == ["A + B + C", "A + C + D"]
    assert late_rows["component_count"].tolist() == [8, 6]

    emerging = timelapse[
        (timelapse["period"] == "1988-2015") & (timelapse["combination_label"] == "A + C + D")
    ].iloc[0]
    assert emerging["first_period_seen"] == "2016-2019"
    assert emerging["last_period_seen"] == "2016-2019"
    assert int(emerging["net_change_from_previous_period"]) == 0
