from dataclasses import dataclass, field
from enum import Enum
from typing import List


class ScoreTier(Enum):
    EARLY    = 0   # < 25% of win score
    MID      = 1   # 25-60%
    LATE     = 2   # 60-85%
    CRITICAL = 3   # >= 85%


def get_score_tier(score: int, win_score: int) -> ScoreTier:
    ratio = score / win_score
    if ratio < 0.25:
        return ScoreTier.EARLY
    if ratio < 0.60:
        return ScoreTier.MID
    if ratio < 0.85:
        return ScoreTier.LATE
    return ScoreTier.CRITICAL


def compute_urgency(my_tier: ScoreTier, opp_tier: ScoreTier) -> float:
    """Returns [-1, 1]. Positive = opponent ahead (need aggression). Negative = we're ahead."""
    return (opp_tier.value - my_tier.value) / 3.0


def compute_position_signal(position: int, n_players: int, position_preference: float) -> float:
    """Returns [-1, 1]. position_preference=0: positive at mano. position_preference=1: positive at last."""
    if n_players <= 1:
        return 0.0
    normalized_pos = position / (n_players - 1)
    preferred_pos = position_preference
    return 1.0 - 2.0 * abs(normalized_pos - preferred_pos)


@dataclass
class BotGameState:
    my_score_tier: ScoreTier
    opponent_score_tier: ScoreTier
    position: int
    n_players: int
    opponent_discard_counts: List[int] = field(default_factory=list)
    mus_rounds_completed: int = 0
