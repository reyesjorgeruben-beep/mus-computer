from card import Card
import random

class Deck():
    def __init__(self):
        self.cards = [Card.A, Card._4, Card._5, Card._6, Card._7, Card.S, Card.C, Card.R] * 4
        self.cards += [Card.A, Card.R] * 4
        random.shuffle(self.cards)
        
    def draw(self, n: int) -> list[Card]:
        drawn_cards = self.cards[:n]
        self.cards = self.cards[n:]
        return drawn_cards