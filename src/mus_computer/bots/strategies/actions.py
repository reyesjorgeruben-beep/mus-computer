"""Typed bot decisions and validated action probabilities."""

import math
import random
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Collection, Generic, Hashable, Mapping, TypeVar

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


A = TypeVar("A", bound=Hashable)


@dataclass(frozen=True)
class ActionDistribution(Generic[A]):
    probabilities: Mapping[A, float]

    def __post_init__(self) -> None:
        probabilities = dict(self.probabilities)
        if (
            not probabilities
            or any(not math.isfinite(value) or value < 0 for value in probabilities.values())
            or abs(math.fsum(probabilities.values()) - 1.0) > 1e-9
        ):
            raise ValueError("Action probabilities must be finite, nonnegative, and sum to one.")
        object.__setattr__(self, "probabilities", MappingProxyType(probabilities))

    def sample(self, rng: random.Random, legal_actions: Collection[A]) -> A:
        legal = set(legal_actions)
        if not legal or any(
            action not in legal and probability > 0
            for action, probability in self.probabilities.items()
        ):
            raise ValueError("Distribution assigns probability to an illegal action.")
        point = rng.random()
        cumulative = 0.0
        last_action = None
        for action, probability in self.probabilities.items():
            if action not in legal or probability <= 0:
                continue
            cumulative += probability
            last_action = action
            if point < cumulative:
                return action
        if last_action is None:
            raise ValueError("Distribution has no legal action with positive probability.")
        return last_action


def legal_wager_actions(wager_state: WagerState | None) -> frozenset[WagerAction]:
    actions = set(WagerAction)
    if wager_state is None or wager_state.offering_team is None:
        actions.remove(WagerAction.FOLD)
    return frozenset(actions)
