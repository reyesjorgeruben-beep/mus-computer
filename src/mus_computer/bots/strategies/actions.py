"""Typed bot decisions and validated action probabilities."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import TYPE_CHECKING, Collection, Generic, Hashable, Mapping, TypeVar

if TYPE_CHECKING:
    from mus_computer.game.context import WagerState


class DecisionKind(str, Enum):
    MUS = "mus"
    DISCARD = "discard"
    WAGER = "wager"


class MusAction(str, Enum):
    MUS = "mus"
    CORTA = "corta"


class WagerAction(str, Enum):
    ORDAGO = "ordago"
    RAISE_5 = "raise_5"
    RAISE_4 = "raise_4"
    RAISE_3 = "raise_3"
    RAISE_2 = "raise_2"
    MATCH_OR_PASS = "match_or_pass"
    FOLD = "fold"


@dataclass(frozen=True)
class DiscardAction:
    """Original positions of cards to discard; empty means keep every card."""

    indices: tuple[int, ...]

    def __post_init__(self) -> None:
        indices = tuple(self.indices)
        if any(type(index) is not int or index < 0 for index in indices):
            raise ValueError("Discard indices must be nonnegative integers.")
        if len(set(indices)) != len(indices):
            raise ValueError("Discard indices cannot contain duplicates.")
        object.__setattr__(self, "indices", tuple(sorted(indices)))


ActionT = TypeVar("ActionT", bound=Hashable)


@dataclass(frozen=True)
class ActionDistribution(Generic[ActionT]):
    """Probabilities over one hashable action type per decision.

    Mus and wager policies use enum actions; discard policies use
    ``DiscardAction``. A distribution never mixes these action types.
    """

    probabilities: Mapping[ActionT, float]

    def __post_init__(self) -> None:
        probabilities = dict(self.probabilities)
        if probabilities:
            action_type = type(next(iter(probabilities)))
            if any(type(action) is not action_type for action in probabilities):
                raise ValueError("A distribution must contain one action type.")
        if (
            not probabilities
            or any(not math.isfinite(value) or value < 0 for value in probabilities.values())
            or abs(math.fsum(probabilities.values()) - 1.0) > 1e-9
        ):
            raise ValueError("Action probabilities must be finite, nonnegative, and sum to one.")
        object.__setattr__(self, "probabilities", MappingProxyType(probabilities))

    def sample(self, rng: random.Random, legal_actions: Collection[ActionT]) -> ActionT:
        legal = set(legal_actions)
        if not legal or any(
            action not in legal and probability > 0
            for action, probability in self.probabilities.items()
        ):
            raise ValueError("Distribution assigns probability to an illegal action.")
        actions = tuple(
            action for action, probability in self.probabilities.items()
            if action in legal and probability > 0
        )
        return rng.choices(
            actions,
            weights=[self.probabilities[action] for action in actions],
            k=1,
        )[0]


def legal_wager_actions(wager_state: WagerState | None) -> frozenset[WagerAction]:
    if wager_state is not None and wager_state.ordago_offered:
        return frozenset({WagerAction.MATCH_OR_PASS, WagerAction.FOLD})
    actions = set(WagerAction)
    if wager_state is None or wager_state.offering_team is None:
        actions.remove(WagerAction.FOLD)
    return frozenset(actions)
