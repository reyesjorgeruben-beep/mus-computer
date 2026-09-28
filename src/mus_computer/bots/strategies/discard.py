"""Select discard indices from estimated post-Mus phase value."""

from dataclasses import dataclass

from mus_computer.bots.strategies.actions import ActionDistribution
from mus_computer.bots.strategies.contexts import HandStatistics, PlayerDecisionContext
from mus_computer.bots.strategies.mus import _phase_weights
from mus_computer.bots.strategies.portfolio import BotPersonality
from mus_computer.game.context import GlobalGameContext


def _expected_value(statistics: HandStatistics, personality: BotPersonality) -> float:
    return sum(
        weight * statistics.expected_points[name]
        for name, weight in _phase_weights(personality).items()
    )


@dataclass(frozen=True)
class ExpectedValueDiscardStrategy:
    def decide(
        self,
        global_context: GlobalGameContext,
        player_context: PlayerDecisionContext,
        personality: BotPersonality,
    ) -> ActionDistribution[tuple[int, ...]]:
        options = dict(player_context.discard_options)
        if not options:
            options[()] = player_context.statistics
        candidates = {}
        for indices, statistics in options.items():
            if any(index < 0 or index >= len(player_context.cards) for index in indices):
                raise ValueError("Discard option contains an invalid card index.")
            if len(set(indices)) != len(indices):
                raise ValueError("Discard option repeats a card index.")
            candidates[indices] = _expected_value(statistics, personality)
        best = max(
            candidates,
            key=lambda indices: (
                candidates[indices],
                (personality.discard_aggressiveness - 0.5) * len(indices),
                -len(indices),
                indices,
            ),
        )
        return ActionDistribution({best: 1.0})
