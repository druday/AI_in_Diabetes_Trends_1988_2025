from __future__ import annotations

from collections import Counter
from itertools import combinations
from typing import Callable, Iterable

import networkx as nx
import numpy as np
import pandas as pd

def build_collaboration_graph(publication_institutions: Iterable[list[str]]) -> nx.Graph:
    edge_counter: Counter[tuple[str, str]] = Counter()
    graph = nx.Graph()

    for institutions in publication_institutions:
        unique = list(dict.fromkeys(inst for inst in institutions if inst))
        graph.add_nodes_from(unique)
        for a, b in combinations(sorted(unique), 2):
            edge_counter[(a, b)] += 1

    for (a, b), weight in edge_counter.items():
        graph.add_edge(a, b, weight=weight)

    return graph


def annotate_node_types(graph: nx.Graph, classify: Callable[[str], str]) -> None:
    for node in graph.nodes():
        graph.nodes[node]["type"] = classify(node)


def largest_connected_component_subgraph(graph: nx.Graph) -> nx.Graph:
    if graph.number_of_nodes() == 0:
        return graph.copy()
    if nx.is_empty(graph):
        return graph.copy()
    component_nodes = max(nx.connected_components(graph), key=len)
    return graph.subgraph(component_nodes).copy()


def global_metrics(graph: nx.Graph) -> dict[str, float | int]:
    nodes = graph.number_of_nodes()
    edges = graph.number_of_edges()
    density = nx.density(graph) if nodes > 1 else 0.0
    avg_degree = (2 * edges / nodes) if nodes else 0.0
    median_degree = 0.0
    if nodes:
        degree_values = sorted(float(deg) for _, deg in graph.degree())
        mid = len(degree_values) // 2
        if len(degree_values) % 2 == 1:
            median_degree = degree_values[mid]
        else:
            median_degree = (degree_values[mid - 1] + degree_values[mid]) / 2.0

    if edges > 0:
        avg_clustering = nx.average_clustering(graph, weight="weight")
    else:
        avg_clustering = 0.0
    largest_cc = len(max(nx.connected_components(graph), key=len)) if nodes > 0 else 0

    return {
        "nodes": nodes,
        "edges": edges,
        "density": density,
        "avg_degree": avg_degree,
        "median_degree": median_degree,
        "avg_clustering_weighted": avg_clustering,
        "largest_connected_component_size": largest_cc,
    }


def top_centrality_table(
    graph: nx.Graph,
    top_n: int = 10,
    use_lcc_for_path_metrics: bool = True,
) -> pd.DataFrame:
    degree_input = graph
    path_input = largest_connected_component_subgraph(graph) if use_lcc_for_path_metrics else graph

    degree_scores = nx.degree_centrality(degree_input) if degree_input.number_of_nodes() else {}
    between_scores = (
        nx.betweenness_centrality(path_input, weight="weight", normalized=True)
        if path_input.number_of_nodes()
        else {}
    )

    top_degree = sorted(degree_scores.items(), key=lambda x: x[1], reverse=True)[:top_n]
    top_between = sorted(between_scores.items(), key=lambda x: x[1], reverse=True)[:top_n]

    max_len = max(len(top_degree), len(top_between), top_n)
    rows: list[dict[str, object]] = []
    for idx in range(max_len):
        row = {"rank": idx + 1}
        if idx < len(top_degree):
            row["degree_node"] = top_degree[idx][0]
            row["degree_score"] = top_degree[idx][1]
        else:
            row["degree_node"] = ""
            row["degree_score"] = 0.0

        if idx < len(top_between):
            row["betweenness_node"] = top_between[idx][0]
            row["betweenness_score"] = top_between[idx][1]
        else:
            row["betweenness_node"] = ""
            row["betweenness_score"] = 0.0
        rows.append(row)

    return pd.DataFrame(rows)


def core_newcomer_metrics(prev_graph: nx.Graph, curr_graph: nx.Graph) -> dict[str, float | int]:
    prev_nodes = set(prev_graph.nodes())
    curr_nodes = set(curr_graph.nodes())
    returning = prev_nodes & curr_nodes
    new_nodes = curr_nodes - prev_nodes

    if len(returning) > 1:
        density_existing = nx.density(curr_graph.subgraph(returning))
    else:
        density_existing = 0.0

    if len(new_nodes) > 1:
        density_new = nx.density(curr_graph.subgraph(new_nodes))
    else:
        density_new = 0.0

    edges_with_new = sum(1 for u, v in curr_graph.edges() if u in new_nodes or v in new_nodes)
    edge_growth_per_new = edges_with_new / len(new_nodes) if new_nodes else 0.0

    return {
        "density_existing": density_existing,
        "density_new": density_new,
        "edge_growth_per_new": edge_growth_per_new,
        "new_nodes": len(new_nodes),
        "returning_nodes": len(returning),
    }


