"""Select discard indices from estimated post-Mus phase value."""

from dataclasses import dataclass
from typing import Protocol

from mus_computer.bots.strategies.actions import ActionDistribution, DiscardAction
from mus_computer.bots.strategies.contexts import DiscardOption, HandStatistics, PlayerDecisionContext
from mus_computer.bots.strategies.personality import BotPersonality, FIXED_PHASE_WEIGHTS
from mus_computer.game.context import GlobalGameContext


def _point_utility(statistics: HandStatistics) -> float:
    """Rank a hand by fixed phase weights without changing its estimates."""
    return sum(
        weight * statistics.expected_points_by_phase[name]
        for name, weight in FIXED_PHASE_WEIGHTS.items()
    )


@dataclass(frozen=True, order=True)
class DiscardOptionScore:
    """Ordered criteria for choosing one discard option."""

    phase_utility: float
    fewer_discards: int
    indices: tuple[int, ...]


def _discard_option_score(
    option: DiscardOption,
) -> DiscardOptionScore:
    discard_count = len(option.action.indices)
    return DiscardOptionScore(
        phase_utility=_point_utility(option.statistics),
        fewer_discards=-discard_count,
        indices=option.action.indices,
    )


class DiscardStrategy(Protocol):
    """Choose among the discard options supplied in the private context."""

    def decide(
        self,
        global_context: GlobalGameContext,
        player_context: PlayerDecisionContext,
        personality: BotPersonality,
    ) -> ActionDistribution[DiscardAction]: ...


@dataclass(frozen=True)
class PersonalityWeightedDiscardStrategy(DiscardStrategy):
    """Choose the discard with the best fixed phase utility.

    The underlying expected-point estimates remain objective. Fixed weights
    express how this bot ranks phase value. If post-discard estimates were not
    requested, the only option is to keep all cards.
    """

    def decide(
        self,
        global_context: GlobalGameContext,
        player_context: PlayerDecisionContext,
        personality: BotPersonality,
    ) -> ActionDistribution[DiscardAction]:
        best = max(
            player_context.discard_options,
            key=_discard_option_score,
        )
        return ActionDistribution({best.action: 1.0})


# Retain the original import name for callers that adopted the first strategy API.
ExpectedValueDiscardStrategy = PersonalityWeightedDiscardStrategy
