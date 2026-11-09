"""Dependency-free coefficient evolution charts and the underlying CSV data."""

import csv
from pathlib import Path

from .policy import PARAMETERS


def render_charts(history: list[dict], run_dir: Path):
    if not history:
        raise ValueError("Coefficient history is empty")
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    with (run_dir / "coefficients.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(
            ["batch"]
            + [
                f"{condition}_{name}"
                for condition in ("losing", "winning")
                for name in PARAMETERS
            ]
        )
        writer.writerows(
            [row["iteration"]]
            + [row[c][n] for c in ("losing", "winning") for n in PARAMETERS]
            for row in history
        )
    colors = ("#d45349", "#5267d4", "#2a947c", "#d48a18", "#9d58ba", "#252e43")
    end = max(1, history[-1]["iteration"])
    svg = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="820" viewBox="0 0 1100 820">',
        "<title>Wager coefficient evolution</title>",
        "<desc>Six conditional probabilities for losing and winning hands, recorded after each frozen batch.</desc>",
        '<rect width="1100" height="820" fill="#fafbfe"/>',
        '<g font-family="Segoe UI, sans-serif" fill="#252e43">',
        '<text x="70" y="40" font-size="26" font-weight="600">Wager coefficient evolution</text>',
        '<text x="70" y="65" font-size="14">Opening pass/bet and response fold/match are pairs; re-bid and ordago are independent gates.</text>',
    ]
    for panel, condition in enumerate(("losing", "winning")):
        top = 135 + panel * 350
        svg.append(
            f'<text x="70" y="{top - 47}" font-size="19" font-weight="600">{condition.capitalize()} coefficients</text>'
        )
        for i, (name, color) in enumerate(zip(PARAMETERS, colors)):
            x: float = 70 + 158 * i
            svg.append(
                f'<line x1="{x}" y1="{top - 23}" x2="{x + 20}" y2="{top - 23}" stroke="{color}" stroke-width="3"/>'
            )
            svg.append(
                f'<text x="{x + 27}" y="{top - 18}" font-size="13">{name}</text>'
            )
        for tick in range(6):
            y = top + 230 * (1 - tick / 5)
            svg.append(f'<line x1="70" y1="{y}" x2="1030" y2="{y}" stroke="#dfe4ed"/>')
            svg.append(
                f'<text x="55" y="{y + 4}" text-anchor="end" font-size="12">{tick / 5:.1f}</text>'
            )
            x = 70 + 960 * tick / 5
            svg.append(
                f'<text x="{x}" y="{top + 251}" text-anchor="middle" font-size="12">{end * tick / 5:g}</text>'
            )
        for name, color in zip(PARAMETERS, colors):
            points = " ".join(
                f"{70 + 960 * row['iteration'] / end:.2f},{top + 230 * (1 - row[condition][name]):.2f}"
                for row in history
            )
            svg.append(
                f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="2.2"/>'
            )
        svg.append(
            f'<text x="550" y="{top + 277}" text-anchor="middle" font-size="13">Completed training batches</text>'
        )
    svg.append("</g></svg>")
    (run_dir / "coefficients.svg").write_text("\n".join(svg), encoding="utf-8")
