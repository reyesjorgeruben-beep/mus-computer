"""Full-match baselines, live wager adapter, and coefficient history artifacts."""

import json
from types import SimpleNamespace
from xml.etree import ElementTree

import pytest

from mus_computer.bots.strategies.actions import WagerAction
from mus_computer.game.context import WagerState
from mus_computer.training.coefficient_cfr.bot import CoefficientBot
from mus_computer.training.coefficient_cfr.charts import render_charts
from mus_computer.training.coefficient_cfr.policy import PARAMETERS, Coefficients
from mus_computer.training.coefficient_cfr.validation import (
    OPPONENTS,
    validate_coefficients,
)


def test_live_bot_uses_counter_raise_and_ordago_contexts():
    bot = CoefficientBot("A1", SimpleNamespace(name="A"), Coefficients())
    private = SimpleNamespace(
        statistics=SimpleNamespace(
            outcomes_by_phase={"Grande": SimpleNamespace(p_win=0.4, p_tie=0.1)}
        )
    )
    shared = SimpleNamespace(phase_name="Grande", eligible_seats=(0, 1, 2, 3))
    for wager, expected in (
        (
            WagerState(1, 1, None),
            {WagerAction.MATCH_OR_PASS, WagerAction.RAISE_2, WagerAction.ORDAGO},
        ),
        (
            WagerState(2, 1, "B"),
            {
                WagerAction.FOLD,
                WagerAction.MATCH_OR_PASS,
                WagerAction.RAISE_2,
                WagerAction.ORDAGO,
            },
        ),
        (WagerState(4, 2, "B"), {WagerAction.FOLD, WagerAction.ORDAGO}),
        (WagerState(4, 2, "B", True), {WagerAction.FOLD, WagerAction.MATCH_OR_PASS}),
    ):
        shared.wager = wager
        distribution = bot.wager_distribution(shared, private, 0)
        assert set(distribution) == expected
        assert sum(distribution.values()) == pytest.approx(1)


def test_validation_uses_three_baselines_balanced_sides_and_match_target(
    tmp_path, monkeypatch
):
    tasks = []

    def fake_match(task):
        tasks.append(task)
        assert task.wins_to_match == 4
        return (
            task.candidate_team,
            4 if task.candidate_team == "A" else 0,
            4 if task.candidate_team == "B" else 0,
        )

    monkeypatch.setattr(
        "mus_computer.training.coefficient_cfr.validation._play_match", fake_match
    )
    report = validate_coefficients(Coefficients(), tmp_path, workers=1, matches=4)
    assert len(tasks) == 12
    for opponent in OPPONENTS:
        assigned = [t for t in tasks if t.opponent == opponent]
        assert [t.candidate_team for t in assigned].count("A") == 2
        assert [t.candidate_team for t in assigned].count("B") == 2
        assert assigned[0].seed == assigned[1].seed
        assert report["benchmarks"][opponent]["win_percentage"] == 100
    random_tasks = [t for t in tasks if t.opponent == "random_coefficients"]
    assert (
        random_tasks[0].opponent_coefficients == random_tasks[1].opponent_coefficients
    )
    assert (
        random_tasks[0].opponent_coefficients != random_tasks[2].opponent_coefficients
    )
    assert (tmp_path / "validation.md").exists()
    assert json.loads((tmp_path / "validation.json").read_text()) == report


def test_real_match_validation_is_reproducible_across_worker_counts(tmp_path):
    serial = validate_coefficients(
        Coefficients(), tmp_path / "serial", workers=1, matches=2, wins_to_match=1
    )
    parallel = validate_coefficients(
        Coefficients(), tmp_path / "parallel", workers=2, matches=2, wins_to_match=1
    )
    assert serial == parallel
    assert all(b["matches"] == 2 for b in serial["benchmarks"].values())


def test_charts_show_all_twelve_coefficients_and_export_history(tmp_path):
    first = Coefficients()
    last = first.updated((1, -1, 0, 0, 1, -1) * 2, 0.1)
    history = [
        {"iteration": 0, **first.as_dict()},
        {"iteration": 1000, **last.as_dict()},
    ]
    render_charts(history, tmp_path)
    root = ElementTree.parse(tmp_path / "coefficients.svg").getroot()
    assert len(root.findall(".//{http://www.w3.org/2000/svg}polyline")) == 12
    csv = (tmp_path / "coefficients.csv").read_text()
    assert "1000" in csv
    for condition in ("losing", "winning"):
        for name in PARAMETERS:
            assert f"{condition}_{name}" in csv
