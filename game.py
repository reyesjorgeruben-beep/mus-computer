from deck import Deck
from hand import Hand
from phases import Phase, Grande, Chica, Pares, Juego, Punto
from player_base import PlayerBase
from player import HumanPlayer
from team import Team
from wager_session import WagerSession

WIN_SCORE = 40


class Game:
    def __init__(self, player_a1: str, player_a2: str, player_b1: str, player_b2: str):
        team_a = Team("A")
        team_b = Team("B")
        self.players_in_order: list[PlayerBase] = [
            HumanPlayer(player_a1, team_a),
            HumanPlayer(player_b1, team_b),
            HumanPlayer(player_a2, team_a),
            HumanPlayer(player_b2, team_b),
        ]
        self.teams = [team_a, team_b]
        self.deck = Deck()

    def play(self):
        while all(t.points < WIN_SCORE for t in self.teams):
            self.deck = Deck()
            self._deal_initial_cards()
            self._mus_phase()
            self._play_all_phases()

        winner = next(t for t in self.teams if t.points >= WIN_SCORE)
        print(f"Team {winner.name} wins with {winner.points} points!")

    def _deal_initial_cards(self):
        for player in self.players_in_order:
            player.throw_cards()
            player.receive_cards(self.deck.draw(4))

    def _mus_phase(self):
        while self._all_vote_mus():
            for player in self.players_in_order:
                indices = player.choose_discards()
                for idx in sorted(indices, reverse=True):
                    player.throw_card(idx)
                player.receive_cards(self.deck.draw(len(indices)))

    def _all_vote_mus(self) -> bool:
        return all(p.vote_mus() for p in self.players_in_order)

    def _play_all_phases(self):
        phases = [Grande, Chica, Pares, Juego]
        while phases:
            phase = phases.pop(0)
            players_in_phase = self._players_that_can_play(phase)

            if not players_in_phase:
                if phase is Juego:
                    phases.insert(0, Punto)
                continue

            winner_team = None
            bet_points = 0

            if self._is_contested(players_in_phase):
                team_scores = {t.name: t.points for t in self.teams}
                winner_team, bet_points = WagerSession(
                    players=players_in_phase,
                    base_bet=phase.base_bet,
                    phase_name=phase.__name__,
                    team_scores=team_scores,
                ).run()

            if winner_team is None:
                winner_team = self._resolve_phase(phase)
                for p in self.players_in_order:
                    if p.team is winner_team:
                        bet_points += phase.calculate_points(Hand(p.cards))

            winner_team.points += bet_points

    def _players_that_can_play(self, phase: type) -> list[PlayerBase]:
        return [p for p in self.players_in_order if phase.can_play(Hand(p.cards))]

    def _is_contested(self, players: list[PlayerBase]) -> bool:
        return len({p.team for p in players}) > 1

    def _resolve_phase(self, phase: type) -> Team:
        p = self.players_in_order

        # Find each team's best hand
        team_a_idx = 0 if phase.play(Hand(p[0].cards), Hand(p[2].cards)) >= 0 else 2
        team_b_idx = 1 if phase.play(Hand(p[1].cards), Hand(p[3].cards)) >= 0 else 3

        champion_a = p[team_a_idx]
        champion_b = p[team_b_idx]

        winner = (
            champion_a
            if phase.play(Hand(champion_a.cards), Hand(champion_b.cards)) >= 0
            else champion_b
        )
        return winner.team
