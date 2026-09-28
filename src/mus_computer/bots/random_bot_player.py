import random
from mus_computer.game.player_base import PlayerBase
from mus_computer.bots.strategies.actions import MusAction, legal_wager_actions


class RandomBotPlayer(PlayerBase):
    """Uniform random legal actions, independent of hand strength."""

    def vote_mus(self, global_context, player_context):
        return random.choice(tuple(MusAction))

    def choose_discards(self, global_context, player_context):
        count = random.randint(0, len(self.cards))
        return tuple(sorted(random.sample(range(len(self.cards)), count)))

    def wager_action(self, global_context, player_context):
        return random.choice(tuple(sorted(legal_wager_actions(global_context.wager), key=lambda a: a.value)))
