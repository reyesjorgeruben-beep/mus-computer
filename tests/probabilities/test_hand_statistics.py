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
    assert mano.phase_outcomes["Punto"] == later.phase_outcomes["Punto"]
    assert mano.expected_points["Punto"] - later.expected_points["Punto"] == pytest.approx(
        mano.phase_outcomes["Punto"].p_tie
    )


def test_hand_statistics_uses_bundled_phase_lookup_and_intrinsic_points():
    cards = (Card.R, Card.R, Card.A, Card.A)
    stats = estimate_hand_statistics(cards)
    assert set(stats.phase_outcomes) == {"Grande", "Chica", "Pares", "Juego", "Punto"}
    assert stats.phase_outcomes["Grande"].p_win == lookup(cards, "Grande")["p_win"]
    assert stats.expected_points["Pares"] == pytest.approx(
        stats.phase_outcomes["Pares"].p_win * 3
    )


def test_discard_options_use_original_indices_for_duplicate_ranks():
    cards = (Card.R, Card.R, Card.A, Card.A)
    options = estimate_discard_options(cards)
    assert len(options) == 16
    assert () in options and (0,) in options and (1,) in options and (0, 1, 2, 3) in options
    assert options[(0,)].phase_outcomes["Grande"] == options[(1,)].phase_outcomes["Grande"]
    assert options[()].phase_outcomes["Punto"] == estimate_punto(cards)
    with pytest.raises(TypeError):
        options[(0,)] = options[()]
