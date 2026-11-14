"""Action sampling, replay prefixes, and target and behavior reach tracking."""

from __future__ import annotations

import random
from collections.abc import Mapping

from mus_computer.bots.strategies.actions import (
    ActionDistribution,
    DecisionKind,
)
from mus_computer.bots.strategies.contexts import PlayerDecisionContext
from mus_computer.game.context import GlobalGameContext

from .features import betting_features
from .policy import CFRPolicy
from .state import Action, DecisionRecord, action_name, information_key


class DecisionController:
    """Sample or force bot actions while exposing only decision contexts to policy."""

    def __init__(
        self,
        policy: CFRPolicy,
        rng: random.Random,
        *,
        exploration: float,
        average: bool = False,
        prefix: tuple[str, ...] = (),
        forced_action: str | None = None,
        record: bool = True,
        policy_by_player: Mapping[int, CFRPolicy] | None = None,
    ) -> None:
        self.policy = policy
        self.rng = rng
        self.exploration = exploration
        self.average = average
        self.prefix = prefix
        self.forced_action = forced_action
        self.record = record
        self.policy_by_player = policy_by_player or {}
        self.decisions: list[DecisionRecord] = []
        self.ordinal = 0
        self.target_reach = [1.0] * 4
        self.behavior_reach = 1.0

    def choose(
        self,
        seat: int,
        kind: DecisionKind,
        public: GlobalGameContext,
        private: PlayerDecisionContext,
        distribution: ActionDistribution,
        legal: tuple[Action, ...],
    ) -> Action:
        names = tuple(action_name(action) for action in legal)
        prior = {
            action_name(action): distribution.probabilities.get(action, 0.0)
            for action in legal
        }
        key = information_key(kind, public, private, legal)
        features = (
            betting_features(public, private) if kind is DecisionKind.WAGER else None
        )
        strategy = self.policy_by_player.get(seat, self.policy).probabilities(
            key, names, prior, average=self.average, features=features
        )
        behavior = {
            name: (1 - self.exploration) * strategy[name]
            + self.exploration / len(names)
            for name in names
        }
        ordinal = self.ordinal
        self.ordinal += 1
        if ordinal < len(self.prefix):
            selected = self.prefix[ordinal]
        elif ordinal == len(self.prefix) and self.forced_action is not None:
            selected = self.forced_action
        else:
            selected = self.rng.choices(names, weights=list(behavior.values()), k=1)[0]
        if selected not in names:
            raise ValueError("Replay prefix diverged from its original decision")
        if self.record:
            opponents = 1.0
            for other_seat, reach in enumerate(self.target_reach):
                if other_seat != seat:
                    opponents *= reach
            self.decisions.append(
                DecisionRecord(
                    ordinal,
                    seat,
                    key,
                    names,
                    prior,
                    strategy,
                    selected,
                    self.target_reach[seat],
                    opponents,
                    self.behavior_reach,
                    features,
                )
            )
        self.target_reach[seat] *= strategy[selected]
        self.behavior_reach *= behavior[selected]
        return legal[names.index(selected)]
