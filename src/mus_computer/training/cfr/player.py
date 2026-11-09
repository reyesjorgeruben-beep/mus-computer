"""Adapt the existing bot interface to CFR action selection."""

from __future__ import annotations

from typing import Literal, overload

from mus_computer.bots.bot_genome import BotGenome
from mus_computer.bots.bot_player import BotPlayer
from mus_computer.bots.strategies.actions import (
    ActionDistribution,
    DecisionKind,
    DiscardAction,
    MusAction,
    WagerAction,
    legal_wager_actions,
)
from mus_computer.bots.strategies.contexts import PlayerDecisionContext
from mus_computer.bots.strategies.portfolio import StrategyPortfolio
from mus_computer.game.context import GlobalGameContext
from mus_computer.game.team import Team

from .sampling import DecisionController
from .state import Action


class CFRBotPlayer(BotPlayer):
    """Existing bot interface with decisions routed through a shared table."""

    def __init__(
        self,
        name: str,
        team: Team,
        personality: BotGenome,
        strategies: StrategyPortfolio,
        controller: DecisionController,
        player_id: int,
    ) -> None:
        super().__init__(name, team, personality, strategies)
        self.controller = controller
        self.player_id = player_id

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
    ) -> Action:
        distribution: (
            ActionDistribution[MusAction]
            | ActionDistribution[DiscardAction]
            | ActionDistribution[WagerAction]
        )
        if kind is DecisionKind.MUS:
            distribution = self.strategies.mus_strategy.decide(
                global_context, player_context, self._personality
            )
            legal: tuple[Action, ...] = tuple(MusAction)
        elif kind is DecisionKind.DISCARD:
            distribution = self.strategies.discard_strategy.decide(
                global_context, player_context, self._personality
            )
            legal = tuple(option.action for option in player_context.discard_options)
        else:
            phase = global_context.phase_name or player_context.phase_name
            if phase is None:
                raise ValueError("Wager decision requires a phase")
            distribution = self.strategies.wagers_by_phase[phase].decide(
                global_context, player_context, self._personality
            )
            legal = tuple(
                action
                for action in WagerAction
                if action in legal_wager_actions(global_context.wager)
            )
        return self.controller.choose(
            self.player_id, kind, global_context, player_context, distribution, legal
        )
