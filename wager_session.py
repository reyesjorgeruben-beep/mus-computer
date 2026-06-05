from typing import List, Tuple, Optional, Dict
from player_base import PlayerBase
from team import Team
from game_context import GameContext


class WagerSession:
    def __init__(
        self,
        players: List[PlayerBase],
        base_bet: int,
        phase_name: str,
        team_scores: Dict[str, int],
        discard_counts: Dict[str, int] = None,
    ):
        self.players = players
        self.phase_name = phase_name
        self.team_scores = team_scores
        self.current_bet = base_bet
        self.previous_bet = 0
        self.team_leading_bet: Optional[Team] = None
        self.discard_counts: Dict[str, int] = discard_counts or {}

    def run(self) -> Tuple[Optional[Team], int]:
        last_raiser_idx: Optional[int] = None
        consecutive_passes = 0
        n_players = len(self.players)

        for i in range(40 * n_players):
            idx = i % n_players
            player = self.players[idx]

            if last_raiser_idx is not None and idx == last_raiser_idx:
                return (None, self.current_bet)

            opp_discards = [
                self.discard_counts.get(p.name, 0)
                for p in self.players
                if p.team != player.team
            ]

            context = GameContext(
                phase_name=self.phase_name,
                team_scores=self.team_scores,
                current_bet=self.current_bet,
                previous_bet=self.previous_bet,
                hand=list(player.cards),
                position=idx,
                n_players=n_players,
                opponent_discard_counts=opp_discards,
            )

            action = player.wager_action(context)

            if action < 0:
                opponent_team = next(p.team for p in self.players if p.team != player.team)
                return (opponent_team, self.current_bet)

            if action > 0:
                self.previous_bet = self.current_bet
                self.current_bet += action
                self.team_leading_bet = player.team
                last_raiser_idx = idx
                consecutive_passes = 0
            else:
                consecutive_passes += 1
                if consecutive_passes >= n_players:
                    return (None, self.current_bet)

        return (None, self.current_bet)
