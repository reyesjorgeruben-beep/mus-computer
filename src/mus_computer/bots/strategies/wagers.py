"""Wager strategy contract and the built-in heuristic implementation."""

from dataclasses import dataclass
from typing import Protocol

from mus_computer.bots.strategies.actions import (
    ActionDistribution, WagerAction, legal_wager_actions,
)
from mus_computer.bots.strategies.contexts import PlayerDecisionContext
from mus_computer.bots.strategies.personality import BotPersonality
from mus_computer.game.context import GlobalGameContext
from mus_computer.game.phases import PhaseName, PHASE_ORDER


class WagerStrategy(Protocol):
    """Choose a wager action; the game remains responsible for settling it."""

    def decide(
        self,
        global_context: GlobalGameContext,
        player_context: PlayerDecisionContext,
        personality: BotPersonality,
    ) -> ActionDistribution[WagerAction]:
        """Return the action probabilities for the current wagering decision."""
        ...


@dataclass(frozen=True)
class HandStrengthWagerStrategy(WagerStrategy):
    """Base wager policy using only this hand's phase loss probability.

    An opening turn passes on a loss or offers two otherwise. In response
    to an opponent's offer, the same probabilities fold or match. Ties are
    included in the non-loss branch. An offered ordago can only be folded or
    matched. Genome values do not affect this policy.
    """

    phase_name: PhaseName

    def __post_init__(self) -> None:
        """Normalize and validate the phase this strategy handles."""
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
        """Map phase loss probability to pass/raise or fold/match actions."""
        if global_context.phase_name != self.phase_name or player_context.phase_name != self.phase_name:
            raise ValueError("Wager strategy and decision phase disagree.")
        p_loss = player_context.statistics.outcomes_by_phase[self.phase_name].p_loss
        if global_context.wager is not None and global_context.wager.offering_team is not None:
            return ActionDistribution({
                WagerAction.FOLD: p_loss,
                WagerAction.MATCH_OR_PASS: 1.0 - p_loss,
            })
        return ActionDistribution({
            WagerAction.MATCH_OR_PASS: p_loss,
            WagerAction.RAISE_2: 1.0 - p_loss,
        })


class WagerLayer(Protocol):
    """Adjust a private copy of the base wager probabilities in place."""

    def apply(
        self,
        probabilities: dict[WagerAction, float],
        global_context: GlobalGameContext,
        player_context: PlayerDecisionContext,
        personality: BotPersonality,
    ) -> None:
        """Change the copied probabilities using the current decision context."""
        ...


def _move_passive_probability(
    probabilities: dict[WagerAction, float], global_context: GlobalGameContext,
    target: WagerAction, rate: float,
) -> None:
    """Move ``rate`` of the current pass or fold chance to a legal target.

    The dictionary is the composition's private copy. An illegal target,
    such as raising over an offered ordago, leaves it unchanged.
    """
    if target not in legal_wager_actions(global_context.wager):
        return
    passive = WagerAction.FOLD if WagerAction.FOLD in probabilities else WagerAction.MATCH_OR_PASS
    moved = probabilities[passive] * rate
    probabilities[passive] -= moved
    probabilities[target] = probabilities.get(target, 0.0) + moved


@dataclass(frozen=True)
class BluffRaiseLayer(WagerLayer):
    """Move a share of pass or fold probability to a two-point raise."""

    def apply(
        self,
        probabilities: dict[WagerAction, float],
        global_context: GlobalGameContext,
        player_context: PlayerDecisionContext,
        personality: BotPersonality,
    ) -> None:
        """Transfer ``bluff_rate`` of the passive chance to raising two."""
        _move_passive_probability(probabilities, global_context, WagerAction.RAISE_2, personality.bluff_rate)


@dataclass(frozen=True)
class ExtremeBluffLayer(WagerLayer):
    """Move a share of remaining pass or fold probability to ordago."""

    def apply(
        self,
        probabilities: dict[WagerAction, float],
        global_context: GlobalGameContext,
        player_context: PlayerDecisionContext,
        personality: BotPersonality,
    ) -> None:
        """Transfer ``extreme_bluff_rate`` of the remaining chance to ordago."""
        _move_passive_probability(
            probabilities, global_context, WagerAction.ORDAGO, personality.extreme_bluff_rate,
        )


