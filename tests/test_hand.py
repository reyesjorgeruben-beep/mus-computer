import pytest
from card import Card
from hand import Hand


class TestHandSorting:
    def test_cards_sorted_descending(self):
        h = Hand([Card.A, Card.R, Card._5, Card._7])
        assert h.cards == [Card.R, Card._7, Card._5, Card.A]

    def test_already_sorted_unchanged(self):
        h = Hand([Card.R, Card.C, Card.S, Card.A])
        assert h.cards[0] == Card.R
        assert h.cards[-1] == Card.A

    def test_duplicates_preserved(self):
        h = Hand([Card.A, Card.A, Card.R, Card.R])
        assert h.cards.count(Card.A) == 2
        assert h.cards.count(Card.R) == 2


class TestHandGroups:
    def test_all_different_cards(self):
        h = Hand([Card.A, Card.R, Card._5, Card._7])
        assert all(v == 1 for v in h.groups.values())

    def test_one_pair(self):
        h = Hand([Card.A, Card.A, Card.R, Card._5])
        assert h.groups[Card.A] == 2

    def test_trio(self):
        h = Hand([Card.R, Card.R, Card.R, Card._5])
        assert h.groups[Card.R] == 3

    def test_four_of_a_kind(self):
        h = Hand([Card.A, Card.A, Card.A, Card.A])
        assert h.groups[Card.A] == 4

    def test_two_pairs(self):
        h = Hand([Card.A, Card.A, Card.R, Card.R])
        assert h.groups[Card.A] == 2
        assert h.groups[Card.R] == 2


class TestHandPares:
    def test_no_pairs_score_zero(self):
        h = Hand([Card.A, Card.R, Card._5, Card._7])
        assert h.pares_big_score == 0

    def test_has_pares_false_when_no_pairs(self):
        assert not Hand([Card.A, Card.R, Card._5, Card._7]).has_pares

    def test_single_pair_score_one(self):
        assert Hand([Card.A, Card.A, Card.R, Card._5]).pares_big_score == 1

    def test_single_pair_has_pares(self):
        assert Hand([Card.A, Card.A, Card.R, Card._5]).has_pares

    def test_trio_score_two(self):
        assert Hand([Card.R, Card.R, Card.R, Card._5]).pares_big_score == 2

    def test_two_pairs_score_three(self):
        assert Hand([Card.A, Card.A, Card.R, Card.R]).pares_big_score == 3

    def test_four_of_a_kind_score_three(self):
        assert Hand([Card.A, Card.A, Card.A, Card.A]).pares_big_score == 3

    def test_trio_plus_pair_score_four(self):
        # Not possible with 4-card hand but good boundary to confirm formula
        # Actually with 4 cards: trio+pair = 5 cards, impossible. Skip.
        pass


class TestHandJuego:
    def test_juego_sum(self):
        # R(10) + R(10) + R(10) + A(1) = 31
        h = Hand([Card.R, Card.R, Card.R, Card.A])
        assert h.juego == 31

    def test_juego_sum_below_threshold(self):
        h = Hand([Card.A, Card._5, Card._6, Card._7])
        assert h.juego == 19

    def test_has_juego_true(self):
        assert Hand([Card.R, Card.R, Card.R, Card.A]).has_juego  # 31

    def test_has_juego_false(self):
        assert not Hand([Card.A, Card._5, Card._6, Card._7]).has_juego  # 19

    def test_has_juego_boundary_30(self):
        # Exactly 30 is NOT juego (must be > 30)
        h = Hand([Card.R, Card.R, Card._7, Card._3]) if hasattr(Card, '_3') \
            else Hand([Card.S, Card.C, Card._7, Card._6])
        # S(10)+C(10)+_7(7)+_6(6) = 33 — test boundary with exact 31
        h31 = Hand([Card.R, Card.R, Card.R, Card.A])  # 31 → has_juego
        h30 = Hand([Card.R, Card.C, Card._7, Card._6])  # 10+10+7+6 = 33? no
        # Build a 30: R(10)+S(10)+_7(7)+_A(1)... = 28. R(10)+S(10)+_6(6)+_4(4)=30
        h_30 = Hand([Card.R, Card.S, Card._6, Card._4])  # 10+10+6+4=30
        assert not h_30.has_juego
        assert h31.has_juego

    def test_juego_score_31(self):
        h = Hand([Card.R, Card.R, Card.R, Card.A])  # 31
        assert h.get_juego_score() == 12

    def test_juego_score_32(self):
        h = Hand([Card.R, Card.R, Card._7, Card._5])  # 10+10+7+5=32
        assert h.juego == 32
        assert h.get_juego_score() == 11

    def test_juego_score_33(self):
        h = Hand([Card.R, Card.R, Card._7, Card._6])  # 10+10+7+6=33
        assert h.get_juego_score() == 3  # 33-30

    def test_juego_score_40(self):
        h = Hand([Card.S, Card.C, Card.R, Card.R])  # 10+10+10+10=40
        assert h.get_juego_score() == 10  # 40-30

    def test_juego_score_no_juego(self):
        h = Hand([Card.A, Card._4, Card._5, Card._6])  # 1+4+5+6=16
        assert h.get_juego_score() <= 0

    def test_juego_calculate_points_31(self):
        from phases import Juego
        h = Hand([Card.R, Card.R, Card.R, Card.A])
        assert Juego.calculate_points(h) == 3

    def test_juego_calculate_points_other(self):
        from phases import Juego
        h = Hand([Card.R, Card.R, Card._7, Card._5])  # 32
        assert Juego.calculate_points(h) == 2

    def test_juego_calculate_points_no_juego(self):
        from phases import Juego
        h = Hand([Card.A, Card._4, Card._5, Card._6])
        assert Juego.calculate_points(h) == 0
