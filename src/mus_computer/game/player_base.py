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
        """Build private information using only this player's current hand."""
        from mus_computer.bots.strategies.contexts import PlayerDecisionContext
        from mus_computer.cards.hand import Hand
        from mus_computer.game.phases import Grande, Chica, Pares, Juego, Punto
        from mus_computer.probabilities.estimates import estimate_hand_statistics, estimate_discard_options
        is_mano = seat == global_context.mano_seat
        cards = tuple(self.cards)
        return PlayerDecisionContext(
            self.name, self.team.name, seat, cards, global_context.phase_name,
            seat in global_context.eligible_seats,
            {phase.__name__: phase.calculate_points(Hand(list(cards)))
             for phase in (Grande, Chica, Pares, Juego, Punto)},
            estimate_hand_statistics(cards, is_mano),
            estimate_discard_options(cards, is_mano)
            if include_discards and self.needs_discard_statistics else {},
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
