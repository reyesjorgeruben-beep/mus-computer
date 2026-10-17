"""Final winners are compared with distinct seat-balanced baselines."""

from dataclasses import fields

from mus_computer.bots.bot_genome import BotGenome
from mus_computer.training.validation import validate_winners


def test_validation_reports_ten_games_per_opponent_type(tmp_path):
    values = {field.name: 0.5 for field in fields(BotGenome)}
    values.update(cut_prone=1.0, cut_prone_with_pares=1.0, cut_prone_with_juego=1.0)
    winner = BotGenome(**values)

    report = validate_winners([winner], tmp_path, seed=7, workers=2)

    benchmarks = report["winners"][0]["benchmarks"]
    assert set(benchmarks) == {"random_genes", "random_decisions", "mus_maestro"}
    for benchmark in benchmarks.values():
        assert benchmark["games"] == 10
        assert len(benchmark["matchups"]) == 10
        assert sum(matchup["candidate_team"] == "A" for matchup in benchmark["matchups"]) == 5
        assert sum(matchup["candidate_team"] == "B" for matchup in benchmark["matchups"]) == 5
        assert benchmark["win_percentage"] == 10 * benchmark["wins"]
    assert all("opponent_genome" in game for game in benchmarks["random_genes"]["matchups"])
    assert all("opponent_genome" not in game for game in benchmarks["mus_maestro"]["matchups"])
    assert (tmp_path / "validation" / "results.json").exists()
