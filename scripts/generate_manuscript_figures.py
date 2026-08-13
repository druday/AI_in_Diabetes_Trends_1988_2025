#!/usr/bin/env python3
"""Publication-quality manuscript figures for AI-in-Diabetology v3.0.

Generates main-text Figures 1–4 and Supplementary Figures S1–S14 from
existing analysis tables / networks under outputs/ and data/.

Outputs (PDF + 600 dpi PNG, plus TIFF where practical):
  Reports/figures/manuscript_v3/
"""

from __future__ import annotations

import ast
import json
import os
import sys
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).resolve().parents[1] / ".mplconfig"))

import matplotlib as mpl
import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd
import yaml
from matplotlib.colors import LinearSegmentedColormap, LogNorm
from matplotlib.lines import Line2D
from matplotlib.patches import FancyBboxPatch, Polygon, Rectangle
from matplotlib.ticker import FuncFormatter, LogLocator, NullFormatter

warnings.filterwarnings("ignore", category=FutureWarning)

ROOT = Path(__file__).resolve().parents[1]
TABLE = ROOT / "outputs" / "tables"
FLOW = ROOT / "outputs" / "figures" / "flow_options"
NETWORKS = ROOT / "outputs" / "networks"
OUT = ROOT / "Reports" / "figures" / "manuscript_v3"
PANEL_OUT = OUT / "panels"

# ---------------------------------------------------------------------------
# Visual system
# ---------------------------------------------------------------------------

PERIOD_ORDER = [
    "1988-2015",
    "2016-2019",
    "2020-2021",
    "2022-2023",
    "2024-2024",
    "2025-2025",
]
PERIOD_DISPLAY = {
    "1988-2015": "1988–2015",
    "2016-2019": "2016–2019",
    "2020-2021": "2020–2021",
    "2022-2023": "2022–2023",
    "2024-2024": "2024",
    "2025-2025": "2025",
}

# Okabe–Ito–inspired, print-safe palette
C = {
    "ink": "#1a1a1a",
    "muted": "#5c5c5c",
    "grid": "#e6e6e6",
    "spine": "#333333",
    "navy": "#0B3D5C",
    "blue": "#0072B2",
    "sky": "#56B4E9",
    "teal": "#009E73",
    "ochre": "#E69F00",
    "vermilion": "#D55E00",
    "purple": "#CC79A7",
    "grey": "#999999",
    "light": "#F2F2F2",
    "outlier": "#E69F00",
}

ROLE_KEYS = ["Core", "Semi-Peripheral", "Peripheral", "Isolate", "Absent"]
ROLE_LABELS = {
    "Core": "Highly collaborative",
    "Semi-Peripheral": "Moderately collaborative",
    "Peripheral": "Limited collaboration",
    "Isolate": "Isolated",
    "Absent": "Entry / exit",
}
# Match earlier role-flow / Sankey assets (role_flow.py, generate_flow_prototypes.py)
ROLE_COLORS = {
    "Core": "#1f77b4",
    "Semi-Peripheral": "#17becf",
    "Peripheral": "#ff7f0e",
    "Isolate": "#bcbd22",
    "Absent": "#c7c7c7",
}

DOMAIN_LABELS = {
    "Technical_AI_Informatics": "Technical / AI & informatics",
    "Endocrinology_Diabetes": "Endocrinology & diabetes",
    "Ophthalmology_Vision": "Ophthalmology & vision",
    "Complications_Cardiometabolic_Nephrology_Neurology": "Complications & cardiometabolic",
    "Pediatrics_Maternal_Health": "Pediatrics & maternal health",
    "General_Clinical_Medicine": "Clinical medicine",
    "Public_Health_Epidemiology": "Public health & epidemiology",
    "Nutrition": "Nutrition",
    "Nursing_Diabetes_Education": "Nursing & diabetes education",
    "Behavioral_Psychological": "Behavioral & psychological",
    "Exercise_Lifestyle": "Exercise & lifestyle",
    "Industry_Digital_Health_Device": "Industry / digital health / device",
    "Other": "Unclassified",
}
DOMAIN_SHORT = {
    "Technical_AI_Informatics": "Tech/AI",
    "Endocrinology_Diabetes": "Endocrinology",
    "Ophthalmology_Vision": "Ophthalmology",
    "Complications_Cardiometabolic_Nephrology_Neurology": "Complications",
    "Pediatrics_Maternal_Health": "Pediatrics",
    "General_Clinical_Medicine": "Clinical med.",
    "Public_Health_Epidemiology": "Public health",
    "Nutrition": "Nutrition",
    "Nursing_Diabetes_Education": "Nursing",
    "Behavioral_Psychological": "Behavioral",
    "Exercise_Lifestyle": "Exercise",
    "Industry_Digital_Health_Device": "Industry",
    "Other": "Other",
}

WHO_ORDER = ["WPRO", "PAHO", "EURO", "SEARO", "EMRO", "AFRO"]
WHO_COLORS = {
    "WPRO": C["ochre"],
    "PAHO": C["navy"],
    "EURO": C["blue"],
    "SEARO": C["sky"],
    "EMRO": "#7A9EBF",
    "AFRO": C["grey"],
}

PERIOD_COLORS = {
    "1988-2015": "#9CA3AF",
    "2016-2019": "#E69F00",
    "2020-2021": "#0072B2",
    "2022-2023": "#009E73",
    "2024-2024": "#CC79A7",
    "2025-2025": "#D55E00",
}

FUNDING_ORDER = ["US_FEDERAL_FUNDED", "NON_US_OR_INTL_FUNDED", "NO_GRANT_LISTED"]
FUNDING_LABELS = {
    "US_FEDERAL_FUNDED": "US federally funded",
    "NON_US_OR_INTL_FUNDED": "Non-US / international",
    "NO_GRANT_LISTED": "No grant listed",
}
FUNDING_COLORS = {
    "US_FEDERAL_FUNDED": C["blue"],
    "NON_US_OR_INTL_FUNDED": C["ochre"],
    "NO_GRANT_LISTED": C["grey"],
}

MM = 1 / 25.4  # inches per mm
SINGLE_COL = 89 * MM
DOUBLE_COL = 183 * MM


def apply_style() -> None:
    mpl.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "savefig.facecolor": "white",
            "savefig.bbox": "tight",
            "savefig.pad_inches": 0.02,
            "font.family": "sans-serif",
            "font.sans-serif": [
                "Helvetica Neue",
                "Helvetica",
                "Arial",
                "DejaVu Sans",
            ],
            "font.size": 7,
            "axes.titlesize": 8,
            "axes.labelsize": 7.5,
            "xtick.labelsize": 7,
            "ytick.labelsize": 7,
            "legend.fontsize": 7,
            "axes.linewidth": 0.6,
            "axes.edgecolor": C["spine"],
            "axes.labelcolor": C["ink"],
            "xtick.color": C["ink"],
            "ytick.color": C["ink"],
            "text.color": C["ink"],
            "axes.spines.top": False,
            "axes.spines.right": False,
            "xtick.major.width": 0.5,
            "ytick.major.width": 0.5,
            "xtick.major.size": 2.5,
            "ytick.major.size": 2.5,
            "lines.linewidth": 1.4,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "svg.fonttype": "none",
        }
    )


def panel_label(
    ax: plt.Axes,
    label: str,
    x: float = 0.0,
    y: float = 1.0,
    *,
    dx: float = -4.0,
    dy: float = 3.0,
) -> None:
    """Nature-style panel letter: outside top-left of the axes, clear of spines/data."""
    ax.annotate(
        label,
        xy=(x, y),
        xycoords="axes fraction",
        xytext=(dx, dy),
        textcoords="offset points",
        fontsize=9,
        fontweight="bold",
        va="bottom",
        ha="right",
        color=C["ink"],
        clip_on=False,
        annotation_clip=False,
        zorder=20,
    )


def style_ax(ax: plt.Axes, grid_y: bool = True) -> None:
    ax.spines["left"].set_linewidth(0.6)
    ax.spines["bottom"].set_linewidth(0.6)
    ax.tick_params(direction="out", length=2.5, width=0.5, pad=2)
    if grid_y:
        ax.yaxis.grid(True, color=C["grid"], linewidth=0.4, zorder=0)
        ax.set_axisbelow(True)


def period_ticks(ax: plt.Axes, rotation: float = 30) -> None:
    ax.set_xticks(range(len(PERIOD_ORDER)))
    ax.set_xticklabels(
        [PERIOD_DISPLAY[p] for p in PERIOD_ORDER],
        rotation=rotation,
        ha="right" if rotation else "center",
        rotation_mode="anchor",
    )


