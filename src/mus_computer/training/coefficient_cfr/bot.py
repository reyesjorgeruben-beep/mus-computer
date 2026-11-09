"""Use the trained wager probabilities in normal multi-hand Mus games."""

import random

from mus_computer.bots.strategies.actions import MusAction, WagerAction
from mus_computer.game.player_base import PlayerBase

from .policy import Action, Coefficients, Stage


class CoefficientBot(PlayerBase):
    """Always cut Mus; wager using private estimates and the public wager state."""

    def __init__(self, name, team, coefficients: Coefficients, rng=None):
        super().__init__(name, team)
        self.coefficients = coefficients
        self.rng = rng if rng is not None else random.Random()

    def vote_mus(self, global_context, player_context):
        return MusAction.CORTA

    def choose_discards(self, global_context, player_context):
        return ()

    def wager_distribution(self, public, private, seat):
        wager = public.wager
        if wager is None or wager.offering_team is None:
            stage = Stage.OPEN
        elif wager.ordago_offered:
            stage = Stage.ORDAGO
        elif wager.previous_accepted_total >= 2:
            stage = Stage.COUNTER
        else:
            stage = Stage.OFFER
        estimate = private.statistics.outcomes_by_phase[public.phase_name]
        p_win = estimate.p_win + (
            estimate.p_tie if seat == public.eligible_seats[0] else 0
        )
        actions = {
            Action.FOLD: WagerAction.FOLD,
            Action.PASS: WagerAction.MATCH_OR_PASS,
            Action.MATCH: WagerAction.MATCH_OR_PASS,
            Action.BET: WagerAction.RAISE_2,
            Action.RAISE: WagerAction.RAISE_2,
            Action.ORDAGO: WagerAction.ORDAGO,
        }
        return {
            actions[a]: p
            for a, p in self.coefficients.distribution(p_win, stage).items()
        }

    def wager_action(self, global_context, player_context):
        probabilities = self.wager_distribution(
            global_context, player_context, player_context.seat
        )
        return self.rng.choices(
            tuple(probabilities), weights=tuple(probabilities.values()), k=1
        )[0]
