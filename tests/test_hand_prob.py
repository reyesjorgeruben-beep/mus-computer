import pytest
import math
from utils import hand_prob
from card import Card
from hand import Hand

def test_four_fours_probability():
    """Target: All four '4's (Must be a Hand object now)"""
    target = Hand([Card._4, Card._4, Card._4, Card._4])
    
    # 40 cards in deck, choosing 4. Only 1 combination is 4-4-4-4.
    expected_prob = 1 / math.comb(40, 4)
    
    result = hand_prob(target, [], [])
    
    assert result == pytest.approx(expected_prob)
    
def test_three_blocked_gain_one_more():
    """
    Scenario: Target is four '5's. We already have three '5's (blocked).
    Remaining: 1 more '5' needed from 37 cards.
    """
    target = Hand([Card._5, Card._5, Card._5, Card._5])
    blocked = [Card._5, Card._5, Card._5]
    burnt = []
    
    # 1 available '5' left / 37 available cards left
    expected = 1 / 37
    assert hand_prob(target, blocked, burnt) == pytest.approx(expected)

def test_four_fours_with_one_burnt():
    """If a card you need is burnt, probability is 0"""
    target = Hand([Card._4, Card._4, Card._4, Card._4])
    burnt = [Card._4]
    
    result = hand_prob(target, [], burnt)
    
    assert result == 0.0
    
def test_blocked_not_subset_of_target():
    """You hold an Ace but you're trying to calculate the prob of a pure 5-5-5-5 hand"""
    target = Hand([Card._5, Card._5, Card._5, Card._5])
    blocked = [Card.A]
    burnt = []
    
    assert hand_prob(target, blocked, burnt) == 0.0

def test_mixed_hand_probability():
    """
    Scenario: Probability of getting 2 Kings (R) and 2 Aces (A) from a fresh deck.
    Kings available: 8, Aces available: 8. Total cards: 40.
    """
    target = Hand([Card.R, Card.R, Card.A, Card.A])
    
    # math: (comb(8, 2) * comb(8, 2)) / comb(40, 4)
    numerator = math.comb(8, 2) * math.comb(8, 2)
    denominator = math.comb(40, 4)
    expected = numerator / denominator
    
    result = hand_prob(target, [], [])
    
    assert result == pytest.approx(expected)
    
def test_already_have_hand():
    """Target is two Kings, and we already hold two Kings."""
    target = Hand([Card.R, Card.R])
    blocked = [Card.R, Card.R]
    
    # Probability of drawing 0 more cards is 100%
    assert hand_prob(target, blocked, []) == 1.0