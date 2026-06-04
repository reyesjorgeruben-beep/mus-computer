import pytest
from card import Card


class TestCardOrdering:
    def test_ace_is_weakest(self):
        assert Card.A < Card._4

    def test_numerical_order(self):
        assert Card._4 < Card._5 < Card._6 < Card._7

    def test_face_cards_order(self):
        assert Card._7 < Card.S < Card.C < Card.R

    def test_king_beats_all(self):
        for card in [Card.A, Card._4, Card._5, Card._6, Card._7, Card.S, Card.C]:
            assert Card.R > card

    def test_symmetric_lt_gt(self):
        assert Card.A < Card.R
        assert Card.R > Card.A

    def test_le_ge(self):
        assert Card.A <= Card.A
        assert Card.R >= Card.R
        assert Card.A <= Card.R
        assert Card.R >= Card.A

    def test_equality(self):
        assert Card.R == Card.R
        assert Card.A == Card.A
        assert not (Card.A == Card.R)

    def test_not_equal(self):
        assert Card.A != Card.R

    def test_not_lt_self(self):
        assert not (Card.R < Card.R)


class TestCardValues:
    def test_strongness_values(self):
        expected = {
            Card.A: 1, Card._4: 4, Card._5: 5,
            Card._6: 6, Card._7: 7,
            Card.S: 10, Card.C: 11, Card.R: 12,
        }
        for card, val in expected.items():
            assert card.strongness == val

    def test_juego_values(self):
        expected = {
            Card.A: 1, Card._4: 4, Card._5: 5,
            Card._6: 6, Card._7: 7,
            Card.S: 10, Card.C: 10, Card.R: 10,
        }
        for card, val in expected.items():
            assert card.juego_value == val

    def test_face_cards_equal_juego_value(self):
        assert Card.S.juego_value == Card.C.juego_value == Card.R.juego_value == 10


class TestCardHashing:
    def test_hashable(self):
        s = {Card.A, Card.R, Card._5}
        assert len(s) == 3

    def test_duplicate_in_set(self):
        s = {Card.A, Card.A, Card.R}
        assert len(s) == 2

    def test_usable_as_dict_key(self):
        d = {Card.A: 8, Card.R: 8}
        assert d[Card.A] == 8


class TestCardInvalidComparisons:
    def test_lt_non_card_returns_not_implemented(self):
        result = Card.A.__lt__(42)
        assert result is NotImplemented

    def test_eq_non_card_returns_not_implemented(self):
        result = Card.A.__eq__(42)
        assert result is NotImplemented
