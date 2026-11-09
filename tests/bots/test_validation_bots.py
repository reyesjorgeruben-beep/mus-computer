"""Validation baselines choose only the actions described by their policies."""

import random

from mus_computer.bots.mus_maestro_bot import MusMaestroBot
from mus_computer.bots.random_decision_bot import RandomDecisionBot
from mus_computer.bots.strategies.actions import (
    MusAction,
    WagerAction,
    legal_wager_actions,
)
from mus_computer.game.context import WagerState
from mus_computer.game.phases import PhaseName
from mus_computer.game.team import Team
from tests.bots.test_contextual_strategies import global_context, player_context


class CaptureChoices(random.Random):
    def __init__(self):
        super().__init__(0)
        self.options = []

    def choice(self, options):
        self.options.append(tuple(options))
        return options[-1]


def test_random_decision_bot_offers_every_legal_action_uniformly():
    rng = CaptureChoices()
    bot = RandomDecisionBot("B1", Team("B"), rng)
    bot.receive_cards([1, 2, 3, 4])

    assert bot.vote_mus(global_context(), player_context()) in MusAction
    assert set(rng.options[-1]) == set(MusAction)
    bot.choose_discards(global_context(), player_context())
    assert len(rng.options[-1]) == 16
    assert len(set(rng.options[-1])) == 16
    assert () in rng.options[-1] and (0, 1, 2, 3) in rng.options[-1]
    for wager in (
        WagerState(1, 1, None),
        WagerState(2, 1, "A"),
        WagerState(2, 1, "A", True),
    ):
        bot.wager_action(
            global_context(PhaseName.GRANDE, wager), player_context(PhaseName.GRANDE)
        )
        assert set(rng.options[-1]) == legal_wager_actions(wager)


def test_mus_maestro_always_mus_discards_all_passes_and_folds():
    bot = MusMaestroBot("B1", Team("B"))
    bot.receive_cards([1, 2, 3, 4])

    assert bot.vote_mus(global_context(), player_context()) is MusAction.MUS
    assert bot.choose_discards(global_context(), player_context()) == (0, 1, 2, 3)
    assert (
        bot.wager_action(
            global_context(PhaseName.GRANDE, WagerState(1, 1, None)),
            player_context(PhaseName.GRANDE),
        )
        is WagerAction.MATCH_OR_PASS
    )
    assert (
        bot.wager_action(
            global_context(PhaseName.GRANDE, WagerState(2, 1, "A")),
            player_context(PhaseName.GRANDE),
        )
        is WagerAction.FOLD
    )
    assert (
        bot.wager_action(
            global_context(PhaseName.GRANDE, WagerState(2, 1, "A", True)),
            player_context(PhaseName.GRANDE),
        )
        is WagerAction.FOLD
    )
