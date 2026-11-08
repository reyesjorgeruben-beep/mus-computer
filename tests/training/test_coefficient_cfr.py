"""Exact wager probabilities, survival, and frozen coefficient learning."""

import math
from dataclasses import replace

import pytest

from mus_computer.training.coefficient_cfr.policy import Action, Coefficients, Stage
from mus_computer.training.coefficient_cfr.tree import Settlement, WagerTree, build_wager_tree
from mus_computer.training.coefficient_cfr.round import Lance, Round, evaluate_round, sample_round
from mus_computer.training.coefficient_cfr.trainer import CoefficientTrainer, TrainingConfig


def test_context_probabilities_and_conditional_ordago():
    # fold, pass, match, opening bet, re-bid, ordago
    coefficients = Coefficients((0.8, 0.7, 0.2, 0.3, 0.4, 0.1),
                                (0.2, 0.3, 0.8, 0.7, 0.6, 0.5))
    mixed = [0.6 * a + 0.4 * b for a, b in zip(coefficients.losing, coefficients.winning)]
    fold, pass_, match, bet, rebid, ordago = mixed
    assert coefficients.distribution(0.4, Stage.OPEN) == pytest.approx({
        Action.PASS: pass_, Action.BET: bet * (1 - ordago), Action.ORDAGO: bet * ordago})
    assert coefficients.distribution(0.4, Stage.OFFER) == pytest.approx({
        Action.FOLD: (1 - rebid) * fold, Action.MATCH: (1 - rebid) * match,
        Action.RAISE: rebid * (1 - ordago), Action.ORDAGO: rebid * ordago})
    assert coefficients.distribution(0.4, Stage.COUNTER) == pytest.approx({
        Action.FOLD: 1 - rebid * ordago, Action.ORDAGO: rebid * ordago})
    assert coefficients.distribution(0.4, Stage.ORDAGO) == pytest.approx({Action.FOLD: fold, Action.MATCH: match})


@pytest.mark.parametrize('stage', list(Stage))
def test_local_gradient_matches_finite_differences(stage):
    coefficients = Coefficients()
    values = {a: float(2 * a - 3) for a in coefficients.distribution(0.4, stage)}
    gradient = coefficients.gradient(0.4, stage, values)
    for index in range(12):
        direction = tuple(1.0 if i == index else 0.0 for i in range(12))
        changed = coefficients.updated(direction, 1e-6)
        value = lambda policy: sum(p * values[a] for a, p in policy.distribution(0.4, stage).items())
        assert gradient[index] == pytest.approx((value(changed) - value(coefficients)) / 1e-6, abs=1e-5)


def test_tree_contains_only_bounded_stages_and_preserves_probability():
    tree = build_wager_tree((0, 1, 2, 3), (0.2, 0.8, 0.4, 0.6),
                            (Coefficients(), Coefficients()), 1, 0, (0, 0))
    assert sum(p for _, p in tree.outcomes) == pytest.approx(1)
    assert {node.stage for node in tree.decisions} == set(Stage)
    assert any(outcome.ordago for outcome, _ in tree.outcomes)
    assert all(outcome.points in (0, 1, 2, 4) for outcome, _ in tree.outcomes)
    assert any(node.seat == 3 and node.stage is Stage.OFFER for node in tree.decisions)
    assert any(node.seat == 3 and node.history == ('0:bet', '1:fold') for node in tree.decisions)
    assert any(node.stage is Stage.COUNTER and node.history == ('0:bet', '1:raise') for node in tree.decisions)
    for node in tree.decisions:
        assert sum(node.probabilities.values()) == pytest.approx(1)
        for outcomes in node.children.values():
            assert sum(p for _, p in outcomes) == pytest.approx(1)


def fixed_lance(name, outcomes):
    return Lance(name, WagerTree(tuple(outcomes), ()))


def test_survival_weights_next_lance_and_ordago_has_no_future_points():
    round_ = Round((10, 28), (
        fixed_lance('Grande', [(Settlement(0, 0, True), 0.25), (Settlement(1, 1), 0.75)]),
        fixed_lance('Chica', [(Settlement(1, 2), 1.0)]),
    ))
    result = evaluate_round(round_, (Coefficients(), Coefficients()))
    assert result.phase_reach == pytest.approx((1.0, 0.75))
    assert result.expected_points == pytest.approx((7.5, 2.25))
    assert {(outcome.scores, outcome.reason): outcome.probability for outcome in result.outcomes} == {
        ((40, 28), 'ordago'): 0.25, ((10, 31), 'hand'): 0.75,
    }


