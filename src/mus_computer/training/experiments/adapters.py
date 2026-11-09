"""Thin adapters around existing CFR training and existing static opponents."""

from __future__ import annotations

import hashlib
import random
from collections.abc import Mapping
from dataclasses import fields
from pathlib import Path
from typing import Any

from mus_computer.bots.bot_genome import BotGenome
from mus_computer.bots.bot_player import BotPlayer
from mus_computer.bots.mus_maestro_bot import MusMaestroBot
from mus_computer.bots.random_decision_bot import RandomDecisionBot
from mus_computer.bots.strategies.portfolio import StrategyPortfolio
from mus_computer.game.player_base import PlayerBase
from mus_computer.game.team import Team
from mus_computer.training.cfr import (
    CFRBotPlayer,
    CFRConfig,
    CFRPolicy,
    CFRTrainer,
    DecisionController,
)
from mus_computer.training.coefficient_cfr.bot import CoefficientBot
from mus_computer.training.coefficient_cfr.policy import Coefficients

from .contracts import PlayerFactory, read_json, write_json

STATIC_STRATEGIES = (
    "heuristic",
    "random_decisions",
    "mus_maestro",
    "random_coefficients",
)
_PACKAGE = Path(__file__).resolve().parents[2]


def _inference_version(kind: str, paths: list[Path]) -> str:
    checksum = hashlib.sha256()
    for path in sorted(set(paths)):
        checksum.update(path.relative_to(_PACKAGE).as_posix().encode())
        checksum.update(path.read_bytes())
    return f"{kind}-v1:{checksum.hexdigest()}"


def _common_sources() -> list[Path]:
    return [
        Path(__file__),
        _PACKAGE / "constants.py",
        _PACKAGE / "probabilities" / "data" / "probability_tables.pkl",
        _PACKAGE / "bots" / "bot_player.py",
        _PACKAGE / "bots" / "bot_genome.py",
        *(
            _PACKAGE / "bots" / "strategies" / f"{name}.py"
            for name in (
                "actions",
                "contexts",
                "discard",
                "mus",
                "personality",
                "portfolio",
                "wagers",
            )
        ),
        *(_PACKAGE / "game").glob("*.py"),
        *(_PACKAGE / "cards").glob("*.py"),
        *(_PACKAGE / "probabilities").glob("*.py"),
    ]


def _personality() -> BotGenome:
    return BotGenome(**{item.name: 0.5 for item in fields(BotGenome)})


class CFRAdapter:
    @property
    def version(self) -> str:
        # Training-only changes may compare old/new artifacts with the same reader.
        names = ("features", "glm_policy", "policy", "state", "sampling", "player")
        return _inference_version(
            "cfr-average",
            _common_sources()
            + [_PACKAGE / "training" / "cfr" / f"{name}.py" for name in names],
        )

    def train(self, config: Mapping[str, Any], *, seed: int, run_dir: Path) -> Path:
        options = dict(config)
        options.setdefault("snapshot_every", options.get("iterations", 100))
        trainer = CFRTrainer(CFRConfig(seed=seed, **options), run_dir=run_dir)
        trainer.train()
        return run_dir / "snapshots" / f"iteration_{trainer.config.iterations:06d}.json"

    def load(self, checkpoint: Path, config: Mapping[str, Any]) -> PlayerFactory:
        policy = CFRPolicy.from_snapshot(read_json(checkpoint))
        strategies = StrategyPortfolio.default()
        personality = _personality()

        def player(name: str, team: Team, player_id: int, seed: int) -> PlayerBase:
            controller = DecisionController(
                policy, random.Random(seed), exploration=0, average=True, record=False
            )
            return CFRBotPlayer(
                name, team, personality, strategies, controller, player_id
            )

        return player


class StaticAdapter:
    @property
    def version(self) -> str:
        return _inference_version(
            "static",
            _common_sources()
            + [
                _PACKAGE / "bots" / "mus_maestro_bot.py",
                _PACKAGE / "bots" / "random_decision_bot.py",
                _PACKAGE / "training" / "coefficient_cfr" / "bot.py",
                _PACKAGE / "training" / "coefficient_cfr" / "policy.py",
            ],
        )

    def train(self, config: Mapping[str, Any], *, seed: int, run_dir: Path) -> Path:
        if set(config) != {"strategy"} or config["strategy"] not in STATIC_STRATEGIES:
            raise ValueError(f"Static strategy must be one of {STATIC_STRATEGIES}")
        path = run_dir / "static.json"
        write_json(path, {"strategy": config["strategy"], "seed": seed})
        return path

    def load(self, checkpoint: Path, config: Mapping[str, Any]) -> PlayerFactory:
        data = read_json(checkpoint)
        strategy = data["strategy"]
        if strategy != config["strategy"] or strategy not in STATIC_STRATEGIES:
            raise ValueError("Static checkpoint and design disagree")
        coefficients = Coefficients.random(random.Random(data["seed"]))
        portfolio, personality = StrategyPortfolio.default(), _personality()

        def player(name: str, team: Team, player_id: int, seed: int) -> PlayerBase:
            rng = random.Random(seed)
            if strategy == "random_decisions":
                return RandomDecisionBot(name, team, rng)
            if strategy == "mus_maestro":
                return MusMaestroBot(name, team)
            if strategy == "random_coefficients":
                return CoefficientBot(name, team, coefficients, rng)
            return BotPlayer(name, team, personality, portfolio, rng)

        return player
