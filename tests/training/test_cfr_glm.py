"""Phase separation, observable history, weighted fitting and reproducibility."""

import json
import math
from dataclasses import replace

import pytest

from mus_computer.bots.strategies.actions import WagerAction, legal_wager_actions
from mus_computer.cards.card import Card
from mus_computer.game.context import GlobalGameContext, SeatOrderEntry, WagerState
from mus_computer.game.phases import PhaseName
from mus_computer.game.team import Team
from mus_computer.training.cfr import CFRConfig, CFRPolicy, CFRTrainer, DecisionRecord
from mus_computer.training.cfr.features import betting_features
from mus_computer.training.cfr.glm_policy import GLMCFRPolicy
from mus_computer.training.cfr.state import action_name
from tests.conftest import ScriptedPlayer


def context(phase=PhaseName.CHICA, events=(), wager=None, team="A"):
    public = GlobalGameContext(
        {"A": 0, "B": 0},
        0,
        phase,
        wager,
        tuple(events),
        {},
        (
            SeatOrderEntry("A1", "A"),
            SeatOrderEntry("B1", "B"),
            SeatOrderEntry("A2", "A"),
            SeatOrderEntry("B2", "B"),
        ),
        0,
        (0, 1, 2, 3),
    )
    player = ScriptedPlayer("A1" if team == "A" else "B1", Team(team))
    player.receive_cards([Card.R, Card.R, Card.C, Card.A])
    return public, player.decision_context(public, 0 if team == "A" else 1)


def features(phase=PhaseName.CHICA, events=(), wager=None, team="A"):
    return betting_features(*context(phase, events, wager, team))


PASS = action_name(WagerAction.MATCH_OR_PASS)
BET = action_name(WagerAction.RAISE_2)
FOLD = action_name(WagerAction.FOLD)
ACTIONS = (PASS, BET)
PRIOR = {PASS: 0.5, BET: 0.5}


@pytest.mark.parametrize(
    "event", ["envida", "envida 5", "envida 3 (total 7)", "ordago"]
)
def test_only_opponent_wagers_activate_history(event):
    assert (
        features(events=[f"Grande | B1: {event}"]).values["opponent_wager_Grande"] == 1
    )
    assert (
        features(events=[f"Grande | A2: {event}"]).values["opponent_wager_Grande"] == 0
    )
    assert (
        features(events=[f"Grande | B1: {event}"], team="B").values[
            "opponent_wager_Grande"
        ]
        == 0
    )


@pytest.mark.parametrize("event", ["paso", "quiero", "no quiero", "envidamos"])
def test_nonoffers_and_unknown_players_do_not_activate_history(event):
    assert (
        features(events=[f"Grande | B2: {event}", "Grande | Unknown: envida"]).values[
            "opponent_wager_Grande"
        ]
        == 0
    )


def test_chronological_features_and_existing_private_strength():
    events = [f"{p} | B1: envida" for p in PhaseName]
    for phase, previous in [
        (PhaseName.GRANDE, ()),
        (PhaseName.CHICA, ("Grande",)),
        (PhaseName.PARES, ("Grande", "Chica")),
        (PhaseName.JUEGO, ("Grande", "Chica", "Pares")),
        (PhaseName.PUNTO, ("Grande", "Chica", "Pares")),
    ]:
        public, private = context(phase, events)
        result = betting_features(public, private)
        assert result.values == {
            "baseline": 1.0,
            "hand_strength": 1 - private.statistics.outcomes_by_phase[phase].p_loss,
            **{f"opponent_wager_{p}": 1.0 for p in previous},
        }


def predict(policy, feature, actions=ACTIONS, average=False):
    return policy.probabilities(
        "unseen",
        actions,
        {a: 1 / len(actions) for a in actions},
        features=feature,
        average=average,
    )