def save_figure(fig: plt.Figure, stem: str, also_tiff: bool = True) -> list[Path]:
    OUT.mkdir(parents=True, exist_ok=True)
    PANEL_OUT.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    pdf = OUT / f"{stem}.pdf"
    png = OUT / f"{stem}.png"
    fig.savefig(pdf, dpi=600, bbox_inches="tight", pad_inches=0.04)
    fig.savefig(png, dpi=600, bbox_inches="tight", pad_inches=0.04)
    paths.extend([pdf, png])
    if also_tiff:
        tiff = OUT / f"{stem}.tiff"
        try:
            fig.savefig(tiff, dpi=600, bbox_inches="tight", pad_inches=0.04, pil_kwargs={"compression": "tiff_lzw"})
            paths.append(tiff)
        except Exception:
            fig.savefig(tiff, dpi=300, bbox_inches="tight", pad_inches=0.04)
            paths.append(tiff)
    print(f"  saved {stem}: " + ", ".join(p.suffix for p in paths))
    return paths


def category_order() -> list[str]:
    with (ROOT / "config" / "protocol.yaml").open(encoding="utf-8") as handle:
        protocol = yaml.safe_load(handle)
    return [str(item["label"]) for item in protocol["classification"]["categories"]]


def parse_listlike(value: Any) -> list[Any]:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return []
    if isinstance(value, list):
        return value
    if hasattr(value, "tolist") and not isinstance(value, str):
        try:
            return list(value.tolist())
        except Exception:
            pass
    if isinstance(value, str):
        text = value.strip()
        if not text or text == "[]":
            return []
        for loader in (json.loads, ast.literal_eval):
            try:
                parsed = loader(text)
                if isinstance(parsed, list):
                    return parsed
            except Exception:
                continue
    return []


def normalize_country(name: str) -> str:
    key = str(name).strip().lower()
    aliases = {
        "usa": "United States",
        "us": "United States",
        "united states": "United States",
        "united states of america": "United States",
        "uk": "United Kingdom",
        "united kingdom": "United Kingdom",
        "england": "United Kingdom",
        "scotland": "United Kingdom",
        "wales": "United Kingdom",
        "korea": "South Korea",
        "republic of korea": "South Korea",
        "south korea": "South Korea",
        "china": "China",
        "india": "India",
        "australia": "Australia",
        "germany": "Germany",
        "canada": "Canada",
        "japan": "Japan",
        "italy": "Italy",
        "spain": "Spain",
        "france": "France",
        "brazil": "Brazil",
    }
    if key in aliases:
        return aliases[key]
    return " ".join(part.capitalize() for part in key.split())


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------


def load_structural() -> pd.DataFrame:
    df = pd.read_csv(TABLE / "structural_comparison_summary.csv")
    df["period"] = pd.Categorical(df["period"], PERIOD_ORDER, ordered=True)
    return df.sort_values("period").reset_index(drop=True)


def load_cluster() -> pd.DataFrame:
    df = pd.read_csv(TABLE / "cluster_interdisciplinarity_metrics.csv")
    df["period"] = pd.Categorical(df["period"], PERIOD_ORDER, ordered=True)
    df["none_ratio"] = (
        1.0
        - df["single_field_ratio"]
        - df["two_field_ratio"]
        - df["three_or_more_field_ratio"]
    ).clip(lower=0)
    return df.sort_values("period").reset_index(drop=True)


def load_role_transitions() -> pd.DataFrame:
    df = pd.read_csv(TABLE / "role_transition_counts.csv")
    return df


def graphml_path(period: str) -> Path:
    return NETWORKS / f"institutions_{period.replace('-', '_')}.graphml"


def load_tier_shares() -> pd.DataFrame:
    """Participation-tier shares from the descriptive table (matches manuscript Fig. 2b)."""
    desc = pd.read_csv(TABLE / "table_descriptive_by_period.csv")
    role_from_metric = [
        ("High-centrality", "Core"),
        ("Mid-centrality", "Semi-Peripheral"),
        ("Low-centrality", "Peripheral"),
        ("Zero-centrality", "Isolate"),
    ]
    rows = []
    for _, row in desc.iterrows():
        metric = str(row["Metric"])
        key = None
        for token, role in role_from_metric:
            if token in metric:
                key = role
                break
        if key is None:
            continue
        for period in PERIOD_ORDER:
            cell = str(row[period])
            if "(" in cell and "%" in cell:
                pct = float(cell.split("(")[1].split("%")[0])
            else:
                pct = np.nan
            rows.append({"period": period, "role": key, "share": pct})
    out = pd.DataFrame(rows)
    if out.empty:
        out = _tier_shares_from_graphs()
    return out


def _tier_shares_from_graphs() -> pd.DataFrame:
    rows = []
    for period in PERIOD_ORDER:
        G = nx.read_graphml(graphml_path(period))
        degrees = np.array([d for _, d in G.degree()])
        n = len(degrees)
        nonzero = degrees[degrees > 0]
        isolate = int((degrees == 0).sum())
        if len(nonzero) == 0:
            shares = {"Isolate": 100.0, "Peripheral": 0, "Semi-Peripheral": 0, "Core": 0}
        else:
            thr90 = np.quantile(nonzero, 0.90)
            thr50 = np.quantile(nonzero, 0.50)
            core_n = int(((degrees > 0) & (degrees >= thr90)).sum())
            mid_n = int(((degrees > 0) & (degrees >= thr50) & (degrees < thr90)).sum())
            low_n = int(((degrees > 0) & (degrees < thr50)).sum())
            shares = {
                "Core": 100 * core_n / n,
                "Semi-Peripheral": 100 * mid_n / n,
                "Peripheral": 100 * low_n / n,
                "Isolate": 100 * isolate / n,
            }
        for role, share in shares.items():
            rows.append({"period": period, "role": role, "share": share})
    return pd.DataFrame(rows)


def load_domain_counts_2025() -> pd.DataFrame:
    G = nx.read_graphml(graphml_path("2025-2025"))
    counts: dict[str, int] = {}
    for _, attrs in G.nodes(data=True):
        t = str(attrs.get("type", "Other"))
        counts[t] = counts.get(t, 0) + 1
    rows = [{"domain": k, "count": v} for k, v in counts.items() if k != "Other"]
    df = pd.DataFrame(rows).sort_values("count", ascending=True)
    return df


def load_clinical_partners(period: str = "2025-2025") -> pd.DataFrame:
    pw = pd.read_csv(TABLE / "component_field_pairwise_collaboration_by_period.csv")
    clin = "General_Clinical_Medicine"
    sub = pw[(pw["period"] == period) & (~pw["is_diagonal"])].copy()
    partners = []
    for row in sub.itertuples(index=False):
        if row.field_a == clin:
            partners.append({"domain": row.field_b, "count": int(row.component_count)})
        elif row.field_b == clin:
            partners.append({"domain": row.field_a, "count": int(row.component_count)})
    df = pd.DataFrame(partners).groupby("domain", as_index=False)["count"].sum()
    return df.sort_values("count", ascending=True)


def load_who_shares() -> pd.DataFrame:
    who = pd.read_csv(TABLE / "who_region_summary.csv")
    totals = who.groupby("period")["publication_count"].transform("sum")
    who = who.copy()
    who["share"] = 100.0 * who["publication_count"] / totals
    return who


def load_country_shares(top_countries: list[str] | None = None) -> pd.DataFrame:
    pubs = pd.read_parquet(ROOT / "data" / "processed" / "publications.parquet")
    if top_countries is None:
        top_countries = ["United States", "China", "India", "Australia", "Germany"]
    records = []
    for period, g in pubs.groupby("period", observed=True):
        counts: dict[str, int] = {}
        for raw in g["countries"]:
            countries = {normalize_country(c) for c in parse_listlike(raw) if str(c).strip()}
            for c in countries:
                counts[c] = counts.get(c, 0) + 1
        tot = len(g)
        for c in top_countries:
            records.append(
                {
                    "period": period,
                    "country": c,
                    "count": counts.get(c, 0),
                    "share": 100.0 * counts.get(c, 0) / tot if tot else 0.0,
                }
            )
    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# Alluvial helper
# ---------------------------------------------------------------------------


@dataclass
class NodeSpan:
    y0: float
    y1: float


def _hex_to_rgb(color: str) -> np.ndarray:
    raw = str(color).strip().lstrip("#")
    if len(raw) != 6:
        return np.array([0.6, 0.6, 0.6], dtype=float)
    try:
        return np.array([int(raw[i : i + 2], 16) / 255.0 for i in (0, 2, 4)], dtype=float)
    except ValueError:
        return np.array([0.6, 0.6, 0.6], dtype=float)


