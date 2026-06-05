import pytest
from game_context import GameContext
from card import Card


class TestGameContext:
    def test_fields_accessible(self):
        ctx = GameContext(
            phase_name="Grande",
            team_scores={"A": 5, "B": 3},
            current_bet=2,
            previous_bet=1,
            hand=[Card.R, Card.A],
        )
        assert ctx.phase_name == "Grande"
        assert ctx.team_scores == {"A": 5, "B": 3}
        assert ctx.current_bet == 2
        assert ctx.previous_bet == 1
        assert ctx.hand == [Card.R, Card.A]

    def test_zero_bets(self):
        ctx = GameContext(
            phase_name="Pares",
            team_scores={},
            current_bet=0,
            previous_bet=0,
            hand=[],
        )
        assert ctx.current_bet == 0
        assert ctx.previous_bet == 0

    def test_hand_stores_reference(self):
        cards = [Card.R, Card.A]
        ctx = GameContext("G", {}, 1, 0, cards)
        assert ctx.hand is cards


def test_game_context_has_position_field():
    from game_context import GameContext
    from card import Card
    ctx = GameContext(
        phase_name="Grande",
        team_scores={"A": 0, "B": 0},
        current_bet=1,
        previous_bet=0,
        hand=[Card.A],
        position=2,
        n_players=4,
        opponent_discard_counts=[1, 2],
    )
    assert ctx.position == 2
    assert ctx.n_players == 4
    assert ctx.opponent_discard_counts == [1, 2]

def test_game_context_position_defaults_to_zero():
    from game_context import GameContext
    ctx = GameContext(
        phase_name="Chica",
        team_scores={"A": 0, "B": 0},
        current_bet=1,
        previous_bet=0,
        hand=[],
    )
    assert ctx.position == 0
    assert ctx.n_players == 1
    assert ctx.opponent_discard_counts == []
