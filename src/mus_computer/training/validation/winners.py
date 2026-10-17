"""Seat-balanced validation against three independent opponent policies."""

import json
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from mus_computer.bots.bot_genome import BotGenome
from mus_computer.bots.bot_player import BotPlayer
from mus_computer.bots.mus_maestro_bot import MusMaestroBot
from mus_computer.bots.random_decision_bot import RandomDecisionBot
from mus_computer.game.game import Game
from mus_computer.game.team import Team
from mus_computer.training.config import TrainingConfig
from mus_computer.training.game_runner import TrainingGameRunner, build_genome_strategies
from mus_computer.training.genome_generator import CustomGeneticGenomeGenerator


GAMES_PER_OPPONENT = 10
OpponentKind = Literal["random_genes", "random_decisions", "mus_maestro"]
OPPONENT_KINDS: tuple[OpponentKind, ...] = (
    "random_genes", "random_decisions", "mus_maestro",
)


@dataclass(frozen=True)
class ValidationAssignment:
    """One candidate, its opponent policy, seat, and reproducible game seed."""

    candidate_index: int
    candidate_team: Literal["A", "B"]
    opponent_kind: OpponentKind
    candidate: BotGenome
    opponent_genome: BotGenome | None
    game_number: int
    seed: int


def load_winners(path: Path) -> list[BotGenome]:
    """Read the list format written by ``GeneticTrainer.save_population``."""
    with Path(path).open(encoding="utf-8") as source:
        saved = json.load(source)
    if not isinstance(saved, list) or not saved:
        raise ValueError("Winners file must contain a nonempty list of genomes")
    return [BotGenome(**genes) for genes in saved]


def build_validation_game(assignment: ValidationAssignment) -> Game:
    """Seat the candidate against one of the configured baseline bots."""
    team_a, team_b = Team("A"), Team("B")
    strategies = build_genome_strategies()

    def make_player(name: str, team: Team, random_offset: int):
        if team.name == assignment.candidate_team:
            return BotPlayer(
                name, team, assignment.candidate, strategies,
                random.Random(assignment.seed + random_offset),
            )
        if assignment.opponent_kind == "random_genes":
            if assignment.opponent_genome is None:
                raise ValueError("Random-gene opponent requires a genome")
            return BotPlayer(
                name, team, assignment.opponent_genome, strategies,
                random.Random(assignment.seed + random_offset),
            )
        if assignment.opponent_kind == "random_decisions":
            return RandomDecisionBot(name, team, random.Random(assignment.seed + random_offset))
        if assignment.opponent_kind == "mus_maestro":
            return MusMaestroBot(name, team)
        raise ValueError(f"Unknown validation opponent: {assignment.opponent_kind}")

    return Game.from_players([
        make_player("A1", team_a, 1),
        make_player("B1", team_b, 2),
        make_player("A2", team_a, 3),
        make_player("B2", team_b, 4),
    ])


def _play_validation_game(assignment: ValidationAssignment) -> str:
    """Return the winning team while preserving the worker's random stream."""
    previous_state = random.getstate()
    try:
        random.seed(assignment.seed)
        return build_validation_game(assignment).play().name
    finally:
        random.setstate(previous_state)


def validate_winners(
    winners: list[BotGenome], run_dir: Path, seed: int = 0, workers: int = 10,
    output_path: Path | None = None, active_genes: tuple[str, ...] | None = None,
) -> dict:
    """Play ten games per winner and opponent policy, split evenly across seats."""
    if not winners:
        raise ValueError("At least one winner is required for validation")
    generator = CustomGeneticGenomeGenerator(active_genes=active_genes)
    previous_random_state = random.getstate()
    try:
        random.seed(seed)
        random_genomes = generator.initial_population(len(winners) * GAMES_PER_OPPONENT)
    finally:
        random.setstate(previous_random_state)

    assignments: list[ValidationAssignment] = []
    for candidate_index, candidate in enumerate(winners):
        for opponent_kind in OPPONENT_KINDS:
            for game_index in range(GAMES_PER_OPPONENT):
                opponent_genome = (
                    random_genomes[candidate_index * GAMES_PER_OPPONENT + game_index]
                    if opponent_kind == "random_genes" else None
                )
                candidate_team: Literal["A", "B"] = (
                    "A" if game_index < GAMES_PER_OPPONENT // 2 else "B"
                )
                assignments.append(ValidationAssignment(
                    candidate_index, candidate_team, opponent_kind, candidate,
                    opponent_genome, game_index + 1, seed + len(assignments),
                ))

    with TrainingGameRunner(TrainingConfig(max_concurrent_games=workers)) as runner:
        winners_by_game = runner.map_tasks(_play_validation_game, assignments)
    if len(winners_by_game) != len(assignments):
        raise ValueError("Runner returned the wrong number of validation results")

    records = [
        {
            "index": index,
            "genome": asdict(winner),
            "benchmarks": {
                kind: {"wins": 0, "games": GAMES_PER_OPPONENT, "win_percentage": 0.0, "matchups": []}
                for kind in OPPONENT_KINDS
            },
        }
        for index, winner in enumerate(winners)
    ]
    for assignment, winning_team in zip(assignments, winners_by_game):
        if winning_team not in ("A", "B"):
            raise ValueError(f"Unexpected validation winner: {winning_team!r}")
        benchmark = records[assignment.candidate_index]["benchmarks"][assignment.opponent_kind]
        won = winning_team == assignment.candidate_team
        benchmark["wins"] += int(won)
        game_record = {
            "game": assignment.game_number,
            "candidate_team": assignment.candidate_team,
            "seed": assignment.seed,
            "won": won,
        }
        if assignment.opponent_genome is not None:
            game_record["opponent_genome"] = asdict(assignment.opponent_genome)
        benchmark["matchups"].append(game_record)
    for record in records:
        for benchmark in record["benchmarks"].values():
            benchmark["win_percentage"] = 100.0 * benchmark["wins"] / GAMES_PER_OPPONENT

    report = {
        "seed": seed,
        "active_genes": list(generator.active_genes),
        "games_per_opponent": GAMES_PER_OPPONENT,
        "winners": records,
    }
    destination = Path(output_path) if output_path is not None else Path(run_dir) / "validation" / "results.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report
