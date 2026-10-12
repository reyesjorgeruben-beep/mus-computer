"""Select discard indices from estimated post-Mus phase value."""

from dataclasses import dataclass

from mus_computer.bots.strategies.actions import ActionDistribution, DiscardAction
from mus_computer.bots.strategies.contexts import DiscardOption, HandStatistics, PlayerDecisionContext
from mus_computer.bots.strategies.personality import BotPersonality, phase_utility_weights
from mus_computer.game.context import GlobalGameContext


def _personality_weighted_point_utility(
    statistics: HandStatistics,
    personality: BotPersonality,
) -> float:
    """Rank a hand by personality-weighted points without changing its estimates."""
    return sum(
        weight * statistics.expected_points_by_phase[name]
        for name, weight in phase_utility_weights(personality).items()
    )


def _discard_tiebreak(discard_count: int, personality: BotPersonality) -> float:
    """Apply discard preference only after two options have equal utility."""
    return (personality.discard_aggressiveness - 0.5) * discard_count


@dataclass(frozen=True, order=True)
class DiscardOptionScore:
    """Ordered criteria for choosing one discard option."""

    phase_utility: float
    discard_tiebreak: float
    fewer_discards: int
    indices: tuple[int, ...]


def _discard_option_score(
    option: DiscardOption,
    personality: BotPersonality,
) -> DiscardOptionScore:
    discard_count = len(option.action.indices)
    return DiscardOptionScore(
        phase_utility=_personality_weighted_point_utility(option.statistics, personality),
        discard_tiebreak=_discard_tiebreak(discard_count, personality),
        fewer_discards=-discard_count,
        indices=option.action.indices,
    )


@dataclass(frozen=True)
class PersonalityWeightedDiscardStrategy:
    """Choose the discard with the best personality-weighted phase utility.

    The underlying expected-point estimates remain objective; personality
    weights express how this bot ranks phase value. If post-discard estimates
    were not requested, the only option is to keep all cards.
    """

    def decide(
        self,
        global_context: GlobalGameContext,
        player_context: PlayerDecisionContext,
        personality: BotPersonality,
    ) -> ActionDistribution[DiscardAction]:
        best = max(
            player_context.discard_options,
            key=lambda option: _discard_option_score(option, personality),
        )
        return ActionDistribution({best.action: 1.0})


# Retain the original import name for callers that adopted the first strategy API.
ExpectedValueDiscardStrategy = PersonalityWeightedDiscardStrategy