def cluster_interdisciplinarity_metrics(graph: nx.Graph) -> dict[str, int | float]:
    components = list(nx.connected_components(graph))
    single_field = 0
    two_field = 0
    three_or_more_field = 0
    distinct_counts: list[int] = []

    for component in components:
        component_types = {str(graph.nodes[node].get("type", "Other")) for node in component}
        key_types = {field for field in component_types if field != "Other"}
        distinct_counts.append(len(key_types))
        if len(key_types) == 1:
            single_field += 1
        elif len(key_types) == 2:
            two_field += 1
        elif len(key_types) >= 3:
            three_or_more_field += 1

    total = len(components) if components else 1
    return {
        "num_components": len(components),
        "single_field_components": single_field,
        "two_field_components": two_field,
        "three_field_components": three_or_more_field,
        "three_or_more_field_components": three_or_more_field,
        "single_field_ratio": single_field / total,
        "two_field_ratio": two_field / total,
        "three_field_ratio": three_or_more_field / total,
        "three_or_more_field_ratio": three_or_more_field / total,
        "mean_distinct_key_fields_per_component": (
            float(sum(distinct_counts)) / len(distinct_counts) if distinct_counts else 0.0
        ),
        "max_distinct_key_fields_in_component": max(distinct_counts, default=0),
    }


