"""Phase-specific softmax policies projected from CFR sufficient statistics."""

from __future__ import annotations

import math
from collections.abc import Mapping
from copy import deepcopy

from mus_computer.bots.strategies.actions import WagerAction

from .features import BETTING_STAGES, PREVIOUS_LANCES, BettingFeatures, feature_names
from .policy import CFRPolicy
from .state import DecisionRecord, action_name

Coefficients = dict[str, dict[str, dict[str, float]]]


def _coefficients() -> Coefficients:
    return {
        f"{phase.value}/{stage}": {
            action_name(action): dict.fromkeys(feature_names(phase), 0.0)
            for action in WagerAction
        }
        for phase in PREVIOUS_LANCES
        for stage in BETTING_STAGES
    }


class GLMCFRPolicy(CFRPolicy):
    """Train wagers only, keeping separate current and average projections.

    Tables retain the existing unbiased sampled regret increments and exact
    reach-weighted strategy sums. A normalized weighted cross-entropy step
    fits each phase/stage block to regret-matching and average-table targets.
    This is function approximation, not exact tabular regret matching.
    """

    def __init__(self, learning_rate: float = 0.1) -> None:
        super().__init__()
        if not math.isfinite(learning_rate) or not 0 < learning_rate <= 1:
            raise ValueError("Projection learning rate must be in (0, 1]")
        self.learning_rate = learning_rate
        self.current_coefficients = _coefficients()
        self.average_coefficients = _coefficients()
        self.features: dict[str, BettingFeatures] = {}

    def probabilities(
        self,
        key: str,
        actions: tuple[str, ...],
        prior: Mapping[str, float],
        *,
        average: bool = False,
        features: BettingFeatures | None = None,
    ) -> dict[str, float]:
        features = features or self.features.get(key)
        if features is None:
            return {action: prior[action] for action in actions}
        coefficients = (
            self.average_coefficients if average else self.current_coefficients
        )
        return self._predict(coefficients, features, actions)

    @staticmethod
    def _predict(
        coefficients: Coefficients, features: BettingFeatures, actions: tuple[str, ...]
    ) -> dict[str, float]:
        block = coefficients[features.block]
        logits = {
            action: math.fsum(
                block[action][name] * value for name, value in features.values.items()
            )
            for action in actions
        }
        maximum = max(logits.values())
        weights = {
            action: math.exp(value - maximum) for action, value in logits.items()
        }
        total = math.fsum(weights.values())
        return {action: value / total for action, value in weights.items()}

    def frozen(self) -> GLMCFRPolicy:
        return deepcopy(self)

    def apply(
        self,
        records: list[DecisionRecord],
        increments: Mapping[str, Mapping[str, float]],
    ) -> None:
        wagers = [record for record in records if record.features is not None]
        for record in wagers:
            assert record.features is not None
            self.features[record.key] = record.features
        super().apply(
            wagers,
            {key: value for key, value in increments.items() if key in self.features},
        )
        self._project(self.current_coefficients, average=False)
        self._project(self.average_coefficients, average=True)

    def _project(self, coefficients: Coefficients, *, average: bool) -> None:
        # Accumulate before mutation so every target sees the same frozen model.
        examples: dict[str, list[tuple[str, float]]] = {}
        for key, node in self.nodes.items():
            mass = (
                math.fsum(node.strategy_sum.values())
                if average
                else math.fsum(max(0.0, regret) for regret in node.regrets.values())
            )
            if not average and mass <= 0:
                mass = 1.0  # Regret matching's prior fallback remains trainable.
            if mass > 0:
                examples.setdefault(self.features[key].block, []).append((key, mass))
        for block, entries in examples.items():
            # Rescale before summing to avoid overflowing large sampling weights.
            scale = max(mass for _, mass in entries)
            total = math.fsum(mass / scale for _, mass in entries)
            gradients = {
                action: dict.fromkeys(values, 0.0)
                for action, values in coefficients[block].items()
            }
            for key, mass in entries:
                node = self.nodes[key]
                features = self.features[key]
                target = node.average() if average else node.current()
                predicted = self._predict(coefficients, features, node.actions)
                weight = (mass / scale) / total
                for action in node.actions:
                    error = weight * (target[action] - predicted[action])
                    for name, value in features.values.items():
                        gradients[action][name] += error * value
            for action, values in gradients.items():
                for name, gradient in values.items():
                    coefficients[block][action][name] += self.learning_rate * gradient

    def snapshot(self) -> dict:
        return deepcopy(
            {
                "type": "phase_glm_v1",
                "learning_rate": self.learning_rate,
                "current_coefficients": self.current_coefficients,
                "average_coefficients": self.average_coefficients,
                "nodes": super().snapshot(),
                "features": {
                    key: {"block": f.block, "values": dict(f.values)}
                    for key, f in self.features.items()
                },
            }
        )

    @classmethod
    def from_snapshot(cls, snapshot: Mapping) -> GLMCFRPolicy:
        data = snapshot["information_states"]
        policy = cls(data["learning_rate"])
        policy.current_coefficients = deepcopy(data["current_coefficients"])
        policy.average_coefficients = deepcopy(data["average_coefficients"])
        policy.nodes = CFRPolicy.from_snapshot(
            {"information_states": data["nodes"]}
        ).nodes
        policy.features = {
            key: BettingFeatures(f["block"], dict(f["values"]))
            for key, f in data["features"].items()
        }
        return policy
