from typing import List
from player_base import PlayerBase
from game_context import GameContext


class ScriptedPlayer(PlayerBase):
    """A test double that returns pre-scripted decisions in order."""

    def __init__(self, name, team, mus_votes=(), discards=(), wager_actions=()):
        super().__init__(name, team)
        self._mus_votes = list(mus_votes)
        self._discards = list(discards)
        self._wager_actions = list(wager_actions)
        self._mus_idx = 0
        self._discard_idx = 0
        self._wager_idx = 0

    def vote_mus(self) -> bool:
        v = self._mus_votes[self._mus_idx]
        self._mus_idx += 1
        return v

    def choose_discards(self) -> List[int]:
        d = self._discards[self._discard_idx]
        self._discard_idx += 1
        return d

    def wager_action(self, context: GameContext) -> int:
        a = self._wager_actions[self._wager_idx]
        self._wager_idx += 1
        return a
