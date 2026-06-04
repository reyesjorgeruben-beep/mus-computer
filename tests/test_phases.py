import pytest
from card import Card
from hand import Hand
from phases import (
    Grande,
    Chica,
    Pares,
    Juego,
    Punto
)

class TestPhases:
    
    # --- GRANDE TESTS ---
    def test_play_grande(self):
        h_1 = Hand([Card.R, Card._7, Card._7, Card.R])
        h_2 = Hand([Card.R, Card.S, Card._7, Card._4])
        h_3 = Hand([Card.R, Card.R, Card._7, Card._7])
        
        assert Grande.play(h_1, h_2) == 1
        assert Grande.play(h_2, h_1) == -1
        assert Grande.play(h_1, h_3) == 0
        
    # --- PEQUE TESTS ---
    def test_play_peque(self):
        h_1 = Hand([Card.A, Card._4, Card._5, Card.A])
        h_2 = Hand([Card.A, Card.A, Card._4, Card._6])
        h_3 = Hand([Card.A, Card.A, Card._4, Card._5])
        
        assert Chica.play(h_1, h_2) == 1
        assert Chica.play(h_2, h_1) == -1
        assert Chica.play(h_1, h_3) == 0
        
    # --- PARES TESTS ---
    def test_play_pares_different_scores(self):
        # Duples (score 3) vs Medias (score 2)
        h_duples_1 = Hand([Card.R, Card.A, Card.A, Card.R])
        h_duples_2 = Hand([Card._5, Card._5, Card._6, Card._6])
        h_medias = Hand([Card.R, Card.R, Card.R, Card._4])
        h_par_1 = Hand([Card.C, Card.C, Card.R, Card._5])
        h_par_2 = Hand([Card.C, Card.C, Card._4, Card._5])
        h_no_pares = Hand([Card.R, Card.S, Card._5, Card._4])
        
        assert Pares.play(h_duples_1, h_no_pares) == 1
        assert Pares.play(h_medias, h_duples_2) == -1
        assert Pares.play(h_duples_1, h_duples_2) == 1
        assert Pares.play(h_par_1, h_par_2) == 0
        assert Pares.play(h_par_1, h_no_pares) == 1
        assert Pares.play(h_par_1, h_medias) == -1
        

    # --- JUEGO TESTS ---
    def test_play_juego_hierarchy(self):
        h_kings_31 = Hand([Card.R, Card.R, Card.R, Card.A])
        h_sevens_31 = Hand([Card._7, Card._7, Card._7, Card.R])
        h_32 = Hand([Card._6, Card._6, Card.R, Card.R])
        h_40 = Hand([Card.C, Card.S, Card.R, Card.R])
        h_33 = Hand([Card._7, Card._6, Card.C, Card.R])
        h_no_juego = Hand([Card._7, Card._6, Card.C, Card._5])
        
        
        assert Juego.play(h_kings_31, h_sevens_31) == 0
        assert Juego.play(h_32, h_sevens_31) == -1
        assert Juego.play(h_kings_31, h_40) == 1
        assert Juego.play(h_kings_31, h_32) == 1
        assert Juego.play(h_33, h_no_juego) == 1

    # --- PUNTO TESTS ---
    def test_play_punto(self):
        h_30 = Hand([Card.R, Card.R, Card.S])
        h_28_1 = Hand([Card.R, Card.R, Card._7, Card.A])
        h_28_2 = Hand([Card.R, Card._7, Card._7, Card._4])
        h_4 = Hand([Card.A, Card.A, Card.A, Card.A])
        
        assert Punto.play(h_30, h_28_1) == 1
        assert Punto.play(h_4, h_28_2) == -1
        assert Punto.play(h_28_1, h_28_2) == 0