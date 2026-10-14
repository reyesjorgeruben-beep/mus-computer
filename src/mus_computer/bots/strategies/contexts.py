"""Private per-player decision information and statistical estimates."""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from mus_computer.bots.strategies.actions import DiscardAction
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

    outcomes_by_phase: Mapping[PhaseName, OutcomeProbability]
    expected_points_by_phase: Mapping[PhaseName, float]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "outcomes_by_phase",
            MappingProxyType(
                {PhaseName(phase): outcome for phase, outcome in self.outcomes_by_phase.items()}
            ),
        )
        object.__setattr__(
            self,
            "expected_points_by_phase",
            MappingProxyType(
                {PhaseName(phase): points for phase, points in self.expected_points_by_phase.items()}
            ),
        )


@dataclass(frozen=True)
class DiscardOption:
    """A legal discard action and the estimated hand after its exchange."""

    action: DiscardAction
    statistics: HandStatistics

    def __post_init__(self) -> None:
        if not isinstance(self.action, DiscardAction):
            raise TypeError("A discard option requires a DiscardAction.")
        if not isinstance(self.statistics, HandStatistics):
            raise TypeError("A discard option requires HandStatistics.")


@dataclass(frozen=True)
class PlayerDecisionContext:
    """Frozen private snapshot for one decision prompt.

    ``statistics`` describes the current hand across phases. ``discard_options``
    is always nonempty. Without post-exchange estimates it contains only the
    option to keep all cards, using the current-hand statistics.
    """

    player_name: str
    team_name: str
    seat: int
    cards: tuple[Card, ...]
    phase_name: PhaseName | None
    eligible: bool
    intrinsic_points_by_phase: Mapping[PhaseName, int]
    statistics: HandStatistics
    discard_options: tuple[DiscardOption, ...]

    def __post_init__(self) -> None:
        if self.phase_name is not None:
            object.__setattr__(self, "phase_name", PhaseName(self.phase_name))
        object.__setattr__(self, "cards", tuple(self.cards))
        object.__setattr__(
            self,
            "intrinsic_points_by_phase",
            MappingProxyType(
                {PhaseName(phase): points for phase, points in self.intrinsic_points_by_phase.items()}
            ),
        )
        options = tuple(self.discard_options)
        if not options or any(not isinstance(option, DiscardOption) for option in options):
            raise ValueError("Discard options must contain at least one DiscardOption.")
        actions = [option.action for option in options]
        if len(set(actions)) != len(actions):
            raise ValueError("Discard options cannot repeat an action.")
        if any(index >= len(self.cards) for action in actions for index in action.indices):
            raise ValueError("Discard option contains an invalid card index.")
        object.__setattr__(self, "discard_options", options)
