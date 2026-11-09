from mus_computer.bots.bot_player import BotPlayer
from mus_computer.game.context import GlobalGameContext, SeatOrderEntry, WagerState
from mus_computer.game.game import Game
from mus_computer.game.phases import PhaseName
from mus_computer.game.player_base import PlayerBase


def require_bot_players(game: Game) -> list[BotPlayer]:
    players = []
    for player in game.players_in_order:
        assert isinstance(player, BotPlayer)
        players.append(player)
    return players


def make_global_context(phase_name=PhaseName.GRANDE, current_bet=1, previous_bet=0):
    shared = GlobalGameContext(
        team_scores={"A": 0, "B": 0},
        mus_exchanges=0,
        phase_name=phase_name,
        wager=WagerState(current_bet, previous_bet, None),
        public_actions=(),
        discard_counts={},
        seat_order=(SeatOrderEntry("P", "A"), SeatOrderEntry("Opponent", "B")),
        mano_seat=0,
        eligible_seats=(0, 1),
    )
    return shared


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

    def vote_mus(self, global_context=None, player_context=None):
        v = self._mus_votes[self._mus_idx]
        self._mus_idx += 1
        from mus_computer.bots.strategies.actions import MusAction

        return (
            (MusAction.MUS if v else MusAction.CORTA)
            if global_context is not None
            else v
        )

    def choose_discards(self, global_context=None, player_context=None):
        d = self._discards[self._discard_idx]
        self._discard_idx += 1
        return d

    def wager_action(self, global_context=None, player_context=None):
        a = self._wager_actions[self._wager_idx]
        self._wager_idx += 1
        if player_context is None:
            return a
        from mus_computer.bots.strategies.actions import WagerAction

        if isinstance(a, WagerAction):
            return a
        return (
            WagerAction.FOLD
            if a < 0
            else WagerAction.MATCH_OR_PASS
            if a == 0
            else WagerAction[f"RAISE_{a}"]
        )
