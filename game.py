from deck import Deck
from hand import Hand
from phases import Phase, Grande, Chica, Pares, Juego, Punto
from player_base import PlayerBase
from player import HumanPlayer
from team import Team
from wager_session import WagerSession
from typing import Callable

WIN_SCORE = 40


class Game:
    def __init__(self, player_a1: str, player_a2: str, player_b1: str, player_b2: str):
        team_a = Team("A")
        team_b = Team("B")
        players = [
            HumanPlayer(player_a1, team_a),
            HumanPlayer(player_b1, team_b),
            HumanPlayer(player_a2, team_a),
            HumanPlayer(player_b2, team_b),
        ]
        self._initialize(players, None)

    @classmethod
    def from_players(
        cls,
        players_in_order: list[PlayerBase],
        on_action: Callable[[str], None] | None = None,
    ) -> "Game":
        players = list(players_in_order)
        if len(players) != 4 or any(not isinstance(p, PlayerBase) for p in players):
            raise ValueError("A game requires exactly four PlayerBase players.")
        if (
            players[0].team is not players[2].team
            or players[1].team is not players[3].team
            or players[0].team is players[1].team
            or players[0].team.name != "A"
            or players[1].team.name != "B"
        ):
            raise ValueError("Players must occupy alternating A/B/A/B team seats.")
        game = cls.__new__(cls)
        game._initialize(players, on_action)
        return game

    def _initialize(
        self, players: list[PlayerBase], on_action: Callable[[str], None] | None
    ) -> None:
        self.players_in_order = players
        self.teams = [players[0].team, players[1].team]
        self.on_action = on_action
        self.deck = Deck(on_replenish=self._emit)
        self._discard_counts = {}
        self._mus_rounds = 0

    def _emit(self, message: str) -> None:
        if self.on_action is not None:
            self.on_action(message)

    def _emit_hands(self) -> None:
        if self.on_action is None:
            return
        for player in self.players_in_order:
            ranks = " ".join(card.value for card in player.cards)
            self._emit(f"Hands | {player.name}: {ranks}")

    def play(self):
        while all(t.points < WIN_SCORE for t in self.teams):
            self.deck = Deck(on_replenish=self._emit)
            self._discard_counts = {}
            self._mus_rounds = 0
            self._deal_initial_cards()
            self._mus_phase()
            self._play_all_phases()

        winner = next(t for t in self.teams if t.points >= WIN_SCORE)
        self._emit(f"Team {winner.name} wins with {winner.points} points!")
        return winner

    def _deal_initial_cards(self):
        for player in self.players_in_order:
            player.throw_cards()
            player.receive_cards(self.deck.draw(4))
        self._emit_hands()

    def _mus_phase(self):
        discard_counts = {p.name: 0 for p in self.players_in_order}
        mus_rounds = 0
        self._notify_players_round_state(discard_counts, mus_rounds)

        while self._all_vote_mus():
            mus_rounds += 1
            for player in self.players_in_order:
                indices = player.choose_discards()
                if len(set(indices)) != len(indices) or any(
                    not isinstance(idx, int) or idx < 0 or idx >= len(player.cards)
                    for idx in indices
                ):
                    raise ValueError(f"{player.name} chose invalid discard indices.")
                discard_counts[player.name] += len(indices)
                discarded = []
                for idx in sorted(indices, reverse=True):
                    discarded.append(player.throw_card(idx))
                self.deck.discard(discarded)
                self._emit(f"Mus | {player.name} discards {len(indices)}")
                player.receive_cards(self.deck.draw(len(indices)))
            self._emit_hands()
            self._notify_players_round_state(discard_counts, mus_rounds)

        self._discard_counts = discard_counts
        self._mus_rounds = mus_rounds

    def _notify_players_round_state(self, discard_counts: dict, mus_rounds: int):
        team_scores = {t.name: t.points for t in self.teams}
        for i, player in enumerate(self.players_in_order):
            opp_discards = [
                discard_counts.get(p.name, 0)
                for p in self.players_in_order
                if p.team != player.team
            ]
            player.set_round_state(
                team_scores=team_scores,
                my_team_name=player.team.name,
                position=i,
                n_players=len(self.players_in_order),
                opponent_discard_counts=opp_discards,
                mus_rounds_completed=mus_rounds,
            )

    def _all_vote_mus(self) -> bool:
        for player in self.players_in_order:
            wants_mus = player.vote_mus()
            self._emit(f"Mus | {player.name}: {'mus' if wants_mus else 'corta'}")
            if not wants_mus:
                return False
        return True

    def _play_all_phases(self):
        self._notify_players_round_state(self._discard_counts, self._mus_rounds)
        phases = [Grande, Chica, Pares, Juego]
        pending_awards: list[tuple[Team, int]] = []
        while phases:
            phase = phases.pop(0)
            phase_label = "Pequeña" if phase is Chica else phase.__name__
            self._emit(f"{phase_label} begins")
            players_in_phase = self._players_that_can_play(phase)

            if not players_in_phase:
                self._emit(f"{phase_label} | no players qualify")
                if phase is Juego:
                    phases.insert(0, Punto)
                continue

            winner_team = None
            bet_points = 0

            if self._is_contested(players_in_phase):
                team_scores = {t.name: t.points for t in self.teams}
                winner_team, bet_points = WagerSession(
                    players=players_in_phase,
                    teams=(self.teams[0], self.teams[1]),
                    base_bet=phase.base_bet,
                    phase_name=phase.__name__,
                    team_scores=team_scores,
                    discard_counts=self._discard_counts,
                    on_action=self.on_action,
                    phase_label=phase_label,
                ).run()

            if winner_team is None:
                winner_team = self._resolve_phase(phase, players_in_phase)
                for p in self.players_in_order:
                    if p.team is winner_team:
                        bet_points += phase.calculate_points(Hand(p.cards))
                self._emit(f"{phase_label} | Team {winner_team.name} wins the phase")
                pending_awards.append((winner_team, bet_points))
            else:
                self._emit(f"{phase_label} | Team {winner_team.name} wins the wager")
                self._award_points(winner_team, bet_points)

        for team, points in pending_awards:
            self._award_points(team, points)

    def _award_points(self, team: Team, points: int) -> None:
        team.points += points
        self._emit(
            f"Team {team.name} +{points} | "
            f"Score A {self.teams[0].points} - B {self.teams[1].points}"
        )

    def _players_that_can_play(self, phase: type) -> list[PlayerBase]:
        return [p for p in self.players_in_order if phase.can_play(Hand(p.cards))]

    def _is_contested(self, players: list[PlayerBase]) -> bool:
        return len({p.team for p in players}) > 1

    def _resolve_phase(
        self,
        phase: type,
        eligible_players: list[PlayerBase] | None = None,
    ) -> Team:
        if eligible_players is None:
            eligible_players = self._players_that_can_play(phase)
        if not eligible_players:
            raise ValueError(f"No players qualify for {phase.__name__}.")
        winner = eligible_players[0]
        for player in eligible_players[1:]:
            if phase.play(Hand(player.cards), Hand(winner.cards)) > 0:
                winner = player
        return winner.team
