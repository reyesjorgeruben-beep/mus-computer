"""Self-play iterations, counterfactual rollouts, evaluation, and training snapshots."""

from __future__ import annotations

import json
import random
from collections.abc import Mapping
from dataclasses import fields
from pathlib import Path

from mus_computer.bots.bot_genome import BotGenome
from mus_computer.bots.strategies.portfolio import StrategyPortfolio
from mus_computer.game.game import Game
from mus_computer.game.team import Team

from .config import CFRConfig
from .player import CFRBotPlayer
from .policy import CFRPolicy
from .sampling import DecisionController
from .state import DecisionRecord


class CFRTrainer:
    """Train one shared policy using four independent seats in self-play."""

    def __init__(
        self,
        config: CFRConfig | None = None,
        *,
        strategies: StrategyPortfolio | None = None,
        run_dir: Path | None = None,
    ) -> None:
        self.config = config or CFRConfig()
        self.strategies = strategies or StrategyPortfolio.default()
        self.policy = CFRPolicy()
        self.rng = random.Random(self.config.seed)
        self.personality = BotGenome(**{item.name: 0.5 for item in fields(BotGenome)})
        self.run_dir = Path(run_dir) if run_dir is not None else None
        self.metrics: list[dict] = []
        self.sampled_games = 0
        self._previous_checkpoint = CFRPolicy()

    def _play(
        self,
        deal_seed: int,
        policy: CFRPolicy,
        *,
        exploration: float,
        average: bool = False,
        prefix: tuple[str, ...] = (),
        forced_action: str | None = None,
        record: bool = True,
        action_seed: int = 0,
        policy_by_player: Mapping[int, CFRPolicy] | None = None,
    ) -> tuple[str, list[DecisionRecord]]:
        previous_state = random.getstate()
        try:
            random.seed(deal_seed)
            controller = DecisionController(
                policy,
                random.Random(action_seed),
                exploration=exploration,
                average=average,
                prefix=prefix,
                forced_action=forced_action,
                record=record,
                policy_by_player=policy_by_player,
            )
            a, b = Team("A"), Team("B")
            players = [
                CFRBotPlayer("A1", a, self.personality, self.strategies, controller, 0),
                CFRBotPlayer("B1", b, self.personality, self.strategies, controller, 1),
                CFRBotPlayer("A2", a, self.personality, self.strategies, controller, 2),
                CFRBotPlayer("B2", b, self.personality, self.strategies, controller, 3),
            ]
            winner = Game.from_players(players).play()
            return winner.name, controller.decisions
        finally:
            random.setstate(previous_state)

    @staticmethod
    def regret_increments(
        record: DecisionRecord, utilities: Mapping[str, float], selection_count: int
    ) -> dict[str, float]:
        """Importance-weighted action values minus the mixed-policy value."""
        baseline = sum(
            record.strategy[action] * utilities[action] for action in record.actions
        )
        weight = selection_count * record.opponent_reach / record.behavior_reach
        return {
            action: weight * (utilities[action] - baseline) for action in record.actions
        }

    @staticmethod
    def team_utility(winner: str, player_id: int) -> float:
        """Both teammates receive the same terminal win/loss utility."""
        return 1.0 if winner == ("A" if player_id % 2 == 0 else "B") else -1.0

    def evaluate_average_against(
        self, previous: CFRPolicy, *, games: int = 2, seed: int | None = None
    ) -> float:
        """Score the average policy against a checkpoint, swapping team sides."""
        if games < 1:
            raise ValueError("Evaluation requires at least one paired seed")
        seed_start = self.config.seed + 10_000_000 if seed is None else seed
        wins = 0
        for game_index in range(games):
            deal_seed = seed_start + game_index
            action_seed = deal_seed + 1_000_000
            winner, _ = self._play(
                deal_seed,
                self.policy,
                exploration=0,
                average=True,
                record=False,
                action_seed=action_seed,
                policy_by_player={1: previous, 3: previous},
            )
            wins += winner == "A"
            winner, _ = self._play(
                deal_seed,
                previous,
                exploration=0,
                average=True,
                record=False,
                action_seed=action_seed,
                policy_by_player={1: self.policy, 3: self.policy},
            )
            wins += winner == "B"
        return wins / (2 * games)

    def iterate(self, iteration: int) -> dict:
        frozen = self.policy.frozen()
        deal_seed = self.rng.randrange(2**63)
        action_seed = self.rng.randrange(2**63)
        winner, records = self._play(
            deal_seed,
            frozen,
            exploration=self.config.exploration,
            action_seed=action_seed,
        )
        self.sampled_games += 1
        increments: dict[str, dict[str, float]] = {}
        max_importance_weight = 0.0
        for seat in range(4):
            own_records = [record for record in records if record.seat == seat]
            if not own_records:
                continue
            record = self.rng.choice(own_records)
            prefix = tuple(entry.selected for entry in records[: record.ordinal])
            utilities: dict[str, float] = {}
            rollout_seed = self.rng.randrange(2**63)
            max_importance_weight = max(
                max_importance_weight,
                len(own_records) * record.opponent_reach / record.behavior_reach,
            )
            for action in record.actions:
                branch_winner, _ = self._play(
                    deal_seed,
                    frozen,
                    exploration=0.0,
                    prefix=prefix,
                    forced_action=action,
                    record=False,
                    action_seed=rollout_seed,
                )
                self.sampled_games += 1
                utilities[action] = self.team_utility(branch_winner, seat)
            update = self.regret_increments(record, utilities, len(own_records))
            node_updates = increments.setdefault(record.key, {})
            for action, value in update.items():
                node_updates[action] = node_updates.get(action, 0.0) + value
        self.policy.apply(records, increments)
        metric = {
            "iteration": iteration,
            "sampled_games": self.sampled_games,
            "team_a_utility": 1.0 if winner == "A" else -1.0,
            "team_b_utility": 1.0 if winner == "B" else -1.0,
            "information_states": len(self.policy.nodes),
            "max_importance_weight": max_importance_weight,
            "cumulative_positive_regret": sum(
                max(0.0, value)
                for node in self.policy.nodes.values()
                for value in node.regrets.values()
            ),
        }
        self.metrics.append(metric)
        return metric

    def train(self) -> CFRPolicy:
        for iteration in range(1, self.config.iterations + 1):
            metric = self.iterate(iteration)
            if self.run_dir is not None and (
                iteration % self.config.snapshot_every == 0
                or iteration == self.config.iterations
            ):
                metric["average_strategy_vs_previous_checkpoint"] = (
                    self.evaluate_average_against(self._previous_checkpoint)
                )
                self.save_snapshot(iteration)
                self._previous_checkpoint = self.policy.frozen()
            print(
                f"iteration {iteration}/{self.config.iterations} | "
                f"sampled_games={metric['sampled_games']} | "
                f"states={metric['information_states']} | "
                f"positive_regret={metric['cumulative_positive_regret']:.2f} | "
                f"max_weight={metric['max_importance_weight']:.2g}"
            )
        return self.policy

    def save_snapshot(self, iteration: int) -> Path:
        if self.run_dir is None:
            raise ValueError("A run directory is required to save snapshots")
        snapshot_dir = self.run_dir / "snapshots"
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        path = snapshot_dir / f"iteration_{iteration:06d}.json"
        path.write_text(
            json.dumps(
                {
                    "iteration": iteration,
                    "sampled_games": self.sampled_games,
                    "seed": self.config.seed,
                    "exploration": self.config.exploration,
                    "average_team_a_utility": sum(
                        m["team_a_utility"] for m in self.metrics
                    )
                    / len(self.metrics),
                    "average_team_b_utility": sum(
                        m["team_b_utility"] for m in self.metrics
                    )
                    / len(self.metrics),
                    "metrics": self.metrics,
                    "information_states": self.policy.snapshot(),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return path
