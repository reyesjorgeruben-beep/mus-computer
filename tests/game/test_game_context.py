from mus_computer.cards.card import Card
from mus_computer.game.context import GlobalGameContext, WagerPrompt, WagerState


def test_wager_prompt_keeps_private_cards_outside_public_context():
    cards = [Card.R, Card.A]
    shared = GlobalGameContext(
        team_scores={"A": 5, "B": 3}, mus_exchanges=2,
        phase_name="Grande", wager=WagerState(2, 1, "B"),
        public_actions=("Bot 2: envida",), discard_counts={"Bot 2": 1},
        seat_order=(("Bot 1", "A"), ("Bot 2", "B")),
        mano_seat=0, eligible_seats=(0, 1),
    )
    prompt = WagerPrompt(shared, tuple(cards), 0)
    cards.append(Card.C)
    assert prompt.hand == (Card.R, Card.A)
    assert prompt.current_bet == 2 and prompt.previous_bet == 1
    assert prompt.position == 0 and prompt.n_players == 2
    assert prompt.opponent_discard_counts == (1,)
    assert not hasattr(shared, "hand") and not hasattr(shared, "cards")
