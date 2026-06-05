import pytest
from card import Card
from probability_tables import canonical, load_tables, win_prob, avg_opp_improvement_per_phase

def test_canonical_sorts_descending():
    cards = [Card.A, Card.R, Card._4]
    result = canonical(cards)
    assert result == (Card.R, Card._4, Card.A)

def test_canonical_handles_duplicates():
    cards = [Card.A, Card.A, Card.R, Card.R]
    result = canonical(cards)
    assert result == (Card.R, Card.R, Card.A, Card.A)

def test_tables_contain_330_hands():
    tables = load_tables()
    hand_keys = [k for k in tables if k != "_avg_opp_phase_improvements"]
    assert len(hand_keys) == 330

def test_tables_have_all_phases():
    tables = load_tables()
    key = next(k for k in tables if k != "_avg_opp_phase_improvements")
    assert set(tables[key].keys()) == {"Grande", "Chica", "Pares", "Juego"}

def test_tables_probabilities_sum_to_one():
    tables = load_tables()
    key = next(k for k in tables if k != "_avg_opp_phase_improvements")
    for phase in ["Grande", "Chica", "Pares", "Juego"]:
        entry = tables[key][phase]
        total = entry["p_win"] + entry["p_tie"] + entry["p_loss"]
        assert abs(total - 1.0) < 1e-6

def test_four_aces_low_grande_win_prob():
    hand = (Card.A, Card.A, Card.A, Card.A)
    prob = win_prob(hand, "Grande", is_mano=False)
    assert prob < 0.05

def test_four_kings_high_grande_win_prob():
    hand = (Card.R, Card.R, Card.R, Card.R)
    prob = win_prob(hand, "Grande", is_mano=False)
    assert prob > 0.95

def test_four_aces_high_chica_win_prob():
    hand = (Card.A, Card.A, Card.A, Card.A)
    prob = win_prob(hand, "Chica", is_mano=False)
    assert prob > 0.95

def test_mano_adds_tie_probability():
    hand = (Card.R, Card._7, Card._4, Card.A)
    prob_no_mano = win_prob(hand, "Grande", is_mano=False)
    prob_mano = win_prob(hand, "Grande", is_mano=True)
    assert prob_mano >= prob_no_mano

def test_hand_without_pares_has_zero_pares_win_prob():
    hand = (Card.R, Card._7, Card._4, Card.A)
    prob = win_prob(hand, "Pares", is_mano=False)
    assert prob == 0.0

def test_avg_opp_improvement_per_phase_returns_all_phases():
    improvements = avg_opp_improvement_per_phase()
    assert set(improvements.keys()) == {"Grande", "Chica", "Pares", "Juego"}

def test_avg_opp_improvement_non_negative():
    improvements = avg_opp_improvement_per_phase()
    for phase, val in improvements.items():
        assert val >= 0.0, f"{phase} improvement should be non-negative"
