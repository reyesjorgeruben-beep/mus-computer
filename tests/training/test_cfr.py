"""Regret arithmetic and information boundaries for sampled self-play."""

from types import SimpleNamespace

import pytest

from mus_computer.bots.strategies.actions import DecisionKind, MusAction
from mus_computer.cards.card import Card
from mus_computer.game.context import GlobalGameContext, SeatOrderEntry
from mus_computer.training.cfr import (
    CFRConfig, CFRPolicy, CFRTrainer, DecisionRecord, information_key, regret_match,
)


def test_regret_matching_normalizes_and_uses_prior_without_positive_regret():
    actions = ("cut", "mus")
    prior = {"cut": 0.7, "mus": 0.3}
    assert regret_match(actions, {"cut": -2, "mus": 0}, prior) == prior
    assert regret_match(actions, {"cut": 2, "mus": 6}, prior) == {
        "cut": 0.25, "mus": 0.75,
    }


def test_importance_weighted_regret_compares_all_actions_with_mixed_value():
    record = DecisionRecord(
        0, 0, "state", ("cut", "mus"), {"cut": 0.5, "mus": 0.5},
        {"cut": 0.25, "mus": 0.75}, "cut", 0.5, 0.2, 0.1,
    )
    updates = CFRTrainer.regret_increments(record, {"cut": 1, "mus": -1}, 2)
    assert updates == pytest.approx({"cut": 6, "mus": -2})
    assert sum(record.strategy[action] * updates[action]
               for action in record.actions) == pytest.approx(0)


def test_average_strategy_uses_reach_and_frozen_policy():
    policy = CFRPolicy()
    record = DecisionRecord(
        0, 0, "state", ("cut", "mus"), {"cut": 0.5, "mus": 0.5},
        {"cut": 0.25, "mus": 0.75}, "cut", 0.5, 0.2, 0.1,
    )
    frozen = policy.frozen()
    policy.apply([record], {"state": {"cut": 6, "mus": -2}})
    assert policy.nodes["state"].average() == pytest.approx({"cut": 0.25, "mus": 0.75})
    assert policy.nodes["state"].current() == pytest.approx({"cut": 1, "mus": 0})
    assert frozen.nodes == {}
    restored = CFRPolicy.from_snapshot({"information_states": policy.snapshot()})
    assert restored.snapshot() == policy.snapshot()


def test_policy_update_is_independent_of_player_processing_order():
    first = DecisionRecord(
        0, 0, "state", ("cut", "mus"), {"cut": 0.5, "mus": 0.5},
        {"cut": 0.5, "mus": 0.5}, "cut", 1, 1, 0.5,
    )
    second = DecisionRecord(
        1, 2, "state", ("cut", "mus"), {"cut": 0.5, "mus": 0.5},
        {"cut": 0.5, "mus": 0.5}, "mus", 0.5, 0.5, 0.25,
    )
    updates = {"state": {"cut": 2, "mus": -2}}
    forward, reverse = CFRPolicy(), CFRPolicy()
    forward.apply([first, second], updates)
    reverse.apply([second, first], updates)
    assert forward.snapshot() == reverse.snapshot()


def test_information_key_cannot_access_other_players_cards():
    public = GlobalGameContext(
        {"A": 0, "B": 0}, 0, None, None, (), {},
        (SeatOrderEntry("A1", "A"), SeatOrderEntry("B1", "B"),
         SeatOrderEntry("A2", "A"), SeatOrderEntry("B2", "B")),
        0, (0, 1, 2, 3),
    )
    private = SimpleNamespace(seat=0, team_name="A", cards=(Card.A, Card.R, Card.S, Card.C),
                              opponent_cards=(Card.R,) * 4)
    legal = tuple(MusAction)
    first = information_key(DecisionKind.MUS, public, private, legal)
    private.opponent_cards = (Card.A,) * 4
    assert information_key(DecisionKind.MUS, public, private, legal) == first
    private.cards = (Card.A,) * 4
    assert information_key(DecisionKind.MUS, public, private, legal) != first


def test_team_utility_follows_player_identity_after_seat_rotation():
    assert [CFRTrainer.team_utility("A", player_id) for player_id in range(4)] == [
        1, -1, 1, -1,
    ]
    assert [CFRTrainer.team_utility("B", player_id) for player_id in range(4)] == [
        -1, 1, -1, 1,
    ]


def test_real_sampled_iteration_updates_shared_policy(tmp_path):
    trainer = CFRTrainer(CFRConfig(iterations=1, seed=7, snapshot_every=1), run_dir=tmp_path)
    trainer.train()
    assert trainer.sampled_games > 1
    assert trainer.policy.nodes
    assert trainer.metrics[0]["average_strategy_vs_previous_checkpoint"] >= 0
    assert (tmp_path / "snapshots" / "iteration_000001.json").exists()