def test_forty_points_stops_later_lances_and_caps_awards():
    round_ = Round((39, 28), (
        fixed_lance('Grande', [(Settlement(0, 2), 1.0)]),
        fixed_lance('Chica', [(Settlement(1, 2), 1.0)]),
    ))
    result = evaluate_round(round_, (Coefficients(), Coefficients()))
    assert result.phase_reach == (1.0, 0)
    assert result.expected_points == (1, 0)
    assert result.outcomes[0].reason == 'points'


@pytest.mark.parametrize('team', [0, 1])
def test_round_gradient_holds_the_other_team_fixed(team):
    policy = Coefficients()
    result = sample_round(7, policy, details=True)
    assert sum(outcome.probability for outcome in result.outcomes) == pytest.approx(1)
    assert result.decisions
    assert all(penalty >= -1e-10 for decision in result.decisions for penalty in decision.penalties.values())
    for index in (0, 3, 4, 5, 7, 10, 11):
        changed = policy.updated(tuple(1.0 if i == index else 0 for i in range(12)), 1e-6)
        perturbed = sample_round(7, changed, policy) if team == 0 else sample_round(7, policy, changed)
        margin = lambda r: r.expected_points[team] - r.expected_points[1 - team]
        assert result.team_gradients[team][index] == pytest.approx(
            (margin(perturbed) - margin(result)) / 1e-6, abs=1e-3)


def test_update_keeps_coefficients_positive_and_bounded():
    result = Coefficients().updated((1000, -1000, 0, 2, -2, 3) * 2, 0.1)
    for row in (result.losing, result.winning):
        assert row[0] + row[2] == pytest.approx(1)
        assert row[1] + row[3] == pytest.approx(1)
        assert all(math.isfinite(weight) and 0 < weight < 1 for weight in row)


def test_ordago_update_does_not_rescale_any_other_coefficient():
    before = Coefficients()
    after = before.updated((0, 0, 0, 0, 0, 1) * 2, 0.1)
    for old, new in zip((before.losing, before.winning), (after.losing, after.winning)):
        assert new[:5] == pytest.approx(old[:5])
        assert new[5] > old[5]


def test_uncontested_phase_awards_only_eligible_winners_intrinsic_points():
    tree = build_wager_tree((1, 3), (0.2, 0.8, 0.4, 0.6),
                            (Coefficients(), Coefficients()), 0, 1, (0, 5))
    assert tree.outcomes == ((Settlement(1, 5), 1),)
    assert not tree.decisions


def test_initial_against_itself_has_zero_paired_margin():
    evaluation = CoefficientTrainer().evaluate_against_initial(pairs=2)
    assert evaluation['mean_piedra_margin'] == pytest.approx(0, abs=1e-12)
    assert evaluation['approx_95pct_half_width'] == pytest.approx(0, abs=1e-12)


def test_batch_averages_sixteen_frozen_gradients_before_one_update(tmp_path):
    config = TrainingConfig(rounds=1, batch_size=16, workers=1, seed=7)
    trainer = CoefficientTrainer(config)
    before = trainer.coefficients
    results = []

    def evaluate(seed, coefficients):
        assert trainer.coefficients == before
        assert coefficients == before
        result = sample_round(seed, coefficients)
        results.append(result)
        return result

    trainer.train(tmp_path, evaluator=evaluate)
    assert len(results) == 16
    gradient = tuple(sum(r.team_gradients[t][i] for r in results for t in (0, 1)) / (16 * 2 * 40)
                     for i in range(12))
    assert trainer.coefficients == before.updated(gradient, config.learning_rate)
    assert (tmp_path / 'training.json').exists()
    assert len(trainer.metrics) == 1


def test_parallel_and_serial_training_are_identical(tmp_path):
    config = TrainingConfig(rounds=2, batch_size=2, workers=1, seed=19)
    serial = CoefficientTrainer(config)
    parallel = CoefficientTrainer(replace(config, workers=2))
    serial.train(tmp_path / 'serial')
    parallel.train(tmp_path / 'parallel')
    assert serial.coefficients == parallel.coefficients
    assert serial.metrics == parallel.metrics


@pytest.mark.parametrize('changes', [{'rounds': 0}, {'batch_size': 0}, {'workers': 0},
                                   {'learning_rate': float('nan')}, {'learning_rate': -1}])
def test_invalid_training_configuration_is_rejected(changes):
    with pytest.raises(ValueError):
        TrainingConfig(**changes)
