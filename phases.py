from hand import Hand
from abc import ABC, abstractmethod

class Phase(ABC): 
    base_bet: int = 1
    
    @staticmethod
    @abstractmethod
    def play(hand1: Hand, hand2: Hand) -> int:
        raise NotImplementedError("Must implement play method in subclass")
    
    @staticmethod
    @abstractmethod
    def can_play(hand: Hand) -> bool:
        # Default is True
        return True
    
    @staticmethod
    @abstractmethod
    def calculate_points(hand: Hand) -> int:
        return 0
      
    
class Grande(Phase):
    @staticmethod 
    def play(h1: Hand, h2: Hand) -> int:
        h1_big = sorted(h1.cards, reverse=True)
        h2_big = sorted(h2.cards, reverse=True)
        for m, o in zip(h1_big, h2_big):
            if m > o: return 1
            if m < o: return -1
        return 0
    
    @staticmethod
    def can_play(hand: Hand) -> bool:
        return True
    
    @staticmethod
    def calculate_points(hand: Hand) -> int:
        return 0

class Chica(Phase):
    @staticmethod
    def play(h1: Hand, h2: Hand) -> int:
        h1_low = sorted(h1.cards)
        h2_low = sorted(h2.cards)
        for m, o in zip(h1_low, h2_low):
            if m < o: return 1
            if m > o: return -1
        return 0
    
    @staticmethod
    def can_play(hand: Hand) -> bool:
        return True
    
    @staticmethod
    def calculate_points(hand: Hand) -> int:
        return 0

class Pares(Phase):
    base_bet = 0
    
    @staticmethod
    def play(hand1: Hand, hand2: Hand) -> int:
        score1 = hand1.pares_big_score
        score2 = hand2.pares_big_score
        
        if score1 > score2: return 1
        if score1 < score2: return -1
        
        pairs_cards_1 = [c for c in hand1.cards if hand1.groups[c] > 1]
        pairs_cards_2 = [c for c in hand2.cards if hand2.groups[c] > 1]
        
        return Grande.play(Hand(pairs_cards_1), Hand(pairs_cards_2))
    
    @staticmethod
    def can_play(hand: Hand) -> bool:
        return hand.has_pares
    
    @staticmethod
    def calculate_points(hand: Hand) -> int:
        return hand.pares_big_score

class Juego(Phase):
    base_bet = 0
    
    @staticmethod
    def play(h1: Hand, h2: Hand) -> int:
        r1 = h1.get_juego_score()
        r2 = h2.get_juego_score()

        if r1 > r2: return 1
        if r1 < r2: return -1
        return 0
    
    @staticmethod
    def can_play(hand: Hand) -> bool:
        return hand.has_juego
    
    @staticmethod
    def calculate_points(hand: Hand) -> int:
        if not hand.has_juego: return 0
        return 3 if hand.juego == 31 else 2

class Punto(Phase):
    @staticmethod
    def play(h1: Hand, h2: Hand) -> int:
        if h1.juego > h2.juego: return 1
        if h1.juego < h2.juego: return -1
        return 0
    
    @staticmethod
    def can_play(hand: Hand) -> bool:
        return True
    
    @staticmethod
    def calculate_points(hand: Hand) -> int:
        return 0