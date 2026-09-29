import pytest
from unittest.mock import patch
from mus_computer.game.team import Team
from mus_computer.cards.card import Card
from mus_computer.game.player import HumanPlayer
from tests.conftest import make_global_context
from mus_computer.bots.strategies.actions import MusAction, WagerAction
from dataclasses import replace


@pytest.fixture
def player():
    t = Team("A")
    p = HumanPlayer("Test", t)
    p.receive_cards([Card.R, Card.C, Card.S, Card._7])
    return p


@pytest.fixture
def ctx():
    shared = make_global_context(current_bet=2, previous_bet=1)
    return replace(shared, wager=replace(shared.wager, offering_team="B"))


class TestHumanPlayerVoteMus:
    def test_yes_vote(self, player):
        with patch("builtins.input", return_value="y"):
            assert player.vote_mus() is MusAction.MUS

    def test_no_vote(self, player):
        with patch("builtins.input", return_value="n"):
            assert player.vote_mus() is MusAction.CORTA

    def test_empty_input_is_yes(self, player):
        with patch("builtins.input", return_value=""):
            assert player.vote_mus() is MusAction.MUS

    def test_uppercase_no(self, player):
        with patch("builtins.input", return_value="N"):
            assert player.vote_mus() is MusAction.CORTA


class TestHumanPlayerChooseDiscards:
    def test_valid_single_index(self, player):
        with patch("builtins.input", return_value="1"):
            result = player.choose_discards()
        assert result == [0]

    def test_valid_multiple_indices(self, player):
        with patch("builtins.input", return_value="1,3"):
            result = player.choose_discards()
        assert result == [0, 2]

    def test_all_four_indices(self, player):
        with patch("builtins.input", return_value="1,2,3,4"):
            result = player.choose_discards()
        assert result == [0, 1, 2, 3]

    def test_retry_on_out_of_range(self, player):
        with patch("builtins.input", side_effect=["9", "2"]):
            result = player.choose_discards()
        assert result == [1]

    def test_retry_on_empty_input(self, player):
        with patch("builtins.input", side_effect=["", "1"]):
            result = player.choose_discards()
        assert result == [0]

    def test_retry_on_non_numeric(self, player):
        with patch("builtins.input", side_effect=["abc", "1"]):
            result = player.choose_discards()
        assert result == [0]


class TestHumanPlayerWagerAction:
    def test_raise(self, player, ctx):
        with patch("builtins.input", return_value="3"):
            assert player.wager_action(ctx) is WagerAction.RAISE_3

    def test_call(self, player, ctx):
        with patch("builtins.input", return_value="0"):
            assert player.wager_action(ctx) is WagerAction.MATCH_OR_PASS

    def test_fold(self, player, ctx):
        with patch("builtins.input", return_value="-1"):
            assert player.wager_action(ctx) is WagerAction.FOLD


def test_wager_prompt_explains_phase_stakes_and_counterraise(player,ctx):
    with patch("builtins.input", return_value="0") as read:
        player.wager_action(ctx)
    prompt=read.call_args.args[0]
    assert "Grande" in prompt
    assert "current offer=2" in prompt
    assert "previously accepted=1" in prompt
    assert "0=quiero (accept 2)" in prompt
    assert "2-5=add to current offer" in prompt


def test_unopened_pares_prompt_shows_implicit_stake_awarded_on_refusal(player):
    from mus_computer.game.wager_session import WagerSession
    from tests.conftest import ScriptedPlayer

    opponent = ScriptedPlayer("Opponent", Team("B"), wager_actions=[-1])
    opponent.cards = [Card._4, Card._4, Card._5, Card._6]
    player.cards = [Card.R, Card.R, Card._5, Card._6]
    with patch("builtins.input", return_value="2") as read:
        result = WagerSession(
            [player, opponent], 0, "Pares", {"A": 0, "B": 0},
            (player.team, opponent.team),
        ).run()
    prompt = read.call_args.args[0]
    assert "Pares" in prompt
    assert "current offer=none" in prompt
    assert "previously accepted=1" in prompt
    assert "2-5=opening total" in prompt
    assert result.points == 1
    assert result.winner_team is player.team
