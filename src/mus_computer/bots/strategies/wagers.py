"""One independent wager policy per game phase."""

from dataclasses import dataclass

from mus_computer.bots.strategies.actions import (
    ActionDistribution, WagerAction, legal_wager_actions,
)
from mus_computer.bots.strategies.contexts import PlayerDecisionContext
from mus_computer.bots.strategies.personality import BotPersonality
from mus_computer.game.context import GlobalGameContext
from mus_computer.game.phases import PhaseName, PHASE_ORDER


@dataclass(frozen=True)
class PhaseWagerStrategy:
    phase_name: PhaseName

    def __post_init__(self) -> None:
        phase = PhaseName(self.phase_name)
        if phase not in PHASE_ORDER:
            raise ValueError(f"Unknown wager phase: {phase}")
        object.__setattr__(self, "phase_name", phase)

    def decide(
        self,
        global_context: GlobalGameContext,
        player_context: PlayerDecisionContext,
        personality: BotPersonality,
    ) -> ActionDistribution[WagerAction]:
        if global_context.phase_name != self.phase_name or player_context.phase_name != self.phase_name:
            raise ValueError("Wager strategy and decision phase disagree.")
        outcome = player_context.statistics.phase_outcomes[self.phase_name]
        own_score = global_context.team_scores.get(player_context.team_name, 0)
        opponent_score = max(
            (score for team, score in global_context.team_scores.items() if team != player_context.team_name),
            default=0,
        )
        seat_count = max(1, len(global_context.seat_order) - 1)
        position = (player_context.seat - global_context.mano_seat) % len(global_context.seat_order)
        preference = 1.0 - abs(position / seat_count - personality.position_preference) * 2.0
        expected = player_context.statistics.expected_points[self.phase_name]
        confidence = (
            outcome.p_win + 0.5 * outcome.p_tie
            + min(0.1, max(0.0, expected) * 0.02)
            + personality.score_urgency_sensitivity * (opponent_score - own_score) / 40.0 * 0.2
            + preference * 0.08
            + min(0.12, global_context.mus_exchanges * 0.02)
        )
        confidence = max(0.0, min(1.0, confidence))
        legal = legal_wager_actions(global_context.wager)
        if global_context.wager is not None and global_context.wager.ordago_offered:
            match = max(0.01, confidence + personality.bluff_rate * 0.1)
            fold = max(0.01, 1.0 - confidence)
            total = match + fold
            return ActionDistribution({
                WagerAction.MATCH_OR_PASS: match / total,
                WagerAction.FOLD: fold / total,
            })

        fold = max(0.0, personality.fold_threshold - confidence) * 2.0 if WagerAction.FOLD in legal else 0.0
        raise_drive = max(0.0, confidence - personality.raise_threshold) + 0.3 * personality.bluff_rate
        match = max(0.05, 1.0 - fold - raise_drive)
        weights = {WagerAction.MATCH_OR_PASS: match}
        if WagerAction.FOLD in legal:
            weights[WagerAction.FOLD] = fold
        for increment, action in (
            (2, WagerAction.RAISE_2), (3, WagerAction.RAISE_3),
            (4, WagerAction.RAISE_4), (5, WagerAction.RAISE_5),
        ):
            weights[action] = raise_drive * (
                (1.0 - personality.risk_factor) / 4.0
                + personality.risk_factor * (increment - 1) / 14.0
            )
        weights[WagerAction.ORDAGO] = (
            raise_drive * personality.risk_factor * max(0.0, confidence - 0.8)
        )
        total = sum(weights.values())
        if total <= 0:
            return ActionDistribution({WagerAction.MATCH_OR_PASS: 1.0})
        return ActionDistribution({action: value / total for action, value in weights.items()})
