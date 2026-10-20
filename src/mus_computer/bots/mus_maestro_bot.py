"""Validation opponent with a fixed Mus and conservative wager policy."""

from mus_computer.bots.strategies.actions import MusAction, WagerAction
from mus_computer.game.player_base import PlayerBase


class MusMaestroBot(PlayerBase):
    """Always vote Mus, exchange all cards, pass or fold without raising."""

    def vote_mus(self, global_context, player_context):
        return MusAction.MUS

    def choose_discards(self, global_context, player_context):
        return tuple(range(len(self.cards)))

    def wager_action(self, global_context, player_context):
        if global_context.wager is not None and global_context.wager.offering_team is not None:
            return WagerAction.FOLD
        return WagerAction.MATCH_OR_PASS