def _draw_gradient_ribbon(
    ax: plt.Axes,
    x_curve: np.ndarray,
    y_top: np.ndarray,
    y_bot: np.ndarray,
    color_from: str,
    color_to: str,
    *,
    alpha: float,
    n_seg: int = 40,
) -> None:
    """Draw an alluvial band with source→target hue blend along the path."""
    rgb0 = _hex_to_rgb(color_from)
    rgb1 = _hex_to_rgb(color_to)
    n = len(x_curve)
    if n < 2:
        return
    idxs = np.linspace(0, n - 1, n_seg + 1).astype(int)
    for i in range(n_seg):
        i0, i1 = int(idxs[i]), int(idxs[i + 1])
        if i1 <= i0:
            i1 = min(i0 + 1, n - 1)
        xs = x_curve[i0 : i1 + 1]
        yt = y_top[i0 : i1 + 1]
        yb = y_bot[i0 : i1 + 1]
        poly_xy = np.column_stack([np.concatenate([xs, xs[::-1]]), np.concatenate([yt, yb[::-1]])])
        tmid = (i + 0.5) / n_seg
        rgb = (1.0 - tmid) * rgb0 + tmid * rgb1
        ax.add_patch(
            Polygon(
                poly_xy,
                closed=True,
                facecolor=rgb,
                edgecolor="none",
                alpha=alpha,
                lw=0,
                zorder=1,
            )
        )


def draw_alluvial(
    ax: plt.Axes,
    transition_df: pd.DataFrame,
    stage_labels: list[str],
    states: list[str],
    state_colors: dict[str, str],
    *,
    node_width: float = 0.08,
    alpha: float = 0.34,
) -> None:
    ax.set_xlim(-0.25, len(stage_labels) - 0.75)
    ax.set_ylim(0, 1.08)
    ax.axis("off")
    if transition_df.empty:
        ax.text(0.5, 0.5, "No transitions", ha="center", va="center", transform=ax.transAxes)
        return

    node_totals: dict[tuple[int, str], float] = {}
    for i, stage in enumerate(stage_labels):
        if i == len(stage_labels) - 1:
            incoming = transition_df[transition_df["period_to"] == stage].groupby("state_to")["value"].sum()
            for state in states:
                node_totals[(i, state)] = float(incoming.get(state, 0))
        else:
            outgoing = transition_df[transition_df["period_from"] == stage].groupby("state_from")["value"].sum()
            for state in states:
                node_totals[(i, state)] = float(outgoing.get(state, 0))

    stage_totals = [sum(node_totals[(i, s)] for s in states) for i in range(len(stage_labels))]
    max_total = max(stage_totals) if stage_totals else 1.0
    gap = 0.012
    unit = (0.94 - gap * (len(states) - 1)) / max_total
    node_spans: dict[tuple[int, str], NodeSpan] = {}
    for i, stage_total in enumerate(stage_totals):
        used = stage_total * unit + gap * (len(states) - 1)
        y_top = 0.98 - (0.94 - used) / 2.0
        for state in states:
            h = node_totals[(i, state)] * unit
            y_bot = y_top - h
            node_spans[(i, state)] = NodeSpan(y0=y_bot, y1=y_top)
            y_top = y_bot - gap

    x_positions = {stage: i for i, stage in enumerate(stage_labels)}
    out_cursor = {(i, s): node_spans[(i, s)].y1 for i in range(len(stage_labels)) for s in states}
    in_cursor = {(i, s): node_spans[(i, s)].y1 for i in range(len(stage_labels)) for s in states}

    draw_df = transition_df.copy()
    if "pair_index" not in draw_df.columns:
        pair_map = {p: i for i, p in enumerate(stage_labels[:-1])}
        draw_df["pair_index"] = draw_df["period_from"].map(pair_map)
    draw_df = draw_df.sort_values(["pair_index", "state_from", "state_to"])

    for _, row in draw_df.iterrows():
        sf, st = row["state_from"], row["state_to"]
        if sf not in states or st not in states:
            continue
        i0, i1 = x_positions[row["period_from"]], x_positions[row["period_to"]]
        h = float(row["value"]) * unit
        if h <= 0:
            continue
        y0_top = out_cursor[(i0, sf)]
        y0_bot = y0_top - h
        out_cursor[(i0, sf)] = y0_bot
        y1_top = in_cursor[(i1, st)]
        y1_bot = y1_top - h
        in_cursor[(i1, st)] = y1_bot
        t = np.linspace(0, 1, 48)
        smooth = t * t * (3 - 2 * t)
        x_curve = i0 + (i1 - i0) * t
        y_top = (1 - smooth) * y0_top + smooth * y1_top
        y_bot = (1 - smooth) * y0_bot + smooth * y1_bot
        c_from = state_colors.get(sf, "#9ca3af")
        c_to = state_colors.get(st, "#9ca3af")
        # Entry/exit slightly lighter; cross-tier flows denser so hue blend reads clearly
        if sf == "Absent" or st == "Absent":
            a = 0.24
        elif sf != st:
            a = min(0.48, alpha + 0.10)
        else:
            a = alpha
        _draw_gradient_ribbon(ax, x_curve, y_top, y_bot, c_from, c_to, alpha=a, n_seg=48)

    for i, stage in enumerate(stage_labels):
        for state in states:
            span = node_spans[(i, state)]
            height = span.y1 - span.y0
            if height <= 0:
                continue
            ax.add_patch(
                Rectangle(
                    (i - node_width / 2, span.y0),
                    node_width,
                    height,
                    facecolor=state_colors.get(state, "#9ca3af"),
                    edgecolor="white",
                    linewidth=0.4,
                    alpha=0.95,
                    zorder=3,
                )
            )
        ax.text(
            i,
            1.015,
            PERIOD_DISPLAY.get(stage, stage),
            ha="center",
            va="bottom",
            fontsize=6.2,
            color=C["ink"],
            clip_on=False,
            rotation=18,
            rotation_mode="anchor",
        )


# ---------------------------------------------------------------------------
# Main figures
# ---------------------------------------------------------------------------


def figure1() -> list[Path]:
    """Fig. 1 | Growth and network cohesion."""
    df = load_structural()
    x = np.arange(len(PERIOD_ORDER))
    outlier_idx = PERIOD_ORDER.index("2016-2019")

    fig, axes = plt.subplots(
        1,
        2,
        figsize=(DOUBLE_COL, 58 * MM),
        gridspec_kw={"wspace": 0.32},
    )

    # Panel a — log counts
    ax = axes[0]
    style_ax(ax)
    series = {
        "Publications": (df["publication_count"].to_numpy(), "o", C["grey"], "-"),
        "Institutions": (df["nodes"].to_numpy(), "s", C["blue"], "-"),
        "Ties": (df["edges"].to_numpy(), "^", C["navy"], "-"),
    }
    for name, (vals, marker, color, ls) in series.items():
        ax.plot(x, vals, color=color, marker=marker, markersize=4.5, lw=1.5, label=name, zorder=3)
        # Open outlier marker for 2016–2019 ties / institutions note focuses on ties
        if name == "Ties":
            ax.plot(
                x[outlier_idx],
                vals[outlier_idx],
                marker="^",
                markersize=7.5,
                markerfacecolor="none",
                markeredgecolor=C["outlier"],
                markeredgewidth=1.4,
                zorder=4,
                linestyle="None",
            )
    ax.set_yscale("log")
    ax.set_ylabel("Count (log scale)")
    ax.set_ylim(8e2, 1.2e6)
    ax.yaxis.set_major_locator(LogLocator(base=10))
    ax.yaxis.set_minor_locator(LogLocator(base=10, subs=np.arange(2, 10) * 0.1))
    ax.yaxis.set_minor_formatter(NullFormatter())

    def _fmt(v, _):
        if v >= 1e6:
            return f"{v/1e6:.0f}M"
        if v >= 1e3:
            return f"{v/1e3:.0f}k"
        return f"{v:.0f}"

    ax.yaxis.set_major_formatter(FuncFormatter(_fmt))
    period_ticks(ax)
    # End-of-line labels instead of legend box
    for name, (vals, marker, color, ls) in series.items():
        ax.text(
            len(PERIOD_ORDER) - 0.75,
            vals[-1],
            name,
            color=color,
            fontsize=6.5,
            va="center",
            ha="left",
            clip_on=False,
        )
    panel_label(ax, "a")

    # Panel b — median degree + LCC %
    ax = axes[1]
    style_ax(ax)
    ax2 = ax.twinx()
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_linewidth(0.6)
    med = df["median_degree"].to_numpy()
    lcc = df["lcc_share_pct"].to_numpy()
    ax.plot(x, med, color=C["navy"], marker="o", markersize=4.5, lw=1.5, zorder=3)
    ax2.plot(x, lcc, color=C["sky"], marker="D", markersize=4.0, lw=1.3, ls="--", zorder=3)
    ax2.plot(
        x[outlier_idx],
        lcc[outlier_idx],
        marker="D",
        markersize=7.0,
        markerfacecolor="none",
        markeredgecolor=C["outlier"],
        markeredgewidth=1.4,
        zorder=4,
        linestyle="None",
    )
    ax.set_ylabel("Median collaborators")
    ax2.set_ylabel("Largest component (%)")
    ax.set_ylim(-0.3, 7.2)
    ax2.set_ylim(-0.3, 7.2)
    period_ticks(ax)
    ax.text(0.02, 0.98, "Median collaborators", transform=ax.transAxes, color=C["navy"], fontsize=6.5, va="top")
    ax.text(0.02, 0.90, "Largest component (%)", transform=ax.transAxes, color=C["sky"], fontsize=6.5, va="top")
    panel_label(ax, "b")

    fig.subplots_adjust(left=0.10, right=0.90, top=0.88, bottom=0.22)
    return save_figure(fig, "Figure1")


