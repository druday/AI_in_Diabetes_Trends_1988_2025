#!/usr/bin/env python3
"""Generate deterministic static figure assets for the detailed results report."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import matplotlib
import yaml

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyArrowPatch, Rectangle


ROOT = Path("/Users/uday/AI in Diabetology")
FLOW_ROOT = ROOT / "outputs" / "figures" / "flow_options"
TABLE_ROOT = ROOT / "outputs" / "tables"
ASSET_ROOT = ROOT / "docs" / "report_assets" / "results_report"
INTERACTIVE_ROOT = ROOT / "outputs" / "figures" / "interactive"

ROLE_ORDER = ["Core", "Semi-Peripheral", "Peripheral", "Isolate"]
ROLE_LABELS = {
    "Core": "High-centrality",
    "Semi-Peripheral": "Mid-centrality",
    "Peripheral": "Low-centrality",
    "Isolate": "Zero-centrality",
}
ROLE_SHORT_LABELS = {
    "Core": "High",
    "Semi-Peripheral": "Mid",
    "Peripheral": "Low",
    "Isolate": "Zero",
}
ROLE_COLORS = {
    "Core": "#1f77b4",
    "Semi-Peripheral": "#17becf",
    "Peripheral": "#ff7f0e",
    "Isolate": "#bcbd22",
}
TRANSITION_ROLE_ORDER = ["Core", "Semi-Peripheral", "Peripheral", "Isolate", "Absent"]
TRANSITION_ROLE_LABELS = {
    "Core": "High",
    "Semi-Peripheral": "Mid",
    "Peripheral": "Low",
    "Isolate": "Zero",
    "Absent": "Absent",
}
FUNDING_LABELS = {
    "US_FEDERAL_FUNDED": "US federally funded",
    "NON_US_OR_INTL_FUNDED": "Non-US / international funded",
    "NO_GRANT_LISTED": "No grant listed",
}
FUNDING_ORDER = ["US_FEDERAL_FUNDED", "NON_US_OR_INTL_FUNDED", "NO_GRANT_LISTED"]
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
PERIOD_COLORS = {
    "1988-2015": "#9ca3af",
    "2016-2019": "#f59e0b",
    "2020-2021": "#2563eb",
    "2022-2023": "#059669",
    "2024-2024": "#7c3aed",
    "2025-2025": "#dc2626",
}
FUNDING_COMPARE_LABELS = {
    "FUNDED": "Funded",
    "NO_GRANT_LISTED": "No grant listed",
}
COMBO_PALETTE = [
    "#1f77b4",
    "#ff7f0e",
    "#2ca02c",
    "#d62728",
    "#9467bd",
    "#8c564b",
    "#e377c2",
    "#7f7f7f",
    "#bcbd22",
    "#17becf",
    "#2563eb",
    "#059669",
]


def _category_order() -> list[str]:
    with (ROOT / "config" / "protocol.yaml").open("r", encoding="utf-8") as handle:
        protocol = yaml.safe_load(handle)
    categories = protocol["classification"]["categories"]
    return [str(item["label"]) for item in categories]


def _display_country_label(value: str) -> str:
    parts = str(value).split()
    return " ".join(part.upper() if len(part) <= 3 else part.capitalize() for part in parts)


def _period_positions(nodes: pd.DataFrame) -> dict[str, float]:
    periods = list(dict.fromkeys(nodes["period"].tolist()))
    if len(periods) == 1:
        return {periods[0]: 0.5}
    return {period: idx / (len(periods) - 1) for idx, period in enumerate(periods)}


def _node_positions(nodes: pd.DataFrame) -> tuple[dict[tuple[str, str], tuple[float, float]], dict[str, float]]:
    x_positions = _period_positions(nodes)
    role_y = {role: 0.86 - idx * 0.24 for idx, role in enumerate(ROLE_ORDER)}
    positions: dict[tuple[str, str], tuple[float, float]] = {}
    for row in nodes.itertuples(index=False):
        positions[(row.period, row.role)] = (x_positions[row.period], role_y[row.role])
    return positions, x_positions


def _draw_multi_period_alluvial(ax, nodes: pd.DataFrame, links: pd.DataFrame) -> None:
    positions, x_positions = _node_positions(nodes)
    periods = list(dict.fromkeys(nodes["period"].tolist()))
    node_width = 0.06
    node_height = 0.10
    max_link = max(float(links["value"].max()), 1.0)

    for row in links.itertuples(index=False):
        src_period = str(row.period_from)
        dst_period = str(row.period_to)
        src_role = str(row.state_from)
        dst_role = str(row.state_to)
        if src_role not in ROLE_ORDER or dst_role not in ROLE_ORDER:
            continue
        x0, y0 = positions[(src_period, src_role)]
        x1, y1 = positions[(dst_period, dst_role)]
        lw = 1.5 + 10.0 * (float(row.value) / max_link) ** 0.65
        patch = FancyArrowPatch(
            (x0 + node_width / 2.0, y0),
            (x1 - node_width / 2.0, y1),
            connectionstyle="arc3,rad=0.08",
            arrowstyle="-",
            linewidth=lw,
            color=ROLE_COLORS[src_role],
            alpha=0.28,
            zorder=1,
            capstyle="round",
            joinstyle="round",
        )
        ax.add_patch(patch)

    for period in periods:
        x = x_positions[period]
        ax.text(
            x,
            0.985,
            period,
            ha="center",
            va="top",
            fontsize=10,
            fontweight="bold",
            color="#22354b",
        )
        for role in ROLE_ORDER:
            if (period, role) not in positions:
                continue
            px, py = positions[(period, role)]
            total = nodes.loc[(nodes["period"] == period) & (nodes["role"] == role), ["incoming", "outgoing"]].max(axis=1).iloc[0]
            rect = Rectangle(
                (px - node_width / 2.0, py - node_height / 2.0),
                node_width,
                node_height,
                facecolor=ROLE_COLORS[role],
                edgecolor="white",
                linewidth=1.0,
                zorder=3,
            )
            ax.add_patch(rect)
            ax.text(
                px,
                py + 0.012,
                ROLE_SHORT_LABELS[role],
                ha="center",
                va="center",
                fontsize=7.8,
                color="white",
                fontweight="bold",
                zorder=4,
            )
            ax.text(
                px,
                py - 0.018,
                f"n={int(total):,}",
                ha="center",
                va="center",
                fontsize=7.0,
                color="white",
                zorder=4,
            )

    ax.set_xlim(-0.06, 1.06)
    ax.set_ylim(0.0, 1.0)
    ax.axis("off")


def _draw_two_column_alluvial(ax, transition_counts: pd.DataFrame, title: str) -> None:
    filtered = transition_counts[
        transition_counts["state_from"].isin(ROLE_ORDER) & transition_counts["state_to"].isin(ROLE_ORDER)
    ].copy()
    if filtered.empty:
        ax.axis("off")
        ax.text(0.5, 0.5, "No active-role transitions available", ha="center", va="center")
        return

    outgoing = filtered.groupby("state_from", as_index=True)["value"].sum().to_dict()
    incoming = filtered.groupby("state_to", as_index=True)["value"].sum().to_dict()
    left_x, right_x = 0.20, 0.80
    node_width = 0.12
    node_height = 0.12
    role_y = {role: 0.86 - idx * 0.24 for idx, role in enumerate(ROLE_ORDER)}
    max_link = max(float(filtered["value"].max()), 1.0)

    for row in filtered.itertuples(index=False):
        src = str(row.state_from)
        dst = str(row.state_to)
        lw = 1.5 + 8.0 * (float(row.value) / max_link) ** 0.60
        patch = FancyArrowPatch(
            (left_x + node_width / 2.0, role_y[src]),
            (right_x - node_width / 2.0, role_y[dst]),
            connectionstyle="arc3,rad=0.10",
            arrowstyle="-",
            linewidth=lw,
            color=ROLE_COLORS[src],
            alpha=0.25,
            zorder=1,
            capstyle="round",
        )
        ax.add_patch(patch)

    ax.text(left_x, 0.985, "Previous period role", ha="center", va="top", fontsize=9, fontweight="bold", color="#22354b")
    ax.text(right_x, 0.985, "Next period role", ha="center", va="top", fontsize=9, fontweight="bold", color="#22354b")

    for role in ROLE_ORDER:
        for x, totals, align in [
            (left_x, outgoing, "center"),
            (right_x, incoming, "center"),
        ]:
            rect = Rectangle(
                (x - node_width / 2.0, role_y[role] - node_height / 2.0),
                node_width,
                node_height,
                facecolor=ROLE_COLORS[role],
                edgecolor="white",
                linewidth=1.0,
                zorder=3,
            )
            ax.add_patch(rect)
            total = int(totals.get(role, 0))
            ax.text(
                x,
                role_y[role] + 0.014,
                ROLE_LABELS[role].replace("-centrality", ""),
                ha=align,
                va="center",
                fontsize=7.0,
                fontweight="bold",
                color="white",
                zorder=4,
            )
            ax.text(
                x,
                role_y[role] - 0.018,
                f"n={total:,}",
                ha=align,
                va="center",
                fontsize=6.8,
                color="white",
                zorder=4,
            )

    ax.set_title(title, fontsize=10.5, fontweight="bold", loc="left", pad=6, color="#17324d")
    ax.set_xlim(0.0, 1.0)
    ax.set_ylim(0.0, 1.0)
    ax.axis("off")


def _copy_static_png(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def generate_role_flow_overview(out_path: Path) -> Path:
    nodes = pd.read_csv(FLOW_ROOT / "role_flow_sankey_nodes.csv")
    links = pd.read_csv(FLOW_ROOT / "role_flow_sankey_links.csv")
    fig, ax = plt.subplots(figsize=(10.8, 5.8), dpi=220)
    fig.patch.set_facecolor("white")
    _draw_multi_period_alluvial(ax, nodes, links)
    fig.suptitle(
        "Role-flow among institutions active in adjacent periods",
        fontsize=14,
        fontweight="bold",
        x=0.05,
        ha="left",
        color="#17324d",
    )
    ax.text(
        -0.02,
        -0.03,
        "Static manuscript rendering of the base role-flow Sankey using active institutions only.",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=9,
        color="#52657a",
    )
    fig.tight_layout(rect=[0.02, 0.04, 0.98, 0.93])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    return out_path


def generate_funding_role_flow_comparison(out_path: Path) -> Path:
    df = pd.read_csv(TABLE_ROOT / "funding_role_transition_counts.csv")
    fig, axes = plt.subplots(3, 1, figsize=(10.2, 11.4), dpi=220)
    fig.patch.set_facecolor("white")
    for ax, category in zip(axes, FUNDING_ORDER):
        subset = df[df["funding_category"] == category]
        active = (
            subset[
                subset["state_from"].isin(ROLE_ORDER)
                & subset["state_to"].isin(ROLE_ORDER)
            ]
            .groupby(["state_from", "state_to"], as_index=False)["value"]
            .sum()
        )
        _draw_two_column_alluvial(ax, active, FUNDING_LABELS[category])
    fig.suptitle(
        "Funding-stratified role-flow comparison",
        fontsize=14,
        fontweight="bold",
        x=0.05,
        ha="left",
        color="#17324d",
    )
    fig.text(
        0.05,
        0.02,
        "Aggregated active-role transitions across all adjacent-period comparisons for each funding category.",
        ha="left",
        va="bottom",
        fontsize=9,
        color="#52657a",
    )
    fig.tight_layout(rect=[0.02, 0.04, 0.98, 0.95], h_pad=1.0)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    return out_path


def generate_interdisciplinarity_heatmap(out_path: Path) -> Path:
    pairwise = pd.read_csv(TABLE_ROOT / "component_field_pairwise_collaboration_by_period.csv")
    period_order = pd.read_csv(TABLE_ROOT / "period_definitions.csv")["label"].astype(str).tolist()
    field_order = _category_order()
    n_cols = 2
    n_rows = int(np.ceil(len(period_order) / n_cols))
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(15.8, 17.2), dpi=220)
    axes_array = np.atleast_1d(axes).flatten()
    fig.patch.set_facecolor("white")

    vmax_count = int(pairwise["component_count"].max()) if not pairwise.empty else 1
    vmax_transform = float(np.log10(1.0 + vmax_count))
    if vmax_transform <= 0:
        vmax_transform = 1.0
    image = None
    label_lookup = {field: FIELD_SHORT_LABELS.get(field, field) for field in field_order}

    for ax, period in zip(axes_array, period_order):
        matrix = pd.DataFrame(0.0, index=field_order, columns=field_order)
        subset = pairwise[pairwise["period"] == period]
        for row in subset.itertuples(index=False):
            matrix.loc[row.field_a, row.field_b] = float(row.component_count)
            if row.field_a != row.field_b:
                matrix.loc[row.field_b, row.field_a] = float(row.component_count)
        display_matrix = np.log10(1.0 + matrix.values)
        image = ax.imshow(display_matrix, cmap="Blues", vmin=0.0, vmax=vmax_transform)
        ax.set_title(period, fontsize=12, fontweight="bold", color="#17324d", pad=10)
        ax.set_xticks(range(len(field_order)))
        ax.set_yticks(range(len(field_order)))
        ax.set_xticklabels([label_lookup[f] for f in field_order], rotation=45, ha="right", fontsize=8)
        ax.set_yticklabels([label_lookup[f] for f in field_order], fontsize=8)
        ax.tick_params(length=0)
        ax.set_xticks(np.arange(-0.5, len(field_order), 1), minor=True)
        ax.set_yticks(np.arange(-0.5, len(field_order), 1), minor=True)
        ax.grid(which="minor", color="white", linestyle="-", linewidth=0.5)
        ax.tick_params(which="minor", bottom=False, left=False)
        for row_idx in range(len(field_order)):
            for col_idx in range(len(field_order)):
                count = int(matrix.iloc[row_idx, col_idx])
                color = "white" if display_matrix[row_idx, col_idx] >= (0.58 * vmax_transform) else "#16324d"
                ax.text(
                    col_idx,
                    row_idx,
                    f"{count:,}",
                    ha="center",
                    va="center",
                    fontsize=5.8,
                    color=color,
                )

    for ax in axes_array[len(period_order):]:
        ax.axis("off")

    fig.suptitle(
        "Pairwise field co-occurrence across connected components by period",
        fontsize=16,
        fontweight="bold",
        x=0.05,
        ha="left",
        color="#17324d",
        y=0.975,
    )
    if image is not None:
        cax = fig.add_axes([0.905, 0.19, 0.022, 0.64])
        cbar = fig.colorbar(image, cax=cax)
        count_ticks = [0, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000]
        count_ticks = [tick for tick in count_ticks if tick <= vmax_count]
        if vmax_count not in count_ticks:
            count_ticks.append(vmax_count)
        tick_positions = [float(np.log10(1.0 + tick)) for tick in count_ticks]
        cbar.set_ticks(tick_positions)
        cbar.set_ticklabels([f"{tick:,}" for tick in count_ticks])
        cbar.ax.set_ylabel("Component count (shared log scale)", rotation=90, labelpad=12)
    fig.text(
        0.05,
        0.02,
        "Off-diagonal cells show the number of connected components containing both fields; diagonal cells show components with at least two institutions from the same field.",
        ha="left",
        va="bottom",
        fontsize=9,
        color="#52657a",
    )
    fig.subplots_adjust(left=0.11, right=0.88, top=0.90, bottom=0.10, hspace=0.34, wspace=0.22)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    return out_path


def generate_two_field_spider_profiles(out_path: Path) -> Path:
    profiles = pd.read_csv(TABLE_ROOT / "focal_domain_exact_two_field_profiles_by_period.csv")
    period_order = pd.read_csv(TABLE_ROOT / "period_definitions.csv")["label"].astype(str).tolist()
    field_order = _category_order()
    fig, axes = plt.subplots(2, 2, subplot_kw={"projection": "polar"}, figsize=(15.5, 12.6), dpi=220)
    axes_array = np.atleast_1d(axes).flatten()
    fig.patch.set_facecolor("white")

    handles = []
    labels = []
    for ax, focal_domain in zip(axes_array, FOCAL_DOMAINS):
        partner_domains = [field for field in field_order if field != focal_domain]
        theta = np.linspace(0, 2 * np.pi, len(partner_domains), endpoint=False)
        theta_closed = np.concatenate([theta, [theta[0]]])
        ax.set_theta_offset(np.pi / 2)
        ax.set_theta_direction(-1)
        ax.set_xticks(theta)
        ax.set_xticklabels([FIELD_SHORT_LABELS.get(field, field) for field in partner_domains], fontsize=8)
        ax.set_ylim(0, 1.0)
        ax.set_yticks([0.25, 0.5, 0.75, 1.0])
        ax.set_yticklabels(["25%", "50%", "75%", "100%"], fontsize=7, color="#52657a")
        ax.grid(color="#d9e2ec", linewidth=0.7, alpha=0.85)
        ax.spines["polar"].set_color("#94a3b8")
        ax.spines["polar"].set_linewidth(0.9)
        ax.set_title(
            f"{FIELD_SHORT_LABELS.get(focal_domain, focal_domain)} partner profile",
            fontsize=11,
            fontweight="bold",
            pad=18,
            color="#17324d",
        )

        for period in period_order:
            subset = profiles[
                (profiles["period"] == period)
                & (profiles["focal_domain"] == focal_domain)
            ]
            share_map = {
                str(row.partner_domain): float(row.partner_share_within_focal_domain)
                for row in subset.itertuples(index=False)
            }
            values = [share_map.get(partner, 0.0) for partner in partner_domains]
            values_closed = values + [values[0]]
            line = ax.plot(
                theta_closed,
                values_closed,
                color=PERIOD_COLORS.get(period, "#475569"),
                linewidth=1.8,
                alpha=0.9,
                marker="o",
                markersize=2.8,
            )[0]
            ax.fill(
                theta_closed,
                values_closed,
                color=PERIOD_COLORS.get(period, "#475569"),
                alpha=0.04,
            )
            if focal_domain == FOCAL_DOMAINS[0]:
                handles.append(line)
                labels.append(period)

    for ax in axes_array[len(FOCAL_DOMAINS) :]:
        ax.axis("off")

    fig.suptitle(
        "Exact two-field collaboration partner profiles for selected focal domains",
        fontsize=16,
        fontweight="bold",
        x=0.05,
        ha="left",
        color="#17324d",
        y=0.98,
    )
    fig.legend(
        handles,
        labels,
        loc="lower center",
        bbox_to_anchor=(0.5, 0.02),
        ncol=3,
        frameon=False,
        fontsize=9,
    )
    fig.text(
        0.05,
        0.06,
        "Each spoke shows the share of a focal domain's exact two-field collaboration components that involve that partner domain in the given period.",
        ha="left",
        va="bottom",
        fontsize=9,
        color="#52657a",
    )
    fig.subplots_adjust(left=0.05, right=0.96, top=0.86, bottom=0.14, hspace=0.42, wspace=0.28)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    return out_path


def generate_prominent_institution_transition_heatmap(out_path: Path) -> Path:
    df = pd.read_csv(TABLE_ROOT / "prominent_institution_role_transition_counts.csv")
    period_pairs = (
        df[["period_from", "period_to"]].drop_duplicates().sort_values(["period_from", "period_to"]).values.tolist()
    )
    n_cols = 3
    n_rows = int(np.ceil(len(period_pairs) / n_cols))
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(16.2, 10.4), dpi=220)
    axes_array = np.atleast_1d(axes).flatten()
    fig.patch.set_facecolor("white")

    vmax = int(df["transition_count"].max()) if not df.empty else 1
    image = None
    for ax, (period_from, period_to) in zip(axes_array, period_pairs):
        subset = df[(df["period_from"] == period_from) & (df["period_to"] == period_to)]
        matrix = pd.DataFrame(0, index=TRANSITION_ROLE_ORDER, columns=TRANSITION_ROLE_ORDER, dtype=float)
        for row in subset.itertuples(index=False):
            matrix.loc[row.state_from, row.state_to] = float(row.transition_count)
        image = ax.imshow(matrix.values, cmap="Blues", vmin=0, vmax=vmax)
        ax.set_title(f"{period_from} -> {period_to}", fontsize=10.5, fontweight="bold", color="#17324d", pad=8)
        ax.set_xticks(range(len(TRANSITION_ROLE_ORDER)))
        ax.set_yticks(range(len(TRANSITION_ROLE_ORDER)))
        ax.set_xticklabels([TRANSITION_ROLE_LABELS[s] for s in TRANSITION_ROLE_ORDER], rotation=35, ha="right", fontsize=8)
        ax.set_yticklabels([TRANSITION_ROLE_LABELS[s] for s in TRANSITION_ROLE_ORDER], fontsize=8)
        ax.tick_params(length=0)
        ax.set_xticks(np.arange(-0.5, len(TRANSITION_ROLE_ORDER), 1), minor=True)
        ax.set_yticks(np.arange(-0.5, len(TRANSITION_ROLE_ORDER), 1), minor=True)
        ax.grid(which="minor", color="white", linestyle="-", linewidth=0.7)
        ax.tick_params(which="minor", bottom=False, left=False)
        for r_idx in range(len(TRANSITION_ROLE_ORDER)):
            for c_idx in range(len(TRANSITION_ROLE_ORDER)):
                count = int(matrix.iloc[r_idx, c_idx])
                color = "white" if count >= max(1, int(vmax * 0.45)) else "#17324d"
                ax.text(c_idx, r_idx, f"{count}", ha="center", va="center", fontsize=7.2, color=color)

    for ax in axes_array[len(period_pairs):]:
        ax.axis("off")

    fig.suptitle(
        "Prominent-institution role transitions across adjacent manuscript periods",
        fontsize=16,
        fontweight="bold",
        x=0.05,
        ha="left",
        color="#17324d",
        y=0.98,
    )
    if image is not None:
        cax = fig.add_axes([0.91, 0.18, 0.018, 0.66])
        cbar = fig.colorbar(image, cax=cax)
        cbar.ax.set_ylabel("Institution count", rotation=90, labelpad=10)
    fig.text(
        0.05,
        0.03,
        "Rows show previous-period role and columns show next-period role for the deterministic prominent-institution subset (top degree/betweenness institutions by period, unioned across the study window).",
        ha="left",
        va="bottom",
        fontsize=9,
        color="#52657a",
    )
    fig.subplots_adjust(left=0.08, right=0.88, top=0.88, bottom=0.11, hspace=0.36, wspace=0.28)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    return out_path


def _draw_shared_log_heatmap(
    *,
    df: pd.DataFrame,
    row_col_a: str,
    row_col_b: str,
    value_col: str,
    title: str,
    footer: str,
    out_path: Path,
    display_label_fn,
    n_cols: int = 3,
    annotate_nonzero_only: bool = False,
    figsize: tuple[float, float] = (17.2, 11.0),
    annotate_fontsize: float = 6.0,
    tick_fontsize: float = 8.0,
) -> Path:
    period_order = pd.read_csv(TABLE_ROOT / "period_definitions.csv")["label"].astype(str).tolist()
    n_rows = int(np.ceil(len(period_order) / n_cols))
    fig, axes = plt.subplots(n_rows, n_cols, figsize=figsize, dpi=220)
    axes_array = np.atleast_1d(axes).flatten()
    fig.patch.set_facecolor("white")
    vmax_count = int(df[value_col].max()) if not df.empty else 1
    vmax_transform = max(float(np.log10(1.0 + vmax_count)), 1.0)
    cmap = plt.cm.Blues.copy()
    cmap.set_bad(color="white")
    image = None

    for ax, period in zip(axes_array, period_order):
        subset = df[df["period"] == period].copy()
        labels = sorted(
            set(subset[row_col_a].astype(str).tolist()) | set(subset[row_col_b].astype(str).tolist()),
            key=lambda text: text.lower(),
        )
        if subset.empty or not labels:
            ax.axis("off")
            ax.text(0.5, 0.5, f"{period}\nNo retained pairs", ha="center", va="center", fontsize=10, color="#52657a")
            continue
        matrix = pd.DataFrame(0.0, index=labels, columns=labels)
        for row in subset.itertuples(index=False):
            a = str(getattr(row, row_col_a))
            b = str(getattr(row, row_col_b))
            value = float(getattr(row, value_col))
            matrix.loc[a, b] = value
            if a != b:
                matrix.loc[b, a] = value
        masked = np.ma.masked_where(matrix.values <= 0, np.log10(1.0 + matrix.values))
        image = ax.imshow(masked, cmap=cmap, vmin=0.0, vmax=vmax_transform)
        ax.set_title(period, fontsize=10.5, fontweight="bold", color="#17324d", pad=8)
        ax.set_xticks(range(len(labels)))
        ax.set_yticks(range(len(labels)))
        ax.set_xticklabels([display_label_fn(label) for label in labels], rotation=45, ha="right", fontsize=tick_fontsize)
        ax.set_yticklabels([display_label_fn(label) for label in labels], fontsize=tick_fontsize)
        ax.tick_params(length=0)
        ax.set_xticks(np.arange(-0.5, len(labels), 1), minor=True)
        ax.set_yticks(np.arange(-0.5, len(labels), 1), minor=True)
        ax.grid(which="minor", color="#eef2f7", linestyle="-", linewidth=0.45)
        ax.tick_params(which="minor", bottom=False, left=False)
        for r_idx, row_name in enumerate(labels):
            for c_idx, col_name in enumerate(labels):
                count = int(matrix.loc[row_name, col_name])
                if annotate_nonzero_only and count <= 0:
                    continue
                if count <= 0:
                    continue
                color = "white" if np.log10(1.0 + count) >= (0.55 * vmax_transform) else "#17324d"
                ax.text(c_idx, r_idx, f"{count}", ha="center", va="center", fontsize=annotate_fontsize, color=color)

    for ax in axes_array[len(period_order):]:
        ax.axis("off")

    fig.suptitle(title, fontsize=16, fontweight="bold", x=0.05, ha="left", color="#17324d", y=0.98)
    if image is not None:
        cax = fig.add_axes([0.91, 0.18, 0.018, 0.66])
        cbar = fig.colorbar(image, cax=cax)
        count_ticks = [0, 1, 2, 3, 5, 10, 20, 50, 100, 200, 500]
        count_ticks = [tick for tick in count_ticks if tick <= vmax_count]
        if vmax_count not in count_ticks:
            count_ticks.append(vmax_count)
        positions = [float(np.log10(1.0 + tick)) for tick in count_ticks]
        cbar.set_ticks(positions)
        cbar.set_ticklabels([f"{tick:,}" for tick in count_ticks])
        cbar.ax.set_ylabel("Publication co-occurrence count (shared log scale)", rotation=90, labelpad=12)
    fig.text(0.05, 0.03, footer, ha="left", va="bottom", fontsize=9, color="#52657a")
    fig.subplots_adjust(left=0.08, right=0.88, top=0.88, bottom=0.10, hspace=0.36, wspace=0.28)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    return out_path


def generate_who_region_collaboration_heatmap(out_path: Path) -> Path:
    df = pd.read_csv(TABLE_ROOT / "who_region_pairwise_collaboration_by_period.csv")
    return _draw_shared_log_heatmap(
        df=df,
        row_col_a="who_region_a",
        row_col_b="who_region_b",
        value_col="publication_pair_count",
        title="WHO-region collaboration across manuscript periods",
        footer="Off-diagonal cells show publications that include at least one institution from both WHO regions; diagonal cells show publications containing at least two distinct countries from the same WHO region.",
        out_path=out_path,
        display_label_fn=lambda x: str(x),
        annotate_nonzero_only=True,
        figsize=(16.4, 10.8),
        annotate_fontsize=7.0,
        tick_fontsize=8.2,
    )


def generate_country_collaboration_heatmap(out_path: Path) -> Path:
    df = pd.read_csv(TABLE_ROOT / "country_pairwise_collaboration_display_by_period.csv")
    period_order = pd.read_csv(TABLE_ROOT / "period_definitions.csv")["label"].astype(str).tolist()
    n_cols = 3
    n_rows = int(np.ceil(len(period_order) / n_cols))
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(21.0, 16.0), dpi=220)
    axes_array = np.atleast_1d(axes).flatten()
    fig.patch.set_facecolor("white")
    vmax_count = int(df["publication_pair_count"].max()) if not df.empty else 1
    vmax_transform = max(float(np.log10(1.0 + vmax_count)), 1.0)
    cmap = plt.cm.Blues.copy()
    cmap.set_bad(color="white")
    image = None

    for ax, period in zip(axes_array, period_order):
        subset = df[df["period"] == period].copy()
        if subset.empty:
            ax.axis("off")
            ax.text(0.5, 0.5, f"{period}\nNo retained pairs", ha="center", va="center", fontsize=10, color="#52657a")
            continue

        weighted_degree: dict[str, int] = {}
        for row in subset.itertuples(index=False):
            weighted_degree[str(row.country_a)] = max(
                int(weighted_degree.get(str(row.country_a), 0)),
                int(row.country_a_weighted_degree),
            )
            weighted_degree[str(row.country_b)] = max(
                int(weighted_degree.get(str(row.country_b), 0)),
                int(row.country_b_weighted_degree),
            )
        labels = sorted(weighted_degree.keys(), key=lambda c: (-weighted_degree[c], c))
        matrix = pd.DataFrame(0.0, index=labels, columns=labels)
        for row in subset.itertuples(index=False):
            a = str(row.country_a)
            b = str(row.country_b)
            value = float(row.publication_pair_count)
            matrix.loc[a, b] = value
            if a != b:
                matrix.loc[b, a] = value
        masked = np.ma.masked_where(matrix.values <= 0, np.log10(1.0 + matrix.values))
        image = ax.imshow(masked, cmap=cmap, vmin=0.0, vmax=vmax_transform)
        ax.set_title(period, fontsize=10.5, fontweight="bold", color="#17324d", pad=8)
        ax.set_xticks(range(len(labels)))
        ax.set_yticks(range(len(labels)))
        ax.set_xticklabels([_display_country_label(label) for label in labels], rotation=45, ha="right", fontsize=4.8)
        ax.set_yticklabels([_display_country_label(label) for label in labels], fontsize=4.8)
        ax.tick_params(length=0)
        ax.set_xticks(np.arange(-0.5, len(labels), 1), minor=True)
        ax.set_yticks(np.arange(-0.5, len(labels), 1), minor=True)
        ax.grid(which="minor", color="#eef2f7", linestyle="-", linewidth=0.35)
        ax.tick_params(which="minor", bottom=False, left=False)
        for r_idx, row_name in enumerate(labels):
            for c_idx, col_name in enumerate(labels):
                count = int(matrix.loc[row_name, col_name])
                if count <= 0:
                    continue
                color = "white" if np.log10(1.0 + count) >= (0.55 * vmax_transform) else "#17324d"
                ax.text(c_idx, r_idx, f"{count}", ha="center", va="center", fontsize=4.2, color=color)

    for ax in axes_array[len(period_order):]:
        ax.axis("off")

    fig.suptitle(
        "Thresholded country-level collaboration across manuscript periods",
        fontsize=16,
        fontweight="bold",
        x=0.05,
        ha="left",
        color="#17324d",
        y=0.98,
    )
    if image is not None:
        cax = fig.add_axes([0.91, 0.18, 0.018, 0.66])
        cbar = fig.colorbar(image, cax=cax)
        count_ticks = [0, 1, 2, 3, 5, 10, 20, 50, 100, 200, 500]
        count_ticks = [tick for tick in count_ticks if tick <= vmax_count]
        if vmax_count not in count_ticks:
            count_ticks.append(vmax_count)
        positions = [float(np.log10(1.0 + tick)) for tick in count_ticks]
        cbar.set_ticks(positions)
        cbar.set_ticklabels([f"{tick:,}" for tick in count_ticks])
        cbar.ax.set_ylabel("Publication co-occurrence count (shared log scale)", rotation=90, labelpad=12)
    fig.text(
        0.05,
        0.03,
        "Panels include all country pairs with at least 3 publication-level co-occurrences in that period; axes are ordered by within-period weighted degree and blank cells indicate pairs below threshold.",
        ha="left",
        va="bottom",
        fontsize=9,
        color="#52657a",
    )
    fig.subplots_adjust(left=0.08, right=0.88, top=0.88, bottom=0.10, hspace=0.36, wspace=0.28)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    return out_path


def generate_funding_exact_two_field_spider_profiles(out_path: Path) -> Path:
    profiles = pd.read_csv(TABLE_ROOT / "funding_domain_exact_two_field_profiles_by_period.csv")
    period_order = pd.read_csv(TABLE_ROOT / "period_definitions.csv")["label"].astype(str).tolist()
    field_order = _category_order()
    funding_order = ["FUNDED", "NO_GRANT_LISTED"]
    fig, axes = plt.subplots(4, 2, subplot_kw={"projection": "polar"}, figsize=(14.8, 22.0), dpi=220)
    fig.patch.set_facecolor("white")

    legend_handles = []
    legend_labels = []
    for row_idx, focal_domain in enumerate(FOCAL_DOMAINS):
        partner_domains = [field for field in field_order if field != focal_domain]
        theta = np.linspace(0, 2 * np.pi, len(partner_domains), endpoint=False)
        theta_closed = np.concatenate([theta, [theta[0]]])
        for col_idx, funding_group in enumerate(funding_order):
            ax = axes[row_idx, col_idx]
            ax.set_theta_offset(np.pi / 2)
            ax.set_theta_direction(-1)
            ax.set_xticks(theta)
            ax.set_xticklabels(
                [FIELD_SHORT_LABELS.get(field, field) for field in partner_domains],
                fontsize=7.6,
            )
            ax.set_ylim(0, 1.0)
            ax.set_yticks([0.25, 0.5, 0.75, 1.0])
            ax.set_yticklabels(["25%", "50%", "75%", "100%"], fontsize=7, color="#52657a")
            ax.grid(color="#d9e2ec", linewidth=0.7, alpha=0.85)
            ax.spines["polar"].set_color("#94a3b8")
            ax.spines["polar"].set_linewidth(0.9)
            ax.set_title(
                f"{FIELD_SHORT_LABELS.get(focal_domain, focal_domain)} — {FUNDING_COMPARE_LABELS[funding_group]}",
                fontsize=10.6,
                fontweight="bold",
                pad=18,
                color="#17324d",
            )

            for period in period_order:
                subset = profiles[
                    (profiles["period"] == period)
                    & (profiles["focal_domain"] == focal_domain)
                    & (profiles["funding_group"] == funding_group)
                ]
                share_map = {
                    str(row.partner_domain): float(row.partner_share_within_focal_domain)
                    for row in subset.itertuples(index=False)
                }
                values = [share_map.get(partner, 0.0) for partner in partner_domains]
                values_closed = values + [values[0]]
                line = ax.plot(
                    theta_closed,
                    values_closed,
                    color=PERIOD_COLORS.get(period, "#475569"),
                    linewidth=1.6,
                    alpha=0.95,
                )[0]
                if period == period_order[-1]:
                    ax.fill(
                        theta_closed,
                        values_closed,
                        color=PERIOD_COLORS.get(period, "#475569"),
                        alpha=0.03,
                    )
                if row_idx == 0 and col_idx == 0:
                    legend_handles.append(line)
                    legend_labels.append(period)

    fig.suptitle(
        "Funding-stratified exact two-field partner profiles for selected focal domains",
        fontsize=16,
        fontweight="bold",
        x=0.05,
        ha="left",
        color="#17324d",
        y=0.98,
    )
    fig.legend(
        legend_handles,
        legend_labels,
        loc="lower center",
        bbox_to_anchor=(0.5, 0.025),
        ncol=3,
        frameon=False,
        fontsize=8.6,
    )
    fig.text(
        0.05,
        0.07,
        "Colors encode manuscript period. Left-column panels show funded publications (US federal + non-US/international funded), right-column panels show no grant listed. Radial values show within-focal-domain exact two-field partner shares.",
        ha="left",
        va="bottom",
        fontsize=9,
        color="#52657a",
    )
    fig.subplots_adjust(left=0.06, right=0.96, top=0.93, bottom=0.12, hspace=0.62, wspace=0.28)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    return out_path


def _three_field_combo_colors(labels: list[str]) -> dict[str, str]:
    return {label: COMBO_PALETTE[idx % len(COMBO_PALETTE)] for idx, label in enumerate(labels)}


def _nice_count_ticks(max_count: int) -> list[int]:
    if max_count <= 10:
        return list(range(0, max_count + 1, 2)) or [0]
    if max_count <= 50:
        step = 5
    elif max_count <= 100:
        step = 10
    else:
        step = 20
    ticks = list(range(0, max_count + step, step))
    if ticks[-1] < max_count:
        ticks.append(max_count)
    return sorted(set(ticks))


def generate_exact_three_field_timelapse_html(out_path: Path) -> Path:
    df = pd.read_csv(TABLE_ROOT / "exact_three_field_timelapse_profiles.csv")
    period_order = pd.read_csv(TABLE_ROOT / "period_definitions.csv")["label"].astype(str).tolist()
    labels = list(dict.fromkeys(df["combination_label"].astype(str).tolist()))
    color_map = _three_field_combo_colors(labels)
    max_count = int(df["component_count"].max()) if not df.empty else 1
    tick_values = _nice_count_ticks(max_count)

    payload = {
        "periods": period_order,
        "maxCount": max_count,
        "ticks": tick_values,
        "frames": {},
    }
    for period in period_order:
        subset = (
            df[df["period"] == period]
            .sort_values(["rank_within_period", "combination_label"], ascending=[True, True])
            .reset_index(drop=True)
        )
        payload["frames"][period] = [
            {
                "combination_label": str(row.combination_label),
                "short_combination_label": str(row.short_combination_label),
                "component_count": int(row.component_count),
                "component_share_pct": float(row.component_share_pct),
                "rank_within_period": int(row.rank_within_period),
                "first_period_seen": str(row.first_period_seen),
                "last_period_seen": str(row.last_period_seen),
                "net_change_from_previous_period": int(row.net_change_from_previous_period),
                "color": color_map[str(row.combination_label)],
            }
            for row in subset.itertuples(index=False)
        ]

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Exact Three-Field Collaboration Timelapse</title>
  <style>
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #f7fafc;
      color: #17324d;
    }}
    .wrap {{
      max-width: 1320px;
      margin: 0 auto;
      padding: 24px 28px 32px;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 28px;
      line-height: 1.15;
    }}
    .sub {{
      margin: 0 0 18px;
      font-size: 15px;
      color: #52657a;
      max-width: 980px;
    }}
    .controls {{
      display: flex;
      gap: 10px;
      align-items: center;
      flex-wrap: wrap;
      margin-bottom: 14px;
    }}
    button {{
      border: 1px solid #cbd5e1;
      background: white;
      color: #17324d;
      border-radius: 999px;
      padding: 8px 14px;
      font-size: 14px;
      cursor: pointer;
    }}
    button:hover {{
      background: #eef4f8;
    }}
    #periodLabel {{
      font-weight: 700;
      margin-left: 6px;
      min-width: 110px;
    }}
    #slider {{
      width: 260px;
    }}
    .chart-card {{
      background: white;
      border: 1px solid #dbe5ee;
      border-radius: 18px;
      box-shadow: 0 18px 40px rgba(23, 50, 77, 0.08);
      padding: 14px 14px 12px;
    }}
    svg {{
      width: 100%;
      height: auto;
      display: block;
    }}
    .foot {{
      margin-top: 12px;
      font-size: 13px;
      color: #52657a;
    }}
    .tooltip {{
      position: fixed;
      pointer-events: none;
      background: rgba(17, 24, 39, 0.95);
      color: white;
      padding: 10px 12px;
      border-radius: 10px;
      font-size: 12px;
      line-height: 1.45;
      box-shadow: 0 10px 30px rgba(0,0,0,0.25);
      opacity: 0;
      transform: translate(12px, 12px);
      transition: opacity 100ms ease;
      max-width: 280px;
      z-index: 10;
    }}
    .legend {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 8px 18px;
      margin-top: 14px;
      font-size: 12px;
      color: #35516d;
    }}
    .legend-item {{
      display: flex;
      align-items: center;
      gap: 8px;
      min-width: 0;
    }}
    .legend-chip {{
      width: 12px;
      height: 12px;
      border-radius: 999px;
      flex: 0 0 auto;
    }}
    .legend-text {{
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <h1>Exact three-field collaboration timelapse</h1>
    <p class="sub">This interactive bubble race tracks the leading exact three-field connected-component combinations across manuscript periods. Bubble position and size both encode absolute component counts, so the chart is designed to show persistence, intensification, and late emergence rather than within-period percentages alone.</p>
    <div class="controls">
      <button id="prevBtn" type="button">Previous</button>
      <button id="playBtn" type="button">Play</button>
      <button id="pauseBtn" type="button">Pause</button>
      <button id="nextBtn" type="button">Next</button>
      <input id="slider" type="range" min="0" max="{max(len(period_order) - 1, 0)}" value="0" step="1" />
      <span id="periodLabel"></span>
    </div>
    <div class="chart-card">
      <svg id="chart" viewBox="0 0 1280 840" aria-label="Exact three-field collaboration bubble race"></svg>
      <div class="legend" id="legend"></div>
      <div class="foot">Each bubble represents one exact three-field connected-component combination from the display union of the top 12 triads. Absolute counts drive the axis and bubble size; hovering reveals the full triad label, count, within-period share, and first/last observed period.</div>
    </div>
  </div>
  <div class="tooltip" id="tooltip"></div>
  <script>
    const payload = {json.dumps(payload)};
    const svg = document.getElementById("chart");
    const tooltip = document.getElementById("tooltip");
    const legend = document.getElementById("legend");
    const slider = document.getElementById("slider");
    const periodLabel = document.getElementById("periodLabel");
    const periods = payload.periods;
    const frames = payload.frames;
    const width = 1280;
    const height = 840;
    const margin = {{ top: 78, right: 90, bottom: 72, left: 245 }};
    const plotWidth = width - margin.left - margin.right;
    const plotHeight = height - margin.top - margin.bottom;
    const rowStep = plotHeight / 12.5;
    const maxCount = Math.max(payload.maxCount, 1);
    const tickValues = payload.ticks;
    let activeIndex = 0;
    let timerId = null;

    const comboLabels = [];
    periods.forEach((period) => {{
      (frames[period] || []).forEach((row) => {{
        if (!comboLabels.includes(row.combination_label)) comboLabels.push(row.combination_label);
      }});
    }});

    function xScale(value) {{
      return margin.left + (Math.max(0, value) / maxCount) * plotWidth;
    }}

    function yScale(rank) {{
      return margin.top + (rank - 0.5) * rowStep;
    }}

    function radiusScale(value) {{
      if (value <= 0) return 8;
      return 12 + Math.sqrt(value / maxCount) * 34;
    }}

    function showTooltip(event, row) {{
      tooltip.innerHTML = `
        <div><strong>${{row.short_combination_label}}</strong></div>
        <div>${{row.combination_label}}</div>
        <div>Count: ${{row.component_count}}</div>
        <div>Period share: ${{row.component_share_pct.toFixed(1)}}%</div>
        <div>Rank: #${{row.rank_within_period}}</div>
        <div>Observed: ${{row.first_period_seen}} to ${{row.last_period_seen}}</div>
      `;
      tooltip.style.opacity = "1";
      moveTooltip(event);
    }}

    function moveTooltip(event) {{
      tooltip.style.left = `${{event.clientX + 10}}px`;
      tooltip.style.top = `${{event.clientY + 10}}px`;
    }}

    function hideTooltip() {{
      tooltip.style.opacity = "0";
    }}

    function el(name, attrs = {{}}, parent = null) {{
      const node = document.createElementNS("http://www.w3.org/2000/svg", name);
      Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, value));
      if (parent) parent.appendChild(node);
      return node;
    }}

    function setupStatic() {{
      svg.innerHTML = "";
      el("rect", {{ x: 0, y: 0, width, height, fill: "white" }}, svg);
      el("text", {{
        x: margin.left,
        y: 34,
        fill: "#17324d",
        "font-size": "28",
        "font-weight": "700",
      }}, svg).textContent = "Top exact three-field combinations across manuscript periods";
      el("text", {{
        x: margin.left,
        y: 58,
        fill: "#52657a",
        "font-size": "14",
      }}, svg).textContent = "Animated bubble race using absolute connected-component counts";

      el("line", {{
        x1: margin.left,
        y1: height - margin.bottom,
        x2: width - margin.right,
        y2: height - margin.bottom,
        stroke: "#94a3b8",
        "stroke-width": "1.2",
      }}, svg);

      tickValues.forEach((tick) => {{
        const x = xScale(tick);
        el("line", {{
          x1: x,
          y1: margin.top,
          x2: x,
          y2: height - margin.bottom,
          stroke: "#e2e8f0",
          "stroke-width": "1",
        }}, svg);
        el("text", {{
          x,
          y: height - margin.bottom + 24,
          fill: "#52657a",
          "font-size": "12",
          "text-anchor": "middle",
        }}, svg).textContent = String(tick);
      }});

      for (let rank = 1; rank <= 12; rank += 1) {{
        const y = yScale(rank);
        el("line", {{
          x1: margin.left,
          y1: y,
          x2: width - margin.right,
          y2: y,
          stroke: "#f1f5f9",
          "stroke-width": "1",
        }}, svg);
        el("text", {{
          x: margin.left - 18,
          y: y + 4,
          fill: "#52657a",
          "font-size": "12",
          "text-anchor": "end",
        }}, svg).textContent = `#${{rank}}`;
      }}

      el("text", {{
        x: (margin.left + width - margin.right) / 2,
        y: height - 16,
        fill: "#35516d",
        "font-size": "13",
        "text-anchor": "middle",
      }}, svg).textContent = "Connected components containing the exact three-field combination";
    }}

    function renderLegend() {{
      legend.innerHTML = "";
      comboLabels.forEach((label) => {{
        const sample = periods.map((p) => (frames[p] || []).find((row) => row.combination_label === label)).find(Boolean);
        if (!sample) return;
        const item = document.createElement("div");
        item.className = "legend-item";
        item.innerHTML = `<span class="legend-chip" style="background:${{sample.color}}"></span><span class="legend-text">${{sample.short_combination_label}}</span>`;
        legend.appendChild(item);
      }});
    }}

    function renderFrame(index) {{
      activeIndex = index;
      slider.value = String(index);
      const period = periods[index];
      periodLabel.textContent = period;
      setupStatic();
      const rows = (frames[period] || []).slice().sort((a, b) => a.rank_within_period - b.rank_within_period);

      el("text", {{
        x: width - margin.right,
        y: 48,
        fill: "#17324d",
        "font-size": "30",
        "font-weight": "700",
        "text-anchor": "end",
      }}, svg).textContent = period;

      rows.forEach((row) => {{
        const y = yScale(row.rank_within_period);
        const x = xScale(row.component_count);
        const radius = radiusScale(row.component_count);
        const opacity = row.component_count > 0 ? 0.88 : 0.12;
        const group = el("g", {{ cursor: "pointer" }}, svg);
        const circle = el("circle", {{
          cx: x,
          cy: y,
          r: radius,
          fill: row.color,
          opacity,
          stroke: "white",
          "stroke-width": "1.2",
        }}, group);
        el("text", {{
          x: x + radius + 10,
          y: y + 4,
          fill: row.component_count > 0 ? "#17324d" : "#9aa7b5",
          "font-size": "12",
          "font-weight": row.component_count > 0 ? "600" : "400",
        }}, group).textContent = row.short_combination_label;
        if (row.component_count > 0) {{
          el("text", {{
            x,
            y: y + 4,
            fill: "white",
            "font-size": radius >= 18 ? "12" : "10",
            "font-weight": "700",
            "text-anchor": "middle",
          }}, group).textContent = String(row.component_count);
        }}
        group.addEventListener("mouseenter", (event) => showTooltip(event, row));
        group.addEventListener("mousemove", moveTooltip);
        group.addEventListener("mouseleave", hideTooltip);
      }});
    }}

    function stopPlayback() {{
      if (timerId !== null) {{
        clearInterval(timerId);
        timerId = null;
      }}
    }}

    function nextFrame() {{
      renderFrame((activeIndex + 1) % periods.length);
    }}

    function prevFrame() {{
      renderFrame((activeIndex - 1 + periods.length) % periods.length);
    }}

    document.getElementById("playBtn").addEventListener("click", () => {{
      stopPlayback();
      timerId = setInterval(nextFrame, 1600);
    }});
    document.getElementById("pauseBtn").addEventListener("click", stopPlayback);
    document.getElementById("nextBtn").addEventListener("click", () => {{
      stopPlayback();
      nextFrame();
    }});
    document.getElementById("prevBtn").addEventListener("click", () => {{
      stopPlayback();
      prevFrame();
    }});
    slider.addEventListener("input", (event) => {{
      stopPlayback();
      renderFrame(Number(event.target.value));
    }});

    renderLegend();
    renderFrame(0);
  </script>
</body>
</html>
"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return out_path


def generate_exact_three_field_preview(out_path: Path) -> Path:
    df = pd.read_csv(TABLE_ROOT / "exact_three_field_timelapse_profiles.csv")
    period_order = pd.read_csv(TABLE_ROOT / "period_definitions.csv")["label"].astype(str).tolist()
    labels = list(dict.fromkeys(df["combination_label"].astype(str).tolist()))
    color_map = _three_field_combo_colors(labels)
    max_count = int(df["component_count"].max()) if not df.empty else 1
    x_pad = max(6, int(round(max_count * 0.42)))

    fig, axes = plt.subplots(2, 3, figsize=(18.0, 11.0), dpi=220, sharex=True, sharey=True)
    axes_array = np.atleast_1d(axes).flatten()
    fig.patch.set_facecolor("white")

    for ax, period in zip(axes_array, period_order):
        subset = (
            df[df["period"] == period]
            .sort_values(["rank_within_period", "combination_label"], ascending=[True, True])
            .reset_index(drop=True)
        )
        for row in subset.itertuples(index=False):
            x = int(row.component_count)
            y = int(row.rank_within_period)
            radius = 120 + 70 * np.sqrt(max(x, 1))
            opacity = 0.88 if x > 0 else 0.10
            color = color_map[str(row.combination_label)]
            ax.scatter(
                [x],
                [y],
                s=radius,
                color=color,
                alpha=opacity,
                edgecolors="white",
                linewidths=0.8,
                zorder=3,
            )
            if x > 0:
                ax.text(
                    x,
                    y,
                    f"{x}",
                    ha="center",
                    va="center",
                    fontsize=7.1,
                    color="white",
                    fontweight="bold",
                    zorder=4,
                )
            ax.text(
                x + max_count * 0.04 + 0.5,
                y,
                str(row.short_combination_label),
                ha="left",
                va="center",
                fontsize=6.6,
                color="#17324d" if x > 0 else "#94a3b8",
                zorder=4,
            )

        ax.set_title(period, fontsize=11.5, fontweight="bold", color="#17324d", pad=8)
        ax.set_xlim(0, max_count + x_pad)
        ax.set_ylim(12.8, 0.2)
        ax.set_yticks(range(1, 13))
        ax.set_yticklabels([f"#{rank}" for rank in range(1, 13)], fontsize=8)
        ax.grid(axis="x", color="#dbe5ee", linewidth=0.8)
        ax.grid(axis="y", color="#f1f5f9", linewidth=0.6)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color("#cbd5e1")
        ax.spines["bottom"].set_color("#cbd5e1")
        ax.tick_params(axis="x", labelsize=8, colors="#52657a")
        ax.tick_params(axis="y", labelsize=8, colors="#52657a")
        ax.set_xlabel("Component count", fontsize=8.5, color="#35516d")

    for ax in axes_array[len(period_order) :]:
        ax.axis("off")

    fig.suptitle(
        "Timelapse of leading exact three-field collaboration combinations",
        fontsize=16,
        fontweight="bold",
        x=0.05,
        ha="left",
        color="#17324d",
        y=0.98,
    )
    fig.text(
        0.05,
        0.02,
        "Each panel shows the same top-12 union of exact three-field triads. Bubble size and horizontal position both encode absolute connected-component counts, while labels preserve triad identity across periods.",
        ha="left",
        va="bottom",
        fontsize=9,
        color="#52657a",
    )
    fig.subplots_adjust(left=0.07, right=0.985, top=0.90, bottom=0.08, hspace=0.28, wspace=0.16)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    return out_path


def ensure_report_assets() -> dict[str, Path]:
    ASSET_ROOT.mkdir(parents=True, exist_ok=True)
    INTERACTIVE_ROOT.mkdir(parents=True, exist_ok=True)

    assets = {
        "all_institutions_role_flow": ASSET_ROOT / "figure_option1_all_institutions_role_flow.png",
        "field_small_multiples": ASSET_ROOT / "figure_option2_field_small_multiples_role_flow.png",
        "top_trajectories": ASSET_ROOT / "figure_option3_top_institution_trajectories.png",
        "role_flow_overview": ASSET_ROOT / "figure_role_flow_sankey_static.png",
        "interdisciplinarity_heatmap": ASSET_ROOT / "figure_interdisciplinarity_pairwise_heatmap.png",
        "two_field_spider_profiles": ASSET_ROOT / "figure_exact_two_field_spider_profiles.png",
        "three_field_timelapse_preview": ASSET_ROOT / "figure_exact_three_field_bubble_timelapse.png",
        "prominent_transition_heatmap": ASSET_ROOT / "figure_prominent_institution_transition_heatmap.png",
        "who_region_collaboration_heatmap": ASSET_ROOT / "figure_who_region_collaboration_heatmap.png",
        "country_collaboration_heatmap": ASSET_ROOT / "figure_country_collaboration_heatmap.png",
        "funding_role_flow": ASSET_ROOT / "figure_funding_role_flow_comparison.png",
        "funding_exact_two_field_spider_profiles": ASSET_ROOT / "figure_funding_exact_two_field_spider_profiles.png",
        "three_field_timelapse_html": INTERACTIVE_ROOT / "exact_three_field_bubble_race.html",
    }

    _copy_static_png(FLOW_ROOT / "option1_all_institutions_role_flow.png", assets["all_institutions_role_flow"])
    _copy_static_png(FLOW_ROOT / "option2_field_small_multiples_role_flow.png", assets["field_small_multiples"])
    _copy_static_png(FLOW_ROOT / "option3_top_institution_trajectories.png", assets["top_trajectories"])
    generate_role_flow_overview(assets["role_flow_overview"])
    generate_interdisciplinarity_heatmap(assets["interdisciplinarity_heatmap"])
    generate_two_field_spider_profiles(assets["two_field_spider_profiles"])
    generate_exact_three_field_timelapse_html(assets["three_field_timelapse_html"])
    generate_exact_three_field_preview(assets["three_field_timelapse_preview"])
    generate_prominent_institution_transition_heatmap(assets["prominent_transition_heatmap"])
    generate_who_region_collaboration_heatmap(assets["who_region_collaboration_heatmap"])
    generate_country_collaboration_heatmap(assets["country_collaboration_heatmap"])
    generate_funding_role_flow_comparison(assets["funding_role_flow"])
    generate_funding_exact_two_field_spider_profiles(assets["funding_exact_two_field_spider_profiles"])
    return assets


def main() -> None:
    assets = ensure_report_assets()
    for key, path in assets.items():
        print(f"{key}: {path}")


if __name__ == "__main__":
    main()
