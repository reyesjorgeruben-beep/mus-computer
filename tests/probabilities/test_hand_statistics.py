from collections import Counter
from itertools import combinations

import pytest

from mus_computer.cards.card import Card
from mus_computer.cards.hand import Hand
from mus_computer.constants import cards_space
from mus_computer.game.phases import Punto
from mus_computer.probabilities.estimates import (
    estimate_discard_options, estimate_hand_statistics, estimate_punto,
)
from mus_computer.probabilities.tables import lookup
from mus_computer.probabilities.tables import load_tables, canonical


def physical_punto_outcomes(cards):
    """Independent reference using all physical four-card opponent draws."""
    remaining = Counter(cards_space)
    remaining.subtract(cards)
    deck = [rank for rank, count in remaining.items() for _ in range(count)]
    counts = Counter(Punto.play(Hand(list(cards)), Hand(list(opp))) for opp in combinations(deck, 4))
    total = sum(counts.values())
    return counts[1] / total, counts[0] / total, counts[-1] / total


@pytest.mark.parametrize("cards", [
    (Card.R, Card.R, Card.R, Card.R),
    (Card.A, Card.A, Card.A, Card.A),
    (Card.A, Card._4, Card._5, Card.R),
])
def test_punto_matches_physical_draws_and_preserves_ties(cards):
    expected = physical_punto_outcomes(cards)
    actual = estimate_punto(cards)
    assert (actual.p_win, actual.p_tie, actual.p_loss) == pytest.approx(expected)
    assert actual.p_tie > 0


def test_mano_changes_expected_punto_points_but_not_tie_probability():
    cards = (Card.A, Card._4, Card._5, Card.R)
    later = estimate_hand_statistics(cards, is_mano=False)
    mano = estimate_hand_statistics(cards, is_mano=True)
    assert mano.outcomes_by_phase["Punto"] == later.outcomes_by_phase["Punto"]
    assert mano.expected_points_by_phase["Punto"] - later.expected_points_by_phase["Punto"] == pytest.approx(
        mano.outcomes_by_phase["Punto"].p_tie
    )


def test_hand_statistics_uses_bundled_phase_lookup_and_intrinsic_points():
    cards = (Card.R, Card.R, Card.A, Card.A)
    stats = estimate_hand_statistics(cards)
    assert set(stats.outcomes_by_phase) == {"Grande", "Chica", "Pares", "Juego", "Punto"}
    assert stats.outcomes_by_phase["Grande"].p_win == lookup(cards, "Grande")["p_win"]
    assert stats.expected_points_by_phase["Pares"] == pytest.approx(
        stats.outcomes_by_phase["Pares"].p_win * 3
    )


def test_discard_options_use_original_indices_for_duplicate_ranks():
    cards = (Card.R, Card.R, Card.A, Card.A)
    options = estimate_discard_options(cards)
    assert len(options) == 16
    assert () in options and (0,) in options and (1,) in options and (0, 1, 2, 3) in options
    assert options[(0,)].outcomes_by_phase["Grande"] == options[(1,)].outcomes_by_phase["Grande"]
    assert options[()].outcomes_by_phase["Punto"] == estimate_punto(cards)
    with pytest.raises(TypeError):
        options[(0,)] = options[()]


def test_bundled_decision_estimates_cover_all_phases_and_discards():
    cards = (Card.R, Card.R, Card.A, Card.A)
    table = load_tables()[canonical(cards)]
    assert "Punto" in table
    assert "decision_discard_options" in table
    assert set(table["decision_discard_options"][()]) == {"Grande", "Chica", "Pares", "Juego", "Punto"}
    assert estimate_punto(cards).p_tie > 0
    assert len(estimate_discard_options(cards)) == 16


def test_decision_estimates_reject_wrong_hand_size():
    five_cards = (Card.A,) * 5
    with pytest.raises(ValueError, match="four cards"):
        estimate_punto(five_cards)
    with pytest.raises(ValueError, match="four cards"):
        estimate_discard_options(five_cards)
