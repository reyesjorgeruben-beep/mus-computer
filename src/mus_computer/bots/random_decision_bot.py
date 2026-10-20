"""Validation opponent that samples uniformly from every legal action."""

import random
from itertools import combinations

from mus_computer.bots.strategies.actions import MusAction, legal_wager_actions
from mus_computer.game.player_base import PlayerBase


class RandomDecisionBot(PlayerBase):
    """Ignore hand strength and give each available action equal weight."""

    def __init__(self, name, team, random_generator: random.Random | None = None):
        super().__init__(name, team)
        self._random_generator = random_generator if random_generator is not None else random.Random()

    def vote_mus(self, global_context, player_context):
        return self._random_generator.choice(tuple(MusAction))

    def choose_discards(self, global_context, player_context):
        indices = range(len(self.cards))
        choices = tuple(
            subset for count in range(len(self.cards) + 1)
            for subset in combinations(indices, count)
        )
        return self._random_generator.choice(choices)

    def wager_action(self, global_context, player_context):
        legal = sorted(legal_wager_actions(global_context.wager), key=lambda action: action.value)
        return self._random_generator.choice(legal)
