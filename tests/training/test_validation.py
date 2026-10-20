"""Final winners are compared over seat-balanced, independently sampled matches."""

from dataclasses import fields
from types import SimpleNamespace

from mus_computer.bots.bot_genome import BotGenome
from mus_computer.training.validation import validate_winners
from mus_computer.training.validation.winners import ValidationAssignment, _play_validation_match


def test_validation_counts_one_hundred_matches_and_uses_distinct_random_genes(monkeypatch, tmp_path):
    winner = BotGenome(**{field.name: 0.5 for field in fields(BotGenome)})
    seen_assignments = []

    class RecordingRunner:
        def __init__(self, config):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def map_tasks(self, worker, assignments):
            seen_assignments.extend(assignments)
            return [
                assignment.candidate_team if assignment.match_number <= 37
                else ("B" if assignment.candidate_team == "A" else "A")
                for assignment in assignments
            ]

    monkeypatch.setattr("mus_computer.training.validation.winners.TrainingGameRunner", RecordingRunner)
    report = validate_winners([winner, winner], tmp_path, seed=7, workers=2, wins_to_match=4)

    assert report["matches_per_opponent"] == 100
    assert report["wins_to_match"] == 4
    assert len(report["winners"]) == 2
    for candidate_index, record in enumerate(report["winners"]):
        benchmarks = record["benchmarks"]
        assert set(benchmarks) == {"random_genes", "random_decisions", "mus_maestro"}
        for kind, benchmark in benchmarks.items():
            assert benchmark["matches"] == 100
            assert benchmark["wins"] == 37
            assert benchmark["win_percentage"] == 37
            assignments = [
                item for item in seen_assignments
                if item.candidate_index == candidate_index and item.opponent_kind == kind
            ]
            assert len(assignments) == 100
            assert sum(item.candidate_team == "A" for item in assignments) == 50
            assert sum(item.candidate_team == "B" for item in assignments) == 50
            assert all(item.wins_to_match == 4 for item in assignments)

    random_opponents = [
        item.opponent_genome for item in seen_assignments if item.opponent_kind == "random_genes"
    ]
    assert len({(genome.bluff_rate, genome.extreme_bluff_rate) for genome in random_opponents}) == 200
    assert all(item.opponent_genome is None for item in seen_assignments if item.opponent_kind != "random_genes")
    results = tmp_path / "validation" / "results.md"
    assert "| 1 | 37% | 37% | 37% |" in results.read_text(encoding="utf-8")
    assert "| Average | 37% | 37% | 37% |" in results.read_text(encoding="utf-8")


def test_validation_match_plays_fresh_games_until_win_target(monkeypatch):
    winner = BotGenome(**{field.name: 0.5 for field in fields(BotGenome)})
    assignment = ValidationAssignment(0, "A", "random_genes", winner, winner, 1, 7, 2)
    game_winners = iter(("A", "B", "A"))
    seeds = []

    class FakeGame:
        def play(self):
            return SimpleNamespace(name=next(game_winners))

    def fake_game(item):
        seeds.append(item.seed)
        return FakeGame()

    monkeypatch.setattr("mus_computer.training.validation.winners.build_validation_game", fake_game)
    assert _play_validation_match(assignment) == "A"
    assert len(seeds) == 3
    assert len(set(seeds)) == 3
