from mus_computer.cards.deck import Deck
from mus_computer.cards.hand import Hand
from mus_computer.game.phases import Phase, PhaseName, Grande, Chica, Pares, Juego, Punto
from mus_computer.game.player_base import PlayerBase
from mus_computer.game.player import HumanPlayer
from mus_computer.game.team import Team
from mus_computer.game.wager_session import WagerSession, WagerOutcome, WagerResult
from mus_computer.game.context import GlobalGameContext, SeatOrderEntry
from mus_computer.bots.strategies.actions import MusAction
from typing import Callable, Sequence

WIN_SCORE = 40
ActionCallback = Callable[[str], None]


class Game:
    """Run a four-seat Mus game and publish each public action.

    ``__init__`` creates human players; ``from_players`` accepts existing
    players. Both paths pass their newly assembled seats to ``_initialize``.
    """

    on_action: ActionCallback | None

    def __init__(self, player_a1: str, player_a2: str, player_b1: str, player_b2: str) -> None:
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
        on_action: ActionCallback | None = None,
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
        self, players: list[PlayerBase], on_action: ActionCallback | None
    ) -> None:
        """Store the seats supplied by either constructor before game setup."""
        self.players_in_order = players
        self.teams = [players[0].team, players[1].team]
        self.on_action = on_action
        self.deck = Deck(on_replenish=self._emit)
        self._discard_counts: dict[str, int] = {}
        self._mus_rounds = 0
        self._public_actions: list[str] = []
        self.winner: Team | None = None
        self.victory_reason: str | None = None

    def _emit(self, message: str) -> None:
        """Record a public action and forward it to the optional observer."""
        if not message.startswith("Hands |"):
            self._public_actions.append(message)
        if self.on_action is not None:
            self.on_action(message)

    def _emit_hands(self) -> None:
        """Show hands to the observer without adding them to public history."""
        if self.on_action is None:
            return
        for player in self.players_in_order:
            ranks = " ".join(card.value for card in player.cards)
            self._emit(f"Hands | {player.name}: {ranks}")

    def play(self) -> Team:
        """Play hands until a team reaches the score or wins an ordago."""
        self.winner = self.winner or next((t for t in self.teams if t.points >= WIN_SCORE), None)
        while self.winner is None:
            self.deck = Deck(on_replenish=self._emit)
            self._discard_counts = {}
            self._mus_rounds = 0
            self._public_actions = []
            self._deal_initial_cards()
            self._mus_phase()
            self._play_all_phases()
            if self.winner is None:
                self.players_in_order = self.players_in_order[1:] + self.players_in_order[:1]
        if self.victory_reason == "ordago":
            self._emit(f"Team {self.winner.name} wins by ordago!")
        else:
            self._emit(f"Team {self.winner.name} wins with {self.winner.points} points!")
        return self.winner

    def _deal_initial_cards(self) -> None:
        """Replace each player's cards with an initial four-card hand."""
        for player in self.players_in_order:
            player.throw_cards()
            player.receive_cards(self.deck.draw(4))
        self._emit_hands()

    def _global_context(
        self,
        phase_name: PhaseName | None = None,
        eligible_players: Sequence[PlayerBase] | None = None,
    ) -> GlobalGameContext:
        """Build the public snapshot visible to all seats at this prompt."""
        eligible = self.players_in_order if eligible_players is None else eligible_players
        return GlobalGameContext(
            {t.name: t.points for t in self.teams}, self._mus_rounds, phase_name, None,
            tuple(self._public_actions), self._discard_counts,
            tuple(SeatOrderEntry(p.name, p.team.name) for p in self.players_in_order), 0,
            tuple(i for i,p in enumerate(self.players_in_order) if p in eligible),
        )

    def _mus_phase(self) -> None:
        """Repeat Mus votes and exchanges until a player cuts Mus."""
        self._discard_counts = {p.name: 0 for p in self.players_in_order}
        self._mus_rounds = 0
        while self._all_vote_mus():
            for seat, player in enumerate(self.players_in_order):
                shared = self._global_context()
                indices = tuple(player.choose_discards(shared, player.decision_context(shared, seat, include_discards=True)))
                if len(set(indices)) != len(indices) or any(
                    type(idx) is not int or idx < 0 or idx >= len(player.cards)
                    for idx in indices
                ):
                    raise ValueError(f"{player.name} chose invalid discard indices.")
                self._discard_counts[player.name] += len(indices)
                discarded = [player.throw_card(idx) for idx in sorted(indices, reverse=True)]
                self.deck.discard(discarded)
                self._emit(f"Mus | {player.name} discards {len(indices)}")
                player.receive_cards(self.deck.draw(len(indices)))
            self._mus_rounds += 1
            self._emit_hands()

    def _all_vote_mus(self) -> bool:
        """Ask seats in order; stop as soon as one player cuts Mus."""
        for seat, player in enumerate(self.players_in_order):
            shared = self._global_context()
            action = player.vote_mus(shared, player.decision_context(shared, seat, include_discards=True))
            if not isinstance(action, MusAction):
                raise ValueError(f"{player.name} chose an invalid Mus action.")
            self._emit(f"Mus | {player.name}: {action.value}")
            if action is MusAction.CORTA:
                return False
        return True

    def _play_all_phases(self) -> None:
        """Declare eligibility, settle wagers, then award showdown points."""
        phases: list[type[Phase]] = [Grande, Chica, Pares, Juego]
        pending_awards: list[tuple[Team, int]] = []
        while phases and self.winner is None:
            phase = phases.pop(0)
            phase_label = "Pequeña" if phase is Chica else phase.__name__
            self._emit(f"{phase_label} begins")
            eligible = self._players_that_can_play(phase)
            if phase in (Pares, Juego):
                no_hand_label = "No pares" if phase is Pares else "No Juego"
                for player in self.players_in_order:
                    declaration = phase.__name__ if player in eligible else no_hand_label
                    self._emit(f"{phase_label} | {player.name}: {declaration}")
            if not eligible:
                self._emit(f"{phase_label} | no players qualify")
                if phase is Juego:
                    phases.insert(0, Punto)
                continue
            result: WagerResult | None = None
            if self._is_contested(eligible):
                result = WagerSession(
                    players=eligible, teams=tuple(self.teams), base_bet=phase.base_bet,
                    public_context=self._global_context(PhaseName(phase.__name__), eligible),
                    on_action=self._emit, phase_label=phase_label,
                    players_in_order=self.players_in_order,
                ).run()
            if result is not None and result.outcome is WagerOutcome.ORDAGO_ACCEPTED:
                self.winner = self._resolve_phase(phase, eligible)
                self.victory_reason = "ordago"
                self._emit(f"{phase_label} | Team {self.winner.name} wins the match by ordago")
                return
            if result is not None and result.outcome is WagerOutcome.DECLINED:
                winner = result.offering_team
                self._emit(f"{phase_label} | Team {winner.name} wins the wager")
                self._award_points(winner, result.accepted_stake)
                if self.winner is not None:
                    return
                if phase in (Pares, Juego):
                    intrinsic = sum(phase.calculate_points(Hand(p.cards)) for p in eligible if p.team is winner)
                    pending_awards.append((winner, intrinsic))
            else:
                winner = self._resolve_phase(phase, eligible)
                stake = result.accepted_stake if result is not None else 0
                intrinsic = sum(phase.calculate_points(Hand(p.cards)) for p in eligible if p.team is winner)
                self._emit(f"{phase_label} | Team {winner.name} wins the phase")
                pending_awards.append((winner, stake + intrinsic))
        for team, points in pending_awards:
            self._award_points(team, points)
            if self.winner is not None:
                return

    def _award_points(self, team: Team, points: int) -> None:
        """Apply an award and end the match if it reaches the target."""
        team.points += points
        self._emit(
            f"Team {team.name} +{points} | "
            f"Score A {self.teams[0].points} - B {self.teams[1].points}"
        )
        if team.points >= WIN_SCORE and self.winner is None:
            self.winner = team
            self.victory_reason = "points"

    def _players_that_can_play(self, phase: type[Phase]) -> list[PlayerBase]:
        """Return seats whose current hand qualifies for this phase."""
        return [p for p in self.players_in_order if phase.can_play(Hand(p.cards))]

    def _is_contested(self, players: Sequence[PlayerBase]) -> bool:
        """A wager needs at least one qualified seat on each team."""
        return len({p.team for p in players}) > 1

    def _resolve_phase(
        self,
        phase: type[Phase],
        eligible_players: list[PlayerBase] | None = None,
    ) -> Team:
        """Resolve tied hands by retaining the first eligible seat."""
        if eligible_players is None:
            eligible_players = self._players_that_can_play(phase)
        if not eligible_players:
            raise ValueError(f"No players qualify for {phase.__name__}.")
        winner = eligible_players[0]
        for player in eligible_players[1:]:
            if phase.play(Hand(player.cards), Hand(winner.cards)) > 0:
                winner = player
        return winner.team