def component_field_collaboration_tables(
    graph: nx.Graph,
    *,
    fallback_label: str = "Other",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    components = list(nx.connected_components(graph))
    total_components = len(components) if components else 1
    pair_counter: Counter[tuple[str, str]] = Counter()
    combo_counter: Counter[tuple[str, ...]] = Counter()

    for component in components:
        field_counts: Counter[str] = Counter(
            str(graph.nodes[node].get("type", fallback_label)) for node in component
        )
        key_types = sorted(field for field in field_counts if field != fallback_label)
        for field in key_types:
            if field_counts[field] >= 2:
                pair_counter[(field, field)] += 1
        if len(key_types) >= 2:
            for pair in combinations(key_types, 2):
                pair_counter[pair] += 1
            combo_counter[tuple(key_types)] += 1

    pair_rows: list[dict[str, object]] = []
    for (field_a, field_b), count in sorted(
        pair_counter.items(),
        key=lambda item: (-item[1], item[0][0] != item[0][1], item[0][0], item[0][1]),
    ):
        pair_rows.append(
            {
                "field_a": field_a,
                "field_b": field_b,
                "is_diagonal": bool(field_a == field_b),
                "component_count": int(count),
                "log_component_count": float(np.log10(1.0 + float(count))),
                "component_share": float(count) / float(total_components),
                "component_share_pct": 100.0 * float(count) / float(total_components),
            }
        )

    combo_rows: list[dict[str, object]] = []
    sorted_combos = sorted(
        combo_counter.items(),
        key=lambda item: (-item[1], len(item[0]), item[0]),
    )
    ranks_by_bucket: Counter[str] = Counter()
    for combo, count in sorted_combos:
        combo_size = len(combo)
        if combo_size < 2:
            continue
        size_bucket = "4+" if combo_size >= 4 else str(combo_size)
        ranks_by_bucket[size_bucket] += 1
        combo_rows.append(
            {
                "combination_size": size_bucket,
                "combination_size_exact": combo_size,
                "combination_label": " + ".join(combo),
                "component_count": int(count),
                "component_share": float(count) / float(total_components),
                "component_share_pct": 100.0 * float(count) / float(total_components),
                "rank_within_size": int(ranks_by_bucket[size_bucket]),
            }
        )

    return pd.DataFrame(pair_rows), pd.DataFrame(combo_rows)


def focal_domain_exact_two_field_profiles(
    combinations_df: pd.DataFrame,
    *,
    focal_domains: list[str],
) -> pd.DataFrame:
    subset = combinations_df[combinations_df["combination_size"] == "2"].copy()
    rows: list[dict[str, object]] = []

    for row in subset.itertuples(index=False):
        fields = [part.strip() for part in str(row.combination_label).split(" + ")]
        if len(fields) != 2:
            continue
        field_a, field_b = fields
        count = int(row.component_count)
        for focal, partner in ((field_a, field_b), (field_b, field_a)):
            if focal not in focal_domains:
                continue
            rows.append(
                {
                    "period": str(row.period),
                    "focal_domain": focal,
                    "partner_domain": partner,
                    "component_count": count,
                }
            )

    profile_df = pd.DataFrame(rows)
    if profile_df.empty:
        return pd.DataFrame(
            columns=[
                "period",
                "focal_domain",
                "partner_domain",
                "component_count",
                "focal_domain_total_exact_two_field_components",
                "partner_share_within_focal_domain",
                "partner_rank_within_focal_domain",
            ]
        )

    totals = (
        profile_df.groupby(["period", "focal_domain"], as_index=False)["component_count"]
        .sum()
        .rename(columns={"component_count": "focal_domain_total_exact_two_field_components"})
    )
    profile_df = profile_df.merge(totals, on=["period", "focal_domain"], how="left")
    profile_df["partner_share_within_focal_domain"] = profile_df.apply(
        lambda row: (
            float(row["component_count"]) / float(row["focal_domain_total_exact_two_field_components"])
            if float(row["focal_domain_total_exact_two_field_components"]) > 0
            else 0.0
        ),
        axis=1,
    )
    profile_df = profile_df.sort_values(
        ["period", "focal_domain", "component_count", "partner_domain"],
        ascending=[True, True, False, True],
    ).reset_index(drop=True)
    profile_df["partner_rank_within_focal_domain"] = (
        profile_df.groupby(["period", "focal_domain"]).cumcount() + 1
    )
    return profile_df


def exact_three_field_timelapse_profiles(
    combinations_df: pd.DataFrame,
    *,
    top_k: int = 12,
) -> pd.DataFrame:
    subset = combinations_df[combinations_df["combination_size"] == "3"].copy()
    if subset.empty:
        return pd.DataFrame(
            columns=[
                "period",
                "combination_label",
                "component_count",
                "component_share_pct",
                "rank_within_period",
                "is_top_k_displayed",
                "first_period_seen",
                "last_period_seen",
                "net_change_from_previous_period",
            ]
        )

    subset["period"] = subset["period"].astype(str)
    subset["combination_label"] = subset["combination_label"].astype(str)
    subset["component_count"] = subset["component_count"].astype(int)
    if "component_share_pct" not in subset.columns:
        subset["component_share_pct"] = 0.0
    subset["component_share_pct"] = subset["component_share_pct"].astype(float)

    period_order = list(dict.fromkeys(subset["period"].tolist()))
    subset["period"] = pd.Categorical(subset["period"], categories=period_order, ordered=True)

    combo_stats = (
        subset.groupby("combination_label", as_index=False)
        .agg(
            max_component_count=("component_count", "max"),
            cumulative_component_count=("component_count", "sum"),
        )
        .sort_values(
            ["max_component_count", "cumulative_component_count", "combination_label"],
            ascending=[False, False, True],
        )
        .reset_index(drop=True)
    )
    display_labels = combo_stats["combination_label"].head(top_k).astype(str).tolist()

    selected = subset[subset["combination_label"].isin(display_labels)].copy()
    positive_seen = (
        selected[selected["component_count"] > 0]
        .groupby("combination_label")["period"]
        .agg(["min", "max"])
        .rename(columns={"min": "first_period_seen", "max": "last_period_seen"})
    )

    selected_lookup = {
        (str(row.period), str(row.combination_label)): row
        for row in selected.itertuples(index=False)
    }

    rows: list[dict[str, object]] = []
    for label in display_labels:
        first_seen = ""
        last_seen = ""
        if label in positive_seen.index:
            first_seen = str(positive_seen.loc[label, "first_period_seen"])
            last_seen = str(positive_seen.loc[label, "last_period_seen"])
        for period in period_order:
            key = (str(period), label)
            source_row = selected_lookup.get(key)
            component_count = int(getattr(source_row, "component_count", 0))
            component_share_pct = float(getattr(source_row, "component_share_pct", 0.0))
            rows.append(
                {
                    "period": str(period),
                    "combination_label": label,
                    "component_count": component_count,
                    "component_share_pct": component_share_pct,
                    "is_top_k_displayed": True,
                    "first_period_seen": first_seen,
                    "last_period_seen": last_seen,
                }
            )

    display_df = pd.DataFrame(rows)
    display_df["period"] = pd.Categorical(display_df["period"], categories=period_order, ordered=True)
    display_df = display_df.sort_values(
        ["period", "component_count", "combination_label"],
        ascending=[True, False, True],
    ).reset_index(drop=True)
    display_df["rank_within_period"] = display_df.groupby("period", observed=False).cumcount() + 1
    display_df["net_change_from_previous_period"] = (
        display_df.sort_values(["combination_label", "period"])
        .groupby("combination_label")["component_count"]
        .diff()
        .fillna(display_df["component_count"])
        .astype(int)
    )
    display_df["period"] = display_df["period"].astype(str)
    return display_df[
        [
            "period",
            "combination_label",
            "component_count",
            "component_share_pct",
            "rank_within_period",
            "is_top_k_displayed",
            "first_period_seen",
            "last_period_seen",
            "net_change_from_previous_period",
        ]
    ]
