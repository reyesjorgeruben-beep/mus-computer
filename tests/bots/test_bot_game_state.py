from mus_computer.bots.bot_game_state import ScoreTier, get_score_tier

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
