"""Training settings and validation."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class CFRConfig:
    iterations: int = 100
    seed: int = 0
    exploration: float = 0.1
    snapshot_every: int = 10
    policy: str = "tabular"
    glm_learning_rate: float = 0.1

    def __post_init__(self) -> None:
        if self.iterations < 1 or self.snapshot_every < 1:
            raise ValueError("Iterations and snapshot interval must be positive")
        if not 0 < self.exploration <= 1:
            raise ValueError("Exploration must be in (0, 1]")
        if self.policy not in {"tabular", "glm"}:
            raise ValueError("Policy must be tabular or glm")
        if (
            not math.isfinite(self.glm_learning_rate)
            or not 0 < self.glm_learning_rate <= 1
        ):
            raise ValueError("Projection learning rate must be in (0, 1]")
