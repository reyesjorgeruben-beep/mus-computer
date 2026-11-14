"""Trajectory-sampled Monte Carlo CFR for the existing four-seat game.

One real game samples chance and a behavior-policy trajectory. For each seat,
one of its visited decisions is sampled uniformly and every legal action there
is evaluated by replaying the identical prefix and rolling out the current
policy. If h is the sampled history, its regret multiplier is

    N_i * pi_{-i}(h) / q_actions(h)

where N_i is that seat's number of visited decisions, pi_{-i} is the product
of *target* probabilities of all other seats' prefix actions, and q_actions is
the product of the exploratory behavior probabilities of all prefix actions.
Chance is sampled by the actual deck, so its probability cancels. This is an
unbiased, high-variance, action-expanded trajectory estimator of the CFR
counterfactual regret increment. The average-strategy accumulator uses
pi_i(h) / q_actions(h), again integrating chance by sampling. A single frozen
strategy is used for every seat and rollout in an iteration; only afterward
are regret and average-strategy sums applied.

The information-state table is deliberately tabular and potentially large.
Full public history plus own cards prevents hidden-card leakage, but the game
clears history between hands, so the abstraction does not have perfect recall.
Together with four-player team play, this means standard two-player zero-sum
convergence guarantees do not apply.

Module responsibilities:
- config: training settings and validation.
- state: observable information keys, action names, and decision records.
- policy: regret tables, action probabilities, averages, and serialization.
- features/glm_policy: optional phase-specific additive betting projection.
- sampling: exploratory sampling, forced replay, and reach tracking.
- player: the adapter between the game bot and the sampled policy.
- trainer: self-play, counterfactual evaluations, metrics, and snapshots.
- cli: command-line arguments and training startup.

Public names remain available from mus_computer.training.cfr.
"""

from .cli import main
from .config import CFRConfig
from .glm_policy import GLMCFRPolicy
from .player import CFRBotPlayer
from .policy import CFRPolicy, RegretNode, regret_match
from .sampling import DecisionController
from .state import Action, DecisionRecord, action_name, information_key
from .trainer import CFRTrainer

__all__ = [
    "Action",
    "CFRBotPlayer",
    "CFRConfig",
    "CFRPolicy",
    "CFRTrainer",
    "DecisionController",
    "DecisionRecord",
    "GLMCFRPolicy",
    "RegretNode",
    "action_name",
    "information_key",
    "main",
    "regret_match",
]
