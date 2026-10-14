"""Real, silent game runs used as the starting point for training."""

import os
import random
from time import perf_counter

import pytest

from mus_computer.training.config import TrainingConfig
from mus_computer.training.game_runner import TrainingGameRunner, play_random_game


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
        results = runner.play_games(10, seed_start=0)

    assert len(results) == 10
    assert all(result.winner in {"A", "B"} for result in results)
    assert len({result.worker_pid for result in results}) > 1
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize("workers", [0, 11])
def test_concurrent_game_cap_is_between_one_and_ten(workers):
    with pytest.raises(ValueError, match="max_concurrent_games"):
        TrainingConfig(max_concurrent_games=workers)


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
