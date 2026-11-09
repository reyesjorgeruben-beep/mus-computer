"""Real adapter/artifact boundaries, paired matches and champion selection."""

import json
import random
from pathlib import Path

import pytest

from mus_computer.bots.random_decision_bot import RandomDecisionBot
from mus_computer.training.experiments.contracts import (
    DesignSpec,
    artifact_ref,
    load_artifact,
    train_artifact,
)
from mus_computer.training.experiments.evaluation import paired_matches
from mus_computer.training.experiments.pipeline import (
    SelectionRule,
    bootstrap,
    confirm,
    promote,
    selection_reasons,
    trial,
)

ADAPTER = "mus_computer.training.experiments.adapters:StaticAdapter"
CFR = "mus_computer.training.experiments.adapters:CFRAdapter"


class IndependentAdapter:
    """Test-local native format proving orchestration has no CFR assumptions."""

    version = "independent-v1"

    def train(self, config, *, seed, run_dir):
        path = run_dir / "native.txt"
        path.write_text(f"{config['message']}:{seed}", encoding="utf-8")
        return path

    def load(self, checkpoint, config):
        assert checkpoint.read_text(encoding="utf-8").startswith(config["message"])

        def player(name, team, player_id, seed):
            return RandomDecisionBot(name, team, random.Random(seed))

        return player


def static(root, name="random_decisions"):
    return train_artifact(DesignSpec(ADAPTER, {"strategy": name}), root, seed=7)


def test_native_artifact_supports_independent_adapters_and_refuses_overwrite(tmp_path):
    spec = DesignSpec(f"{__name__}:IndependentAdapter", {"message": "native"})
    manifest = train_artifact(spec, tmp_path / "model", seed=9)
    data, factory = load_artifact(artifact_ref(manifest))
    assert data["checkpoint"] == "native.txt"
    assert data["training_seed"] == 9
    assert callable(factory)
    with pytest.raises(FileExistsError):
        train_artifact(spec, tmp_path / "model", seed=9)


@pytest.mark.parametrize(
    "damage", ["checkpoint", "missing", "version", "escape", "manifest"]
)
def test_invalid_artifacts_fail_before_inference(tmp_path, damage):
    manifest = static(tmp_path / "model")
    ref = artifact_ref(manifest)
    data = json.loads(manifest.read_text())
    checkpoint = manifest.parent / data["checkpoint"]
    if damage == "checkpoint":
        checkpoint.write_text("corrupt")
    elif damage == "missing":
        checkpoint.unlink()
    elif damage == "version":
        data["adapter_version"] = "unavailable"
    elif damage == "escape":
        data["checkpoint"] = "../outside.json"
    else:
        data["training_seed"] = 999
    if damage in {"version", "escape", "manifest"}:
        manifest.write_text(json.dumps(data))
        if damage != "manifest":
            ref = artifact_ref(manifest)
    with pytest.raises((ValueError, FileNotFoundError)):
        load_artifact(ref)


def test_adapter_checkpoint_cannot_escape_artifact_root(tmp_path):
    class EscapingAdapter(IndependentAdapter):
        def train(self, config, *, seed, run_dir):
            outside = run_dir.parent / "outside.txt"
            outside.write_text("outside")
            return outside

    # Dynamic test plugin follows the same import contract as external designs.
    globals()["EscapingAdapter"] = EscapingAdapter
    with pytest.raises(ValueError):
        train_artifact(
            DesignSpec(f"{__name__}:EscapingAdapter", {}), tmp_path / "model", seed=1
        )
    assert not (tmp_path / "model" / "artifact.json").exists()


def test_real_cfr_average_checkpoint_round_trip(tmp_path):
    path = train_artifact(
        DesignSpec(CFR, {"policy": "glm", "iterations": 1}), tmp_path / "cfr", seed=7
    )
    data, factory = load_artifact(artifact_ref(path))
    assert data["spec"]["config"]["policy"] == "glm"
    assert callable(factory)


def test_real_paired_matches_are_seeded_reproducible_and_restore_rng(tmp_path):
    left = artifact_ref(static(tmp_path / "left", "mus_maestro"))
    right = artifact_ref(static(tmp_path / "right"))
    before = random.getstate()
    result = paired_matches(left, right, pairs=3, seed=41, wins_to_match=2)
    assert random.getstate() == before
    assert result == paired_matches(left, right, pairs=3, seed=41, wins_to_match=2)
    assert len(result["records"]) == 6
    for index in range(0, 6, 2):
        a, b = result["records"][index : index + 2]
        assert (a["left_team"], b["left_team"]) == ("A", "B")
        assert a["seed"] == b["seed"]
        assert max(a["wins_a"], a["wins_b"]) == 2
        assert max(b["wins_a"], b["wins_b"]) == 2
    assert len(result["pair_scores"]) == 3
    held_out = paired_matches(left, right, pairs=3, seed=41, namespace="confirmation")
    assert {r["seed"] for r in result["records"]}.isdisjoint(
        r["seed"] for r in held_out["records"]
    )


