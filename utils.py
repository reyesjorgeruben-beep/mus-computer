import math
from constants import cards_space
from card import Card
from hand import Hand

def hand_prob(
    target_hand: Hand, 
    blocked_cards: list[Card], 
    burnt_cards: list[Card]
) -> float:
    
    remaining_target = target_hand.groups.copy()
    available_cards = cards_space.copy()
    
    # 1. Process Blocked Cards
    for card in blocked_cards:
        if remaining_target.get(card, 0) > 0:
            remaining_target[card] -= 1
            available_cards[card] -= 1
        else:
            return 0.0
    
    # 2. Process Burnt Cards
    for card in burnt_cards:
        available_cards[card] -= 1
        if available_cards[card] < 0:
            return 0.0

    # 3. Calculate Combinations
    numerator = math.prod(
        math.comb(available_cards[card], req)
        for card, req in remaining_target.items()
    )
    
    total_needed = sum(remaining_target.values())
    total_available = sum(available_cards.values())
    
    denominator = math.comb(total_available, total_needed)
    
    return numerator / denominator if denominator > 0 else 0.0