def figure2() -> list[Path]:
    """Fig. 2 | Institutional participation over time."""
    rt = load_role_transitions()
    shares = load_tier_shares()

    fig = plt.figure(figsize=(DOUBLE_COL, 125 * MM))
    gs = fig.add_gridspec(2, 1, height_ratios=[1.55, 1.0], hspace=0.38)
    ax_a = fig.add_subplot(gs[0])
    ax_b = fig.add_subplot(gs[1])

    draw_alluvial(ax_a, rt, PERIOD_ORDER, ROLE_KEYS, ROLE_COLORS)
    panel_label(ax_a, "a", dx=-2, dy=10)

    # Stacked area of tier shares
    style_ax(ax_b, grid_y=True)
    stack_order = ["Isolate", "Peripheral", "Semi-Peripheral", "Core"]  # bottom → top
    mat = []
    for role in stack_order:
        row = []
        for period in PERIOD_ORDER:
            val = shares.loc[(shares.period == period) & (shares.role == role), "share"]
            row.append(float(val.iloc[0]) if len(val) else 0.0)
        mat.append(row)
    mat = np.array(mat)
    x = np.arange(len(PERIOD_ORDER))
    ax_b.stackplot(
        x,
        mat,
        colors=[ROLE_COLORS[r] for r in stack_order],
        labels=[ROLE_LABELS[r] for r in stack_order],
        alpha=0.92,
        lw=0,
    )
    ax_b.set_xlim(-0.2, len(PERIOD_ORDER) - 0.8)
    ax_b.set_ylim(0, 100)
    ax_b.set_ylabel("Institutions (%)")
    period_ticks(ax_b)
    panel_label(ax_b, "b", dx=-6, dy=8)

    # Shared legend
    handles = [
        Rectangle((0, 0), 1, 1, facecolor=ROLE_COLORS[r], edgecolor="none")
        for r in ["Absent"] + stack_order
    ]
    labels = [ROLE_LABELS[r] for r in ["Absent"] + stack_order]
    fig.legend(
        handles,
        labels,
        loc="lower center",
        ncol=5,
        frameon=False,
        bbox_to_anchor=(0.5, -0.01),
        fontsize=6.5,
        handlelength=1.0,
        columnspacing=1.2,
    )
    fig.subplots_adjust(left=0.10, right=0.98, top=0.90, bottom=0.14)
    return save_figure(fig, "Figure2")


def figure3() -> list[Path]:
    """Fig. 3 | Interdisciplinary structure and clinical medicine."""
    cluster = load_cluster()
    domains = load_domain_counts_2025()
    partners = load_clinical_partners("2025-2025")

    fig = plt.figure(figsize=(DOUBLE_COL, 145 * MM))
    gs = fig.add_gridspec(3, 1, height_ratios=[1.05, 1.15, 1.05], hspace=0.42)
    ax_a = fig.add_subplot(gs[0])
    ax_b = fig.add_subplot(gs[1])
    ax_c = fig.add_subplot(gs[2])

    # a — stacked bars + mean domains
    style_ax(ax_a)
    x = np.arange(len(PERIOD_ORDER))
    width = 0.62
    none = cluster["none_ratio"].to_numpy() * 100
    single = cluster["single_field_ratio"].to_numpy() * 100
    two = cluster["two_field_ratio"].to_numpy() * 100
    three = cluster["three_or_more_field_ratio"].to_numpy() * 100
    colors_stack = ["#D9E2EC", "#9FB6C8", "#4A7A9B", "#0B3D5C"]
    labels_stack = ["No classified domain", "Single-domain", "Two-domain", "Three or more"]
    bottoms = np.zeros(len(PERIOD_ORDER))
    for vals, color, lab in zip([none, single, two, three], colors_stack, labels_stack):
        ax_a.bar(x, vals, width, bottom=bottoms, color=color, edgecolor="white", linewidth=0.3, label=lab, zorder=2)
        bottoms += vals
    ax_a.set_ylim(0, 100)
    ax_a.set_ylabel("Communities (%)")
    ax2 = ax_a.twinx()
    ax2.spines["top"].set_visible(False)
    mean_d = cluster["mean_distinct_key_fields_per_component"].to_numpy()
    ax2.plot(x, mean_d, color=C["ochre"], marker="o", markersize=4.5, lw=1.5, markerfacecolor="white", markeredgewidth=1.2)
    ax2.set_ylabel("Mean domains", color=C["ochre"])
    ax2.set_ylim(0, 2.0)
    ax2.tick_params(axis="y", colors=C["ochre"])
    period_ticks(ax_a)
    ax_a.legend(
        loc="upper center",
        bbox_to_anchor=(0.55, 1.28),
        ncol=4,
        frameon=False,
        fontsize=6.2,
        handlelength=0.9,
        columnspacing=0.9,
    )
    panel_label(ax_a, "a", dx=-6, dy=14)

    # b — domain counts 2025
    style_ax(ax_b, grid_y=False)
    ax_b.xaxis.grid(True, color=C["grid"], linewidth=0.4)
    y = np.arange(len(domains))
    ax_b.barh(y, domains["count"], color=C["navy"], height=0.72, edgecolor="none")
    ax_b.set_yticks(y)
    ax_b.set_yticklabels([DOMAIN_LABELS.get(d, d) for d in domains["domain"]], fontsize=6.5)
    ax_b.set_xlabel("Institutions (2025)")
    xmax = domains["count"].max() * 1.18
    ax_b.set_xlim(0, xmax)
    for yi, val in zip(y, domains["count"]):
        ax_b.text(val + xmax * 0.01, yi, f"{val:,}", va="center", ha="left", fontsize=6.2, color=C["ink"])
    panel_label(ax_b, "b", dx=-8, dy=6)

    # c — clinical partners
    style_ax(ax_c, grid_y=False)
    ax_c.xaxis.grid(True, color=C["grid"], linewidth=0.4)
    y = np.arange(len(partners))
    ax_c.hlines(y, 0, partners["count"], color="#CBD5E1", lw=1.0, zorder=1)
    ax_c.scatter(partners["count"], y, s=28, color=C["navy"], zorder=3, edgecolors="white", linewidths=0.4)
    ax_c.set_yticks(y)
    ax_c.set_yticklabels([DOMAIN_LABELS.get(d, d) for d in partners["domain"]], fontsize=6.5)
    ax_c.set_xlabel("Communities shared with clinical medicine (2025)")
    xmax = partners["count"].max() * 1.18
    ax_c.set_xlim(0, xmax)
    for yi, val in zip(y, partners["count"]):
        ax_c.text(val + xmax * 0.01, yi, f"{val:,}", va="center", ha="left", fontsize=6.2, color=C["ink"])
    panel_label(ax_c, "c", dx=-8, dy=6)

    fig.subplots_adjust(left=0.30, right=0.94, top=0.88, bottom=0.06)
    return save_figure(fig, "Figure3")


def _annotate_series_ends(ax: plt.Axes, series: dict[str, tuple[list[float], str]], x_end: float) -> None:
    """Place non-overlapping end-of-line labels."""
    items = [(name, vals[-1], color) for name, (vals, color) in series.items()]
    items.sort(key=lambda t: t[1])
    # Greedy vertical spacing in data coordinates
    if not items:
        return
    ymin, ymax = ax.get_ylim()
    min_gap = 0.045 * (ymax - ymin)
    placed_y: list[float] = []
    for name, y, color in items:
        yy = y
        for py in placed_y:
            if abs(yy - py) < min_gap:
                yy = py + min_gap
        if yy > ymax:
            yy = ymax - 0.01 * (ymax - ymin)
        placed_y.append(yy)
        ax.annotate(
            name,
            xy=(x_end, y),
            xytext=(x_end + 0.18, yy),
            textcoords="data",
            color=color,
            fontsize=6.5,
            va="center",
            ha="left",
            arrowprops=dict(arrowstyle="-", color=color, lw=0.5, shrinkA=0, shrinkB=0)
            if abs(yy - y) > min_gap * 0.4
            else None,
            clip_on=False,
        )


