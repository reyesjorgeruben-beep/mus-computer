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
    ):
        self.players = players
        self.phase_name = phase_name
        self.team_scores = team_scores
        self.current_bet = base_bet
        self.previous_bet = 0
        self.team_leading_bet: Optional[Team] = None

    def run(self) -> Tuple[Optional[Team], int]:
        """
        Returns (winner_by_resignation, bet_amount).
        winner_by_resignation is None when the round ends in a showdown.
        """
        last_raiser_idx: Optional[int] = None
        consecutive_passes = 0

        for i in range(40 * len(self.players)):
            idx = i % len(self.players)
            player = self.players[idx]

            # The team that last raised has now seen everyone else call → showdown
            if last_raiser_idx is not None and idx == last_raiser_idx:
                return (None, self.current_bet)

            context = GameContext(
                phase_name=self.phase_name,
                team_scores=self.team_scores,
                current_bet=self.current_bet,
                previous_bet=self.previous_bet,
                hand=list(player.cards),
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
                if consecutive_passes >= len(self.players):
                    return (None, self.current_bet)

        return (None, self.current_bet)
