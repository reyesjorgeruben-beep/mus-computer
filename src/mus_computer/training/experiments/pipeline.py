"""Recorded attempts, held-out confirmation and explicit champion promotion."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from .adapters import STATIC_STRATEGIES
from .contracts import (
    DesignSpec,
    artifact_ref,
    checked_ref,
    load_artifact,
    read_json,
    train_artifact,
    write_json,
)
from .evaluation import compare, seed_for, validate_evidence

STATIC_ADAPTER = "mus_computer.training.experiments.adapters:StaticAdapter"


@dataclass(frozen=True)
class SelectionRule:
    min_pairs: int = 32
    win_rate: float = 0.55
    max_regression: float = 0.05

    def __post_init__(self) -> None:
        if type(self.min_pairs) is not int or self.min_pairs < 1:
            raise ValueError("Minimum confirmation pairs must be positive")
        if not math.isfinite(self.win_rate) or not 0.5 < self.win_rate <= 1:
            raise ValueError("Head-to-head threshold must be in (0.5, 1]")
        if not math.isfinite(self.max_regression) or not 0 <= self.max_regression <= 1:
            raise ValueError("Regression tolerance must be in [0, 1]")


@contextmanager
def _registry_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    lock = path.with_name(path.name + ".lock")
    with lock.open("x", encoding="utf-8"):
        pass
    try:
        yield
    finally:
        lock.unlink()


def _replace_pointer(path: Path, data: Mapping) -> None:
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        write_json(temporary, data)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _champion(path: Path) -> dict:
    pointer = read_json(path)
    if pointer.get("schema_version") != 1:
        raise ValueError("Unsupported champion registry")
    load_artifact(pointer["artifact"])
    return pointer


def bootstrap(
    registry: Path, spec: DesignSpec, run_dir: Path, *, seed: int = 7
) -> Path:
    registry = Path(registry).resolve()
    with _registry_lock(registry):
        if registry.exists():
            raise FileExistsError(
                "Champion already exists; use trial without retraining it"
            )
        artifact = train_artifact(spec, run_dir, seed=seed_for(seed, "training"))
        load_artifact(artifact_ref(artifact))
        _replace_pointer(
            registry,
            {"schema_version": 1, "artifact": artifact_ref(artifact), "history": []},
        )
    return registry


def _lineage(report: dict) -> int:
    """Verify the attempt chain before it can satisfy the follow-up requirement."""
    expected, seen = report["attempt"], set()
    current = report
    while True:
        if current.get("stage") != "development" or current["attempt"] != expected:
            raise ValueError("Invalid development attempt chain")
        if (
            current["champion"] != report["champion"]
            or current["rules"] != report["rules"]
            or current["baselines"] != report["baselines"]
        ):
            raise ValueError("Attempt chain changed champion, rules or baseline suite")
        parent = current.get("parent")
        if not parent:
            if expected != 1:
                raise ValueError("Missing parent attempt")
            return report["attempt"]
        if not current.get("rationale", "").strip() or parent["sha256"] in seen:
            raise ValueError(
                "Follow-up requires a rationale and an acyclic parent chain"
            )
        seen.add(parent["sha256"])
        current = read_json(checked_ref(parent))
        expected -= 1


def _report(path: Path, data: dict) -> Path:
    write_json(path, data)
    head = data["comparisons"]["head_to_head"]
    lines = [
        f"# {data['stage'].title()} comparison",
        "",
        f"Attempt: {data['attempt']}. Seed pairs: {data['pairs']}. Games to win each match: {data['wins_to_match']}.",
        f"Challenger vs champion: {head['wins']}/{head['matches']} ({head['win_rate']:.1%}).",
        f"Pair-level standard error: {head['pair_standard_error']}.",
        "",
        "| Static opponent | Champion win rate | Challenger win rate | Difference |",
        "|---|---:|---:|---:|",
    ]
    for name, result in data["comparisons"]["baselines"].items():
        lines.append(
            f"| {name} | {result['champion']['win_rate']:.1%} | {result['challenger']['win_rate']:.1%} | {result['delta']:+.1%} |"
        )
    lines += [
        "",
        f"Rationale: {data.get('rationale', '')}",
        "",
        "Screening thresholds are observed-rate rules, not proof of superiority. Side swaps are paired observations.",
        "See JSON for immutable artifact references, budgets, source provenance and raw match records.",
        "",
    ]
    with path.with_suffix(".md").open("x", encoding="utf-8") as output:
        output.write("\n".join(lines))
    return path


def _validate_budget(pairs: int, wins_to_match: int) -> None:
    if any(type(value) is not int or value < 1 for value in (pairs, wins_to_match)):
        raise ValueError("Pairs and match target must be positive integers")


def trial(
    registry: Path,
    spec: DesignSpec,
    run_dir: Path,
    *,
    seed: int = 7,
    pairs: int = 8,
    wins_to_match: int = 1,
    parent: Path | None = None,
    rationale: str = "",
    rules: SelectionRule | None = None,
    baseline_specs: Mapping[str, DesignSpec] | None = None,
) -> Path:
    _validate_budget(pairs, wins_to_match)
    champion = _champion(registry)["artifact"]
    previous = read_json(parent) if parent is not None else None
    if previous is not None:
        _lineage(previous)
        if not rationale.strip():
            raise ValueError("A follow-up requires an evidence-based rationale")
        if previous["champion"] != champion:
            raise ValueError("The champion changed since the parent attempt")
        if (
            parent is not None
            and parent.with_name("confirmation.started.json").exists()
        ):
            raise ValueError("Confirmation consumed; start a fresh development cycle")
        previous_rules = SelectionRule(**previous["rules"])
        if rules is not None and rules != previous_rules:
            raise ValueError("Follow-up must retain its predeclared selection rules")
        rules = previous_rules
        if baseline_specs is not None:
            raise ValueError("Follow-ups inherit the frozen baseline suite")
    if baseline_specs is None:
        baseline_specs = {
            name: DesignSpec(STATIC_ADAPTER, {"strategy": name})
            for name in STATIC_STRATEGIES
        }
    if not baseline_specs or any(
        not re.fullmatch(r"[A-Za-z0-9_-]+", name) for name in baseline_specs
    ):
        raise ValueError(
            "Baseline IDs must be nonempty letters, digits, underscores or hyphens"
        )
    rules = rules or SelectionRule()
    root = Path(run_dir).resolve()
    root.mkdir(parents=True, exist_ok=False)
    start = perf_counter()
    try:
        challenger = artifact_ref(
            train_artifact(spec, root / "challenger", seed=seed_for(seed, "training"))
        )
        baselines = (
            previous["baselines"]
            if previous
            else {
                name: artifact_ref(
                    train_artifact(
                        baseline_spec,
                        root / "baselines" / name,
                        seed=seed_for(0, "static", name),
                    )
                )
                for name, baseline_spec in baseline_specs.items()
            }
        )
        comparisons = compare(
            champion,
            challenger,
            baselines,
            pairs=pairs,
            seed=seed,
            wins_to_match=wins_to_match,
            namespace="development",
        )
        return _report(
            root / "development.json",
            {
                "schema_version": 1,
                "stage": "development",
                "namespace": "development",
                "attempt": previous["attempt"] + 1 if previous else 1,
                "parent": artifact_ref(parent) if parent is not None else None,
                "rationale": rationale,
                "champion": champion,
                "challenger": challenger,
                "baselines": baselines,
                "rules": asdict(rules),
                "pairs": pairs,
                "wins_to_match": wins_to_match,
                "evaluation_seed": seed,
                "comparisons": comparisons,
                "elapsed_seconds": perf_counter() - start,
            },
        )
    except Exception as error:
        write_json(
            root / "failure.json",
            {"error": type(error).__name__, "message": str(error)},
        )
        raise


def confirm(registry: Path, development: Path, *, pairs: int = 32) -> Path:
    report = read_json(development)
    if _lineage(report) < 2:
        raise ValueError(
            "Confirmation requires at least one recorded follow-up attempt"
        )
    rule = SelectionRule(**report["rules"])
    _validate_budget(pairs, report["wins_to_match"])
    if pairs < rule.min_pairs:
        raise ValueError("Insufficient confirmation pairs")
    if _champion(registry)["artifact"] != report["champion"]:
        raise ValueError("The champion changed after development")
    # Claim once before consuming held-out results; failed/partial attempts stay visible.
    marker = Path(development).parent / "confirmation.started.json"
    write_json(marker, {"development": artifact_ref(development), "pairs": pairs})
    start = perf_counter()
    try:
        namespace = f"confirmation:{report['challenger']['sha256']}"
        comparisons = compare(
            report["champion"],
            report["challenger"],
            report["baselines"],
            pairs=pairs,
            seed=report["evaluation_seed"],
            wins_to_match=report["wins_to_match"],
            namespace=namespace,
        )
        return _report(
            Path(development).parent / "confirmation.json",
            {
                **report,
                "stage": "confirmation",
                "namespace": namespace,
                "development": artifact_ref(development),
                "pairs": pairs,
                "comparisons": comparisons,
                "elapsed_seconds": perf_counter() - start,
            },
        )
    except Exception as error:
        write_json(
            marker.parent / "confirmation.failure.json",
            {"error": type(error).__name__, "message": str(error)},
        )
        raise


def selection_reasons(comparisons: dict, rule: SelectionRule) -> list[str]:
    reasons = []
    head = comparisons["head_to_head"]
    if head["matches"] < 2 * rule.min_pairs:
        reasons.append("Insufficient confirmation pairs")
    if head["win_rate"] < rule.win_rate:
        reasons.append("Challenger failed the head-to-head threshold")
    if not comparisons["baselines"]:
        reasons.append("Missing static baseline evidence")
    for name, result in comparisons["baselines"].items():
        if result["delta"] < -rule.max_regression - 1e-12:
            reasons.append(f"Material static regression: {name}")
    return reasons


def promote(registry: Path, confirmation: Path) -> dict:
    evidence = read_json(confirmation)
    if evidence.get("stage") != "confirmation":
        raise ValueError("Promotion requires held-out confirmation")
    development = read_json(checked_ref(evidence["development"]))
    if _lineage(development) < 2:
        raise ValueError("Promotion requires a follow-up attempt")
    for name in (
        "champion",
        "challenger",
        "baselines",
        "rules",
        "evaluation_seed",
        "wins_to_match",
    ):
        if evidence[name] != development[name]:
            raise ValueError(
                "Confirmation differs from its frozen development candidate"
            )
    for reference in (
        evidence["champion"],
        evidence["challenger"],
        *evidence["baselines"].values(),
    ):
        load_artifact(reference)
    if evidence["namespace"] != f"confirmation:{evidence['challenger']['sha256']}":
        raise ValueError("Invalid confirmation evidence namespace")
    validate_evidence(evidence)
    reasons = selection_reasons(
        evidence["comparisons"], SelectionRule(**evidence["rules"])
    )
    with _registry_lock(Path(registry)):
        pointer = _champion(registry)
        if pointer["artifact"] != evidence["champion"]:
            raise ValueError("Stale confirmation: champion changed")
        if reasons:
            return {"promoted": False, "reasons": reasons}
        history = [
            *pointer["history"],
            {
                "previous": pointer["artifact"],
                "confirmation": artifact_ref(confirmation),
            },
        ]
        _replace_pointer(
            Path(registry),
            {
                "schema_version": 1,
                "artifact": evidence["challenger"],
                "history": history,
            },
        )
    return {"promoted": True, "reasons": []}
