import random

import pytest

from mus_computer.bots.strategies.actions import (
    ActionDistribution, MusAction, WagerAction, legal_wager_actions,
)
from mus_computer.game.context import WagerState


def test_distribution_copies_input_and_samples_only_legal_action():
    source = {MusAction.MUS: 1.0, MusAction.CORTA: 0.0}
    distribution = ActionDistribution(source)
    source[MusAction.MUS] = 0.0
    assert distribution.sample(random.Random(0), {MusAction.MUS}) is MusAction.MUS
    with pytest.raises(TypeError):
        distribution.probabilities[MusAction.MUS] = 0.0


@pytest.mark.parametrize("values", [
    {MusAction.MUS: -0.1, MusAction.CORTA: 1.1},
    {MusAction.MUS: float("nan"), MusAction.CORTA: 0.0},
    {MusAction.MUS: float("inf"), MusAction.CORTA: 0.0},
    {MusAction.MUS: 0.9, MusAction.CORTA: 0.0},
    {},
])
def test_invalid_distribution_is_rejected(values):
    with pytest.raises(ValueError):
        ActionDistribution(values)


def test_sampling_rejects_positive_mass_on_illegal_action():
    distribution = ActionDistribution({WagerAction.FOLD: 1.0})
    with pytest.raises(ValueError):
        distribution.sample(random.Random(0), legal_wager_actions(None))


def test_fold_is_legal_only_when_responding_to_offer():
    opening = legal_wager_actions(WagerState(1, 1, None, False))
    response = legal_wager_actions(WagerState(2, 1, "A", False))
    assert WagerAction.FOLD not in opening
    assert WagerAction.MATCH_OR_PASS in opening
    assert WagerAction.FOLD in response
