from typing import List, Tuple, Optional
from player import Player
from team import Team

class WagerSession:
    def __init__(self, players: List[Player], base_bet: int):
        self.players = players
        self.team_leading_bet = None
        self.current_bet = base_bet
        self.previous_bet = 0

    def run(self) -> Tuple[Optional[Team], int]:
        """
        Returns (winner_by_resignation, bet_amount)
        winner: 1 (Team 0), -1 (Team 1), 0 (Showdown needed)
        """
        player_pos = 0
        while not self.is_accepted and not self.is_resigned and player_pos <40:
            player = self.players[player_pos % len(self.players)]
            player_pos += 1
            if player.team == self.team_leading_bet:
                pass
            
            # raise, match or fold
            raise_bet = player.wager_action(self.current_bet, self.previous_bet)
            if raise_bet < 0:
                return (self.team_leading_bet, self.current_bet)
            
            if raise_bet == 0:
                if self.team_leading_bet is None:
                    pass
                
                return (None, self.current_bet)
            
            if raise_bet > 0:
                self.previous_bet = self.current_bet
                self.current_bet += raise_bet
                self.team_leading_bet = player.team
        
        return (self.winner_team_by_resignation, self.current_bet)