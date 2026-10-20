"""The first wager layer maps phase loss probability to legal actions."""

from dataclasses import replace

import pytest

from mus_computer.bots.strategies.actions import WagerAction
from mus_computer.bots.strategies.contexts import HandStatistics, OutcomeProbability
from mus_computer.bots.strategies.wagers import (
    BluffRaiseLayer, ComposedWagerStrategy, ExtremeBluffLayer, HandStrengthWagerStrategy,
)
from mus_computer.game.context import WagerState

from tests.bots.test_contextual_strategies import genome, global_context, player_context


@pytest.mark.parametrize("phase", ["Grande", "Chica", "Pares", "Juego", "Punto"])
def test_opening_wager_passes_on_loss_and_offers_two_on_win_or_tie(phase):
    private = player_context(phase)
    outcomes = dict(private.statistics.outcomes_by_phase)
    outcomes[phase] = OutcomeProbability(0.4, 0.1, 0.5)
    private = replace(private, statistics=HandStatistics(outcomes, private.statistics.expected_points_by_phase))

    probabilities = HandStrengthWagerStrategy(phase).decide(
        global_context(phase, WagerState(1, 1, None)), private,
        genome(bluff_rate=0, extreme_bluff_rate=0),
    ).probabilities

    assert probabilities == {WagerAction.MATCH_OR_PASS: 0.5, WagerAction.RAISE_2: 0.5}


def test_answer_to_opponent_offer_folds_on_loss_and_matches_otherwise():
    private = player_context("Grande", probabilities={name: 0.8 for name in (
        "Grande", "Chica", "Pares", "Juego", "Punto",
    )})

    probabilities = HandStrengthWagerStrategy("Grande").decide(
        global_context("Grande", WagerState(2, 1, "B")), private,
        genome(bluff_rate=0, extreme_bluff_rate=0),
    ).probabilities

    assert probabilities == {WagerAction.FOLD: pytest.approx(0.2), WagerAction.MATCH_OR_PASS: 0.8}
    assert WagerAction.RAISE_2 not in probabilities


def test_ordago_answer_uses_same_fold_or_match_distribution():
    probabilities = HandStrengthWagerStrategy("Grande").decide(
        global_context("Grande", WagerState(2, 1, "B", True)),
        player_context("Grande"), genome(bluff_rate=0, extreme_bluff_rate=0),
    ).probabilities

    assert probabilities == {WagerAction.FOLD: 0.5, WagerAction.MATCH_OR_PASS: 0.5}


def test_hand_strength_baseline_ignores_bluff_genes():
    public = global_context("Grande", WagerState(1, 1, None))
    private = player_context("Grande")
    base = HandStrengthWagerStrategy("Grande")

    quiet = base.decide(public, private, genome(bluff_rate=0, extreme_bluff_rate=0))
    bold = base.decide(public, private, genome(bluff_rate=1, extreme_bluff_rate=1))

    assert quiet.probabilities == bold.probabilities
    assert WagerAction.ORDAGO not in bold.probabilities


def test_composed_layers_apply_in_order_without_changing_base():
    public = global_context("Grande", WagerState(1, 1, None))
    private = player_context("Grande")
    personality = genome(bluff_rate=0.2, extreme_bluff_rate=0.25)
    base = HandStrengthWagerStrategy("Grande")
    baseline = base.decide(public, private, personality).probabilities

    regular_first = ComposedWagerStrategy(
        base, (BluffRaiseLayer(), ExtremeBluffLayer()),
    ).decide(public, private, personality).probabilities
    extreme_first = ComposedWagerStrategy(
        base, (ExtremeBluffLayer(), BluffRaiseLayer()),
    ).decide(public, private, personality).probabilities

    assert regular_first[WagerAction.ORDAGO] == pytest.approx(0.1)
    assert extreme_first[WagerAction.ORDAGO] == pytest.approx(0.125)
    assert base.decide(public, private, personality).probabilities == baseline


def composed(phase):
    return ComposedWagerStrategy(
        HandStrengthWagerStrategy(phase), (BluffRaiseLayer(), ExtremeBluffLayer()),
    )


@pytest.mark.parametrize("wager,passive", [
    (WagerState(1, 1, None), WagerAction.MATCH_OR_PASS),
    (WagerState(2, 1, "B"), WagerAction.FOLD),
])
def test_bluff_layers_move_losing_hand_probability_to_raise_and_ordago(wager, passive):
    probabilities = composed("Grande").decide(
        global_context("Grande", wager), player_context("Grande"),
        genome(bluff_rate=0.2, extreme_bluff_rate=0.25),
    ).probabilities

    assert probabilities[passive] == pytest.approx(0.3)
    assert probabilities[WagerAction.ORDAGO] == pytest.approx(0.1)
    assert probabilities[WagerAction.RAISE_2] == pytest.approx(
        0.6 if passive is WagerAction.MATCH_OR_PASS else 0.1
    )
    if passive is WagerAction.FOLD:
        assert probabilities[WagerAction.MATCH_OR_PASS] == pytest.approx(0.5)


def test_bluff_layers_do_not_offer_illegal_raise_over_ordago():
    probabilities = composed("Grande").decide(
        global_context("Grande", WagerState(2, 1, "B", True)),
        player_context("Grande"), genome(bluff_rate=1, extreme_bluff_rate=1),
    ).probabilities
    assert probabilities == {WagerAction.FOLD: 0.5, WagerAction.MATCH_OR_PASS: 0.5}
