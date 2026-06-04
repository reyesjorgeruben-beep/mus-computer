import pytest
from unittest.mock import patch
from team import Team
from card import Card
from player import HumanPlayer
from game_context import GameContext


@pytest.fixture
def player():
    t = Team("A")
    p = HumanPlayer("Test", t)
    p.receive_cards([Card.R, Card.C, Card.S, Card._7])
    return p


@pytest.fixture
def ctx():
    return GameContext("Grande", {"A": 0, "B": 0}, current_bet=2, previous_bet=1, hand=[])


class TestHumanPlayerVoteMus:
    def test_yes_vote(self, player):
        with patch("builtins.input", return_value="y"):
            assert player.vote_mus() is True

    def test_no_vote(self, player):
        with patch("builtins.input", return_value="n"):
            assert player.vote_mus() is False

    def test_empty_input_is_yes(self, player):
        with patch("builtins.input", return_value=""):
            assert player.vote_mus() is True

    def test_uppercase_no(self, player):
        with patch("builtins.input", return_value="N"):
            assert player.vote_mus() is False


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
            assert player.wager_action(ctx) == 3

    def test_call(self, player, ctx):
        with patch("builtins.input", return_value="0"):
            assert player.wager_action(ctx) == 0

    def test_fold(self, player, ctx):
        with patch("builtins.input", return_value="-1"):
            assert player.wager_action(ctx) == -1