def figure4() -> list[Path]:
    """Fig. 4 | Geographic distribution."""
    who = load_who_shares()
    countries = load_country_shares()

    fig, axes = plt.subplots(
        2,
        1,
        figsize=(DOUBLE_COL * 0.78, 110 * MM),
        sharex=True,
        gridspec_kw={"hspace": 0.18},
    )
    x = np.arange(len(PERIOD_ORDER))

    ax = axes[0]
    style_ax(ax)
    who_series: dict[str, tuple[list[float], str]] = {}
    for region in WHO_ORDER:
        vals = []
        for period in PERIOD_ORDER:
            sub = who[(who.period == period) & (who.who_region == region)]
            vals.append(float(sub["share"].iloc[0]) if len(sub) else 0.0)
        ax.plot(x, vals, marker="o", markersize=3.8, color=WHO_COLORS[region], lw=1.4)
        who_series[region] = (vals, WHO_COLORS[region])
    ax.set_ylabel("Share of publications (%)")
    ax.set_ylim(0, 45)
    _annotate_series_ends(ax, who_series, len(PERIOD_ORDER) - 1)
    panel_label(ax, "a")

    ax = axes[1]
    style_ax(ax)
    country_colors = {
        "China": C["ochre"],
        "United States": C["navy"],
        "India": C["blue"],
        "Australia": C["teal"],
        "Germany": C["sky"],
    }
    country_series: dict[str, tuple[list[float], str]] = {}
    for country, color in country_colors.items():
        vals = []
        for period in PERIOD_ORDER:
            sub = countries[(countries.period == period) & (countries.country == country)]
            vals.append(float(sub["share"].iloc[0]) if len(sub) else 0.0)
        ax.plot(x, vals, marker="o", markersize=3.8, color=color, lw=1.4)
        country_series[country] = (vals, color)
    ax.set_ylabel("Share of publications (%)")
    ax.set_ylim(0, 45)
    period_ticks(ax)
    _annotate_series_ends(ax, country_series, len(PERIOD_ORDER) - 1)
    panel_label(ax, "b")

    fig.subplots_adjust(left=0.14, right=0.78, top=0.92, bottom=0.12)
    return save_figure(fig, "Figure4")


# ---------------------------------------------------------------------------
# Supplementary figures
# ---------------------------------------------------------------------------


def fig_s1() -> list[Path]:
    """S1 | Tier-transition heatmap (active institutions only), row-normalised."""
    rt = load_role_transitions()
    active = ["Core", "Semi-Peripheral", "Peripheral", "Isolate"]
    sub = rt[rt["state_from"].isin(active) & rt["state_to"].isin(active)].copy()
    agg = sub.groupby(["state_from", "state_to"], as_index=False)["value"].sum()
    mat = pd.DataFrame(0.0, index=active, columns=active)
    for row in agg.itertuples(index=False):
        mat.loc[row.state_from, row.state_to] = row.value
    row_sums = mat.sum(axis=1).replace(0, np.nan)
    pct = mat.div(row_sums, axis=0) * 100

    fig, ax = plt.subplots(figsize=(SINGLE_COL * 1.35, SINGLE_COL * 1.2))
    im = ax.imshow(pct.values, cmap="Blues", vmin=0, vmax=100)
    ax.set_xticks(range(len(active)))
    ax.set_yticks(range(len(active)))
    ax.set_xticklabels([ROLE_LABELS[s].replace(" ", "\n") for s in active], fontsize=6.2)
    ax.set_yticklabels([ROLE_LABELS[s] for s in active], fontsize=6.5)
    ax.set_xlabel("Next-period tier")
    ax.set_ylabel("Current-period tier")
    for i in range(len(active)):
        for j in range(len(active)):
            val = pct.values[i, j]
            if np.isnan(val):
                continue
            color = "white" if val >= 45 else C["ink"]
            ax.text(j, i, f"{val:.1f}", ha="center", va="center", fontsize=6.5, color=color)
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("% of institutions", fontsize=6.5)
    cbar.ax.tick_params(labelsize=6)
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_linewidth(0.5)
    fig.tight_layout()
    return save_figure(fig, "FigS1")


def fig_s2() -> list[Path]:
    """S2 | Static institutional role flow overview."""
    rt = load_role_transitions()
    fig, ax = plt.subplots(figsize=(DOUBLE_COL, 78 * MM))
    draw_alluvial(ax, rt, PERIOD_ORDER, ROLE_KEYS, ROLE_COLORS)
    handles = [
        Rectangle((0, 0), 1, 1, facecolor=ROLE_COLORS[r], edgecolor="none") for r in ROLE_KEYS
    ]
    ax.legend(
        handles,
        [ROLE_LABELS[r] for r in ROLE_KEYS],
        loc="lower center",
        bbox_to_anchor=(0.5, -0.10),
        ncol=5,
        frameon=False,
        fontsize=6.5,
        handlelength=1.0,
    )
    fig.subplots_adjust(left=0.02, right=0.98, top=0.88, bottom=0.14)
    return save_figure(fig, "FigS2")


def fig_s3() -> list[Path]:
    """S3a/b | Field-stratified role-flow small multiples."""
    paths: list[Path] = []
    fields = [
        "Technical_AI_Informatics",
        "General_Clinical_Medicine",
        "Endocrinology_Diabetes",
        "Public_Health_Epidemiology",
        "Complications_Cardiometabolic_Nephrology_Neurology",
        "Ophthalmology_Vision",
        "Pediatrics_Maternal_Health",
        "Industry_Digital_Health_Device",
        "Nursing_Diabetes_Education",
        "Behavioral_Psychological",
        "Exercise_Lifestyle",
        "Nutrition",
    ]
    # Load role per institution per period from graphs
    role_rows = []
    for period in PERIOD_ORDER:
        G = nx.read_graphml(graphml_path(period))
        degrees = {n: d for n, d in G.degree()}
        nonzero = np.array([d for d in degrees.values() if d > 0])
        if len(nonzero):
            thr90 = float(np.quantile(nonzero, 0.90))
            thr50 = float(np.quantile(nonzero, 0.50))
        else:
            thr90 = thr50 = 0
        for n, attrs in G.nodes(data=True):
            deg = degrees[n]
            if deg == 0:
                role = "Isolate"
            elif deg >= thr90:
                role = "Core"
            elif deg >= thr50:
                role = "Semi-Peripheral"
            else:
                role = "Peripheral"
            role_rows.append(
                {
                    "period": period,
                    "institution": n,
                    "role": role,
                    "field": str(attrs.get("type", "Other")),
                }
            )
    role_df = pd.DataFrame(role_rows)

    def transitions_for_field(field: str) -> pd.DataFrame:
        sub = role_df[role_df["field"] == field]
        rows = []
        for left, right in zip(PERIOD_ORDER[:-1], PERIOD_ORDER[1:]):
            lmap = dict(zip(sub.loc[sub.period == left, "institution"], sub.loc[sub.period == left, "role"]))
            rmap = dict(zip(sub.loc[sub.period == right, "institution"], sub.loc[sub.period == right, "role"]))
            counts: dict[tuple[str, str], int] = {}
            for inst in set(lmap) | set(rmap):
                key = (lmap.get(inst, "Absent"), rmap.get(inst, "Absent"))
                counts[key] = counts.get(key, 0) + 1
            for (sf, st), val in counts.items():
                rows.append(
                    {
                        "period_from": left,
                        "period_to": right,
                        "state_from": sf,
                        "state_to": st,
                        "value": val,
                        "pair_index": PERIOD_ORDER.index(left),
                    }
                )
        return pd.DataFrame(rows)

    # S3a: first 6 fields
    for part, subset, stem in [
        (fields[:6], fields[:6], "FigS3a"),
        (fields[6:], fields[6:], "FigS3b"),
    ]:
        fig, axes = plt.subplots(3, 2, figsize=(DOUBLE_COL, 160 * MM))
        axes_flat = axes.flatten()
        for ax, field in zip(axes_flat, subset):
            td = transitions_for_field(field)
            draw_alluvial(ax, td, PERIOD_ORDER, ROLE_KEYS, ROLE_COLORS, node_width=0.07, alpha=0.32)
            ax.set_title(DOMAIN_LABELS.get(field, field), fontsize=7, pad=14, loc="left", fontweight="bold")
        for ax in axes_flat[len(subset) :]:
            ax.axis("off")
        handles = [Rectangle((0, 0), 1, 1, facecolor=ROLE_COLORS[r], edgecolor="none") for r in ROLE_KEYS]
        fig.legend(
            handles,
            [ROLE_LABELS[r] for r in ROLE_KEYS],
            loc="lower center",
            ncol=5,
            frameon=False,
            fontsize=6.2,
            bbox_to_anchor=(0.5, -0.01),
        )
        fig.subplots_adjust(left=0.03, right=0.98, top=0.94, bottom=0.08, hspace=0.42, wspace=0.10)
        paths.extend(save_figure(fig, stem))
        plt.close(fig)
    return paths


