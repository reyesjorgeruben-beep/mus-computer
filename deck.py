from card import Card
import random
from typing import Callable

class Deck():
    def __init__(self, on_replenish: Callable[[str], None] | None = None):
        self.cards = [Card.A, Card._4, Card._5, Card._6, Card._7, Card.S, Card.C, Card.R] * 4
        self.cards += [Card.A, Card.R] * 4
        random.shuffle(self.cards)
        self.discards: list[Card] = []
        self.on_replenish = on_replenish

    def discard(self, cards: list[Card]) -> None:
        self.discards.extend(cards)
        
    def draw(self, n: int) -> list[Card]:
        if n < 0:
            raise ValueError("Cannot draw a negative number of cards.")
        if len(self.cards) < n:
            self.cards.extend(self.discards)
            self.discards.clear()
            random.shuffle(self.cards)
            if self.on_replenish is not None:
                self.on_replenish("Mus | Stock replenished from discards and shuffled")
        if len(self.cards) < n:
            raise ValueError("Not enough cards remain to complete the draw.")
        drawn_cards = self.cards[:n]
        self.cards = self.cards[n:]
        return drawn_cards
