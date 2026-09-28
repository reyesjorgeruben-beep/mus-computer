"""Private per-player decision information and statistical estimates."""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from mus_computer.cards.card import Card


@dataclass(frozen=True)
class OutcomeProbability:
    p_win: float
    p_tie: float
    p_loss: float


@dataclass(frozen=True)
class HandStatistics:
    phase_outcomes: Mapping[str, OutcomeProbability]
    expected_points: Mapping[str, float]

    def __post_init__(self) -> None:
        object.__setattr__(self, "phase_outcomes", MappingProxyType(dict(self.phase_outcomes)))
        object.__setattr__(self, "expected_points", MappingProxyType(dict(self.expected_points)))


@dataclass(frozen=True)
class PlayerDecisionContext:
    player_name: str
    team_name: str
    seat: int
    cards: tuple[Card, ...]
    phase_name: str | None
    eligible: bool
    intrinsic_points: Mapping[str, int]
    statistics: HandStatistics
    discard_options: Mapping[tuple[int, ...], HandStatistics]

    def __post_init__(self) -> None:
        object.__setattr__(self, "cards", tuple(self.cards))
        object.__setattr__(self, "intrinsic_points", MappingProxyType(dict(self.intrinsic_points)))
        object.__setattr__(self, "discard_options", MappingProxyType(dict(self.discard_options)))