def fig_s4() -> list[Path]:
    df = pd.read_csv(TABLE / "prominent_institution_role_transition_counts.csv")
    pairs = df[["period_from", "period_to"]].drop_duplicates().values.tolist()
    roles = ROLE_KEYS
    n = len(pairs)
    ncols = 3
    nrows = int(np.ceil(n / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=(DOUBLE_COL, 28 * MM * nrows + 20 * MM))
    axes_arr = np.atleast_1d(axes).flatten()
    vmax = max(int(df["transition_count"].max()), 1)
    im = None
    for ax, (pf, pt) in zip(axes_arr, pairs):
        sub = df[(df.period_from == pf) & (df.period_to == pt)]
        mat = pd.DataFrame(0, index=roles, columns=roles, dtype=float)
        for row in sub.itertuples(index=False):
            if row.state_from in roles and row.state_to in roles:
                mat.loc[row.state_from, row.state_to] = row.transition_count
        im = ax.imshow(mat.values, cmap="Blues", vmin=0, vmax=vmax)
        ax.set_title(f"{PERIOD_DISPLAY[pf]} -> {PERIOD_DISPLAY[pt]}", fontsize=6.5, pad=4)
        ax.set_xticks(range(len(roles)))
        ax.set_yticks(range(len(roles)))
        short = {"Core": "High", "Semi-Peripheral": "Mod", "Peripheral": "Lim", "Isolate": "Iso", "Absent": "Abs"}
        ax.set_xticklabels([short[r] for r in roles], fontsize=5.5, rotation=45, ha="right")
        ax.set_yticklabels([short[r] for r in roles], fontsize=5.5)
        ax.tick_params(length=0)
        for i in range(len(roles)):
            for j in range(len(roles)):
                v = int(mat.values[i, j])
                if v == 0:
                    continue
                ax.text(j, i, str(v), ha="center", va="center", fontsize=5.2, color="white" if v > vmax * 0.45 else C["ink"])
    for ax in axes_arr[n:]:
        ax.axis("off")
    if im is not None:
        cax = fig.add_axes([0.92, 0.18, 0.015, 0.6])
        fig.colorbar(im, cax=cax).set_label("Institutions", fontsize=6.5)
    fig.subplots_adjust(left=0.08, right=0.90, top=0.94, bottom=0.08, hspace=0.45, wspace=0.35)
    return save_figure(fig, "FigS4")


def _heatmap_periods(
    df: pd.DataFrame,
    a_col: str,
    b_col: str,
    val_col: str,
    labels: list[str],
    stem: str,
    label_fn,
    figsize=(DOUBLE_COL, 150 * MM),
    annotate: bool = True,
    ann_fs: float = 4.8,
) -> list[Path]:
    ncols = 2
    nrows = int(np.ceil(len(PERIOD_ORDER) / ncols))
    fig, axes = plt.subplots(nrows, ncols, figsize=figsize)
    axes_arr = np.atleast_1d(axes).flatten()
    vmax = max(int(df[val_col].max()), 1)
    cmap = plt.cm.Blues.copy()
    cmap.set_bad("white")
    im = None
    for ax, period in zip(axes_arr, PERIOD_ORDER):
        sub = df[df.period == period]
        mat = pd.DataFrame(0.0, index=labels, columns=labels)
        for row in sub.itertuples(index=False):
            a = str(getattr(row, a_col))
            b = str(getattr(row, b_col))
            if a not in mat.index or b not in mat.columns:
                continue
            v = float(getattr(row, val_col))
            mat.loc[a, b] = v
            if a != b:
                mat.loc[b, a] = v
        display = np.ma.masked_where(mat.values <= 0, np.log10(1 + mat.values))
        im = ax.imshow(display, cmap=cmap, vmin=0, vmax=np.log10(1 + vmax))
        ax.set_title(PERIOD_DISPLAY[period], fontsize=7, fontweight="bold", pad=4)
        ax.set_xticks(range(len(labels)))
        ax.set_yticks(range(len(labels)))
        ax.set_xticklabels([label_fn(l) for l in labels], rotation=45, ha="right", fontsize=5.2)
        ax.set_yticklabels([label_fn(l) for l in labels], fontsize=5.2)
        ax.tick_params(length=0)
        if annotate:
            for i in range(len(labels)):
                for j in range(len(labels)):
                    v = int(mat.values[i, j])
                    if v <= 0:
                        continue
                    ax.text(
                        j,
                        i,
                        f"{v}",
                        ha="center",
                        va="center",
                        fontsize=ann_fs,
                        color="white" if np.log10(1 + v) >= 0.55 * np.log10(1 + vmax) else C["ink"],
                    )
    for ax in axes_arr[len(PERIOD_ORDER) :]:
        ax.axis("off")
    if im is not None:
        cax = fig.add_axes([0.92, 0.2, 0.015, 0.6])
        cbar = fig.colorbar(im, cax=cax)
        ticks = [0, 1, 2, 5, 10, 20, 50, 100, 200, 500]
        ticks = [t for t in ticks if t <= vmax] + ([vmax] if vmax not in ticks else [])
        cbar.set_ticks([np.log10(1 + t) for t in ticks])
        cbar.set_ticklabels([str(t) for t in ticks])
        cbar.set_label("Count (log scale)", fontsize=6.5)
    fig.subplots_adjust(left=0.12, right=0.90, top=0.95, bottom=0.08, hspace=0.4, wspace=0.25)
    return save_figure(fig, stem)


def fig_s5() -> list[Path]:
    df = pd.read_csv(TABLE / "component_field_pairwise_collaboration_by_period.csv")
    labels = category_order()
    return _heatmap_periods(
        df,
        "field_a",
        "field_b",
        "component_count",
        labels,
        "FigS5",
        lambda x: DOMAIN_SHORT.get(x, x),
        figsize=(DOUBLE_COL, 170 * MM),
        ann_fs=4.2,
    )


def fig_s6() -> list[Path]:
    df = pd.read_csv(TABLE / "exact_three_field_timelapse_profiles.csv")
    # Top combinations overall by max count
    top = (
        df.groupby("short_combination_label")["component_count"]
        .max()
        .sort_values(ascending=False)
        .head(10)
        .index.tolist()
    )
    fig, ax = plt.subplots(figsize=(DOUBLE_COL, 70 * MM))
    style_ax(ax)
    x = np.arange(len(PERIOD_ORDER))
    cmap = plt.get_cmap("tab10")
    for i, label in enumerate(top):
        vals = []
        for period in PERIOD_ORDER:
            sub = df[(df.period == period) & (df.short_combination_label == label)]
            vals.append(int(sub.component_count.iloc[0]) if len(sub) else 0)
        ax.plot(x, vals, marker="o", markersize=3.5, lw=1.3, color=cmap(i % 10), label=label)
    period_ticks(ax)
    ax.set_ylabel("Connected communities")
    ax.legend(
        loc="center left",
        bbox_to_anchor=(1.02, 0.5),
        frameon=False,
        fontsize=5.8,
        handlelength=1.2,
    )
    fig.subplots_adjust(left=0.08, right=0.62, top=0.95, bottom=0.18)
    return save_figure(fig, "FigS6")


def _spider(ax, focal: str, profiles: pd.DataFrame, partners: list[str]) -> list:
    theta = np.linspace(0, 2 * np.pi, len(partners), endpoint=False)
    theta_c = np.concatenate([theta, [theta[0]]])
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    ax.set_xticks(theta)
    ax.set_xticklabels([DOMAIN_SHORT.get(p, p) for p in partners], fontsize=5.5)
    ax.set_ylim(0, 1.0)
    ax.set_yticks([0.25, 0.5, 0.75, 1.0])
    ax.set_yticklabels(["25%", "50%", "75%", "100%"], fontsize=5.5, color=C["muted"])
    ax.grid(color=C["grid"], lw=0.5)
    ax.spines["polar"].set_color("#94a3b8")
    ax.spines["polar"].set_linewidth(0.6)
    handles = []
    for period in PERIOD_ORDER:
        sub = profiles[(profiles.period == period) & (profiles.focal_domain == focal)]
        share = {str(r.partner_domain): float(r.partner_share_within_focal_domain) for r in sub.itertuples(index=False)}
        vals = [share.get(p, 0.0) for p in partners]
        vals_c = vals + [vals[0]]
        (line,) = ax.plot(theta_c, vals_c, color=PERIOD_COLORS[period], lw=1.3, marker="o", markersize=2.2)
        ax.fill(theta_c, vals_c, color=PERIOD_COLORS[period], alpha=0.04)
        handles.append(line)
    ax.set_title(DOMAIN_LABELS.get(focal, focal), fontsize=7.5, fontweight="bold", pad=12)
    return handles


def fig_s7() -> list[Path]:
    profiles = pd.read_csv(TABLE / "focal_domain_exact_two_field_profiles_by_period.csv")
    focals = [
        "Technical_AI_Informatics",
        "Endocrinology_Diabetes",
        "General_Clinical_Medicine",
        "Public_Health_Epidemiology",
    ]
    fields = category_order()
    fig, axes = plt.subplots(2, 2, subplot_kw={"projection": "polar"}, figsize=(DOUBLE_COL, DOUBLE_COL * 0.95))
    handles = []
    for ax, focal in zip(axes.flatten(), focals):
        partners = [f for f in fields if f != focal]
        handles = _spider(ax, focal, profiles, partners)
    fig.legend(
        handles,
        [PERIOD_DISPLAY[p] for p in PERIOD_ORDER],
        loc="lower center",
        ncol=6,
        frameon=False,
        fontsize=6.2,
        bbox_to_anchor=(0.5, 0.02),
    )
    fig.subplots_adjust(left=0.05, right=0.95, top=0.92, bottom=0.10, hspace=0.35, wspace=0.25)
    return save_figure(fig, "FigS7")


def fig_s8() -> list[Path]:
    df = pd.read_csv(TABLE / "who_region_pairwise_collaboration_by_period.csv")
    return _heatmap_periods(
        df,
        "who_region_a",
        "who_region_b",
        "publication_pair_count",
        WHO_ORDER,
        "FigS8",
        lambda x: x,
        figsize=(DOUBLE_COL, 110 * MM),
        ann_fs=6.0,
    )


def fig_s9() -> list[Path]:
    df = pd.read_csv(TABLE / "country_pairwise_collaboration_display_by_period.csv")
    # Keep top countries by max weighted degree overall for readable axes
    # Per-period top-12 by weighted degree
    ncols = 2
    nrows = 3
    fig, axes = plt.subplots(nrows, ncols, figsize=(DOUBLE_COL, 180 * MM))
    axes_arr = axes.flatten()
    vmax = max(int(df["publication_pair_count"].max()), 1)
    cmap = plt.cm.Blues.copy()
    cmap.set_bad("white")
    im = None
    for ax, period in zip(axes_arr, PERIOD_ORDER):
        sub = df[df.period == period].copy()
        if sub.empty:
            ax.axis("off")
            continue
        wdeg: dict[str, int] = {}
        for row in sub.itertuples(index=False):
            wdeg[str(row.country_a)] = max(wdeg.get(str(row.country_a), 0), int(row.country_a_weighted_degree))
            wdeg[str(row.country_b)] = max(wdeg.get(str(row.country_b), 0), int(row.country_b_weighted_degree))
        labels = sorted(wdeg, key=lambda c: (-wdeg[c], c))[:15]
        mat = pd.DataFrame(0.0, index=labels, columns=labels)
        for row in sub.itertuples(index=False):
            a, b = str(row.country_a), str(row.country_b)
            if a in mat.index and b in mat.columns:
                mat.loc[a, b] = row.publication_pair_count
                if a != b:
                    mat.loc[b, a] = row.publication_pair_count
        display = np.ma.masked_where(mat.values <= 0, np.log10(1 + mat.values))
        im = ax.imshow(display, cmap=cmap, vmin=0, vmax=np.log10(1 + vmax))
        ax.set_title(PERIOD_DISPLAY[period], fontsize=7, fontweight="bold", pad=3)
        ax.set_xticks(range(len(labels)))
        ax.set_yticks(range(len(labels)))
        pretty = [normalize_country(l) for l in labels]
        ax.set_xticklabels(pretty, rotation=45, ha="right", fontsize=4.5)
        ax.set_yticklabels(pretty, fontsize=4.5)
        ax.tick_params(length=0)
    if im is not None:
        cax = fig.add_axes([0.92, 0.2, 0.015, 0.6])
        fig.colorbar(im, cax=cax).set_label("Co-publications (log)", fontsize=6.5)
    fig.subplots_adjust(left=0.12, right=0.90, top=0.96, bottom=0.06, hspace=0.4, wspace=0.3)
    return save_figure(fig, "FigS9")


def fig_s10() -> list[Path]:
    df = pd.read_csv(TABLE / "funding_role_transition_counts.csv")
    active = ["Core", "Semi-Peripheral", "Peripheral", "Isolate"]
    fig, axes = plt.subplots(1, 3, figsize=(DOUBLE_COL, 55 * MM))
    for ax, cat in zip(axes, FUNDING_ORDER):
        sub = df[
            (df.funding_category == cat)
            & df.state_from.isin(active)
            & df.state_to.isin(active)
        ]
        agg = sub.groupby(["state_from", "state_to"], as_index=False)["value"].sum()
        mat = pd.DataFrame(0.0, index=active, columns=active)
        for row in agg.itertuples(index=False):
            mat.loc[row.state_from, row.state_to] = row.value
        pct = mat.div(mat.sum(axis=1).replace(0, np.nan), axis=0) * 100
        im = ax.imshow(pct.values, cmap="Blues", vmin=0, vmax=100)
        ax.set_title(FUNDING_LABELS[cat], fontsize=7, fontweight="bold", pad=4)
        short = {"Core": "High", "Semi-Peripheral": "Mod", "Peripheral": "Lim", "Isolate": "Iso"}
        ax.set_xticks(range(4))
        ax.set_yticks(range(4))
        ax.set_xticklabels([short[s] for s in active], fontsize=6, rotation=45, ha="right")
        ax.set_yticklabels([short[s] for s in active], fontsize=6)
        ax.tick_params(length=0)
        for i in range(4):
            for j in range(4):
                v = pct.values[i, j]
                if np.isnan(v):
                    continue
                ax.text(j, i, f"{v:.0f}", ha="center", va="center", fontsize=6, color="white" if v >= 45 else C["ink"])
    cax = fig.add_axes([0.92, 0.2, 0.015, 0.6])
    fig.colorbar(im, cax=cax).set_label("%", fontsize=6.5)
    fig.subplots_adjust(left=0.06, right=0.90, top=0.88, bottom=0.18, wspace=0.35)
    return save_figure(fig, "FigS10")


def fig_s11() -> list[Path]:
    profiles = pd.read_csv(TABLE / "funding_domain_exact_two_field_profiles_by_period.csv")
    focals = [
        "Technical_AI_Informatics",
        "Endocrinology_Diabetes",
        "General_Clinical_Medicine",
        "Public_Health_Epidemiology",
    ]
    fields = category_order()
    fig, axes = plt.subplots(4, 2, subplot_kw={"projection": "polar"}, figsize=(DOUBLE_COL, 200 * MM))
    legend_handles = []
    for r, focal in enumerate(focals):
        partners = [f for f in fields if f != focal]
        for c, group in enumerate(["FUNDED", "NO_GRANT_LISTED"]):
            ax = axes[r, c]
            # filter profiles to funding group via temporary frame shaped like focal profiles
            sub = profiles[(profiles.focal_domain == focal) & (profiles.funding_group == group)].copy()
            # reshape for _spider which expects period/focal_domain/partner columns
            tmp = sub.rename(columns={})  # already has needed cols
            handles = _spider(ax, focal, tmp, partners)
            if r == 0 and c == 0:
                legend_handles = handles
            title_g = "Funded" if group == "FUNDED" else "No grant listed"
            ax.set_title(f"{DOMAIN_SHORT.get(focal, focal)} — {title_g}", fontsize=7, fontweight="bold", pad=10)
    fig.legend(
        legend_handles,
        [PERIOD_DISPLAY[p] for p in PERIOD_ORDER],
        loc="lower center",
        ncol=6,
        frameon=False,
        fontsize=6,
        bbox_to_anchor=(0.5, 0.01),
    )
    fig.subplots_adjust(left=0.04, right=0.96, top=0.96, bottom=0.05, hspace=0.45, wspace=0.2)
    return save_figure(fig, "FigS11")


def fig_s12() -> list[Path]:
    """Cohort derivation / analytic workflow schematic."""
    fig, ax = plt.subplots(figsize=(DOUBLE_COL, 70 * MM))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 4.2)
    ax.axis("off")

    boxes = [
        (0.3, 2.6, 2.2, 1.2, "PubMed retrieval\n2 protocol-defined\nquery blocks"),
        (3.0, 2.6, 2.2, 1.2, "Screening &\naffiliation filter\nto 16,953 pubs\n(1988–2025)"),
        (5.7, 2.6, 2.2, 1.2, "LLM-assisted\naffiliation domain\nclassification"),
        (8.0, 2.6, 1.7, 1.2, "Six study\nperiods"),
        (1.2, 0.4, 2.4, 1.3, "Temporal\ncollaboration\nnetworks"),
        (4.0, 0.4, 2.4, 1.3, "Interdisciplinarity\n& role-flow\nanalyses"),
        (6.8, 0.4, 2.4, 1.3, "Geography &\nfunding-stratified\nnetworks"),
    ]
    for x, y, w, h, text in boxes:
        ax.add_patch(
            FancyBboxPatch(
                (x, y),
                w,
                h,
                boxstyle="round,pad=0.03,rounding_size=0.08",
                facecolor="#F7FAFC",
                edgecolor=C["navy"],
                linewidth=0.9,
            )
        )
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=6.5, color=C["ink"])

    arrows = [
        ((2.5, 3.2), (3.0, 3.2)),
        ((5.2, 3.2), (5.7, 3.2)),
        ((7.9, 3.2), (8.0, 3.2)),
        ((4.1, 2.6), (2.4, 1.7)),
        ((6.8, 2.6), (5.2, 1.7)),
        ((8.85, 2.6), (8.0, 1.7)),
    ]
    for (x0, y0), (x1, y1) in arrows:
        ax.annotate(
            "",
            xy=(x1, y1),
            xytext=(x0, y0),
            arrowprops=dict(arrowstyle="-|>", color=C["navy"], lw=0.9),
        )
    return save_figure(fig, "FigS12")


