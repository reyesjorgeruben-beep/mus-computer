"""Training settings and validation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CFRConfig:
    iterations: int = 100
    seed: int = 0
    exploration: float = 0.1
    snapshot_every: int = 10

    def __post_init__(self) -> None:
        if self.iterations < 1 or self.snapshot_every < 1:
            raise ValueError("Iterations and snapshot interval must be positive")
        if not 0 < self.exploration <= 1:
            raise ValueError("Exploration must be in (0, 1]")
