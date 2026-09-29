"""Bot player whose actions come from an injectable strategy portfolio."""

import random

from mus_computer.bots.strategies.actions import (
    DecisionKind, MusAction, WagerAction, legal_wager_actions,
)
from mus_computer.bots.strategies.contexts import PlayerDecisionContext
from mus_computer.bots.strategies.personality import BotPersonality
from mus_computer.bots.strategies.portfolio import StrategyPortfolio
from mus_computer.game.context import GlobalGameContext
from mus_computer.game.player_base import PlayerBase
from mus_computer.game.team import Team


class BotPlayer(PlayerBase):
    needs_discard_statistics = True

    def __init__(
        self,
        name: str,
        team: Team,
        genome: BotPersonality,
        strategies: StrategyPortfolio | None = None,
        rng: random.Random | None = None,
    ):
        super().__init__(name, team)
        self._genome = genome
        self.strategies = strategies if strategies is not None else StrategyPortfolio.default()
        self._rng = rng if rng is not None else random.Random()

    def take_decision(
        self,
        kind: DecisionKind,
        global_context: GlobalGameContext,
        player_context: PlayerDecisionContext,
    ) -> MusAction | tuple[int, ...] | WagerAction:
        if kind is DecisionKind.MUS:
            distribution = self.strategies.mus.decide(global_context, player_context, self._genome)
            return distribution.sample(self._rng, frozenset(MusAction))
        if kind is DecisionKind.DISCARD:
            distribution = self.strategies.discard.decide(global_context, player_context, self._genome)
            legal = set(player_context.discard_options)
            if not legal:
                legal = {()}
            return distribution.sample(self._rng, legal)
        if kind is DecisionKind.WAGER:
            phase = global_context.phase_name or player_context.phase_name
            if phase is None:
                raise ValueError("A wager decision requires a phase.")
            distribution = self.strategies.wagers_by_phase[phase].decide(
                global_context, player_context, self._genome,
            )
            return distribution.sample(self._rng, legal_wager_actions(global_context.wager))
        raise ValueError(f"Unknown decision kind: {kind}")

    def vote_mus(
        self, global_context: GlobalGameContext, player_context: PlayerDecisionContext,
    ) -> MusAction:
        return self.take_decision(DecisionKind.MUS, global_context, player_context)

    def choose_discards(
        self, global_context: GlobalGameContext, player_context: PlayerDecisionContext,
    ) -> tuple[int, ...]:
        return self.take_decision(DecisionKind.DISCARD, global_context, player_context)

    def wager_action(
        self, global_context: GlobalGameContext, player_context: PlayerDecisionContext,
    ) -> WagerAction:
        return self.take_decision(DecisionKind.WAGER, global_context, player_context)