def test_chica_history_changes_logits_without_changing_grande():
    policy = GLMCFRPolicy()
    grande = predict(policy, features(PhaseName.GRANDE))
    policy.current_coefficients["Chica/opening"][BET]["opponent_wager_Grande"] = (
        math.log(3)
    )
    assert predict(policy, features())[BET] == pytest.approx(0.5)
    assert predict(policy, features(events=["Grande | B2: envida"]))[
        BET
    ] == pytest.approx(0.75)
    assert predict(policy, features(PhaseName.GRANDE, ["Chica | B2: envida"])) == grande


def test_pares_effects_are_independent_and_additive_in_log_odds():
    policy = GLMCFRPolicy()
    block = policy.current_coefficients["Pares/opening"][BET]
    block["opponent_wager_Grande"] = math.log(2)
    block["opponent_wager_Chica"] = math.log(3)
    for events, odds in [
        ([], 1),
        (["Grande | B1: envida"], 2),
        (["Chica | B2: envida"], 3),
        (["Grande | B1: envida", "Chica | B2: envida"], 6),
    ]:
        p = predict(policy, features(PhaseName.PARES, events))
        assert p[BET] / p[PASS] == pytest.approx(odds)


def test_game_pequena_event_label_is_chica_history_and_betting_stage():
    events = ["Pequeña | A1: envida", "Pequeña | B1: envida 3 (total 5)"]
    assert features(PhaseName.PARES, events).values["opponent_wager_Chica"] == 1
    assert (
        features(events=events, wager=WagerState(5, 2, "B")).block
        == "Chica/counter_raise"
    )


def test_response_actions_have_independent_history_effects():
    policy = GLMCFRPolicy()
    f = features(events=["Grande | B1: envida"], wager=WagerState(2, 1, "B"))
    block = policy.current_coefficients["Chica/response"]
    block[BET]["opponent_wager_Grande"] = math.log(2)
    block[FOLD]["opponent_wager_Grande"] = -math.log(2)
    p = predict(policy, f, (PASS, BET, FOLD))
    assert p[BET] > p[PASS] > p[FOLD]
    assert predict(policy, features())[BET] == pytest.approx(0.5)


@pytest.mark.parametrize(
    "wager,events,stage",
    [
        (None, (), "opening"),
        (WagerState(2, 1, "B"), ("Chica | B1: envida",), "response"),
        (
            WagerState(4, 2, "B"),
            ("Chica | A1: envida", "Chica | B1: envida 2 (total 4)"),
            "counter_raise",
        ),
        (WagerState(2, 1, "B", True), ("Chica | B1: ordago",), "ordago_response"),
    ],
)
def test_stages_and_stable_legal_softmax(wager, events, stage):
    policy = GLMCFRPolicy()
    f = features(events=events, wager=wager)
    assert f.block == f"Chica/{stage}"
    actions = tuple(
        action_name(a) for a in WagerAction if a in legal_wager_actions(wager)
    )
    policy.current_coefficients[f.block][actions[0]]["baseline"] = 1000
    p = predict(policy, f, actions)
    assert set(p) == set(actions)
    assert sum(p.values()) == pytest.approx(1)
    assert all(math.isfinite(v) and 0 <= v <= 1 for v in p.values())


def record(key, strategy, feature, own=1, behavior=1):
    return DecisionRecord(
        0, 0, key, ACTIONS, PRIOR, strategy, PASS, own, 1, behavior, feature
    )


