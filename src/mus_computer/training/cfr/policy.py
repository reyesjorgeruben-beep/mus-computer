"""Tabular regrets, regret matching, average strategies, and policy serialization."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from .features import BettingFeatures
from .state import DecisionRecord


def regret_match(
    actions: tuple[str, ...], regrets: Mapping[str, float], prior: Mapping[str, float]
) -> dict[str, float]:
    """Normalize positive cumulative regrets, falling back to the prior."""
    positives = {action: max(0.0, regrets.get(action, 0.0)) for action in actions}
    total = sum(positives.values())
    if total > 0:
        return {action: positives[action] / total for action in actions}
    return {action: prior[action] for action in actions}


@dataclass
class RegretNode:
    actions: tuple[str, ...]
    prior: dict[str, float]
    regrets: dict[str, float] = field(default_factory=dict)
    strategy_sum: dict[str, float] = field(default_factory=dict)

    def current(self) -> dict[str, float]:
        return regret_match(self.actions, self.regrets, self.prior)

    def average(self) -> dict[str, float]:
        total = sum(self.strategy_sum.values())
        if total <= 0:
            return self.current()
        return {
            action: self.strategy_sum.get(action, 0.0) / total
            for action in self.actions
        }


class CFRPolicy:
    """Shared tabular regret and reach-weighted average strategy."""

    def __init__(self) -> None:
        self.nodes: dict[str, RegretNode] = {}

    def probabilities(
        self,
        key: str,
        actions: tuple[str, ...],
        prior: Mapping[str, float],
        *,
        average: bool = False,
        features: BettingFeatures | None = None,
    ) -> dict[str, float]:
        node = self.nodes.get(key)
        if node is None:
            return {action: prior[action] for action in actions}
        if node.actions != actions:
            raise ValueError("Information state has inconsistent legal actions")
        return node.average() if average else node.current()

    def frozen(self) -> CFRPolicy:
        frozen = CFRPolicy()
        frozen.nodes = {
            key: RegretNode(
                node.actions,
                dict(node.prior),
                dict(node.regrets),
                dict(node.strategy_sum),
            )
            for key, node in self.nodes.items()
        }
        return frozen

    def apply(
        self,
        records: list[DecisionRecord],
        increments: Mapping[str, Mapping[str, float]],
    ) -> None:
        """Apply all estimates together, independent of seat processing order."""
        for record in records:
            node = self.nodes.setdefault(
                record.key,
                RegretNode(record.actions, dict(record.prior)),
            )
            weight = record.own_reach / record.behavior_reach
            for action in record.actions:
                node.strategy_sum[action] = (
                    node.strategy_sum.get(action, 0.0)
                    + weight * record.strategy[action]
                )
        for key, values in increments.items():
            node = self.nodes[key]
            for action, value in values.items():
                node.regrets[action] = node.regrets.get(action, 0.0) + value

    def snapshot(self) -> dict:
        return {
            key: {
                "actions": node.actions,
                "prior": node.prior,
                "regrets": node.regrets,
                "strategy_sum": node.strategy_sum,
                "current": node.current(),
                "average": node.average(),
            }
            for key, node in self.nodes.items()
        }

    @classmethod
    def from_snapshot(cls, snapshot: Mapping) -> CFRPolicy:
        """Restore both current and average policies from saved node data."""
        if snapshot["information_states"].get("type") == "phase_glm_v1":
            from .glm_policy import GLMCFRPolicy

            return GLMCFRPolicy.from_snapshot(snapshot)
        policy = cls()
        for key, data in snapshot["information_states"].items():
            policy.nodes[key] = RegretNode(
                tuple(data["actions"]),
                dict(data["prior"]),
                dict(data["regrets"]),
                dict(data["strategy_sum"]),
            )
        return policy
