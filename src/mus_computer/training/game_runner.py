"""Run independent four-random-bot games without terminal action logs."""

import os
import multiprocessing
import random
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from itertools import repeat
from time import perf_counter

from mus_computer.cli import build_default_game
from mus_computer.training.config import TrainingConfig


@dataclass(frozen=True)
class GameResult:
    winner: str
    victory_reason: str
    elapsed_seconds: float
    worker_pid: int


def play_random_game(seed: int | None = None) -> GameResult:
    """Play one complete game with real public and private decision contexts."""
    previous_random_state = random.getstate() if seed is not None else None
    try:
        if seed is not None:
            random.seed(seed)
        start = perf_counter()
        game = build_default_game(on_action=None)
        winner = game.play()
        return GameResult(winner.name, game.victory_reason or "points", perf_counter() - start, os.getpid())
    finally:
        if previous_random_state is not None:
            random.setstate(previous_random_state)


def _prepare_worker(ready_barrier) -> None:
    # Each process owns its table cache; load it before timed batches begin.
    from mus_computer.cards.card import Card
    from mus_computer.probabilities.estimates import estimate_hand_statistics

    estimate_hand_statistics((Card.R, Card.C, Card.S, Card.A))
    ready_barrier.wait(timeout=30)


def _worker_pid(_: int) -> int:
    return os.getpid()


class TrainingGameRunner:
    """Reuse at most ten processes across batches of independent games."""

    def __init__(self, config: TrainingConfig | None = None) -> None:
        self.config = config or TrainingConfig()
        self._executor: ProcessPoolExecutor | None = None

    def __enter__(self) -> "TrainingGameRunner":
        context = multiprocessing.get_context()
        ready_barrier = context.Barrier(self.config.max_concurrent_games)
        self._executor = ProcessPoolExecutor(
            max_workers=self.config.max_concurrent_games,
            mp_context=context,
            initializer=_prepare_worker,
            initargs=(ready_barrier,),
        )
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        if self._executor is not None:
            self._executor.shutdown(wait=True)
            self._executor = None

    def warm_up(self) -> None:
        """Start workers and load their tables outside a timed game batch."""
        if self._executor is None:
            raise RuntimeError("TrainingGameRunner must be used as a context manager")
        list(self._executor.map(_worker_pid, range(self.config.max_concurrent_games)))

    def play_games(self, count: int, seed_start: int | None = None) -> list[GameResult]:
        if self._executor is None:
            raise RuntimeError("TrainingGameRunner must be used as a context manager")
        if count < 0:
            raise ValueError("Game count must be nonnegative")
        seeds = range(seed_start, seed_start + count) if seed_start is not None else repeat(None, count)
        return list(self._executor.map(play_random_game, seeds))
