#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
import unicodedata
from collections import Counter
from itertools import combinations
from pathlib import Path

import networkx as nx
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ai_diabetology.classifier_loader import build_protocol_classifier
from ai_diabetology.config import load_protocol
from ai_diabetology.funding import FUNDING_OUTPUT_ORDER
from ai_diabetology.geography import map_country_to_who_region
from ai_diabetology.network_metrics import (
    annotate_node_types,
    build_collaboration_graph,
    cluster_interdisciplinarity_metrics,
    component_field_collaboration_tables,
    exact_three_field_timelapse_profiles,
    focal_domain_exact_two_field_profiles,
    global_metrics,
)


FUNDING_SLUGS = {
    "US_FEDERAL_FUNDED": "us_federal_funded",
    "NON_US_OR_INTL_FUNDED": "non_us_or_intl_funded",
    "NO_GRANT_LISTED": "no_grant_listed",
}
FOCAL_DOMAINS = [
    "Technical_AI_Informatics",
    "Endocrinology_Diabetes",
    "General_Clinical_Medicine",
    "Public_Health_Epidemiology",
]
FIELD_SHORT_LABELS = {
    "Technical_AI_Informatics": "Tech/AI",
    "Endocrinology_Diabetes": "Endocrino",
    "Ophthalmology_Vision": "Ophthal",
    "Complications_Cardiometabolic_Nephrology_Neurology": "Complications",
    "Pediatrics_Maternal_Health": "Peds/Maternal",
    "General_Clinical_Medicine": "Clinical Med",
    "Public_Health_Epidemiology": "Public Health",
    "Nutrition": "Nutrition",
    "Nursing_Diabetes_Education": "Nursing",
    "Behavioral_Psychological": "Behavioral",
    "Exercise_Lifestyle": "Exercise",
    "Industry_Digital_Health_Device": "Industry",
}
ROLE_ORDER = ["Core", "Semi-Peripheral", "Peripheral", "Isolate", "Absent"]
COUNTRY_ALIAS_MAP = {
    "usa": "united states",
    "england": "united kingdom",
    "scotland": "united kingdom",
    "south korea": "republic of korea",
    "korea south": "republic of korea",
    "vietnam": "viet nam",
}
FUNDED_PROFILE_GROUPS = {
    "FUNDED": {"US_FEDERAL_FUNDED", "NON_US_OR_INTL_FUNDED"},
    "NO_GRANT_LISTED": {"NO_GRANT_LISTED"},
}


def short_combination_label(text: str) -> str:
    parts = [FIELD_SHORT_LABELS.get(part.strip(), part.strip()) for part in str(text).split(" + ")]
    return " + ".join(parts)


def parse_listlike(value) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        for loader in (json.loads, ast.literal_eval):
            try:
                parsed = loader(text)
            except Exception:
                continue
            if isinstance(parsed, list):
                return parsed
    return []


def parse_institutions(value) -> list[str]:
    return [str(item).strip() for item in parse_listlike(value) if str(item).strip()]


def parse_country_pairs(value) -> list[dict[str, str]]:
    rows = []
    for item in parse_listlike(value):
        if not isinstance(item, dict):
            continue
        institution = str(item.get("institution", "")).strip()
        country = str(item.get("country", "")).strip()
        rows.append({"institution": institution, "country": country})
    return rows


def normalize_country_token(value: str) -> str:
    folded = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii")
    folded = folded.lower().strip()
    folded = re.sub(r"[^a-z0-9\s]", " ", folded)
    folded = re.sub(r"\s+", " ", folded).strip()
    if not folded:
        return ""
    return COUNTRY_ALIAS_MAP.get(folded, folded)


def display_country(value: str) -> str:
    parts = str(value).split()
    return " ".join(part.upper() if len(part) <= 3 else part.capitalize() for part in parts)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh summary tables from completed GraphML outputs.")
    parser.add_argument("--project-root", default=str(PROJECT_ROOT), help="Repository root.")
    return parser.parse_args()


def load_period_labels(project_root: Path) -> list[str]:
    period_path = project_root / "outputs" / "tables" / "period_definitions.csv"
    if period_path.exists():
        df = pd.read_csv(period_path)
        return df["label"].astype(str).tolist()
    protocol = load_protocol(project_root / "config" / "protocol.yaml")
    fixed = protocol.get("temporal_segmentation", {}).get("fixed_periods") or protocol.get("periods", [])
    return [str(row["label"]) for row in fixed]


