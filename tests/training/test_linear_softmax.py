"""Action-independent initialization, inference and weighted projection."""

import math

import pytest

from mus_computer.training.cfr.linear_softmax import (
    BlockSpec,
    ProjectionExample,
    fit_targets,
    initialize_coefficients,
    predict_distribution,
)


def test_explicit_schema_supports_non_game_actions_and_independent_parameters():
    schema = {"routing": BlockSpec(("left", "right"), ("bias", "distance"))}
    first = initialize_coefficients(schema)
    second = initialize_coefficients(schema)
    assert first == {
        "routing": {
            "left": {"bias": 0.0, "distance": 0.0},
            "right": {"bias": 0.0, "distance": 0.0},
        }
    }
    first["routing"]["left"]["distance"] = 2.0
    assert first["routing"]["right"]["distance"] == 0.0
    assert second["routing"]["left"]["distance"] == 0.0


def test_predict_distribution_is_stable_and_masks_to_supplied_actions():
    coefficients = {
        "left": {"bias": 1000.0},
        "right": {"bias": 1000.0 + math.log(3)},
        "disabled": {"bias": 2000.0},
    }
    result = predict_distribution(coefficients, {"bias": 1.0}, ("left", "right"))
    assert set(result) == {"left", "right"}
    assert result["right"] == pytest.approx(0.75)
    assert sum(result.values()) == pytest.approx(1.0)


def test_fit_targets_normalizes_weights_and_keeps_blocks_separate():
    spec = BlockSpec(("left", "right"), ("bias",))
    coefficients = initialize_coefficients({"routing": spec, "untouched": spec})
    examples = [
        ProjectionExample(
            "routing", {"bias": 1.0}, spec.actions, {"left": 0.0, "right": 1.0}, 3.0
        ),
        ProjectionExample(
            "routing", {"bias": 1.0}, spec.actions, {"left": 1.0, "right": 0.0}, 1.0
        ),
    ]
    fit_targets(coefficients, examples, 0.1)
    assert coefficients["routing"]["right"]["bias"] == pytest.approx(0.025)
    assert coefficients["routing"]["left"]["bias"] == pytest.approx(-0.025)
    assert coefficients["untouched"] == {"left": {"bias": 0.0}, "right": {"bias": 0.0}}


def test_model_output_can_be_used_as_another_models_input():
    coefficients = initialize_coefficients(
        {
            "first": BlockSpec(("route", "stop"), ("bias",)),
            "second": BlockSpec(("accept", "reject"), ("upstream_probability",)),
        }
    )
    first = predict_distribution(
        coefficients["first"], {"bias": 1.0}, ("route", "stop")
    )
    coefficients["second"]["accept"]["upstream_probability"] = 2 * math.log(3)
    second = predict_distribution(
        coefficients["second"],
        {"upstream_probability": first["route"]},
        ("accept", "reject"),
    )
    assert first["route"] == pytest.approx(0.5)
    assert second["accept"] == pytest.approx(0.75)
