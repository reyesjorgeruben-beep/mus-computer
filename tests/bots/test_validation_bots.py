"""Validation baselines choose only the actions described by their policies."""

from mus_computer.bots.mus_maestro_bot import MusMaestroBot
from mus_computer.bots.random_decision_bot import RandomDecisionBot
from mus_computer.bots.strategies.actions import MusAction, WagerAction, legal_wager_actions
from mus_computer.game.context import WagerState
from mus_computer.game.team import Team

from tests.bots.test_contextual_strategies import global_context, player_context


class CaptureChoices:
    def __init__(self):
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
    for wager in (WagerState(1, 1, None), WagerState(2, 1, "A"), WagerState(2, 1, "A", True)):
        bot.wager_action(global_context("Grande", wager), player_context("Grande"))
        assert set(rng.options[-1]) == legal_wager_actions(wager)


def test_mus_maestro_always_mus_discards_all_passes_and_folds():
    bot = MusMaestroBot("B1", Team("B"))
    bot.receive_cards([1, 2, 3, 4])

    assert bot.vote_mus(global_context(), player_context()) is MusAction.MUS
    assert bot.choose_discards(global_context(), player_context()) == (0, 1, 2, 3)
    assert bot.wager_action(global_context("Grande", WagerState(1, 1, None)), player_context("Grande")) is WagerAction.MATCH_OR_PASS
    assert bot.wager_action(global_context("Grande", WagerState(2, 1, "A")), player_context("Grande")) is WagerAction.FOLD
    assert bot.wager_action(global_context("Grande", WagerState(2, 1, "A", True)), player_context("Grande")) is WagerAction.FOLD
