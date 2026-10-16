"""Initial limits for running silent training games."""

from dataclasses import dataclass

from mus_computer.training.constants import MAX_CONCURRENT_GAMES


@dataclass(frozen=True)
class TrainingConfig:
    """Runtime cap and warm-run performance targets for random-bot games."""

    max_concurrent_games: int = MAX_CONCURRENT_GAMES
    single_game_max_seconds: float = 0.6
    ten_game_max_seconds: float = 0.6

    def __post_init__(self) -> None:
        if not 1 <= self.max_concurrent_games <= MAX_CONCURRENT_GAMES:
            raise ValueError(f"max_concurrent_games must be between 1 and {MAX_CONCURRENT_GAMES}")
        if self.single_game_max_seconds <= 0 or self.ten_game_max_seconds <= 0:
            raise ValueError("Training time thresholds must be positive")
