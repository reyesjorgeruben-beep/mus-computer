"""Versioned design adapters and immutable, integrity-checked native artifacts."""

from __future__ import annotations

import hashlib
import importlib
import json
import subprocess
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol, cast

from mus_computer.game.player_base import PlayerBase
from mus_computer.game.team import Team


class PlayerFactory(Protocol):
    def __call__(
        self, name: str, team: Team, player_id: int, seed: int
    ) -> PlayerBase: ...


class DesignAdapter(Protocol):
    @property
    def version(self) -> str: ...
    def train(self, config: Mapping[str, Any], *, seed: int, run_dir: Path) -> Path: ...
    def load(self, checkpoint: Path, config: Mapping[str, Any]) -> PlayerFactory: ...


@dataclass(frozen=True)
class DesignSpec:
    adapter: str
    config: dict[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.adapter, str) or ":" not in self.adapter:
            raise ValueError("Adapter must be a trusted local module:Class")
        if not isinstance(self.config, dict):
            raise TypeError("Design config must be a JSON object")
        json.dumps(self.config, allow_nan=False)


def read_json(path: Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError("Expected a JSON object")
    return data


def write_json(path: Path, data: Mapping) -> None:
    """Create once; a completed report/artifact must never be overwritten."""
    payload = json.dumps(data, indent=2, allow_nan=False) + "\n"
    with Path(path).open("x", encoding="utf-8") as output:
        output.write(payload)


def digest(path: Path) -> str:
    checksum = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            checksum.update(block)
    return checksum.hexdigest()


def artifact_ref(path: Path) -> dict:
    return {"path": str(Path(path).resolve()), "sha256": digest(path)}


def checked_ref(reference: Mapping) -> Path:
    path = Path(reference["path"])
    if digest(path) != reference["sha256"]:
        raise ValueError(f"Integrity check failed: {path.name}")
    return path


def adapter_for(spec: DesignSpec) -> DesignAdapter:
    module, name = spec.adapter.split(":", 1)
    adapter = getattr(importlib.import_module(module), name)()
    if not isinstance(adapter.version, str) or not adapter.version:
        raise ValueError("Adapter requires a nonempty inference version")
    if not all(
        callable(getattr(adapter, method, None)) for method in ("train", "load")
    ):
        raise ValueError("Adapter must implement train and load")
    return cast(DesignAdapter, adapter)


def provenance() -> dict:
    """Source identity, including uncommitted source files, without storing diffs."""
    root = Path(__file__).resolve().parents[4]
    source = root / "src"
    checksum = hashlib.sha256()
    for path in sorted(source.rglob("*.py")):
        checksum.update(path.relative_to(root).as_posix().encode())
        checksum.update(path.read_bytes())
    try:
        revision = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        revision = None
    bundled_data = {
        path.relative_to(root).as_posix(): digest(path)
        for path in sorted(source.rglob("*"))
        if path.is_file()
        and path.suffix not in {".py", ".pyc", ".pyo"}
        and "__pycache__" not in path.parts
    }
    return {
        "git_revision": revision,
        "source_sha256": checksum.hexdigest(),
        "bundled_data_sha256": bundled_data,
    }


def _contained(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if path == root or not path.is_relative_to(root):
        raise ValueError("Artifact payload must stay within its run directory")
    return path


def _payload_files(root: Path) -> dict[str, Path]:
    paths = list(root.rglob("*"))
    if any(
        path.is_symlink() or not path.resolve().is_relative_to(root) for path in paths
    ):
        raise ValueError("Artifact payload cannot contain symlinks or escaping paths")
    return {
        path.relative_to(root).as_posix(): path
        for path in paths
        if path.is_file() and path != root / "artifact.json"
    }


def train_artifact(spec: DesignSpec, run_dir: Path, *, seed: int) -> Path:
    adapter = adapter_for(spec)
    root = Path(run_dir).resolve()
    root.mkdir(parents=True, exist_ok=False)
    try:
        checkpoint = Path(adapter.train(spec.config, seed=seed, run_dir=root)).resolve()
        if (
            not checkpoint.is_relative_to(root)
            or checkpoint == root
            or not checkpoint.exists()
        ):
            raise ValueError(
                "Native checkpoint must exist inside the artifact directory"
            )
        files = {
            relative: digest(path)
            for relative, path in sorted(_payload_files(root).items())
        }
        if not files:
            raise ValueError("Training produced no checkpoint payload")
        manifest = root / "artifact.json"
        write_json(
            manifest,
            {
                "schema_version": 1,
                "spec": asdict(spec),
                "adapter_version": adapter.version,
                "training_seed": seed,
                "checkpoint": checkpoint.relative_to(root).as_posix(),
                "files": files,
                "provenance": provenance(),
            },
        )
        return manifest
    except Exception as error:
        write_json(
            root / "failure.json",
            {"error": type(error).__name__, "message": str(error)},
        )
        raise


def load_artifact(reference: Mapping) -> tuple[dict, PlayerFactory]:
    manifest = checked_ref(reference)
    data = read_json(manifest)
    if data.get("schema_version") != 1:
        raise ValueError("Unsupported artifact schema")
    root = manifest.parent.resolve()
    checkpoint = _contained(root, data["checkpoint"])
    if not data.get("files") or not checkpoint.exists():
        raise ValueError("Missing native checkpoint")
    if set(_payload_files(root)) != set(data["files"]):
        raise ValueError("Artifact payload file set changed after publication")
    relative_checkpoint = checkpoint.relative_to(root).as_posix()
    if checkpoint.is_file() and relative_checkpoint not in data["files"]:
        raise ValueError("Checkpoint is absent from the integrity manifest")
    for relative, checksum in data["files"].items():
        path = _contained(root, relative)
        if digest(path) != checksum:
            raise ValueError(f"Checkpoint integrity check failed: {path.name}")
    spec = DesignSpec(**data["spec"])
    adapter = adapter_for(spec)
    if adapter.version != data["adapter_version"]:
        raise ValueError(
            "Matching inference version unavailable; retain/install the frozen adapter"
        )
    return data, adapter.load(checkpoint, spec.config)
