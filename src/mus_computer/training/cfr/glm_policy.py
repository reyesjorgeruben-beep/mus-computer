"""Phase-specific softmax policies projected from CFR sufficient statistics."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from copy import deepcopy

from mus_computer.bots.strategies.actions import WagerAction
from mus_computer.game.phases import PhaseName

from .features import BETTING_STAGES, PREVIOUS_LANCES, BettingFeatures, feature_names
from .linear_softmax import (
    BlockSpec,
    Coefficients,
    ProjectionExample,
    fit_targets,
    initialize_coefficients,
    predict_distribution,
)
from .policy import CFRPolicy
from .state import DecisionRecord, action_name


def _betting_schema(
    phases: Sequence[PhaseName], stages: Sequence[str], actions: tuple[str, ...]
) -> dict[str, BlockSpec]:
    """Translate explicit game definitions into generic action/input blocks.

    For Chica/opening, each supplied action gets baseline, hand_strength and
    opponent_wager_Grande inputs. Other phases declare their own earlier lances.
    This adapter, rather than the numerical model, owns those betting semantics.
    """
    return {
        f"{phase.value}/{stage}": BlockSpec(actions, feature_names(phase))
        for phase in phases
        for stage in stages
    }


class GLMCFRPolicy(CFRPolicy):
    """Adapt generic linear-softmax models to the existing CFR betting targets.

    The adapter declares betting blocks and inputs, retains cumulative regrets
    and strategy sums, and chooses fitting targets. The action-independent
    numerical helpers perform scoring, normalization and weighted fitting.
    Separate current/average coefficients approximate the two table targets;
    non-betting decisions keep their portfolio prior. This is not exact CFR.
    """

    def __init__(self, learning_rate: float = 0.1) -> None:
        """Allocate independent current/average weights and the betting schema."""
        super().__init__()
        if not math.isfinite(learning_rate) or not 0 < learning_rate <= 1:
            raise ValueError("Projection learning rate must be in (0, 1]")
        self.learning_rate = learning_rate
        schema = _betting_schema(
            tuple(PREVIOUS_LANCES),
            BETTING_STAGES,
            tuple(action_name(action) for action in WagerAction),
        )
        self.current_coefficients = initialize_coefficients(schema)
        self.average_coefficients = initialize_coefficients(schema)
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
        """Predict legal wager probabilities, or keep the prior without features."""
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
        """Select a betting block and delegate action-agnostic score inference."""
        return predict_distribution(
            coefficients[features.block], features.values, actions
        )

    def frozen(self) -> GLMCFRPolicy:
        """Copy all coefficients and retained tables for stable iteration rollouts."""
        return deepcopy(self)

    def apply(
        self,
        records: list[DecisionRecord],
        increments: Mapping[str, Mapping[str, float]],
    ) -> None:
        """Accumulate wager statistics, then fit current and average models once."""
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
        """Build CFR-specific targets and pass them to the generic weighted fit."""
        examples = []
        for key, node in self.nodes.items():
            mass = (
                math.fsum(node.strategy_sum.values())
                if average
                else math.fsum(max(0.0, regret) for regret in node.regrets.values())
            )
            if not average and mass <= 0:
                mass = 1.0  # Regret matching's prior fallback remains trainable.
            if mass > 0:
                features = self.features[key]
                examples.append(
                    ProjectionExample(
                        features.block,
                        features.values,
                        node.actions,
                        node.average() if average else node.current(),
                        mass,
                    )
                )
        fit_targets(coefficients, examples, self.learning_rate)

    def snapshot(self) -> dict:
        """Copy the unchanged phase_glm_v1 checkpoint layout for serialization."""
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
        """Restore both generic weight sets and betting-specific retained state."""
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
