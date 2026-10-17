"""A match is a series of fresh games won by the first team to a target."""

from collections.abc import Callable
from dataclasses import dataclass

from mus_computer.game.game import Game


@dataclass(frozen=True)
class MatchResult:
    """The winning team and the number of games won by each team."""

    winner: str
    wins_a: int
    wins_b: int


class Match:
    """Play fresh games until A or B wins ``wins_to_match`` games."""

    def __init__(self, game_factory: Callable[[], Game], wins_to_match: int) -> None:
        if type(wins_to_match) is not int or wins_to_match < 1:
            raise ValueError("wins_to_match must be a positive integer")
        self.game_factory = game_factory
        self.wins_to_match = wins_to_match

    def play(self) -> MatchResult:
        wins = {"A": 0, "B": 0}
        while max(wins.values()) < self.wins_to_match:
            game = self.game_factory()
            winner = game.play().name
            if winner not in wins:
                raise ValueError(f"Match game returned unknown team {winner!r}")
            wins[winner] += 1
        return MatchResult(winner, wins["A"], wins["B"])
