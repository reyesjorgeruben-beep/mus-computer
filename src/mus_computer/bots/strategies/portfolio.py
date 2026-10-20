"""Assembly point for a bot's replaceable phase-specific strategies."""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from mus_computer.bots.strategies.discard import DiscardStrategy
from mus_computer.bots.strategies.mus import MusStrategy
from mus_computer.bots.strategies.wagers import WagerStrategy
from mus_computer.game.phases import PHASE_ORDER, PhaseName


@dataclass(frozen=True)
class StrategyPortfolio:
    """Compose one Mus, one discard, and one wager policy per phase.

    Any implementation of the three strategy interfaces can replace the
    defaults. ``BotPlayer`` receives this portfolio at construction time.
    """

    mus_strategy: MusStrategy
    discard_strategy: DiscardStrategy
    wagers_by_phase: Mapping[PhaseName, WagerStrategy]

    def __post_init__(self) -> None:
        if not callable(getattr(self.mus_strategy, "decide", None)):
            raise TypeError("Mus strategy must provide decide().")
        if not callable(getattr(self.discard_strategy, "decide", None)):
            raise TypeError("Discard strategy must provide decide().")
        if not isinstance(self.wagers_by_phase, Mapping):
            raise TypeError("Wager strategy map is required.")
        strategies = {
            PhaseName(phase): strategy
            for phase, strategy in self.wagers_by_phase.items()
        }
        if set(strategies) != set(PHASE_ORDER):
            raise ValueError("A wager strategy is required for every phase.")
        if any(not callable(getattr(strategy, "decide", None)) for strategy in strategies.values()):
            raise TypeError("Every wager strategy must provide decide().")
        if len({id(strategy) for strategy in strategies.values()}) != len(PHASE_ORDER):
            raise ValueError("Every wager phase needs a distinct strategy instance.")
        object.__setattr__(self, "wagers_by_phase", MappingProxyType(strategies))

    @classmethod
    def default(cls) -> "StrategyPortfolio":
        """Build the default Mus, discard, and wager strategies."""
        from mus_computer.bots.strategies.discard import PersonalityWeightedDiscardStrategy
        from mus_computer.bots.strategies.mus import EstimateMusStrategy
        from mus_computer.bots.strategies.wagers import HeuristicWagerStrategy

        return cls(
            mus_strategy=EstimateMusStrategy(),
            discard_strategy=PersonalityWeightedDiscardStrategy(),
            wagers_by_phase={phase: HeuristicWagerStrategy(phase) for phase in PHASE_ORDER},
        )
