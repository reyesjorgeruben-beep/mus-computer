"""Mus or corta policy based on the acting player's estimated improvement."""

from dataclasses import dataclass
from typing import Protocol

from mus_computer.bots.strategies.actions import ActionDistribution, MusAction
from mus_computer.bots.strategies.contexts import HandStatistics, PlayerDecisionContext
from mus_computer.bots.strategies.personality import BotPersonality, FIXED_PHASE_WEIGHTS
from mus_computer.game.context import GlobalGameContext


def _weighted_hand_strength(statistics: HandStatistics) -> float:
    return sum(
        weight * (statistics.outcomes_by_phase[name].p_win + 0.5 * statistics.outcomes_by_phase[name].p_tie)
        for name, weight in FIXED_PHASE_WEIGHTS.items()
    )


class MusStrategy(Protocol):
    """Choose a Mus vote from public state and private estimates."""

    def decide(
        self,
        global_context: GlobalGameContext,
        player_context: PlayerDecisionContext,
        personality: BotPersonality,
    ) -> ActionDistribution[MusAction]: ...


@dataclass(frozen=True)
class EstimateMusStrategy(MusStrategy):
    """Default Mus policy using the current weighted-estimate formula."""

    def decide(
        self,
        global_context: GlobalGameContext,
        player_context: PlayerDecisionContext,
        personality: BotPersonality,
    ) -> ActionDistribution[MusAction]:
        current = _weighted_hand_strength(player_context.statistics)
        best_after_discard = max(
            (_weighted_hand_strength(option.statistics) for option in player_context.discard_options),
            default=current,
        )
        improvement = max(0.0, best_after_discard - current)
        own_score = global_context.team_scores.get(player_context.team_name, 0)
        opponent_score = max(
            (score for team, score in global_context.team_scores.items() if team != player_context.team_name),
            default=0,
        )
        score_signal = (opponent_score - own_score) / 40.0
        mano_signal = 1.0 if player_context.seat == global_context.mano_seat else 0.0
        p_mus = (
            0.55
            + 0.4 * improvement
            - 0.5 * current
            + 0.06 * score_signal
            - 0.04 * mano_signal
            - 0.04 * global_context.mus_exchanges
        )
        p_mus = max(0.0, min(1.0, p_mus))
        return ActionDistribution({MusAction.MUS: p_mus, MusAction.CORTA: 1.0 - p_mus})
