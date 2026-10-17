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


@dataclass
class BotGameState:
    my_score_tier: ScoreTier
    opponent_score_tier: ScoreTier
    position: int
    n_players: int
    opponent_discard_counts: List[int] = field(default_factory=list)
    mus_rounds_completed: int = 0
