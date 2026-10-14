"""Initial limits for running silent training games."""

from dataclasses import dataclass


@dataclass(frozen=True)
class TrainingConfig:
    """Runtime cap and warm-run performance targets for random-bot games."""

    max_concurrent_games: int = 10
    single_game_max_seconds: float = 0.6
    ten_game_max_seconds: float = 0.6

    def __post_init__(self) -> None:
        if not 1 <= self.max_concurrent_games <= 10:
            raise ValueError("max_concurrent_games must be between 1 and 10")
        if self.single_game_max_seconds <= 0 or self.ten_game_max_seconds <= 0:
            raise ValueError("Training time thresholds must be positive")
