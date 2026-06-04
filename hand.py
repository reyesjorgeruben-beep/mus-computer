from typing import List
from card import Card
from collections import Counter

class Hand:
    def __init__(self, cards: List[Card]):
        # Store sorted desc so Grande/Peque are always predictable
        self.cards = sorted(cards, reverse=True)

    @property
    def groups(self) -> dict[Card, int]:
        """Returns a dictionary mapping Card to the count of that card."""
        return dict(Counter(self.cards))
    
    @property
    def pares_big_score(self) -> int:
        """
        Returns the quantity of cards involved in pairs/sets:
        Duples (3 cards) = 3
        Medias (2 cards) = 2
        Pares  (1 cards) = 1
        None             = 0
        """

        counts = sorted([count for count in self.groups.values() if count > 1], reverse=True)
        if not counts: return 0
        return sum(counts)-1
    
    @property
    def has_pares(self) -> bool:
        return self.pares_big_score > 0

    @property
    def juego(self) -> int:
        return sum(card.juego_value for card in self.cards)
    
    def get_juego_score(self) -> int:
        """
        Returns the rank of the aggregate juego value with 10
        being the highest (31) and 0 or negative being no juego.
        """
        if self.juego == 31: return 12
        if self.juego == 32: return 11
        return self.juego - 30
    
    @property
    def has_juego(self) -> bool:
        return self.juego > 30