def test_projection_uses_regret_targets_and_separate_reach_weighted_average():
    policy = GLMCFRPolicy(learning_rate=0.1)
    f = features()
    records = [
        record("first", {PASS: 0.8, BET: 0.2}, f, own=0.5, behavior=0.1),
        record("second", {PASS: 0.2, BET: 0.8}, f),
    ]
    policy.apply(records, {"first": {PASS: -3, BET: 3}, "second": {PASS: 1, BET: -1}})
    # Current target bet=(3*1+1*0)/4=.75; average target bet=(5*.2+1*.8)/6=.3.
    assert policy.current_coefficients[f.block][BET]["baseline"] == pytest.approx(0.025)
    assert policy.average_coefficients[f.block][BET]["baseline"] == pytest.approx(-0.02)
    assert predict(policy, f)[BET] > 0.5
    assert predict(policy, f, average=True)[BET] < 0.5
    assert policy.nodes["first"].strategy_sum[BET] == pytest.approx(1)
    assert policy.nodes["first"].regrets[BET] == 3
    frozen = policy.frozen()
    restored = CFRPolicy.from_snapshot(
        {"information_states": json.loads(json.dumps(policy.snapshot()))}
    )
    assert isinstance(restored, GLMCFRPolicy)
    assert restored.snapshot() == policy.snapshot()
    policy.apply(records, {})
    assert frozen.snapshot() == restored.snapshot()


def test_glm_does_not_train_mus_or_discard():
    policy = GLMCFRPolicy()
    r = replace(
        record("mus", PRIOR, None),
        actions=("mus", "cut"),
        prior={"mus": 0.7, "cut": 0.3},
        strategy={"mus": 0.7, "cut": 0.3},
        selected="mus",
    )
    policy.apply([r], {"mus": {"mus": 10, "cut": -10}})
    assert policy.nodes == {}
    assert policy.probabilities("mus", r.actions, r.prior) == r.prior


def test_seeded_self_play_and_checkpoint_continuation(tmp_path):
    config = CFRConfig(iterations=2, seed=7, policy="glm")
    first, second = CFRTrainer(config, run_dir=tmp_path), CFRTrainer(config)
    assert first.iterate(1) == second.iterate(1)
    assert first.policy.snapshot() == second.policy.snapshot()
    assert isinstance(first.policy, GLMCFRPolicy)
    assert first.policy.current_coefficients != GLMCFRPolicy().current_coefficients
    path = first.save_snapshot(1)
    restored = CFRTrainer.from_snapshot(path, run_dir=tmp_path)
    assert restored.iterate(2) == first.iterate(2) == second.iterate(2)
    assert (
        restored.policy.snapshot()
        == first.policy.snapshot()
        == second.policy.snapshot()
    )
    assert (
        restored._play(
            123, restored.policy, exploration=0, average=True, action_seed=456
        )[0]
        == first._play(123, first.policy, exploration=0, average=True, action_seed=456)[
            0
        ]
    )


def test_tabular_remains_default():
    assert type(CFRTrainer(CFRConfig()).policy) is CFRPolicy


def test_train_resumes_checkpoint_without_repeating_iterations(tmp_path):
    original = CFRTrainer(
        CFRConfig(iterations=2, seed=8, policy="glm", snapshot_every=1),
        run_dir=tmp_path,
    )
    original.train()
    restored = CFRTrainer.from_snapshot(
        tmp_path / "snapshots" / "iteration_000001.json", run_dir=tmp_path / "resumed"
    )
    restored.train()
    assert restored.metrics == original.metrics
    assert restored.sampled_games == original.sampled_games
    assert restored.policy.snapshot() == original.policy.snapshot()


def test_glm_counterfactual_selection_counts_only_betting_decisions(monkeypatch):
    trainer = CFRTrainer(CFRConfig(iterations=1, seed=7, policy="glm"))
    trajectories = []
    selected = []
    play = trainer._play
    regret_increments = trainer.regret_increments

    def observe_play(*args, **kwargs):
        winner, records = play(*args, **kwargs)
        if records:
            trajectories.extend(records)
        return winner, records

    def observe_regrets(record, utilities, count):
        selected.append((record, count))
        return regret_increments(record, utilities, count)

    monkeypatch.setattr(trainer, "_play", observe_play)
    monkeypatch.setattr(trainer, "regret_increments", observe_regrets)
    trainer.iterate(1)
    assert selected
    assert any(record.features is None for record in trajectories)
    for record, count in selected:
        assert record.features is not None
        assert count == sum(
            r.seat == record.seat and r.features is not None for r in trajectories
        )
