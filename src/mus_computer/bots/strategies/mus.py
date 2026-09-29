"""Mus or corta policy based on the acting player's estimated improvement."""

from dataclasses import dataclass

from mus_computer.bots.strategies.actions import ActionDistribution, MusAction
from mus_computer.bots.strategies.contexts import HandStatistics, PlayerDecisionContext
from mus_computer.bots.strategies.personality import BotPersonality, phase_utility_weights
from mus_computer.game.context import GlobalGameContext


def _weighted_hand_strength(statistics: HandStatistics, personality: BotPersonality) -> float:
    return sum(
        weight * (statistics.phase_outcomes[name].p_win + 0.5 * statistics.phase_outcomes[name].p_tie)
        for name, weight in phase_utility_weights(personality).items()
    )


@dataclass(frozen=True)
class EstimateMusStrategy:
    def decide(
        self,
        global_context: GlobalGameContext,
        player_context: PlayerDecisionContext,
        personality: BotPersonality,
    ) -> ActionDistribution[MusAction]:
        current = _weighted_hand_strength(player_context.statistics, personality)
        best_after_discard = max(
            (_weighted_hand_strength(stats, personality) for stats in player_context.discard_options.values()),
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
            + 0.6 * (personality.mus_eagerness - 0.5)
            + 0.8 * personality.mus_risk_sensitivity * improvement
            - 0.5 * current
            + 0.12 * personality.score_urgency_sensitivity * score_signal
            - 0.08 * (1.0 - personality.position_preference) * mano_signal
            - 0.04 * global_context.mus_exchanges
        )
        p_mus = max(0.0, min(1.0, p_mus))
        return ActionDistribution({MusAction.MUS: p_mus, MusAction.CORTA: 1.0 - p_mus})
