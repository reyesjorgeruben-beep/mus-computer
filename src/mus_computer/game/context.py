"""Public game state and the temporary private prompt for legacy wager players."""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from mus_computer.cards.card import Card


@dataclass(frozen=True)
class WagerState:
    current_total: int
    previous_accepted_total: int
    offering_team: str | None
    ordago_offered: bool = False


@dataclass(frozen=True)
class GlobalGameContext:
    """A snapshot every seat may read, with no private hand information."""

    team_scores: Mapping[str, int]
    mus_exchanges: int
    phase_name: str | None
    wager: WagerState | None
    public_actions: tuple[str, ...]
    discard_counts: Mapping[str, int]
    seat_order: tuple[tuple[str, str], ...]
    mano_seat: int
    eligible_seats: tuple[int, ...]

    def __post_init__(self) -> None:
        if any(action.startswith("Hands |") for action in self.public_actions):
            raise ValueError("Hand display events cannot enter public decision history.")
        object.__setattr__(self, "team_scores", MappingProxyType(dict(self.team_scores)))
        object.__setattr__(self, "discard_counts", MappingProxyType(dict(self.discard_counts)))
        object.__setattr__(self, "public_actions", tuple(self.public_actions))
        object.__setattr__(self, "seat_order", tuple(tuple(seat) for seat in self.seat_order))
        object.__setattr__(self, "eligible_seats", tuple(self.eligible_seats))


@dataclass(frozen=True)
class WagerPrompt:
    """Per-player adapter until wager callers use both decision contexts directly."""

    global_context: GlobalGameContext
    cards: tuple[Card, ...]
    seat: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "cards", tuple(self.cards))

    @property
    def phase_name(self) -> str | None:
        return self.global_context.phase_name

    @property
    def team_scores(self) -> Mapping[str, int]:
        return self.global_context.team_scores

    @property
    def current_bet(self) -> int:
        return self.global_context.wager.current_total

    @property
    def previous_bet(self) -> int:
        return self.global_context.wager.previous_accepted_total

    @property
    def hand(self) -> tuple[Card, ...]:
        return self.cards

    @property
    def position(self) -> int:
        return self.seat

    @property
    def n_players(self) -> int:
        return len(self.global_context.eligible_seats)

    @property
    def opponent_discard_counts(self) -> tuple[int, ...]:
        own_team = self.global_context.seat_order[self.seat][1]
        return tuple(
            self.global_context.discard_counts.get(name, 0)
            for name, team in self.global_context.seat_order
            if team != own_team
        )
