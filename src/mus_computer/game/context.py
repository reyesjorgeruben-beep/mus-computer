"""Immutable public snapshots shared by all seats."""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


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
