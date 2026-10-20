"""Bot player whose actions come from an injectable strategy portfolio."""

import random
from typing import Literal, overload

from mus_computer.bots.strategies.actions import (
    DecisionKind, DiscardAction, MusAction, WagerAction, legal_wager_actions,
)
from mus_computer.bots.strategies.contexts import PlayerDecisionContext
from mus_computer.bots.strategies.personality import BotPersonality
from mus_computer.bots.strategies.portfolio import StrategyPortfolio
from mus_computer.game.context import GlobalGameContext
from mus_computer.game.player_base import PlayerBase
from mus_computer.game.team import Team


class BotPlayer(PlayerBase):
    """Choose actions through replaceable decision strategies.

    The personality remains available to injected strategies. The built-in
    heuristic portfolio currently ignores it.
    """

    needs_discard_statistics = True

    def __init__(
        self,
        name: str,
        team: Team,
        personality: BotPersonality,
        strategies: StrategyPortfolio | None = None,
        random_generator: random.Random | None = None,
    ):
        super().__init__(name, team)
        self._personality = personality
        self.strategies = strategies if strategies is not None else StrategyPortfolio.default()
        self._random_generator = random_generator if random_generator is not None else random.Random()

    @overload
    def take_decision(
        self,
        kind: Literal[DecisionKind.MUS],
        global_context: GlobalGameContext,
        player_context: PlayerDecisionContext,
    ) -> MusAction: ...

    @overload
    def take_decision(
        self,
        kind: Literal[DecisionKind.DISCARD],
        global_context: GlobalGameContext,
        player_context: PlayerDecisionContext,
    ) -> DiscardAction: ...

    @overload
    def take_decision(
        self,
        kind: Literal[DecisionKind.WAGER],
        global_context: GlobalGameContext,
        player_context: PlayerDecisionContext,
    ) -> WagerAction: ...

    def take_decision(
        self,
        kind: DecisionKind,
        global_context: GlobalGameContext,
        player_context: PlayerDecisionContext,
    ) -> MusAction | DiscardAction | WagerAction:
        if kind is DecisionKind.MUS:
            distribution = self.strategies.mus_strategy.decide(global_context, player_context, self._personality)
            return distribution.sample(self._random_generator, frozenset(MusAction))
        if kind is DecisionKind.DISCARD:
            distribution = self.strategies.discard_strategy.decide(global_context, player_context, self._personality)
            legal = {option.action for option in player_context.discard_options}
            return distribution.sample(self._random_generator, legal)
        if kind is DecisionKind.WAGER:
            phase = global_context.phase_name or player_context.phase_name
            if phase is None:
                raise ValueError("A wager decision requires a phase.")
            distribution = self.strategies.wagers_by_phase[phase].decide(
                global_context, player_context, self._personality,
            )
            return distribution.sample(self._random_generator, legal_wager_actions(global_context.wager))
        raise ValueError(f"Unknown decision kind: {kind}")

    def vote_mus(
        self, global_context: GlobalGameContext, player_context: PlayerDecisionContext,
    ) -> MusAction:
        return self.take_decision(DecisionKind.MUS, global_context, player_context)

    def choose_discards(
        self, global_context: GlobalGameContext, player_context: PlayerDecisionContext,
    ) -> tuple[int, ...]:
        return self.take_decision(DecisionKind.DISCARD, global_context, player_context).indices

    def wager_action(
        self, global_context: GlobalGameContext, player_context: PlayerDecisionContext,
    ) -> WagerAction:
        return self.take_decision(DecisionKind.WAGER, global_context, player_context)
