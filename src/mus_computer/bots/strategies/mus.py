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
class AlwaysCutMusStrategy(MusStrategy):
    """End Mus immediately, independent of the hand and genome."""

    def decide(
        self,
        global_context: GlobalGameContext,
        player_context: PlayerDecisionContext,
        personality: BotPersonality,
    ) -> ActionDistribution[MusAction]:
        return ActionDistribution({MusAction.CORTA: 1.0, MusAction.MUS: 0.0})


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


@dataclass(frozen=True)
class GeneCutMusStrategy(MusStrategy):
    """Use the base cut probability or combine active Pares/Juego cut genes.

    The two feature probabilities combine as independent reasons to cut:
    Juego + (1 - Juego) * Pares when the hand has both. Hand strength,
    teammate cards, score, and prior Mus exchanges do not enter this policy.
    """

    def decide(
        self,
        global_context: GlobalGameContext,
        player_context: PlayerDecisionContext,
        personality: BotPersonality,
    ) -> ActionDistribution[MusAction]:
        has_pares = player_context.intrinsic_points_by_phase.get("Pares", 0) > 0
        has_juego = player_context.intrinsic_points_by_phase.get("Juego", 0) > 0
        return self.distribution_for_hand(personality, has_pares, has_juego)

    def distribution_for_hand(
        self, personality: BotPersonality, has_pares: bool, has_juego: bool,
    ) -> ActionDistribution[MusAction]:
        """Return the same decision distribution for known Pares/Juego flags."""
        if not has_pares and not has_juego:
            p_cut = personality.cut_prone
        else:
            juego = float(has_juego) * personality.cut_prone_with_juego
            pares = float(has_pares) * personality.cut_prone_with_pares
            p_cut = juego + (1.0 - juego) * pares
        p_cut = max(0.0, min(1.0, p_cut))
        return ActionDistribution({MusAction.CORTA: p_cut, MusAction.MUS: 1.0 - p_cut})
