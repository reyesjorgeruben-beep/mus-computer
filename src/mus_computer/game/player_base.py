from abc import ABC, abstractmethod
from mus_computer.game.team import Team


class PlayerBase(ABC):
    def __init__(self, name: str, team: Team):
        self.name = name
        self.team = team
        self.cards: list = []

    def receive_cards(self, cards: list) -> None:
        self.cards.extend(cards)

    def throw_card(self, index: int):
        if 0 <= index < len(self.cards):
            return self.cards.pop(index)
        raise ValueError(f"Player {self.name} has no card at index {index}.")

    def throw_cards(self) -> None:
        self.cards = []

    needs_discard_statistics = False

    def decision_context(self, global_context, seat: int, include_discards=False):
        """Build a frozen private snapshot for this decision from this player's hand.

        A new view keeps cards, phase eligibility, and intrinsic points aligned
        with the current prompt. Reusing a mutable context across prompts could
        leave a strategy holding stale or out-of-scope state; hand estimates are
        cached by card set and mano status.
        """
        from mus_computer.bots.strategies.actions import DiscardAction
        from mus_computer.bots.strategies.contexts import DiscardOption, HandStatistics, PlayerDecisionContext
        from mus_computer.cards.hand import Hand
        from mus_computer.game.phases import Grande, Chica, Pares, Juego, Punto, PhaseName
        from mus_computer.probabilities.estimates import estimate_hand_statistics, estimate_discard_options
        is_mano = seat == global_context.mano_seat
        cards = tuple(self.cards)
        statistics = estimate_hand_statistics(cards, is_mano)
        phase_name = global_context.phase_name
        if phase_name is not None and global_context.eligible_seats:
            # Every phase resolves an equal hand in favor of its first eligible seat.
            has_priority = seat == min(global_context.eligible_seats)
            phase_statistics = estimate_hand_statistics(cards, has_priority)
            expected_points_by_phase = dict(statistics.expected_points_by_phase)
            expected_points_by_phase[phase_name] = phase_statistics.expected_points_by_phase[phase_name]
            statistics = HandStatistics(statistics.outcomes_by_phase, expected_points_by_phase)
        if include_discards and self.needs_discard_statistics:
            discard_options = tuple(
                DiscardOption(DiscardAction(indices), estimated_statistics)
                for indices, estimated_statistics in estimate_discard_options(cards, is_mano).items()
            )
        else:
            discard_options = (DiscardOption(DiscardAction(()), statistics),)
        return PlayerDecisionContext(
            self.name, self.team.name, seat, cards, global_context.phase_name,
            seat in global_context.eligible_seats,
            {PhaseName(phase.__name__): phase.calculate_points(Hand(list(cards)))
             for phase in (Grande, Chica, Pares, Juego, Punto)},
            statistics,
            discard_options,
        )

    @abstractmethod
    def vote_mus(self, global_context, player_context):
        """Return MusAction.MUS or MusAction.CORTA."""
        ...

    @abstractmethod
    def choose_discards(self, global_context, player_context):
        """Return original zero-based card indices to discard."""
        ...

    @abstractmethod
    def wager_action(self, global_context, player_context):
        """Return a legal typed WagerAction."""
        ...
