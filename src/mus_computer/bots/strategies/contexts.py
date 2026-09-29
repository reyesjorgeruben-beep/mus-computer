"""Private per-player decision information and statistical estimates."""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from mus_computer.cards.card import Card
from mus_computer.game.phases import PhaseName


@dataclass(frozen=True)
class OutcomeProbability:
    p_win: float
    p_tie: float
    p_loss: float


@dataclass(frozen=True)
class HandStatistics:
    """Hand estimates keyed by the typed phase each estimate describes."""

    phase_outcomes: Mapping[PhaseName, OutcomeProbability]
    expected_points: Mapping[PhaseName, float]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "phase_outcomes",
            MappingProxyType(
                {PhaseName(phase): outcome for phase, outcome in self.phase_outcomes.items()}
            ),
        )
        object.__setattr__(
            self,
            "expected_points",
            MappingProxyType(
                {PhaseName(phase): points for phase, points in self.expected_points.items()}
            ),
        )


@dataclass(frozen=True)
class PlayerDecisionContext:
    """Frozen private snapshot for one decision prompt.

    ``statistics`` describes the current hand across phases. ``discard_options``
    contains post-exchange estimates when requested; an empty mapping means
    those alternatives were not computed, so discard policies can safely fall
    back to standing pat using ``statistics``.
    """

    player_name: str
    team_name: str
    seat: int
    cards: tuple[Card, ...]
    phase_name: PhaseName | None
    eligible: bool
    intrinsic_points: Mapping[PhaseName, int]
    statistics: HandStatistics
    discard_options: Mapping[tuple[int, ...], HandStatistics]

    def __post_init__(self) -> None:
        if self.phase_name is not None:
            object.__setattr__(self, "phase_name", PhaseName(self.phase_name))
        object.__setattr__(self, "cards", tuple(self.cards))
        object.__setattr__(
            self,
            "intrinsic_points",
            MappingProxyType(
                {PhaseName(phase): points for phase, points in self.intrinsic_points.items()}
            ),
        )
        object.__setattr__(self, "discard_options", MappingProxyType(dict(self.discard_options)))
