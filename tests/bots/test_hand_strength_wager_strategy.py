"""The first wager layer maps phase loss probability to legal actions."""

from dataclasses import replace

import pytest

from mus_computer.bots.strategies.actions import WagerAction
from mus_computer.bots.strategies.contexts import HandStatistics, OutcomeProbability
from mus_computer.bots.strategies.wagers import HandStrengthWagerStrategy
from mus_computer.game.context import WagerState

from tests.bots.test_contextual_strategies import genome, global_context, player_context


@pytest.mark.parametrize("phase", ["Grande", "Chica", "Pares", "Juego", "Punto"])
def test_opening_wager_passes_on_loss_and_offers_two_on_win_or_tie(phase):
    private = player_context(phase)
    outcomes = dict(private.statistics.outcomes_by_phase)
    outcomes[phase] = OutcomeProbability(0.4, 0.1, 0.5)
    private = replace(private, statistics=HandStatistics(outcomes, private.statistics.expected_points_by_phase))

    probabilities = HandStrengthWagerStrategy(phase).decide(
        global_context(phase, WagerState(1, 1, None)), private, genome(),
    ).probabilities

    assert probabilities == {WagerAction.MATCH_OR_PASS: 0.5, WagerAction.RAISE_2: 0.5}


def test_answer_to_opponent_offer_folds_on_loss_and_matches_otherwise():
    private = player_context("Grande", probabilities={name: 0.8 for name in (
        "Grande", "Chica", "Pares", "Juego", "Punto",
    )})

    probabilities = HandStrengthWagerStrategy("Grande").decide(
        global_context("Grande", WagerState(2, 1, "B")), private, genome(),
    ).probabilities

    assert probabilities == {WagerAction.FOLD: pytest.approx(0.2), WagerAction.MATCH_OR_PASS: 0.8}
    assert WagerAction.RAISE_2 not in probabilities


def test_ordago_answer_uses_same_fold_or_match_distribution():
    probabilities = HandStrengthWagerStrategy("Grande").decide(
        global_context("Grande", WagerState(2, 1, "B", True)),
        player_context("Grande"), genome(),
    ).probabilities

    assert probabilities == {WagerAction.FOLD: 0.5, WagerAction.MATCH_OR_PASS: 0.5}