@dataclass(frozen=True)
class ComposedWagerStrategy(WagerStrategy):
    """Apply ordered probability layers after a hand-strength baseline."""

    base: HandStrengthWagerStrategy
    layers: tuple[WagerLayer, ...]

    def __post_init__(self) -> None:
        """Require a hand-strength base and usable layers in their given order."""
        if not isinstance(self.base, HandStrengthWagerStrategy):
            raise TypeError("Composed wager strategy requires a hand-strength base.")
        layers = tuple(self.layers)
        if any(not callable(getattr(layer, "apply", None)) for layer in layers):
            raise TypeError("Every wager layer must provide apply().")
        object.__setattr__(self, "layers", layers)

    def decide(
        self,
        global_context: GlobalGameContext,
        player_context: PlayerDecisionContext,
        personality: BotPersonality,
    ) -> ActionDistribution[WagerAction]:
        """Copy the base distribution, apply each layer, and validate the result."""
        base_distribution = self.base.decide(global_context, player_context, personality)
        if not self.layers:
            return base_distribution
        probabilities = dict(base_distribution.probabilities)
        for layer in self.layers:
            layer.apply(probabilities, global_context, player_context, personality)
        return ActionDistribution({
            action: chance for action, chance in probabilities.items() if chance > 0
        })


@dataclass(frozen=True)
class HeuristicWagerStrategy(WagerStrategy):
    """Default phase policy combining estimates, score, and seat."""

    phase_name: PhaseName

    def __post_init__(self) -> None:
        """Normalize and validate the phase this strategy handles."""
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
        """Weight legal actions using hand estimates, score, seat, and Mus history."""
        if global_context.phase_name != self.phase_name or player_context.phase_name != self.phase_name:
            raise ValueError("Wager strategy and decision phase disagree.")
        outcome = player_context.statistics.outcomes_by_phase[self.phase_name]
        own_score = global_context.team_scores.get(player_context.team_name, 0)
        opponent_score = max(
            (score for team, score in global_context.team_scores.items() if team != player_context.team_name),
            default=0,
        )
        seat_count = max(1, len(global_context.seat_order) - 1)
        position = (player_context.seat - global_context.mano_seat) % len(global_context.seat_order)
        preference = 1.0 - abs(position / seat_count - 0.5) * 2.0
        expected = player_context.statistics.expected_points_by_phase[self.phase_name]
        confidence = (
            outcome.p_win + 0.5 * outcome.p_tie
            + min(0.1, max(0.0, expected) * 0.02)
            + 0.1 * (opponent_score - own_score) / 40.0
            + preference * 0.08
            + min(0.12, global_context.mus_exchanges * 0.02)
        )
        confidence = max(0.0, min(1.0, confidence))
        legal = legal_wager_actions(global_context.wager)
        if global_context.wager is not None and global_context.wager.ordago_offered:
            match = max(0.01, confidence + 0.05)
            fold = max(0.01, 1.0 - confidence)
            total = match + fold
            return ActionDistribution({
                WagerAction.MATCH_OR_PASS: match / total,
                WagerAction.FOLD: fold / total,
            })

        fold = max(0.0, 0.5 - confidence) * 2.0 if WagerAction.FOLD in legal else 0.0
        raise_drive = max(0.0, confidence - 0.5) + 0.15
        match = max(0.05, 1.0 - fold - raise_drive)
        weights = {WagerAction.MATCH_OR_PASS: match}
        if WagerAction.FOLD in legal:
            weights[WagerAction.FOLD] = fold
        for increment, action in (
            (2, WagerAction.RAISE_2), (3, WagerAction.RAISE_3),
            (4, WagerAction.RAISE_4), (5, WagerAction.RAISE_5),
        ):
            weights[action] = raise_drive * (
                0.5 / 4.0
                + 0.5 * (increment - 1) / 14.0
            )
        weights[WagerAction.ORDAGO] = (
            raise_drive * 0.5 * max(0.0, confidence - 0.8)
        )
        total = sum(weights.values())
        if total <= 0:
            return ActionDistribution({WagerAction.MATCH_OR_PASS: 1.0})
        return ActionDistribution({action: value / total for action, value in weights.items()})


# Preserve imports used by callers of the first contextual-bot API.
PhaseWagerStrategy = HeuristicWagerStrategy
