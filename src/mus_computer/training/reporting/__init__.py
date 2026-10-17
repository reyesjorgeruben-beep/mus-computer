"""Snapshot summaries and interactive training charts."""

import json
from dataclasses import fields
from pathlib import Path
from statistics import fmean

from mus_computer.bots.bot_genome import BotGenome


def _percentile(sorted_values: list[float], fraction: float) -> float:
    position = (len(sorted_values) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(sorted_values) - 1)
    return sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * (position - lower)


def build_gene_series(snapshot_dir: Path) -> dict[str, list[tuple[int, float, float, float]]]:
    """Return generation, mean, p5, and p95 for each gene in saved populations."""
    paths = sorted(Path(snapshot_dir).glob("generation_*.json"))
    if not paths:
        raise ValueError(f"No generation snapshots found in {snapshot_dir}")
    known_names = [field.name for field in fields(BotGenome)]
    first = json.loads(paths[0].read_text(encoding="utf-8"))
    names = first.get("active_genes", known_names)
    if any(name not in known_names for name in names):
        raise ValueError("Snapshot contains an unknown active gene")
    series: dict[str, list[tuple[int, float, float, float]]] = {name: [] for name in names}
    for path in paths:
        snapshot = json.loads(path.read_text(encoding="utf-8"))
        if snapshot.get("active_genes", known_names) != names:
            raise ValueError("Snapshots have inconsistent active genes")
        generation = snapshot["generation"]
        population = snapshot["population"]
        if not population:
            raise ValueError(f"Empty population in {path}")
        for name in names:
            values = sorted(genome[name] for genome in population)
            series[name].append((
                generation, fmean(values), _percentile(values, 0.05), _percentile(values, 0.95),
            ))
    return series


def generate_charts(run_dir: Path) -> list[Path]:
    """Write offline Plotly HTML charts from a run's population snapshots."""
    run_dir = Path(run_dir)
    series = build_gene_series(run_dir / "snapshots")
    chart_dir = run_dir / "charts"
    chart_dir.mkdir(parents=True, exist_ok=True)
    if not series:
        (chart_dir / "index.html").write_text(
            "<!doctype html><html><head><meta charset='utf-8'><title>Training baseline</title>"
            "</head><body><h1>Training baseline</h1><p>No active genes. "
            "Every bot uses the fixed neutral personality.</p></body></html>",
            encoding="utf-8",
        )
        return []

    import plotly.graph_objects as go
    from plotly.colors import qualitative
    palette = qualitative.Dark24
    common_layout = dict(
        template="plotly_white", hovermode="x unified",
        xaxis_title="Generation", yaxis_title="Gene value",
        yaxis_range=[0, 1], height=620,
    )

    overview = go.Figure()
    for index, (name, points) in enumerate(series.items()):
        overview.add_trace(go.Scatter(
            x=[point[0] for point in points], y=[point[1] for point in points],
            mode="lines+markers", name=name,
            line=dict(color=palette[index % len(palette)], width=2),
        ))
    overview.update_layout(title="Mean genome values across training", **common_layout)
    outputs = [chart_dir / "all_genes.html"]
    overview.write_html(outputs[0], include_plotlyjs="directory")

    for index, (name, points) in enumerate(series.items()):
        generations, means, lows, highs = zip(*points)
        color = palette[index % len(palette)]
        figure = go.Figure()
        figure.add_trace(go.Scatter(
            x=generations, y=lows, mode="lines", name="p5",
            line=dict(color="rgba(0,0,0,0)", width=0), showlegend=False,
        ))
        figure.add_trace(go.Scatter(
            x=generations, y=highs, mode="lines", name="p5–p95",
            line=dict(color="rgba(0,0,0,0)", width=0),
            fill="tonexty", fillcolor="rgba(80,110,160,0.20)",
            hovertemplate="p95: %{y:.3f}<extra></extra>",
        ))
        figure.add_trace(go.Scatter(
            x=generations, y=means, mode="lines+markers", name="Mean",
            line=dict(color=color, width=3),
        ))
        figure.update_layout(title=name.replace("_", " ").title(), **common_layout)
        path = chart_dir / f"{name}.html"
        figure.write_html(path, include_plotlyjs="directory")
        outputs.append(path)

    links = "\n".join(f'<li><a href="{path.name}">{path.stem.replace("_", " ").title()}</a></li>' for path in outputs)
    (chart_dir / "index.html").write_text(
        f"<!doctype html><html><head><meta charset='utf-8'><title>Training charts</title></head>"
        f"<body><h1>Training charts</h1><p>Population means every saved generation; individual charts "
        f"show the p5–p95 range.</p><ul>{links}</ul></body></html>",
        encoding="utf-8",
    )
    return outputs
