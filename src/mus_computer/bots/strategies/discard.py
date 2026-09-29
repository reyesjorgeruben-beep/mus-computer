"""Select discard indices from estimated post-Mus phase value."""

from dataclasses import dataclass

from mus_computer.bots.strategies.actions import ActionDistribution
from mus_computer.bots.strategies.contexts import HandStatistics, PlayerDecisionContext
from mus_computer.bots.strategies.personality import BotPersonality, phase_utility_weights
from mus_computer.game.context import GlobalGameContext


def _personality_weighted_point_utility(
    statistics: HandStatistics,
    personality: BotPersonality,
) -> float:
    """Rank a hand by personality-weighted points without changing its estimates."""
    return sum(
        weight * statistics.expected_points[name]
        for name, weight in phase_utility_weights(personality).items()
    )


def _discard_aggressiveness_tiebreak(discard_count: int, personality: BotPersonality) -> float:
    """Apply discard preference only after two options have equal utility."""
    return (personality.discard_aggressiveness - 0.5) * discard_count


def _discard_option_rank(
    indices: tuple[int, ...],
    statistics: HandStatistics,
    personality: BotPersonality,
) -> tuple[float, float, int, tuple[int, ...]]:
    return (
        _personality_weighted_point_utility(statistics, personality),
        _discard_aggressiveness_tiebreak(len(indices), personality),
        -len(indices),
        indices,
    )


@dataclass(frozen=True)
class PersonalityWeightedDiscardStrategy:
    """Choose the discard with the best personality-weighted phase utility.

    The underlying expected-point estimates remain objective; personality
    weights express how this bot ranks phase value. If post-discard estimates
    were not requested, the only candidate is standing pat (``()``).
    """

    def decide(
        self,
        global_context: GlobalGameContext,
        player_context: PlayerDecisionContext,
        personality: BotPersonality,
    ) -> ActionDistribution[tuple[int, ...]]:
        options = dict(player_context.discard_options) or {(): player_context.statistics}
        candidates = {}
        for indices, statistics in options.items():
            if any(index < 0 or index >= len(player_context.cards) for index in indices):
                raise ValueError("Discard option contains an invalid card index.")
            if len(set(indices)) != len(indices):
                raise ValueError("Discard option repeats a card index.")
            candidates[indices] = statistics
        best = max(
            candidates,
            key=lambda indices: _discard_option_rank(indices, candidates[indices], personality),
        )
        return ActionDistribution({best: 1.0})


# Retain the original import name for callers that adopted the first strategy API.
ExpectedValueDiscardStrategy = PersonalityWeightedDiscardStrategy
