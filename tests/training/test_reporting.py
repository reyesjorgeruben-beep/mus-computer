import json
from dataclasses import asdict, fields

import pytest

from mus_computer.bots.bot_genome import BotGenome
from mus_computer.training.reporting import build_gene_series, generate_charts


def genome(value):
    return BotGenome(*([value] * len(fields(BotGenome))))


def test_series_uses_snapshot_generation_and_population_quantiles(tmp_path):
    snapshots = tmp_path / "snapshots"
    snapshots.mkdir()
    for generation, values in [(50, [0.0, 0.5, 1.0]), (100, [0.25, 0.5, 0.75])]:
        (snapshots / f"generation_{generation:04d}.json").write_text(json.dumps({
            "generation": generation,
            "population": [asdict(genome(value)) for value in values],
        }))

    series = build_gene_series(snapshots)

    assert list(series) == [field.name for field in fields(BotGenome)]
    assert series["mus_eagerness"][0] == pytest.approx((50, 0.5, 0.05, 0.95))
    assert series["mus_eagerness"][1] == pytest.approx((100, 0.5, 0.275, 0.725))


def test_charts_include_all_genes_and_percentile_band(tmp_path):
    plotly = pytest.importorskip("plotly")
    snapshots = tmp_path / "snapshots"
    snapshots.mkdir()
    (snapshots / "generation_0050.json").write_text(json.dumps({
        "generation": 50,
        "population": [asdict(genome(value)) for value in (0.0, 0.5, 1.0)],
    }))

    outputs = generate_charts(tmp_path)

    assert len(outputs) == 1 + len(fields(BotGenome))
    overview = (tmp_path / "charts" / "all_genes.html").read_text(encoding="utf-8")
    single = (tmp_path / "charts" / "mus_eagerness.html").read_text(encoding="utf-8")
    assert "mus_eagerness" in overview and "position_preference" in overview
    assert "p5\\u2013p95" in single and "tonexty" in single


def test_reporting_shows_only_active_genes(tmp_path):
    snapshots = tmp_path / "snapshots"
    snapshots.mkdir()
    (snapshots / "generation_0050.json").write_text(json.dumps({
        "generation": 50,
        "active_genes": ["mus_eagerness"],
        "population": [asdict(genome(0.25)), asdict(genome(0.75))],
    }))

    assert list(build_gene_series(snapshots)) == ["mus_eagerness"]
    assert [path.name for path in generate_charts(tmp_path)] == [
        "all_genes.html", "mus_eagerness.html",
    ]


def test_zero_gene_baseline_has_no_gene_charts(tmp_path):
    snapshots = tmp_path / "snapshots"
    snapshots.mkdir()
    (snapshots / "generation_0050.json").write_text(json.dumps({
        "generation": 50,
        "active_genes": [],
        "population": [asdict(genome(0.5))] * 4,
    }))

    assert build_gene_series(snapshots) == {}
    assert generate_charts(tmp_path) == []
    assert "No active genes" in (tmp_path / "charts" / "index.html").read_text()
