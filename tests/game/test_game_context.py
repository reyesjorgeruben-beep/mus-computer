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
