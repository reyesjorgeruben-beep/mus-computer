from abc import ABC, abstractmethod
from typing import List
from team import Team
from game_context import GameContext


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

    def set_round_state(
        self,
        team_scores: dict,
        my_team_name: str,
        position: int,
        n_players: int,
        opponent_discard_counts: list,
        mus_rounds_completed: int,
    ) -> None:
        """Called by Game before mus phase and before wagering. No-op by default."""
        pass

    @abstractmethod
    def vote_mus(self) -> bool:
        """Return True to request mus (exchange cards), False to decline."""
        ...

    @abstractmethod
    def choose_discards(self) -> List[int]:
        """Return 0-based indices of cards to discard."""
        ...

    @abstractmethod
    def wager_action(self, context: GameContext) -> int:
        """Return raise amount: >0 raise, 0 call/pass, <0 fold."""
        ...
