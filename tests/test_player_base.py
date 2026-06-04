import pytest
from team import Team
from card import Card
from game_context import GameContext
from tests.conftest import ScriptedPlayer


class TestPlayerBaseCards:
    def setup_method(self):
        self.team = Team("A")
        self.player = ScriptedPlayer("P", self.team)

    def test_initial_cards_empty(self):
        assert self.player.cards == []

    def test_receive_cards(self):
        self.player.receive_cards([Card.A, Card.R])
        assert self.player.cards == [Card.A, Card.R]

    def test_receive_cards_extends(self):
        self.player.receive_cards([Card.A])
        self.player.receive_cards([Card.R])
        assert self.player.cards == [Card.A, Card.R]

    def test_throw_card_removes_by_index(self):
        self.player.receive_cards([Card.A, Card.R, Card._5])
        removed = self.player.throw_card(1)
        assert removed == Card.R
        assert self.player.cards == [Card.A, Card._5]

    def test_throw_card_first(self):
        self.player.receive_cards([Card.A, Card.R])
        self.player.throw_card(0)
        assert self.player.cards == [Card.R]

    def test_throw_card_last(self):
        self.player.receive_cards([Card.A, Card.R, Card._5])
        self.player.throw_card(2)
        assert self.player.cards == [Card.A, Card.R]

    def test_throw_card_invalid_index_raises(self):
        self.player.receive_cards([Card.A, Card.R])
        with pytest.raises(ValueError):
            self.player.throw_card(5)

    def test_throw_card_negative_index_raises(self):
        self.player.receive_cards([Card.A, Card.R])
        with pytest.raises(ValueError):
            self.player.throw_card(-1)

    def test_throw_cards_clears_all(self):
        self.player.receive_cards([Card.A, Card.R, Card._5, Card._7])
        self.player.throw_cards()
        assert self.player.cards == []

    def test_each_player_has_own_cards_list(self):
        p2 = ScriptedPlayer("P2", self.team)
        self.player.receive_cards([Card.A])
        assert p2.cards == []


class TestPlayerBaseAbstract:
    def test_cannot_instantiate_abstract_class(self):
        from player_base import PlayerBase
        with pytest.raises(TypeError):
            PlayerBase("name", Team("A"))  # type: ignore


class TestScriptedPlayerDecisions:
    def setup_method(self):
        self.team_a = Team("A")
        self.team_b = Team("B")

    def test_vote_mus_sequence(self):
        p = ScriptedPlayer("P", self.team_a, mus_votes=[True, False, True])
        assert p.vote_mus() is True
        assert p.vote_mus() is False
        assert p.vote_mus() is True

    def test_choose_discards_sequence(self):
        p = ScriptedPlayer("P", self.team_a, discards=[[0, 1], [2]])
        assert p.choose_discards() == [0, 1]
        assert p.choose_discards() == [2]

    def test_wager_action_sequence(self):
        ctx = GameContext("Grande", {}, 1, 0, [])
        p = ScriptedPlayer("P", self.team_a, wager_actions=[2, 0, -1])
        assert p.wager_action(ctx) == 2
        assert p.wager_action(ctx) == 0
        assert p.wager_action(ctx) == -1
