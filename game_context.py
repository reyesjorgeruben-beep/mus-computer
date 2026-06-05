from dataclasses import dataclass, field
from typing import List, Dict
from card import Card


@dataclass
class GameContext:
    phase_name: str
    team_scores: Dict[str, int]
    current_bet: int
    previous_bet: int
    hand: List[Card]
    position: int = 0
    n_players: int = 1
    opponent_discard_counts: List[int] = field(default_factory=list)
