import pytest
from card import Card
from hand import Hand
from phases import Grande, Chica, Pares, Juego, Punto


class TestCanPlay:
    def test_grande_always_true(self):
        assert Grande.can_play(Hand([Card.A, Card._4, Card._5, Card._6]))
        assert Grande.can_play(Hand([Card.R, Card.R, Card.R, Card.R]))

    def test_chica_always_true(self):
        assert Chica.can_play(Hand([Card.R, Card.R, Card.R, Card.R]))

    def test_pares_true_with_pair(self):
        assert Pares.can_play(Hand([Card.A, Card.A, Card.R, Card._5]))

    def test_pares_false_without_pairs(self):
        assert not Pares.can_play(Hand([Card.A, Card.R, Card._5, Card._7]))

    def test_pares_true_with_trio(self):
        assert Pares.can_play(Hand([Card.R, Card.R, Card.R, Card._5]))

    def test_juego_true_with_juego(self):
        assert Juego.can_play(Hand([Card.R, Card.R, Card.R, Card.A]))  # 31

    def test_juego_false_without_juego(self):
        assert not Juego.can_play(Hand([Card.A, Card._4, Card._5, Card._6]))

    def test_punto_always_true(self):
        assert Punto.can_play(Hand([Card.A, Card._4, Card._5, Card._6]))


class TestCalculatePoints:
    def test_grande_zero_points(self):
        assert Grande.calculate_points(Hand([Card.R, Card.R, Card.R, Card.C])) == 0

    def test_chica_zero_points(self):
        assert Chica.calculate_points(Hand([Card.A, Card.A, Card.A, Card._4])) == 0

    def test_pares_single_pair(self):
        assert Pares.calculate_points(Hand([Card.A, Card.A, Card.R, Card._5])) == 1

    def test_pares_trio(self):
        assert Pares.calculate_points(Hand([Card.R, Card.R, Card.R, Card._5])) == 2

    def test_pares_two_pairs(self):
        assert Pares.calculate_points(Hand([Card.A, Card.A, Card.R, Card.R])) == 3

    def test_juego_31_gives_3(self):
        assert Juego.calculate_points(Hand([Card.R, Card.R, Card.R, Card.A])) == 3

    def test_juego_32_gives_2(self):
        assert Juego.calculate_points(Hand([Card.R, Card.R, Card._7, Card._5])) == 2

    def test_juego_other_gives_2(self):
        assert Juego.calculate_points(Hand([Card.R, Card.R, Card._7, Card._6])) == 2  # 33

    def test_juego_no_juego_gives_0(self):
        assert Juego.calculate_points(Hand([Card.A, Card._4, Card._5, Card._6])) == 0

    def test_punto_zero_points(self):
        assert Punto.calculate_points(Hand([Card.R, Card.R, Card.R, Card.C])) == 0


class TestBasebet:
    def test_grande_base_bet_one(self):
        assert Grande.base_bet == 1

    def test_chica_base_bet_one(self):
        assert Chica.base_bet == 1

    def test_pares_base_bet_zero(self):
        assert Pares.base_bet == 0

    def test_juego_base_bet_zero(self):
        assert Juego.base_bet == 0


class TestGrandeEdgeCases:
    def test_tie(self):
        h = Hand([Card.R, Card.R, Card._7, Card._7])
        assert Grande.play(h, h) == 0

    def test_tie_by_composition(self):
        h1 = Hand([Card.R, Card.R, Card._7, Card._7])
        h2 = Hand([Card.R, Card.R, Card._7, Card._7])
        assert Grande.play(h1, h2) == 0


class TestChicaEdgeCases:
    def test_tie(self):
        h = Hand([Card.A, Card.A, Card._4, Card._5])
        assert Chica.play(h, h) == 0

    def test_lower_is_better(self):
        h1 = Hand([Card.A, Card.A, Card._4, Card._5])  # low
        h2 = Hand([Card.A, Card.A, Card._4, Card._6])  # slightly higher
        assert Chica.play(h1, h2) == 1


class TestPuntoCases:
    def test_higher_sum_wins(self):
        h1 = Hand([Card.R, Card.R, Card.S, Card._7])  # 10+10+10+7=37
        h2 = Hand([Card.R, Card.R, Card._7, Card._7])  # 10+10+7+7=34
        assert Punto.play(h1, h2) == 1

    def test_lower_sum_loses(self):
        h1 = Hand([Card.A, Card.A, Card.A, Card.A])  # 4
        h2 = Hand([Card.R, Card._7, Card._6, Card._5])  # 28
        assert Punto.play(h1, h2) == -1
