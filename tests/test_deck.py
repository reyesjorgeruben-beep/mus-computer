import pytest
from collections import Counter
from deck import Deck
from card import Card


class TestDeckInit:
    def test_total_size(self):
        # [A,4,5,6,7,S,C,R]*4 + [A,R]*4 = 32 + 8 = 40
        assert len(Deck().cards) == 40

    def test_ace_count(self):
        assert Counter(Deck().cards)[Card.A] == 8

    def test_king_count(self):
        assert Counter(Deck().cards)[Card.R] == 8

    def test_middle_card_counts(self):
        counts = Counter(Deck().cards)
        for card in [Card._4, Card._5, Card._6, Card._7, Card.S, Card.C]:
            assert counts[card] == 4

    def test_all_cards_are_card_instances(self):
        assert all(isinstance(c, Card) for c in Deck().cards)


class TestDeckDraw:
    def test_draw_reduces_deck_size(self):
        deck = Deck()
        deck.draw(4)
        assert len(deck.cards) == 36

    def test_draw_returns_correct_count(self):
        deck = Deck()
        drawn = deck.draw(7)
        assert len(drawn) == 7

    def test_draw_zero(self):
        deck = Deck()
        assert deck.draw(0) == []
        assert len(deck.cards) == 40

    def test_draw_all(self):
        deck = Deck()
        drawn = deck.draw(40)
        assert len(drawn) == 40
        assert deck.cards == []

    def test_drawn_cards_removed_from_deck(self):
        deck = Deck()
        before = list(deck.cards)
        drawn = deck.draw(4)
        assert drawn == before[:4]
        assert deck.cards == before[4:]

    def test_sequential_draws(self):
        deck = Deck()
        deck.draw(10)
        deck.draw(10)
        assert len(deck.cards) == 20
