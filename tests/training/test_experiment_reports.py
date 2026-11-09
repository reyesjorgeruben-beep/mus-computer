"""Offline HTML evidence, safe rendering and presentation-only regeneration."""

import copy
import sys
from html.parser import HTMLParser

import pytest

from mus_computer.training.experiments.contracts import write_json
from mus_computer.training.experiments.reports import render_report, write_report


def report():
    def series(wins):
        return {
            "wins": wins,
            "matches": 64,
            "win_rate": wins / 64,
            "pair_standard_error": 0.04754,
            "records": [],
        }

    return {
        "stage": "confirmation",
        "attempt": 3,
        "pairs": 32,
        "wins_to_match": 1,
        "evaluation_seed": 7,
        "elapsed_seconds": 12.1,
        "rationale": "Try a gentler update.",
        "rules": {"min_pairs": 32, "win_rate": 0.55, "max_regression": 0.05},
        "champion": {"path": "private/champion.json", "sha256": "a" * 64},
        "challenger": {"path": "private/challenger.json", "sha256": "b" * 64},
        "comparisons": {
            "head_to_head": series(33),
            "baselines": {
                "heuristic": {
                    "champion": series(27),
                    "challenger": series(26),
                    "delta": -1 / 64,
                    "delta_pair_standard_error": 0.04,
                }
            },
        },
    }


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text = []
        self.tags = []
        self.attributes = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.attributes.extend(attrs)

    def handle_data(self, data):
        self.text.append(data)


def test_report_shows_real_outcomes_thresholds_and_safe_text_offline():
    data = report()
    data["rationale"] = (
        '<script>alert("bad")</script> & check <img src=x onerror=alert(1)>'
    )
    data["comparisons"]["baselines"]["<svg onload=alert(2)>"] = copy.deepcopy(
        data["comparisons"]["baselines"]["heuristic"]
    )
    original = copy.deepcopy(data)
    html = render_report(data, reasons=["Challenger failed the head-to-head threshold"])
    page = Page()
    page.feed(html)
    visible = " ".join(page.text)
    assert "Keep champion" in visible
    assert "33/64" in visible
    assert "51.6%" in visible
    assert "55.0%" in visible
    assert "32" in visible
    assert data["rationale"] in visible
    assert "script" not in page.tags
    assert "img" not in page.tags
    assert all(not name.startswith("on") for name, _ in page.attributes)
    assert all(
        not value.startswith(("http:", "https:", "javascript:"))
        for name, value in page.attributes
        if name in {"href", "src"}
    )
    assert data == original


def test_development_and_eligible_confirmation_do_not_claim_promotion():
    data = report()
    assert "Eligible for explicit promotion" in render_report(data, reasons=[])
    data["stage"] = "development"
    assert "Development comparison" in render_report(data, reasons=None)
    assert "Keep champion" not in render_report(data, reasons=None)


def test_confirmation_requires_an_evaluated_gate_result():
    with pytest.raises(ValueError, match="gate"):
        render_report(report())


def test_saved_json_regenerates_html_without_touching_evidence(tmp_path):
    data = report()
    # A self-contained historical report needs no live model/checkpoint loader.
    data.pop("champion")
    data.pop("challenger")
    data["stage"] = "development"
    data["parent"] = None
    path = tmp_path / "development.json"
    write_json(path, data)
    before = path.read_bytes()
    output = write_report(path)
    assert output == path.with_suffix(".html")
    assert "33/64" in output.read_text(encoding="utf-8")
    assert path.read_bytes() == before
    assert not path.with_suffix(".md").exists()
    with pytest.raises(FileExistsError):
        write_report(path)


@pytest.mark.parametrize("rate", [float("nan"), float("inf"), -1, 2])
def test_invalid_chart_rates_are_rejected(rate):
    data = report()
    data["comparisons"]["head_to_head"]["win_rate"] = rate
    with pytest.raises(ValueError):
        render_report(data, reasons=[])


def test_cli_regenerates_html_from_saved_evidence(tmp_path, monkeypatch, capsys):
    from mus_computer.training.experiments.__main__ import main

    data = report()
    data.pop("champion")
    data.pop("challenger")
    data.update(stage="development", parent=None)
    source = tmp_path / "development.json"
    write_json(source, data)
    before = source.read_bytes()
    monkeypatch.setattr(sys, "argv", ["experiments", "report", "--input", str(source)])
    assert main() == 0
    assert str(source.with_suffix(".html")) in capsys.readouterr().out
    assert source.read_bytes() == before


def test_history_preserves_static_results_budgets_and_screening_failures():
    data = report()
    historical = report()
    historical.update(stage="development", attempt=1, pairs=8)
    historical["comparisons"]["head_to_head"].update(
        wins=9, matches=16, win_rate=9 / 16
    )
    baseline = historical["comparisons"]["baselines"].pop("heuristic")
    baseline["champion"].update(wins=11, matches=16, win_rate=11 / 16)
    baseline["challenger"].update(wins=8, matches=16, win_rate=0.5)
    baseline["delta"] = -3 / 16
    historical["comparisons"]["baselines"]["random_coefficients"] = baseline
    html = render_report(
        data,
        reasons=["Challenger failed the head-to-head threshold"],
        history=[
            {
                "report": historical,
                "model": {},
                "screening_reasons": [
                    "Material static regression: random_coefficients"
                ],
            }
        ],
    )
    page = Page()
    page.feed(html)
    visible = " ".join(page.text)
    assert "8 seed pairs" in visible
    assert "Development screening" in visible
    assert "Material static regression: random_coefficients" in visible
    assert "11/16 (68.8%)" in visible
    assert "8/16 (50.0%)" in visible
    assert "-18.75 pp" in visible


def test_related_confirmation_retains_separate_historical_evidence(tmp_path):
    current = report()
    current.pop("champion")
    current.pop("challenger")
    current.update(stage="development", parent=None)
    older = report()
    older["comparisons"]["head_to_head"].update(wins=31, win_rate=31 / 64)
    old_static = older["comparisons"]["baselines"].pop("heuristic")
    old_static["champion"].update(wins=33, win_rate=33 / 64)
    old_static["challenger"].update(wins=29, win_rate=29 / 64)
    old_static["delta"] = -4 / 64
    older["comparisons"]["baselines"]["random_decisions"] = old_static
    source, prior = tmp_path / "current.json", tmp_path / "older.json"
    write_json(source, current)
    write_json(prior, older)
    before = prior.read_bytes()
    output = write_report(source, related=[prior])
    page = Page()
    page.feed(output.read_text(encoding="utf-8"))
    visible = " ".join(page.text)
    assert "Related saved comparison" in visible
    assert "31/64 (48.4%)" in visible
    assert "Material static regression: random_decisions" in visible
    assert "-6.25 pp" in visible
    assert prior.read_bytes() == before