def fig_s13() -> list[Path]:
    pw = pd.read_csv(TABLE / "component_field_pairwise_collaboration_by_period.csv")
    clin = "General_Clinical_Medicine"
    partners = [d for d in category_order() if d != clin]
    fig, ax = plt.subplots(figsize=(DOUBLE_COL, 70 * MM))
    style_ax(ax)
    x = np.arange(len(PERIOD_ORDER))
    # Plot top partners by 2025 count
    counts_2025 = {}
    for p in partners:
        sub = pw[
            (pw.period == "2025-2025")
            & (~pw.is_diagonal)
            & (
                ((pw.field_a == clin) & (pw.field_b == p))
                | ((pw.field_b == clin) & (pw.field_a == p))
            )
        ]
        counts_2025[p] = int(sub.component_count.sum()) if len(sub) else 0
    top = sorted(partners, key=lambda d: -counts_2025[d])[:8]
    cmap = plt.get_cmap("tab10")
    for i, p in enumerate(top):
        vals = []
        for period in PERIOD_ORDER:
            sub = pw[
                (pw.period == period)
                & (~pw.is_diagonal)
                & (
                    ((pw.field_a == clin) & (pw.field_b == p))
                    | ((pw.field_b == clin) & (pw.field_a == p))
                )
            ]
            vals.append(int(sub.component_count.sum()) if len(sub) else 0)
        ax.plot(x, vals, marker="o", markersize=3.5, lw=1.3, color=cmap(i), label=DOMAIN_LABELS.get(p, p))
    period_ticks(ax)
    ax.set_ylabel("Communities shared with\nclinical medicine")
    ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5), frameon=False, fontsize=5.8)
    fig.subplots_adjust(left=0.12, right=0.68, top=0.95, bottom=0.18)
    return save_figure(fig, "FigS13")


