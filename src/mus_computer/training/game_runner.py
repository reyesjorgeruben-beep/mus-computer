"""Run silent random baseline games or genome configured training matchups."""

import multiprocessing
import os
import random
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from itertools import repeat
from time import perf_counter

from mus_computer.bots.bot_genome import BotGenome
from mus_computer.bots.bot_player import BotPlayer
from mus_computer.bots.strategies.discard import PersonalityWeightedDiscardStrategy
from mus_computer.bots.strategies.mus import GeneCutMusStrategy
from mus_computer.bots.strategies.portfolio import StrategyPortfolio
from mus_computer.bots.strategies.wagers import HandStrengthWagerStrategy
from mus_computer.cli import build_default_game
from mus_computer.game.game import Game
from mus_computer.game.match import Match
from mus_computer.game.phases import PHASE_ORDER
from mus_computer.game.team import Team
from mus_computer.training.config import TrainingConfig


@dataclass(frozen=True)
class GameResult:
    """A single game's outcome and elapsed time measured with ``perf_counter``."""

    winner: str
    victory_reason: str
    elapsed_seconds: float
    worker_pid: int


@dataclass(frozen=True)
class MatchRunResult:
    """A match outcome, game-win score, and elapsed time."""

    winner: str
    wins_a: int
    wins_b: int
    elapsed_seconds: float
    worker_pid: int


@dataclass(frozen=True)
class GenomeMatchup:
    team_a: BotGenome
    team_b: BotGenome
    seed: int = 0
    wins_to_match: int = 1


def build_bot_game(matchup: GenomeMatchup, seed: int | None = None) -> Game:
    """Seat two copies of each team's genome in A/B/A/B order."""
    game_seed = matchup.seed if seed is None else seed
    team_a, team_b = Team("A"), Team("B")
    strategies = StrategyPortfolio(
        mus_strategy=GeneCutMusStrategy(),
        discard_strategy=PersonalityWeightedDiscardStrategy(),
        wagers_by_phase={phase: HandStrengthWagerStrategy(phase) for phase in PHASE_ORDER},
    )
    players = [
        BotPlayer("A1", team_a, matchup.team_a, strategies, random.Random(game_seed + 1)),
        BotPlayer("B1", team_b, matchup.team_b, strategies, random.Random(game_seed + 2)),
        BotPlayer("A2", team_a, matchup.team_a, strategies, random.Random(game_seed + 3)),
        BotPlayer("B2", team_b, matchup.team_b, strategies, random.Random(game_seed + 4)),
    ]
    return Game.from_players(players)


def _play_game(factory, seed: int) -> GameResult:
    """Run one game and measure elapsed seconds with a monotonic timer.

    ``perf_counter()`` readings are subtracted to measure the game duration;
    their absolute values are not timestamps. Restore global randomness so
    a direct call does not change the caller's random sequence.
    """
    previous_state = random.getstate()
    try:
        random.seed(seed)
        start = perf_counter()
        game = factory()
        winner = game.play()
        return GameResult(winner.name, game.victory_reason or "points", perf_counter() - start, os.getpid())
    finally:
        random.setstate(previous_state)


def play_random_game(seed: int = 0) -> GameResult:
    """Play a fixed-seed random baseline game without terminal output."""
    return _play_game(lambda: build_default_game(on_action=None), seed)


def play_genome_match(matchup: GenomeMatchup) -> MatchRunResult:
    """Play fresh games until one genome team wins the requested match."""
    previous_state = random.getstate()
    try:
        random.seed(matchup.seed)
        game_index = 0

        def next_game() -> Game:
            nonlocal game_index
            game = build_bot_game(matchup, seed=matchup.seed + 4 * game_index)
            game_index += 1
            return game

        start = perf_counter()
        result = Match(next_game, matchup.wins_to_match).play()
        return MatchRunResult(
            result.winner, result.wins_a, result.wins_b, perf_counter() - start, os.getpid(),
        )
    finally:
        random.setstate(previous_state)


def play_genome_game(matchup: GenomeMatchup) -> MatchRunResult:
    """Compatibility entry point for a genome matchup (one or more games)."""
    return play_genome_match(matchup)


def _prepare_worker() -> None:
    """Load each worker's read-only table cache before its first game."""
    from mus_computer.cards.card import Card
    from mus_computer.probabilities.estimates import estimate_hand_statistics

    estimate_hand_statistics((Card.R, Card.C, Card.S, Card.A))


def _wait_for_pool(barrier) -> None:
    barrier.wait(timeout=30)


class TrainingGameRunner:
    """Reuse a bounded process pool across batches of independent games."""

    def __init__(self, config: TrainingConfig | None = None) -> None:
        self.config = config or TrainingConfig()
        self._executor: ProcessPoolExecutor | None = None

    def __enter__(self) -> "TrainingGameRunner":
        self._executor = ProcessPoolExecutor(
            max_workers=self.config.max_concurrent_games,
            mp_context=multiprocessing.get_context(),
            initializer=_prepare_worker,
        )
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        if self._executor is not None:
            self._executor.shutdown(wait=True)
            self._executor = None

    def warm_up(self) -> None:
        """Start every worker before measuring full-pool throughput."""
        if self._executor is None:
            raise RuntimeError("TrainingGameRunner must be used as a context manager")
        with multiprocessing.Manager() as manager:
            barrier = manager.Barrier(self.config.max_concurrent_games)
            list(self._executor.map(
                _wait_for_pool, repeat(barrier, self.config.max_concurrent_games),
            ))

    def play_games(self, count: int, seed_start: int = 0) -> list[GameResult]:
        if self._executor is None:
            raise RuntimeError("TrainingGameRunner must be used as a context manager")
        if count < 0:
            raise ValueError("Game count must be nonnegative")
        return list(self._executor.map(play_random_game, range(seed_start, seed_start + count)))

    def play_matchups(self, matchups: list[GenomeMatchup]) -> list[MatchRunResult]:
        if self._executor is None:
            raise RuntimeError("TrainingGameRunner must be used as a context manager")
        return list(self._executor.map(play_genome_match, matchups))