def test_evaluator_accepts_different_native_designs(tmp_path):
    native = train_artifact(
        DesignSpec(f"{__name__}:IndependentAdapter", {"message": "own"}),
        tmp_path / "native",
        seed=7,
    )
    cfr = train_artifact(
        DesignSpec(CFR, {"policy": "glm", "iterations": 1}), tmp_path / "glm", seed=7
    )
    result = paired_matches(artifact_ref(cfr), artifact_ref(native), pairs=1, seed=7)
    assert result["matches"] == 2
    assert result["win_rate"] in (0, 0.5, 1)


def test_pipeline_requires_follow_up_and_keeps_champion_on_tie(tmp_path):
    registry = tmp_path / "champion.json"
    spec = DesignSpec(ADAPTER, {"strategy": "random_decisions"})
    bootstrap(registry, spec, tmp_path / "champion", seed=7)
    original = registry.read_bytes()
    with pytest.raises(FileExistsError):
        bootstrap(registry, spec, tmp_path / "must-not-train", seed=7)
    assert not (tmp_path / "must-not-train").exists()
    first = trial(
        registry,
        spec,
        tmp_path / "first",
        seed=7,
        pairs=1,
        rules=SelectionRule(min_pairs=2),
    )
    with pytest.raises(ValueError, match="follow-up"):
        confirm(registry, first, pairs=32)
    with pytest.raises(ValueError, match="rationale"):
        trial(registry, spec, tmp_path / "invalid", seed=7, pairs=1, parent=first)
    second = trial(
        registry,
        spec,
        tmp_path / "second",
        seed=7,
        pairs=1,
        parent=first,
        rationale="Replicate the tied first comparison to verify determinism.",
    )
    report = json.loads(second.read_text())
    assert report["attempt"] == 2
    assert report["comparisons"]["head_to_head"]["win_rate"] == 0.5
    assert report["baselines"] == json.loads(first.read_text())["baselines"]
    with pytest.raises(ValueError, match="pairs"):
        confirm(registry, second, pairs=1)
    confirmation = confirm(registry, second, pairs=2)
    assert promote(registry, confirmation)["promoted"] is False
    assert registry.read_bytes() == original
    with pytest.raises(FileExistsError):
        confirm(registry, second, pairs=2)


def test_stale_or_tampered_attempt_cannot_be_used_for_confirmation(tmp_path):
    registry = tmp_path / "champion.json"
    spec = DesignSpec(ADAPTER, {"strategy": "random_decisions"})
    bootstrap(registry, spec, tmp_path / "champion", seed=7)
    first = trial(registry, spec, tmp_path / "first", pairs=1)
    second = trial(
        registry,
        spec,
        tmp_path / "second",
        pairs=1,
        parent=first,
        rationale="Replication.",
    )
    other = static(tmp_path / "other", "heuristic")
    pointer = json.loads(registry.read_text())
    pointer["artifact"] = artifact_ref(other)
    registry.write_text(json.dumps(pointer))
    with pytest.raises(ValueError, match="champion"):
        confirm(registry, second, pairs=32)


def test_selection_checks_head_to_head_static_regression_and_sample_size():
    rules = SelectionRule()
    comparison: dict = {
        "head_to_head": {"matches": 64, "win_rate": 0.6},
        "baselines": {"static": {"delta": 0}},
    }
    assert selection_reasons(comparison, rules) == []
    comparison["baselines"]["static"]["delta"] = -0.1
    assert "regression" in " ".join(selection_reasons(comparison, rules))
    comparison["head_to_head"] = {"matches": 64, "win_rate": 0.5}
    assert "head-to-head" in " ".join(selection_reasons(comparison, rules))
    comparison["head_to_head"] = {"matches": 2, "win_rate": 1}
    assert "pairs" in " ".join(selection_reasons(comparison, rules))