def load_graphs(graph_root: Path, period_labels: list[str]) -> dict[str, nx.Graph]:
    graphs: dict[str, nx.Graph] = {}
    for period in period_labels:
        path = graph_root / f"institutions_{period.replace('-', '_')}.graphml"
        if not path.exists():
            continue
        graphs[period] = nx.read_graphml(path)
    return graphs


def load_processed_publications(project_root: Path, period_labels: list[str]) -> pd.DataFrame:
    path = project_root / "data" / "processed" / "publications.parquet"
    df = pd.read_parquet(
        path,
        columns=["period", "institutions", "institution_country_pairs", "funding_category"],
    )
    df["period"] = df["period"].astype(str)
    df = df[df["period"].isin(period_labels)].copy()
    df["institutions_parsed"] = df["institutions"].apply(parse_institutions)
    df["institution_country_pairs_parsed"] = df["institution_country_pairs"].apply(parse_country_pairs)
    return df


def build_prominent_institution_transition_counts(
    project_root: Path,
    period_labels: list[str],
) -> pd.DataFrame:
    centrality_dir = project_root / "outputs" / "tables" / "centrality"
    prominent: set[str] = set()
    for path in sorted(centrality_dir.glob("centrality_top10_*.csv")):
        df = pd.read_csv(path)
        prominent.update(str(v).strip() for v in df["degree_node"].dropna().tolist() if str(v).strip())
        prominent.update(str(v).strip() for v in df["betweenness_node"].dropna().tolist() if str(v).strip())

    graphs = load_graphs(project_root / "outputs" / "networks", period_labels)
    role_maps: dict[str, dict[str, str]] = {}
    for period in period_labels:
        graph = graphs.get(period)
        if graph is None or graph.number_of_nodes() == 0:
            role_maps[period] = {}
            continue
        degree = nx.degree_centrality(graph)
        non_zero = sorted(float(v) for v in degree.values() if v > 0)
        q50 = float(pd.Series(non_zero).quantile(0.50)) if non_zero else 0.0
        q90 = float(pd.Series(non_zero).quantile(0.90)) if non_zero else 0.0
        roles = {}
        for inst in graph.nodes():
            deg = float(degree.get(inst, 0.0))
            if deg <= 0:
                role = "Isolate"
            elif deg >= q90:
                role = "Core"
            elif deg >= q50:
                role = "Semi-Peripheral"
            else:
                role = "Peripheral"
            roles[str(inst)] = role
        role_maps[period] = roles

    rows: list[dict[str, object]] = []
    for period_from, period_to in zip(period_labels[:-1], period_labels[1:]):
        counter: Counter[tuple[str, str]] = Counter()
        for institution in sorted(prominent):
            state_from = role_maps.get(period_from, {}).get(institution, "Absent")
            state_to = role_maps.get(period_to, {}).get(institution, "Absent")
            counter[(state_from, state_to)] += 1
        from_totals = Counter()
        for (state_from, _), count in counter.items():
            from_totals[state_from] += count
        for state_from in ROLE_ORDER:
            for state_to in ROLE_ORDER:
                count = int(counter.get((state_from, state_to), 0))
                total = int(from_totals.get(state_from, 0))
                rows.append(
                    {
                        "period_from": period_from,
                        "period_to": period_to,
                        "state_from": state_from,
                        "state_to": state_to,
                        "transition_count": count,
                        "share_within_from_state": (float(count) / float(total)) if total > 0 else 0.0,
                    }
                )
    return pd.DataFrame(rows)