def fig_s14() -> list[Path]:
    fund = pd.read_csv(TABLE / "funding_structural_comparison_summary.csv")
    clus = pd.read_csv(TABLE / "funding_cluster_interdisciplinarity_metrics.csv")
    # Means across periods
    dens = fund.groupby("funding_category")["density"].mean()
    lcc = fund.groupby("funding_category")["lcc_share_pct"].mean()
    three = clus.groupby("funding_category")["three_or_more_field_ratio"].mean() * 100

    fig, axes = plt.subplots(1, 3, figsize=(DOUBLE_COL, 50 * MM))
    metrics = [
        (dens, "Mean network density", "a"),
        (three, "Communities with ≥3 domains (%)", "b"),
        (lcc, "Mean LCC share (%)", "c"),
    ]
    for ax, (series, ylab, lab) in zip(axes, metrics):
        style_ax(ax, grid_y=True)
        vals = [float(series.get(cat, 0)) for cat in FUNDING_ORDER]
        ax.bar(
            range(3),
            vals,
            color=[FUNDING_COLORS[c] for c in FUNDING_ORDER],
            edgecolor="none",
            width=0.65,
        )
        ax.set_xticks(range(3))
        ax.set_xticklabels(["US federal", "Non-US /\nintl.", "No grant"], fontsize=6.2)
        ax.set_ylabel(ylab)
        panel_label(ax, lab, dx=-8, dy=6)
        for i, v in enumerate(vals):
            ax.text(i, v, f"{v:.3g}" if v < 1 else f"{v:.1f}", ha="center", va="bottom", fontsize=6)
    fig.subplots_adjust(left=0.10, right=0.98, top=0.86, bottom=0.18, wspace=0.45)
    return save_figure(fig, "FigS14")


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


FIGURE_FUNCS = [
    ("Figure 1", figure1),
    ("Figure 2", figure2),
    ("Figure 3", figure3),
    ("Figure 4", figure4),
    ("Fig S1", fig_s1),
    ("Fig S2", fig_s2),
    ("Fig S3", fig_s3),
    ("Fig S4", fig_s4),
    ("Fig S5", fig_s5),
    ("Fig S6", fig_s6),
    ("Fig S7", fig_s7),
    ("Fig S8", fig_s8),
    ("Fig S9", fig_s9),
    ("Fig S10", fig_s10),
    ("Fig S11", fig_s11),
    ("Fig S12", fig_s12),
    ("Fig S13", fig_s13),
    ("Fig S14", fig_s14),
]


def main(which: Iterable[str] | None = None) -> dict[str, list[Path]]:
    apply_style()
    OUT.mkdir(parents=True, exist_ok=True)
    results: dict[str, list[Path]] = {}
    for name, fn in FIGURE_FUNCS:
        if which is not None and not any(w.lower() in name.lower() for w in which):
            continue
        print(f"Generating {name}...")
        try:
            paths = fn()
            plt.close("all")
            results[name] = paths
        except Exception as exc:
            plt.close("all")
            print(f"  ERROR in {name}: {exc}")
            import traceback

            traceback.print_exc()
            results[name] = []
    # README
    readme = OUT / "README.md"
    readme.write_text(
        """# Manuscript figures (v3.0)

Generated by `scripts/generate_manuscript_figures.py` and
`notebooks/Manuscript_Figures.ipynb`.

## How to regenerate

```bash
cd "/Users/uday/AI in Diabetology"
python scripts/generate_manuscript_figures.py
# or open notebooks/Manuscript_Figures.ipynb and Run All
```

## Outputs

| File | Manuscript figure |
|------|-------------------|
| Figure1.* | Fig. 1 Growth and network cohesion |
| Figure2.* | Fig. 2 Institutional participation |
| Figure3.* | Fig. 3 Interdisciplinary structure |
| Figure4.* | Fig. 4 Geographic distribution |
| FigS1.*–FigS14.* | Supplementary Figs. S1–S14 |

Formats: PDF (vector), PNG (600 dpi), TIFF (600 dpi, LZW when available).

## Style

Helvetica/Arial sans-serif; Okabe–Ito–inspired colourblind-safe palette for
non-role charts; Sankey/alluvial role colors match earlier role-flow assets
(`#1f77b4`, `#17becf`, `#ff7f0e`, `#bcbd22`, `#c7c7c7`) with source→target
hue blending on transition bands; print-oriented sizes (~89 mm / ~183 mm);
Nature-style panel labels a/b/c outside top-left; thin spines; outlier open
markers for 2016–2019 consortium-inflated network metrics.

**Source of truth:** `scripts/generate_manuscript_figures.py`. The notebook
imports and calls this module.
""",
        encoding="utf-8",
    )
    print(f"\nWrote {readme}")
    return results


if __name__ == "__main__":
    which = sys.argv[1:] or None
    main(which)
