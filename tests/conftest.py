import pytest
from typing import List
from mus_computer.game.player_base import PlayerBase
from mus_computer.game.context import GlobalGameContext, WagerPrompt, WagerState


def make_wager_prompt(cards=(), phase_name="Grande", current_bet=1, previous_bet=0):
    shared = GlobalGameContext(
        team_scores={"A": 0, "B": 0}, mus_exchanges=0,
        phase_name=phase_name,
        wager=WagerState(current_bet, previous_bet, None),
        public_actions=(), discard_counts={},
        seat_order=(("P", "A"), ("Opponent", "B")),
        mano_seat=0, eligible_seats=(0, 1),
    )
    return WagerPrompt(shared, tuple(cards), 0)


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

    def wager_action(self, context: WagerPrompt) -> int:
        a = self._wager_actions[self._wager_idx]
        self._wager_idx += 1
        return a
