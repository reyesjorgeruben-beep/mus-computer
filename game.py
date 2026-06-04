
from deck import Deck
from phases import Phase, Grande, Chica, Pares, Juego, Punto
from player import Player
from team import Team
from wager_session import WagerSession

class Game:
    def __init__(self, player_a1: str, player_a2: str, player_b1: str, player_b2: str):
        
        self.players_in_order = [
            Player(player_a1, Team("A")),
            Player(player_b1, Team("B")),
            Player(player_a2, Team("A")),
            Player(player_b2, Team("B"))]
        self.phases: list[Phase] = [Grande, Chica, Pares, Juego]
        self.deck = Deck()
        
        self.deal_initial_cards()
        self.play_round()
        
    def deal_initial_cards(self):
        for player in self.players_in_order:
            player.throw_cards()
            player.receive_cards(self.deck.draw(4))
            
    def deal_cards_for_mus(self):
        for player in self.players_in_order:
            thrown_cards = player.mus_action()
            player.receive_cards(self.deck.draw(thrown_cards))
        
    def play_phase(self):
        phase = self.phases.pop(0)
        players_in_phase = self.players_that_can_play_phase(phase)
        winner_team = None
        points = 0
        
        if len(players_in_phase) == 0:
            if phase.isinstance(Juego):
                self.phases.append(Punto)
            return
        
        if self.is_phase_contested(players_in_phase):
            winner_team, points = WagerSession(
                players_in_phase, 
                base_bet=phase.base_bet
            ).run()
            
        if winner_team is None:
            winner_team = self.resolve_phase(phase)
        
        for p in self.players_in_order:
            if p.team == winner_team:
                points += phase.calculate_points(p.hand)
        
        winner_team.points += points

        
    def play_round(self):
        while len(self.phases) > 0:
            self.play_phase()

        
    def players_that_can_play_phase(self,phase:Phase) -> list[Player]:
        return [p for p in self.players_in_order if phase.can_play(p.hand)]
    
    def is_phase_contested(self, players:list[Player]) -> bool:
        teams_playing = set(p.team for p in players)
        return True if len(teams_playing) > 1 else False
        
    def resolve_phase(self, phase: Phase) -> Team:
        team_0_champion = (
            0 if phase(self.players_in_order[0].cards, self.players_in_order[2].cards) >= 0 else 2
        )
        
        team_1_champion = (
            1 if phase(self.players_in_order[1].cards, self.players_in_order[3].cards) >= 0 else 3
        )
        
        first_player_pos = min(team_0_champion, team_1_champion)
        second_player_pos = max(team_0_champion, team_1_champion)
        
        first_player = self.players_in_order[first_player_pos]
        second_player = self.players_in_order[second_player_pos]
        
        round_winner = (
            first_player if phase.play(first_player.cards, second_player.cards) >= 0 else second_player
        )
        
        return round_winner.team