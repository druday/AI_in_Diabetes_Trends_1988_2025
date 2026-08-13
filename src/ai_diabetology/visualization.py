from __future__ import annotations

import re
from pathlib import Path

import networkx as nx

DEFAULT_NODE_COLORS = {"Other": "#bdbdbd"}


def export_pyvis_html(
    graph: nx.Graph,
    out_path: str | Path,
    period_label: str,
    node_colors: dict[str, str] | None = None,
    category_order: list[str] | None = None,
    fallback_label: str = "Other",
) -> Path:
    from pyvis.network import Network

    colors = {**DEFAULT_NODE_COLORS, **(node_colors or {})}
    out_file = Path(out_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    net = Network(
        height="1000px",
        width="100%",
        bgcolor="#ffffff",
        font_color="#111827",
        directed=False,
        notebook=False,
        cdn_resources="remote",
    )

    net.set_options(
        """
        var options = {
          "nodes": {
            "shape": "dot",
            "scaling": {"min": 5, "max": 25},
            "font": {"size": 12}
          },
          "edges": {
            "color": {"color": "#9ca3af"},
            "smooth": false
          },
          "interaction": {
            "hover": true,
            "tooltipDelay": 80
          },
          "physics": {
            "stabilization": {"enabled": true, "iterations": 200},
            "barnesHut": {
              "gravitationalConstant": -10000,
              "springLength": 160
            }
          }
        }
        """
    )

    for node, attrs in graph.nodes(data=True):
        category = str(attrs.get("type", fallback_label))
        color = colors.get(category, colors.get(fallback_label, DEFAULT_NODE_COLORS["Other"]))
        degree = int(graph.degree(node))
        net.add_node(
            node,
            label=node,
            value=max(1, degree),
            color=color,
            title=(
                f"<b>Institution:</b> {node}<br>"
                f"<b>Category:</b> {category}<br>"
                f"<b>Degree:</b> {degree}"
            ),
        )

    for source, target, attrs in graph.edges(data=True):
        weight = float(attrs.get("weight", 1))
        weight_label = int(weight) if weight.is_integer() else round(weight, 2)
        net.add_edge(
            source,
            target,
            value=max(1.0, weight),
            title=f"Co-publications: {weight_label}",
        )

    net.write_html(str(out_file))
    html = out_file.read_text(encoding="utf-8")

    # PyVis template renders heading blocks twice; strip those blocks and inject one custom header.
    html = re.sub(r"<center>\s*<h1>[\s\S]*?</h1>\s*</center>", "", html, count=2)
    labels_for_legend = category_order or sorted(colors.keys())
    if fallback_label in labels_for_legend:
        labels_for_legend = [label for label in labels_for_legend if label != fallback_label] + [fallback_label]
    legend_html = " &nbsp; ".join(
        f'<span style="color:{colors.get(label, colors.get(fallback_label, DEFAULT_NODE_COLORS["Other"]))};font-weight:bold;">&#9632; {label}</span>'
        for label in labels_for_legend
    )
    header_html = f"""
    <div style="text-align:center; margin: 8px 0 12px;">
      <h3 style="margin:0 0 8px;">Institution Collaboration Network ({period_label})</h3>
      <p style="margin:0;">
        {legend_html}
      </p>
    </div>
    """
    card_marker = '<div class="card" style="width: 100%">'
    network_marker = '<div id="mynetwork"'
    if card_marker in html:
        html = html.replace(card_marker, f"{header_html}\n{card_marker}", 1)
    elif network_marker in html:
        html = html.replace(network_marker, f"{header_html}\n{network_marker}", 1)

    out_file.write_text(html, encoding="utf-8")
    return out_file
