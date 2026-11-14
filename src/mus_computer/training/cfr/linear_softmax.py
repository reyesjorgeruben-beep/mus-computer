"""Action-independent linear scores, softmax inference and target fitting.

Callers supply block names, action names and input names. This module knows
nothing about card phases, wagers, public history or CFR regret accounting.
An output distribution can be supplied as named inputs to another model.
"""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

Coefficients = dict[str, dict[str, dict[str, float]]]


@dataclass(frozen=True)
class BlockSpec:
    """Action and input names for one independent set of model parameters."""

    actions: tuple[str, ...]
    inputs: tuple[str, ...]


@dataclass(frozen=True)
class ProjectionExample:
    """One target distribution and positive fitting mass for a model block.

    ``actions`` contains the alternatives legal for this example. ``inputs``
    supplies declared predictor values; ``target`` maps those actions to desired
    probabilities. ``weight`` is already corrected by the caller's estimator.
    """

    block: str
    inputs: Mapping[str, float]
    actions: tuple[str, ...]
    target: Mapping[str, float]
    weight: float


def initialize_coefficients(schema: Mapping[str, BlockSpec]) -> Coefficients:
    """Create fresh zero weights from explicit block/action/input definitions.

    For ``{'route': BlockSpec(('left', 'right'), ('bias',))}``, return
    ``{'route': {'left': {'bias': 0.0}, 'right': {'bias': 0.0}}}``.
    Every action and every call receives independent mutable dictionaries.
    No phase or action catalogue is read from module-level game definitions.
    """
    return {
        block: {action: dict.fromkeys(spec.inputs, 0.0) for action in spec.actions}
        for block, spec in schema.items()
    }


def predict_distribution(
    coefficients: Mapping[str, Mapping[str, float]],
    inputs: Mapping[str, float],
    actions: Sequence[str],
) -> dict[str, float]:
    """Turn linear input scores into probabilities over the supplied actions.

    Each score is the sum of weight times input value. Subtracting the largest
    score before exponentiating keeps large finite scores numerically stable.
    Omitted action names receive no probability; input names must be declared.
    """
    logits = {
        action: math.fsum(
            coefficients[action][name] * value for name, value in inputs.items()
        )
        for action in actions
    }
    maximum = max(logits.values())
    weights = {action: math.exp(value - maximum) for action, value in logits.items()}
    total = math.fsum(weights.values())
    return {action: value / total for action, value in weights.items()}


def fit_targets(
    coefficients: Coefficients,
    examples: Sequence[ProjectionExample],
    learning_rate: float,
) -> None:
    """Apply one weighted cross-entropy step to each represented model block.

    Examples supply positive fitting masses, targets and legal actions. Weights
    normalize within each block after rescaling by the largest mass. Gradients
    accumulate against unchanged predictions before updating that block in place.
    The caller chooses targets and must not reapply its sampling corrections here.
    """
    grouped: dict[str, list[ProjectionExample]] = {}
    for example in examples:
        grouped.setdefault(example.block, []).append(example)
    for block, entries in grouped.items():
        scale = max(example.weight for example in entries)
        total = math.fsum(example.weight / scale for example in entries)
        gradients = {
            action: dict.fromkeys(values, 0.0)
            for action, values in coefficients[block].items()
        }
        for example in entries:
            predicted = predict_distribution(
                coefficients[block], example.inputs, example.actions
            )
            weight = (example.weight / scale) / total
            for action in example.actions:
                error = weight * (example.target[action] - predicted[action])
                for name, value in example.inputs.items():
                    gradients[action][name] += error * value
        for action, values in gradients.items():
            for name, gradient in values.items():
                coefficients[block][action][name] += learning_rate * gradient
