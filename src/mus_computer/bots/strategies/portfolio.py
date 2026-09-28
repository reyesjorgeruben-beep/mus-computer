"""Replaceable, phase-specific policies for a Mus bot."""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Protocol, TypeVar

from mus_computer.bots.bot_genome import BotGenome
from mus_computer.bots.strategies.actions import ActionDistribution, MusAction, WagerAction
from mus_computer.bots.strategies.contexts import PlayerDecisionContext
from mus_computer.game.context import GlobalGameContext


BotPersonality = BotGenome
PHASE_NAMES = ("Grande", "Chica", "Pares", "Juego", "Punto")
Action = TypeVar("Action")


class DecisionStrategy(Protocol[Action]):
    def decide(
        self,
        global_context: GlobalGameContext,
        player_context: PlayerDecisionContext,
        personality: BotPersonality,
    ) -> ActionDistribution[Action]:
        ...


@dataclass(frozen=True)
class StrategyPortfolio:
    mus: DecisionStrategy[MusAction]
    discard: DecisionStrategy[tuple[int, ...]]
    wagers_by_phase: Mapping[str, DecisionStrategy[WagerAction]]

    def __post_init__(self) -> None:
        strategies = dict(self.wagers_by_phase)
        if set(strategies) != set(PHASE_NAMES):
            raise ValueError("A wager strategy is required for every phase.")
        if len({id(strategy) for strategy in strategies.values()}) != len(PHASE_NAMES):
            raise ValueError("Every wager phase needs a distinct strategy instance.")
        object.__setattr__(self, "wagers_by_phase", MappingProxyType(strategies))

    @classmethod
    def default(cls) -> "StrategyPortfolio":
        from mus_computer.bots.strategies.discard import ExpectedValueDiscardStrategy
        from mus_computer.bots.strategies.mus import EstimateMusStrategy
        from mus_computer.bots.strategies.wagers import PhaseWagerStrategy

        return cls(
            mus=EstimateMusStrategy(),
            discard=ExpectedValueDiscardStrategy(),
            wagers_by_phase={name: PhaseWagerStrategy(name) for name in PHASE_NAMES},
        )
