"""Assembly point for a bot's replaceable phase-specific strategies."""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Protocol, TypeVar

from mus_computer.bots.strategies.actions import ActionDistribution, MusAction, WagerAction
from mus_computer.bots.strategies.contexts import PlayerDecisionContext
from mus_computer.bots.strategies.personality import BotPersonality
from mus_computer.game.context import GlobalGameContext
from mus_computer.game.phases import PHASE_ORDER, PhaseName


ActionT = TypeVar("ActionT")


class DecisionStrategy(Protocol[ActionT]):
    def decide(
        self,
        global_context: GlobalGameContext,
        player_context: PlayerDecisionContext,
        personality: BotPersonality,
    ) -> ActionDistribution[ActionT]:
        ...


@dataclass(frozen=True)
class StrategyPortfolio:
    """One Mus policy, one discard policy, and one wager policy per phase."""

    mus: DecisionStrategy[MusAction]
    discard: DecisionStrategy[tuple[int, ...]]
    wagers_by_phase: Mapping[PhaseName, DecisionStrategy[WagerAction]]

    def __post_init__(self) -> None:
        strategies = {
            PhaseName(phase): strategy
            for phase, strategy in self.wagers_by_phase.items()
        }
        if set(strategies) != set(PHASE_ORDER):
            raise ValueError("A wager strategy is required for every phase.")
        if len({id(strategy) for strategy in strategies.values()}) != len(PHASE_ORDER):
            raise ValueError("Every wager phase needs a distinct strategy instance.")
        object.__setattr__(self, "wagers_by_phase", MappingProxyType(strategies))

    @classmethod
    def default(cls) -> "StrategyPortfolio":
        from mus_computer.bots.strategies.discard import PersonalityWeightedDiscardStrategy
        from mus_computer.bots.strategies.mus import EstimateMusStrategy
        from mus_computer.bots.strategies.wagers import PhaseWagerStrategy

        return cls(
            mus=EstimateMusStrategy(),
            discard=PersonalityWeightedDiscardStrategy(),
            wagers_by_phase={phase: PhaseWagerStrategy(phase) for phase in PHASE_ORDER},
        )
