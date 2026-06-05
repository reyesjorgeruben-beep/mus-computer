import pytest
from bot_game_state import ScoreTier, get_score_tier, compute_urgency, compute_position_signal

WIN_SCORE = 40

def test_score_tier_early():
    assert get_score_tier(0, WIN_SCORE) == ScoreTier.EARLY
    assert get_score_tier(9, WIN_SCORE) == ScoreTier.EARLY

def test_score_tier_mid():
    assert get_score_tier(10, WIN_SCORE) == ScoreTier.MID
    assert get_score_tier(23, WIN_SCORE) == ScoreTier.MID

def test_score_tier_late():
    assert get_score_tier(24, WIN_SCORE) == ScoreTier.LATE
    assert get_score_tier(33, WIN_SCORE) == ScoreTier.LATE

def test_score_tier_critical():
    assert get_score_tier(34, WIN_SCORE) == ScoreTier.CRITICAL
    assert get_score_tier(39, WIN_SCORE) == ScoreTier.CRITICAL

def test_urgency_zero_when_equal():
    assert compute_urgency(ScoreTier.MID, ScoreTier.MID) == 0.0

def test_urgency_positive_when_opponent_ahead():
    u = compute_urgency(ScoreTier.EARLY, ScoreTier.CRITICAL)
    assert u > 0.0

def test_urgency_negative_when_we_are_ahead():
    u = compute_urgency(ScoreTier.CRITICAL, ScoreTier.EARLY)
    assert u < 0.0

def test_urgency_range():
    u = compute_urgency(ScoreTier.EARLY, ScoreTier.CRITICAL)
    assert -1.0 <= u <= 1.0

def test_position_signal_mano_preferring_at_mano():
    sig = compute_position_signal(0, 4, 0.0)
    assert sig > 0.0

def test_position_signal_mano_preferring_at_last():
    sig = compute_position_signal(3, 4, 0.0)
    assert sig < 0.0

def test_position_signal_last_preferring_at_last():
    sig = compute_position_signal(3, 4, 1.0)
    assert sig > 0.0

def test_position_signal_last_preferring_at_mano():
    sig = compute_position_signal(0, 4, 1.0)
    assert sig < 0.0

def test_position_signal_neutral_at_midpoint():
    sig_mano = compute_position_signal(0, 4, 0.5)
    sig_last = compute_position_signal(3, 4, 0.5)
    assert abs(sig_mano - sig_last) < 1e-9