def test_promotion_validates_raw_evidence_and_preserves_previous_artifacts(
    tmp_path, monkeypatch
):
    from mus_computer.training.experiments.evaluation import seed_for

    def controlled_comparison(
        champion, challenger, baselines, *, pairs, seed, wins_to_match, namespace
    ):
        # Coordinator fixture with hand-checked all-wins pair scores. Gameplay
        # itself is exercised by the real mixed-design tests above.
        def series(all_wins):
            records = []
            for pair in range(pairs):
                for team in ("A", "B"):
                    winner = team if all_wins else "A"
                    records.append(
                        {
                            "pair": pair,
                            "left_team": team,
                            "seed": seed_for(seed, namespace, pair),
                            "winner": winner,
                            "wins_a": wins_to_match if winner == "A" else 0,
                            "wins_b": wins_to_match if winner == "B" else 0,
                        }
                    )
            return {
                "wins": 2 * pairs if all_wins else pairs,
                "matches": 2 * pairs,
                "win_rate": 1.0 if all_wins else 0.5,
                "pair_scores": [1.0 if all_wins else 0.5] * pairs,
                "pair_standard_error": 0.0,
                "records": records,
            }

        return {
            "head_to_head": series(True),
            "baselines": {
                name: {
                    "champion": series(False),
                    "challenger": series(True),
                    "delta": 0.5,
                    "delta_pair_standard_error": 0.0,
                }
                for name in baselines
            },
        }

    monkeypatch.setattr(
        "mus_computer.training.experiments.pipeline.compare", controlled_comparison
    )
    registry = tmp_path / "champion.json"
    spec = DesignSpec(ADAPTER, {"strategy": "random_decisions"})
    bootstrap(registry, spec, tmp_path / "champion")
    original = json.loads(registry.read_text())["artifact"]
    first = trial(
        registry, spec, tmp_path / "first", pairs=2, rules=SelectionRule(min_pairs=2)
    )
    second = trial(
        registry,
        DesignSpec(ADAPTER, {"strategy": "heuristic"}),
        tmp_path / "second",
        pairs=2,
        parent=first,
        rationale="Compare a strength-aware alternative.",
    )
    confirmation = confirm(registry, second, pairs=2)
    saved = confirmation.read_text()
    damaged = json.loads(saved)
    damaged["comparisons"]["head_to_head"]["wins"] = 0
    confirmation.write_text(json.dumps(damaged))
    with pytest.raises(ValueError, match="evidence"):
        promote(registry, confirmation)
    assert json.loads(registry.read_text())["artifact"] == original
    confirmation.write_text(saved)
    assert promote(registry, confirmation)["promoted"] is True
    pointer = json.loads(registry.read_text())
    assert pointer["artifact"] == json.loads(second.read_text())["challenger"]
    assert pointer["history"][0]["previous"] == original
    load_artifact(original)


def test_failed_training_leaves_no_artifact_and_records_failure(tmp_path):
    class FailingAdapter(IndependentAdapter):
        def train(self, config, *, seed, run_dir):
            raise RuntimeError("Numerical failure")

    globals()["FailingAdapter"] = FailingAdapter
    registry = tmp_path / "champion.json"
    with pytest.raises(RuntimeError, match="Numerical"):
        bootstrap(
            registry, DesignSpec(f"{__name__}:FailingAdapter", {}), tmp_path / "failed"
        )
    assert not registry.exists()
    assert not registry.with_name("champion.json.lock").exists()
    assert (tmp_path / "failed" / "failure.json").exists()
    assert not (tmp_path / "failed" / "artifact.json").exists()


def test_custom_baseline_design_needs_no_coordinator_model_branch(tmp_path):
    spec = DesignSpec(ADAPTER, {"strategy": "random_decisions"})
    registry = tmp_path / "champion.json"
    bootstrap(registry, spec, tmp_path / "champion")
    native = DesignSpec(f"{__name__}:IndependentAdapter", {"message": "new-baseline"})
    report_path = trial(
        registry,
        spec,
        tmp_path / "trial",
        pairs=1,
        baseline_specs={"own-design": native},
    )
    report = json.loads(report_path.read_text())
    assert set(report["comparisons"]["baselines"]) == {"own-design"}
    data, _ = load_artifact(report["baselines"]["own-design"])
    assert data["spec"]["config"] == {"message": "new-baseline"}


@pytest.mark.parametrize(
    "design",
    [
        DesignSpec(ADAPTER, {"strategy": "heuristic"}),
        DesignSpec(CFR, {"policy": "glm", "iterations": 1}),
    ],
)
@pytest.mark.parametrize(
    "dependency", ["constants.py", "probabilities/data/probability_tables.pkl"]
)
def test_runtime_input_change_invalidates_frozen_inference(
    tmp_path, monkeypatch, design, dependency
):
    from mus_computer.training.experiments import adapters

    manifest = train_artifact(design, tmp_path / "model", seed=7)
    package = Path(adapters.__file__).resolve().parents[2]
    target = package / dependency
    read_bytes = Path.read_bytes

    def changed_input(path):
        value = read_bytes(path)
        return value + b"changed runtime input" if path == target else value

    # Isolate dependency bytes at the file-read boundary; never modify the
    # repository's real constants or bundled probability table in a test.
    monkeypatch.setattr(Path, "read_bytes", changed_input)
    with pytest.raises(ValueError, match="inference version"):
        load_artifact(artifact_ref(manifest))


def test_directory_checkpoint_rejects_new_payload_files(tmp_path):
    class DirectoryAdapter(IndependentAdapter):
        def train(self, config, *, seed, run_dir):
            native = run_dir / "native"
            native.mkdir()
            (native / "base.txt").write_text("original model")
            return native

        def load(self, checkpoint, config):
            return lambda name, team, player_id, seed: RandomDecisionBot(
                name, team, random.Random(seed)
            )

    globals()["DirectoryAdapter"] = DirectoryAdapter
    manifest = train_artifact(
        DesignSpec(f"{__name__}:DirectoryAdapter", {}), tmp_path / "model", seed=7
    )
    load_artifact(artifact_ref(manifest))
    (manifest.parent / "native" / "override.txt").write_text("changed model")
    with pytest.raises(ValueError, match="payload"):
        load_artifact(artifact_ref(manifest))
