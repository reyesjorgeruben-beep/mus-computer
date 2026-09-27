import random
from typing import List

from game_context import GameContext
from player_base import PlayerBase


class RandomBotPlayer(PlayerBase):
    """A player whose Mus, discard, and wager decisions are random."""

    def vote_mus(self) -> bool:
        return random.choice((True, False))

    def choose_discards(self) -> List[int]:
        count = random.randint(0, len(self.cards))
        return random.sample(range(len(self.cards)), count)

    def wager_action(self, context: GameContext) -> int:
        action = random.choice(("fold", "pass", "raise"))
        if action == "fold":
            return -1
        if action == "pass":
            return 0
        return random.randint(1, 3)
