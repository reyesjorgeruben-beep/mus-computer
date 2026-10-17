"""Real, silent game runs used as the starting point for training."""

import os
import random
from time import perf_counter

import pytest

from mus_computer.training.config import TrainingConfig
from mus_computer.training.game_runner import TrainingGameRunner, play_random_game
from mus_computer.bots.bot_genome import random_genome
from mus_computer.training.game_runner import GenomeMatchup, build_bot_game, play_genome_game
from mus_computer.bots.strategies.wagers import HandStrengthWagerStrategy


def test_one_random_game_finishes_without_terminal_output(capsys):
    state_before = random.getstate()
    result = play_random_game(seed=0)

    assert result.winner in {"A", "B"}
    assert result.victory_reason in {"points", "ordago"}
    assert result.elapsed_seconds >= 0
    assert random.getstate() == state_before
    assert capsys.readouterr() == ("", "")


def test_ten_random_games_run_in_separate_workers_without_terminal_output(capsys):
    with TrainingGameRunner(TrainingConfig()) as runner:
        runner.warm_up()
        results = runner.play_games(10, seed_start=0)

    assert len(results) == 10
    assert all(result.winner in {"A", "B"} for result in results)
    assert len({result.worker_pid for result in results}) > 1
    assert capsys.readouterr() == ("", "")


def test_single_game_can_start_a_ten_worker_pool():
    with TrainingGameRunner(TrainingConfig()) as runner:
        results = runner.play_games(1)
    assert len(results) == 1
    assert results[0].winner in {"A", "B"}


def test_genome_matchup_uses_one_genome_per_team(capsys):
    team_a, team_b = random_genome(), random_genome()
    game = build_bot_game(GenomeMatchup(team_a, team_b, seed=3))
    assert [player._personality for player in game.players_in_order] == [team_a, team_b, team_a, team_b]
    assert all(
        isinstance(strategy, HandStrengthWagerStrategy)
        for strategy in game.players_in_order[0].strategies.wagers_by_phase.values()
    )
    result = play_genome_game(GenomeMatchup(team_a, team_b, seed=3))
    assert result.winner in {"A", "B"}
    assert capsys.readouterr() == ("", "")


def test_genome_match_plays_to_requested_number_of_wins():
    team_a, team_b = random_genome(), random_genome()
    state_before = random.getstate()

    result = play_genome_game(GenomeMatchup(team_a, team_b, seed=9, wins_to_match=2))

    assert result.winner in {"A", "B"}
    assert max(result.wins_a, result.wins_b) == 2
    assert not hasattr(result, "victory_reason")
    assert 2 <= result.wins_a + result.wins_b <= 3
    assert random.getstate() == state_before


@pytest.mark.parametrize("workers", [0, 17])
def test_concurrent_game_cap_is_between_one_and_sixteen(workers):
    with pytest.raises(ValueError, match="max_concurrent_games"):
        TrainingConfig(max_concurrent_games=workers)


def test_sixteen_concurrent_games_are_configurable():
    assert TrainingConfig(max_concurrent_games=16).max_concurrent_games == 16


@pytest.mark.performance
@pytest.mark.skipif(os.getenv("RUN_TRAINING_PERF") != "1", reason="opt-in live timing test")
def test_one_random_game_meets_latency_threshold():
    config = TrainingConfig()
    start = perf_counter()
    result = play_random_game(seed=0)
    elapsed = perf_counter() - start

    print(f"one random-bot game: {elapsed:.3f}s (limit {config.single_game_max_seconds:.3f}s)")
    assert result.winner in {"A", "B"}
    assert elapsed <= config.single_game_max_seconds, f"one game took {elapsed:.3f}s"


@pytest.mark.performance
@pytest.mark.skipif(os.getenv("RUN_TRAINING_PERF") != "1", reason="opt-in live timing test")
def test_ten_parallel_random_games_meet_throughput_threshold():
    config = TrainingConfig()
    with TrainingGameRunner(config) as runner:
        runner.warm_up()
        start = perf_counter()
        results = runner.play_games(10, seed_start=0)
        elapsed = perf_counter() - start

    print(f"ten parallel random-bot games: {elapsed:.3f}s (limit {config.ten_game_max_seconds:.3f}s)")
    assert len(results) == 10
    assert elapsed <= config.ten_game_max_seconds, f"ten games took {elapsed:.3f}s"