def build_publication_geography_tables(
    publications: pd.DataFrame,
    period_labels: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    region_rows: list[dict[str, object]] = []
    country_rows: list[dict[str, object]] = []
    country_display_rows: list[dict[str, object]] = []

    for period in period_labels:
        subset = publications[publications["period"] == period]
        total_publications = len(subset) if len(subset) else 1
        region_counter: Counter[tuple[str, str]] = Counter()
        country_counter: Counter[tuple[str, str]] = Counter()

        for row in subset.itertuples(index=False):
            entries = row.institution_country_pairs_parsed
            normalized_countries = [
                normalize_country_token(item.get("country", ""))
                for item in entries
                if normalize_country_token(item.get("country", ""))
            ]
            if not normalized_countries:
                continue

            country_counts = Counter(normalized_countries)
            unique_countries = sorted(country_counts.keys())
            for country, count in country_counts.items():
                if count >= 2:
                    country_counter[(country, country)] += 1
            for pair in combinations(unique_countries, 2):
                country_counter[pair] += 1

            region_to_countries: dict[str, set[str]] = {}
            for country in unique_countries:
                region = map_country_to_who_region(country)
                if not region or region == "Unknown":
                    continue
                region_to_countries.setdefault(region, set()).add(country)
            unique_regions = sorted(region_to_countries.keys())
            for region, countries in region_to_countries.items():
                if len(countries) >= 2:
                    region_counter[(region, region)] += 1
            for pair in combinations(unique_regions, 2):
                region_counter[pair] += 1

        for (region_a, region_b), count in sorted(region_counter.items(), key=lambda item: (-item[1], item[0])):
            region_rows.append(
                {
                    "period": period,
                    "who_region_a": region_a,
                    "who_region_b": region_b,
                    "is_diagonal": bool(region_a == region_b),
                    "publication_pair_count": int(count),
                    "publication_pair_share_pct": 100.0 * float(count) / float(total_publications),
                }
            )

        kept_country_pairs = {
            pair: count for pair, count in country_counter.items() if int(count) >= 3
        }
        weighted_degree: Counter[str] = Counter()
        for (country_a, country_b), count in kept_country_pairs.items():
            weighted_degree[country_a] += int(count)
            if country_a != country_b:
                weighted_degree[country_b] += int(count)

        for (country_a, country_b), count in sorted(country_counter.items(), key=lambda item: (-item[1], item[0])):
            country_rows.append(
                {
                    "period": period,
                    "country_a": country_a,
                    "country_b": country_b,
                    "country_a_display": display_country(country_a),
                    "country_b_display": display_country(country_b),
                    "is_diagonal": bool(country_a == country_b),
                    "publication_pair_count": int(count),
                    "publication_pair_share_pct": 100.0 * float(count) / float(total_publications),
                }
            )
            if (country_a, country_b) in kept_country_pairs:
                country_display_rows.append(
                    {
                        "period": period,
                        "country_a": country_a,
                        "country_b": country_b,
                        "country_a_display": display_country(country_a),
                        "country_b_display": display_country(country_b),
                        "is_diagonal": bool(country_a == country_b),
                        "publication_pair_count": int(count),
                        "publication_pair_share_pct": 100.0 * float(count) / float(total_publications),
                        "country_a_weighted_degree": int(weighted_degree[country_a]),
                        "country_b_weighted_degree": int(weighted_degree[country_b]),
                    }
                )

    return pd.DataFrame(region_rows), pd.DataFrame(country_rows), pd.DataFrame(country_display_rows)


def build_funding_domain_exact_two_field_profiles(
    project_root: Path,
    publications: pd.DataFrame,
    period_labels: list[str],
) -> pd.DataFrame:
    protocol = load_protocol(project_root / "config" / "protocol.yaml")
    classifier, fallback = build_protocol_classifier(protocol, project_root=project_root)
    profile_frames: list[pd.DataFrame] = []

    for funding_group, source_categories in FUNDED_PROFILE_GROUPS.items():
        combo_rows: list[dict[str, object]] = []
        for period in period_labels:
            subset = publications[
                (publications["period"] == period)
                & (publications["funding_category"].isin(source_categories))
            ]
            graph = build_collaboration_graph(subset["institutions_parsed"].tolist())
            annotate_node_types(graph, classifier)
            _, combo_df = component_field_collaboration_tables(graph, fallback_label=fallback)
            if combo_df.empty:
                continue
            combo_df = combo_df.copy()
            combo_df.insert(0, "period", period)
            combo_rows.extend(combo_df.to_dict(orient="records"))
        combos = pd.DataFrame(combo_rows)
        if combos.empty:
            continue
        profiles = focal_domain_exact_two_field_profiles(combos, focal_domains=FOCAL_DOMAINS)
        if profiles.empty:
            continue
        profiles.insert(1, "funding_group", funding_group)
        profile_frames.append(profiles)

    if not profile_frames:
        return pd.DataFrame(
            columns=[
                "period",
                "funding_group",
                "focal_domain",
                "partner_domain",
                "component_count",
                "focal_domain_total_exact_two_field_components",
                "partner_share_within_focal_domain",
                "partner_rank_within_focal_domain",
            ]
        )
    return pd.concat(profile_frames, ignore_index=True)


def build_base_tables(project_root: Path, period_labels: list[str]) -> dict[str, pd.DataFrame]:
    graph_root = project_root / "outputs" / "networks"
    graphs = load_graphs(graph_root, period_labels)
    publications = load_processed_publications(project_root, period_labels)
    global_rows: list[dict[str, object]] = []
    cluster_rows: list[dict[str, object]] = []
    pair_rows: list[dict[str, object]] = []
    combo_rows: list[dict[str, object]] = []

    protocol = load_protocol(project_root / "config" / "protocol.yaml")
    fallback_label = str(protocol["classification"].get("fallback_label", "Other"))

    for period in period_labels:
        graph = graphs[period]
        global_rows.append({"period": period, **global_metrics(graph)})
        cluster_rows.append({"period": period, **cluster_interdisciplinarity_metrics(graph)})
        pair_df, combo_df = component_field_collaboration_tables(graph, fallback_label=fallback_label)
        if not pair_df.empty:
            pair_df = pair_df.copy()
            pair_df.insert(0, "period", period)
            pair_rows.extend(pair_df.to_dict(orient="records"))
        if not combo_df.empty:
            combo_df = combo_df.copy()
            combo_df.insert(0, "period", period)
            combo_rows.extend(combo_df.to_dict(orient="records"))

    global_df = pd.DataFrame(global_rows)
    cluster_df = pd.DataFrame(cluster_rows)
    pairwise_df = pd.DataFrame(pair_rows)
    combo_df = pd.DataFrame(combo_rows)
    focal_profiles_df = focal_domain_exact_two_field_profiles(combo_df, focal_domains=FOCAL_DOMAINS)
    exact_three_field_df = exact_three_field_timelapse_profiles(combo_df, top_k=12)
    if not exact_three_field_df.empty:
        exact_three_field_df = exact_three_field_df.copy()
        exact_three_field_df.insert(
            2,
            "short_combination_label",
            exact_three_field_df["combination_label"].map(short_combination_label),
        )
    prominent_transition_df = build_prominent_institution_transition_counts(project_root, period_labels)
    who_pairwise_df, country_pairwise_df, country_display_df = build_publication_geography_tables(
        publications,
        period_labels,
    )
    funding_domain_profiles_df = build_funding_domain_exact_two_field_profiles(
        project_root,
        publications,
        period_labels,
    )

    pub_df = pd.read_csv(project_root / "outputs" / "tables" / "publication_counts_by_period.csv")
    core_df = pd.read_csv(project_root / "outputs" / "tables" / "core_newcomer_metrics.csv")
    structural = pub_df.merge(global_df, on="period", how="left")
    if not core_df.empty:
        structural = structural.merge(core_df.rename(columns={"to": "period"}).drop(columns=["from"]), on="period", how="left")
    structural["lcc_share_pct"] = structural.apply(
        lambda r: (100.0 * float(r["largest_connected_component_size"]) / float(r["nodes"])) if float(r["nodes"]) > 0 else 0.0,
        axis=1,
    )
    return {
        "global": global_df,
        "cluster": cluster_df,
        "pairwise": pairwise_df,
        "combos": combo_df,
        "focal_profiles": focal_profiles_df,
        "exact_three_field_timelapse": exact_three_field_df,
        "prominent_transitions": prominent_transition_df,
        "who_pairwise": who_pairwise_df,
        "country_pairwise": country_pairwise_df,
        "country_display": country_display_df,
        "funding_domain_profiles": funding_domain_profiles_df,
        "structural": structural,
    }


def build_funding_tables(project_root: Path, period_labels: list[str]) -> dict[str, pd.DataFrame]:
    global_rows: list[dict[str, object]] = []
    cluster_rows: list[dict[str, object]] = []
    for category in FUNDING_OUTPUT_ORDER:
        slug = FUNDING_SLUGS[category]
        graph_root = project_root / "outputs" / "networks_funding" / slug
        graphs = load_graphs(graph_root, period_labels)
        for period in period_labels:
            if period not in graphs:
                continue
            graph = graphs[period]
            global_rows.append({"period": period, "funding_category": category, **global_metrics(graph)})
            cluster_rows.append({"period": period, "funding_category": category, **cluster_interdisciplinarity_metrics(graph)})

    global_df = pd.DataFrame(global_rows)
    cluster_df = pd.DataFrame(cluster_rows)
    pub_df = pd.read_csv(project_root / "outputs" / "tables" / "funding_publication_counts_by_period.csv")
    core_df = pd.read_csv(project_root / "outputs" / "tables" / "funding_core_newcomer_metrics.csv")
    structural = pub_df.merge(global_df, on=["period", "funding_category"], how="left")
    if not core_df.empty:
        structural = structural.merge(
            core_df.rename(columns={"to": "period"}).drop(columns=["from"]),
            on=["period", "funding_category"],
            how="left",
        )
    structural["lcc_share_pct"] = structural.apply(
        lambda r: (100.0 * float(r["largest_connected_component_size"]) / float(r["nodes"])) if float(r["nodes"]) > 0 else 0.0,
        axis=1,
    )
    return {"global": global_df, "cluster": cluster_df, "structural": structural}


def main() -> None:
    args = parse_args()
    project_root = Path(args.project_root).resolve()
    period_labels = load_period_labels(project_root)
    tables_dir = project_root / "outputs" / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)

    base = build_base_tables(project_root, period_labels)
    base["global"].to_csv(tables_dir / "global_network_metrics.csv", index=False)
    base["cluster"].to_csv(tables_dir / "cluster_interdisciplinarity_metrics.csv", index=False)
    base["structural"].to_csv(tables_dir / "structural_comparison_summary.csv", index=False)
    base["pairwise"].to_csv(tables_dir / "component_field_pairwise_collaboration_by_period.csv", index=False)
    base["combos"].to_csv(tables_dir / "component_field_combination_summary_by_period.csv", index=False)
    base["focal_profiles"].to_csv(tables_dir / "focal_domain_exact_two_field_profiles_by_period.csv", index=False)
    base["exact_three_field_timelapse"].to_csv(tables_dir / "exact_three_field_timelapse_profiles.csv", index=False)
    base["prominent_transitions"].to_csv(tables_dir / "prominent_institution_role_transition_counts.csv", index=False)
    base["who_pairwise"].to_csv(tables_dir / "who_region_pairwise_collaboration_by_period.csv", index=False)
    base["country_pairwise"].to_csv(tables_dir / "country_pairwise_collaboration_by_period.csv", index=False)
    base["country_display"].to_csv(tables_dir / "country_pairwise_collaboration_display_by_period.csv", index=False)
    base["funding_domain_profiles"].to_csv(tables_dir / "funding_domain_exact_two_field_profiles_by_period.csv", index=False)

    funding = build_funding_tables(project_root, period_labels)
    funding["global"].to_csv(tables_dir / "funding_global_network_metrics.csv", index=False)
    funding["cluster"].to_csv(tables_dir / "funding_cluster_interdisciplinarity_metrics.csv", index=False)
    funding["structural"].to_csv(tables_dir / "funding_structural_comparison_summary.csv", index=False)

    print(
        {
            "global_rows": len(base["global"]),
            "pairwise_rows": len(base["pairwise"]),
            "combo_rows": len(base["combos"]),
            "focal_profile_rows": len(base["focal_profiles"]),
            "exact_three_field_timelapse_rows": len(base["exact_three_field_timelapse"]),
            "prominent_transition_rows": len(base["prominent_transitions"]),
            "who_pairwise_rows": len(base["who_pairwise"]),
            "country_pairwise_rows": len(base["country_pairwise"]),
            "funding_domain_profile_rows": len(base["funding_domain_profiles"]),
            "funding_global_rows": len(funding["global"]),
        }
    )


if __name__ == "__main__":
    main()
