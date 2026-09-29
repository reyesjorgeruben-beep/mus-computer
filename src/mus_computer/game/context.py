"""Immutable public snapshots shared by all seats."""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, NamedTuple

from mus_computer.game.phases import PhaseName


class SeatOrderEntry(NamedTuple):
    """A seat's public player and team labels, with named fields."""

    player_name: str
    team_name: str


@dataclass(frozen=True)
class WagerState:
    current_total: int
    previous_accepted_total: int
    offering_team: str | None
    ordago_offered: bool = False


@dataclass(frozen=True)
class GlobalGameContext:
    """Immutable public snapshot available to every seat.

    ``public_actions`` is the public event history for the current hand. It
    excludes display-only hand events; ``seat_order`` names each seat's player
    and team without exposing cards.
    """

    team_scores: Mapping[str, int]
    mus_exchanges: int
    phase_name: PhaseName | None
    wager: WagerState | None
    public_actions: tuple[str, ...]
    discard_counts: Mapping[str, int]
    seat_order: tuple[SeatOrderEntry, ...]
    mano_seat: int
    eligible_seats: tuple[int, ...]

    def __post_init__(self) -> None:
        if self.phase_name is not None:
            object.__setattr__(self, "phase_name", PhaseName(self.phase_name))
        if any(action.startswith("Hands |") for action in self.public_actions):
            raise ValueError("Hand display events cannot enter public decision history.")
        object.__setattr__(self, "team_scores", MappingProxyType(dict(self.team_scores)))
        object.__setattr__(self, "discard_counts", MappingProxyType(dict(self.discard_counts)))
        object.__setattr__(self, "public_actions", tuple(self.public_actions))
        object.__setattr__(
            self,
            "seat_order",
            tuple(
                seat if isinstance(seat, SeatOrderEntry) else SeatOrderEntry(*seat)
                for seat in self.seat_order
            ),
        )
        object.__setattr__(self, "eligible_seats", tuple(self.eligible_seats))
