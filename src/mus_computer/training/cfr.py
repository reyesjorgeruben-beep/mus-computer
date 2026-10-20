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
"""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Mapping

from mus_computer.bots.bot_genome import BotGenome
from mus_computer.bots.bot_player import BotPlayer
from mus_computer.bots.strategies.actions import (
    ActionDistribution, DecisionKind, DiscardAction, MusAction, WagerAction,
    legal_wager_actions,
)
from mus_computer.bots.strategies.contexts import PlayerDecisionContext
from mus_computer.bots.strategies.portfolio import StrategyPortfolio
from mus_computer.game.context import GlobalGameContext
from mus_computer.game.game import Game
from mus_computer.game.team import Team

Action = MusAction | DiscardAction | WagerAction


def action_name(action: Action) -> str:
    """Give typed actions stable, JSON-compatible identifiers."""
    if isinstance(action, DiscardAction):
        return "discard:" + ",".join(map(str, action.indices))
    return f"{type(action).__name__}:{action.value}"


def information_key(
    kind: DecisionKind, public: GlobalGameContext, private: PlayerDecisionContext,
    legal: tuple[Action, ...],
) -> str:
    """Describe only what this seat can observe, including its own hand."""
    return json.dumps({
        "kind": kind.value,
        "seat": private.seat,
        "team": private.team_name,
        "cards": sorted(card.value for card in private.cards),
        "scores": [public.team_scores["A"], public.team_scores["B"]],
        "mus_exchanges": public.mus_exchanges,
        "phase": public.phase_name.value if public.phase_name else None,
        "wager": None if public.wager is None else [
            public.wager.current_total, public.wager.previous_accepted_total,
            public.wager.offering_team, public.wager.ordago_offered,
        ],
        "public_actions": public.public_actions,
        "discard_counts": [public.discard_counts.get(entry.player_name, 0)
                           for entry in public.seat_order],
        "eligible_seats": public.eligible_seats,
        "legal": [action_name(action) for action in legal],
    }, separators=(",", ":"))


def regret_match(actions: tuple[str, ...], regrets: Mapping[str, float],
                 prior: Mapping[str, float]) -> dict[str, float]:
    """Normalize positive cumulative regrets, falling back to the prior."""
    positives = {action: max(0.0, regrets.get(action, 0.0)) for action in actions}
    total = sum(positives.values())
    if total > 0:
        return {action: positives[action] / total for action in actions}
    return {action: prior[action] for action in actions}


@dataclass
class RegretNode:
    actions: tuple[str, ...]
    prior: dict[str, float]
    regrets: dict[str, float] = field(default_factory=dict)
    strategy_sum: dict[str, float] = field(default_factory=dict)

    def current(self) -> dict[str, float]:
        return regret_match(self.actions, self.regrets, self.prior)

    def average(self) -> dict[str, float]:
        total = sum(self.strategy_sum.values())
        if total <= 0:
            return self.current()
        return {action: self.strategy_sum.get(action, 0.0) / total
                for action in self.actions}


class CFRPolicy:
    """Shared tabular regret and reach-weighted average strategy."""

    def __init__(self) -> None:
        self.nodes: dict[str, RegretNode] = {}

    def probabilities(self, key: str, actions: tuple[str, ...],
                      prior: Mapping[str, float], *, average: bool = False) -> dict[str, float]:
        node = self.nodes.get(key)
        if node is None:
            return {action: prior[action] for action in actions}
        if node.actions != actions:
            raise ValueError("Information state has inconsistent legal actions")
        return node.average() if average else node.current()

    def frozen(self) -> "CFRPolicy":
        frozen = CFRPolicy()
        frozen.nodes = {
            key: RegretNode(node.actions, dict(node.prior), dict(node.regrets),
                            dict(node.strategy_sum))
            for key, node in self.nodes.items()
        }
        return frozen

    def apply(self, records: list["DecisionRecord"],
              increments: Mapping[str, Mapping[str, float]]) -> None:
        """Apply all estimates together, independent of seat processing order."""
        for record in records:
            node = self.nodes.setdefault(
                record.key, RegretNode(record.actions, dict(record.prior)),
            )
            weight = record.own_reach / record.behavior_reach
            for action in record.actions:
                node.strategy_sum[action] = (
                    node.strategy_sum.get(action, 0.0)
                    + weight * record.strategy[action]
                )
        for key, values in increments.items():
            node = self.nodes[key]
            for action, value in values.items():
                node.regrets[action] = node.regrets.get(action, 0.0) + value

    def snapshot(self) -> dict:
        return {key: {
            "actions": node.actions, "prior": node.prior,
            "regrets": node.regrets, "strategy_sum": node.strategy_sum,
            "current": node.current(), "average": node.average(),
        } for key, node in self.nodes.items()}

    @classmethod
    def from_snapshot(cls, snapshot: Mapping) -> "CFRPolicy":
        """Restore both current and average policies from saved node data."""
        policy = cls()
        for key, data in snapshot["information_states"].items():
            policy.nodes[key] = RegretNode(
                tuple(data["actions"]), dict(data["prior"]),
                dict(data["regrets"]), dict(data["strategy_sum"]),
            )
        return policy


@dataclass(frozen=True)
class DecisionRecord:
    ordinal: int
    seat: int
    key: str
    actions: tuple[str, ...]
    prior: Mapping[str, float]
    strategy: Mapping[str, float]
    selected: str
    own_reach: float
    opponent_reach: float
    behavior_reach: float


class DecisionController:
    """Sample or force bot actions while exposing only decision contexts to policy."""

    def __init__(self, policy: CFRPolicy, rng: random.Random, *, exploration: float,
                 average: bool = False, prefix: tuple[str, ...] = (),
                 forced_action: str | None = None, record: bool = True,
                 policy_by_player: Mapping[int, CFRPolicy] | None = None) -> None:
        self.policy = policy
        self.rng = rng
        self.exploration = exploration
        self.average = average
        self.prefix = prefix
        self.forced_action = forced_action
        self.record = record
        self.policy_by_player = policy_by_player or {}
        self.decisions: list[DecisionRecord] = []
        self.ordinal = 0
        self.target_reach = [1.0] * 4
        self.behavior_reach = 1.0

    def choose(self, seat: int, kind: DecisionKind, public: GlobalGameContext,
               private: PlayerDecisionContext, distribution: ActionDistribution,
               legal: tuple[Action, ...]) -> Action:
        names = tuple(action_name(action) for action in legal)
        prior = {action_name(action): distribution.probabilities.get(action, 0.0)
                 for action in legal}
        key = information_key(kind, public, private, legal)
        strategy = self.policy_by_player.get(seat, self.policy).probabilities(
            key, names, prior, average=self.average)
        behavior = {name: (1 - self.exploration) * strategy[name]
                    + self.exploration / len(names) for name in names}
        ordinal = self.ordinal
        self.ordinal += 1
        if ordinal < len(self.prefix):
            selected = self.prefix[ordinal]
        elif ordinal == len(self.prefix) and self.forced_action is not None:
            selected = self.forced_action
        else:
            selected = self.rng.choices(names, weights=list(behavior.values()), k=1)[0]
        if selected not in names:
            raise ValueError("Replay prefix diverged from its original decision")
        if self.record:
            opponents = 1.0
            for other_seat, reach in enumerate(self.target_reach):
                if other_seat != seat:
                    opponents *= reach
            self.decisions.append(DecisionRecord(
                ordinal, seat, key, names, prior, strategy, selected,
                self.target_reach[seat], opponents, self.behavior_reach,
            ))
        self.target_reach[seat] *= strategy[selected]
        self.behavior_reach *= behavior[selected]
        return legal[names.index(selected)]


class CFRBotPlayer(BotPlayer):
    """Existing bot interface with decisions routed through a shared table."""

    def __init__(self, name: str, team: Team, personality: BotGenome,
                 strategies: StrategyPortfolio, controller: DecisionController,
                 player_id: int) -> None:
        super().__init__(name, team, personality, strategies)
        self.controller = controller
        self.player_id = player_id

    def take_decision(self, kind: DecisionKind, global_context: GlobalGameContext,
                      player_context: PlayerDecisionContext) -> Action:
        if kind is DecisionKind.MUS:
            distribution = self.strategies.mus_strategy.decide(
                global_context, player_context, self._personality)
            legal: tuple[Action, ...] = tuple(MusAction)
        elif kind is DecisionKind.DISCARD:
            distribution = self.strategies.discard_strategy.decide(
                global_context, player_context, self._personality)
            legal = tuple(option.action for option in player_context.discard_options)
        else:
            phase = global_context.phase_name or player_context.phase_name
            if phase is None:
                raise ValueError("Wager decision requires a phase")
            distribution = self.strategies.wagers_by_phase[phase].decide(
                global_context, player_context, self._personality)
            legal = tuple(action for action in WagerAction
                          if action in legal_wager_actions(global_context.wager))
        return self.controller.choose(self.player_id, kind, global_context,
                                      player_context, distribution, legal)


@dataclass(frozen=True)
class CFRConfig:
    iterations: int = 100
    seed: int = 0
    exploration: float = 0.1
    snapshot_every: int = 10

    def __post_init__(self) -> None:
        if self.iterations < 1 or self.snapshot_every < 1:
            raise ValueError("Iterations and snapshot interval must be positive")
        if not 0 < self.exploration <= 1:
            raise ValueError("Exploration must be in (0, 1]")


class CFRTrainer:
    """Train one shared policy using four independent seats in self-play."""

    def __init__(self, config: CFRConfig | None = None, *,
                 strategies: StrategyPortfolio | None = None,
                 run_dir: Path | None = None) -> None:
        self.config = config or CFRConfig()
        self.strategies = strategies or StrategyPortfolio.default()
        self.policy = CFRPolicy()
        self.rng = random.Random(self.config.seed)
        self.personality = BotGenome(**{item.name: 0.5 for item in fields(BotGenome)})
        self.run_dir = Path(run_dir) if run_dir is not None else None
        self.metrics: list[dict] = []
        self.sampled_games = 0
        self._previous_checkpoint = CFRPolicy()

    def _play(self, deal_seed: int, policy: CFRPolicy, *, exploration: float,
              average: bool = False, prefix: tuple[str, ...] = (),
              forced_action: str | None = None, record: bool = True,
              action_seed: int = 0,
              policy_by_player: Mapping[int, CFRPolicy] | None = None,
              ) -> tuple[str, list[DecisionRecord]]:
        previous_state = random.getstate()
        try:
            random.seed(deal_seed)
            controller = DecisionController(policy, random.Random(action_seed),
                                            exploration=exploration, average=average,
                                            prefix=prefix, forced_action=forced_action,
                                            record=record, policy_by_player=policy_by_player)
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
    def regret_increments(record: DecisionRecord, utilities: Mapping[str, float],
                          selection_count: int) -> dict[str, float]:
        """Importance-weighted action values minus the mixed-policy value."""
        baseline = sum(record.strategy[action] * utilities[action]
                       for action in record.actions)
        weight = selection_count * record.opponent_reach / record.behavior_reach
        return {action: weight * (utilities[action] - baseline)
                for action in record.actions}

    @staticmethod
    def team_utility(winner: str, player_id: int) -> float:
        """Both teammates receive the same terminal win/loss utility."""
        return 1.0 if winner == ("A" if player_id % 2 == 0 else "B") else -1.0

    def evaluate_average_against(self, previous: CFRPolicy, *,
                                 games: int = 2, seed: int | None = None) -> float:
        """Score the average policy against a checkpoint, swapping team sides."""
        if games < 1:
            raise ValueError("Evaluation requires at least one paired seed")
        seed_start = self.config.seed + 10_000_000 if seed is None else seed
        wins = 0
        for game_index in range(games):
            deal_seed = seed_start + game_index
            action_seed = deal_seed + 1_000_000
            winner, _ = self._play(
                deal_seed, self.policy, exploration=0, average=True,
                record=False, action_seed=action_seed,
                policy_by_player={1: previous, 3: previous},
            )
            wins += winner == "A"
            winner, _ = self._play(
                deal_seed, previous, exploration=0, average=True,
                record=False, action_seed=action_seed,
                policy_by_player={1: self.policy, 3: self.policy},
            )
            wins += winner == "B"
        return wins / (2 * games)

    def iterate(self, iteration: int) -> dict:
        frozen = self.policy.frozen()
        deal_seed = self.rng.randrange(2**63)
        action_seed = self.rng.randrange(2**63)
        winner, records = self._play(deal_seed, frozen,
                                     exploration=self.config.exploration,
                                     action_seed=action_seed)
        self.sampled_games += 1
        increments: dict[str, dict[str, float]] = {}
        max_importance_weight = 0.0
        for seat in range(4):
            own_records = [record for record in records if record.seat == seat]
            if not own_records:
                continue
            record = self.rng.choice(own_records)
            prefix = tuple(entry.selected for entry in records[:record.ordinal])
            utilities: dict[str, float] = {}
            rollout_seed = self.rng.randrange(2**63)
            max_importance_weight = max(
                max_importance_weight,
                len(own_records) * record.opponent_reach / record.behavior_reach,
            )
            for action in record.actions:
                branch_winner, _ = self._play(
                    deal_seed, frozen, exploration=0.0,
                    prefix=prefix, forced_action=action, record=False,
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
            "iteration": iteration, "sampled_games": self.sampled_games,
            "team_a_utility": 1.0 if winner == "A" else -1.0,
            "team_b_utility": 1.0 if winner == "B" else -1.0,
            "information_states": len(self.policy.nodes),
            "max_importance_weight": max_importance_weight,
            "cumulative_positive_regret": sum(
                max(0.0, value) for node in self.policy.nodes.values()
                for value in node.regrets.values()),
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
            print(f"iteration {iteration}/{self.config.iterations} | "
                  f"sampled_games={metric['sampled_games']} | "
                  f"states={metric['information_states']} | "
                  f"positive_regret={metric['cumulative_positive_regret']:.2f} | "
                  f"max_weight={metric['max_importance_weight']:.2g}")
        return self.policy

    def save_snapshot(self, iteration: int) -> Path:
        if self.run_dir is None:
            raise ValueError("A run directory is required to save snapshots")
        snapshot_dir = self.run_dir / "snapshots"
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        path = snapshot_dir / f"iteration_{iteration:06d}.json"
        path.write_text(json.dumps({
            "iteration": iteration, "sampled_games": self.sampled_games,
            "seed": self.config.seed, "exploration": self.config.exploration,
            "average_team_a_utility": sum(m["team_a_utility"] for m in self.metrics) / len(self.metrics),
            "average_team_b_utility": sum(m["team_b_utility"] for m in self.metrics) / len(self.metrics),
            "metrics": self.metrics,
            "information_states": self.policy.snapshot(),
        }, indent=2), encoding="utf-8")
        return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Train shared Mus strategy with sampled CFR")
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--exploration", type=float, default=0.1)
    parser.add_argument("--snapshot-every", type=int, default=10)
    parser.add_argument("--run-dir", type=Path, default=Path("docs/training/cfr_runs"))
    args = parser.parse_args()
    trainer = CFRTrainer(CFRConfig(args.iterations, args.seed, args.exploration,
                                   args.snapshot_every), run_dir=args.run_dir)
    trainer.train()
    print(f"Snapshots: {args.run_dir / 'snapshots'}")


if __name__ == "__main__":
    main()
