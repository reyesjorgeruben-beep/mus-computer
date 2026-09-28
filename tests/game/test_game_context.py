from mus_computer.cards.card import Card
from mus_computer.game.context import GlobalGameContext, WagerState


def test_player_context_keeps_private_cards_outside_public_context():
    from mus_computer.game.team import Team
    from tests.conftest import ScriptedPlayer
    player = ScriptedPlayer("Bot 1", Team("A"))
    player.cards = [Card.R, Card.A, Card._4, Card._5]
    shared = GlobalGameContext(
        team_scores={"A": 5, "B": 3}, mus_exchanges=2,
        phase_name="Grande", wager=WagerState(2, 1, "B"),
        public_actions=("Bot 2: envida",), discard_counts={"Bot 2": 1},
        seat_order=(("Bot 1", "A"), ("Bot 2", "B")),
        mano_seat=0, eligible_seats=(0, 1),
    )
    private = player.decision_context(shared, seat=0)
    player.cards[0] = Card.C
    assert private.cards == (Card.R, Card.A, Card._4, Card._5)
    assert shared.wager.current_total == 2 and shared.wager.previous_accepted_total == 1
    assert private.seat == 0 and shared.eligible_seats == (0, 1)
    assert shared.discard_counts["Bot 2"] == 1
    assert not hasattr(shared, "hand") and not hasattr(shared, "cards")



def test_juego_estimate_uses_eligible_priority_only_for_active_phase():
    import pytest
    from mus_computer.game.team import Team
    from mus_computer.probabilities.estimates import estimate_hand_statistics
    from tests.conftest import ScriptedPlayer

    shared = GlobalGameContext(
        team_scores={"A":0,"B":0}, mus_exchanges=0, phase_name="Juego",
        wager=WagerState(0,1,None), public_actions=(), discard_counts={},
        seat_order=(("A1","A"),("B1","B"),("A2","A"),("B2","B")),
        mano_seat=0, eligible_seats=(2,3),
    )
    cards = [Card.R,Card.C,Card.S,Card.A]
    without_priority = estimate_hand_statistics(cards, is_mano=False)
    for seat, name, team_name in ((2,"A2","A"),(3,"B2","B")):
        player = ScriptedPlayer(name, Team(team_name))
        player.cards = cards
        private = player.decision_context(shared, seat)
        juego = private.statistics.phase_outcomes["Juego"]
        assert juego.p_tie > 0
        expected = 3 * (juego.p_win + (juego.p_tie if seat == 2 else 0))
        assert private.statistics.expected_points["Juego"] == pytest.approx(expected)
        for phase in ("Grande","Chica","Pares","Punto"):
            assert private.statistics.expected_points[phase] == without_priority.expected_points[phase]
