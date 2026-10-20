"""Seat-balanced validation against three independent opponent policies."""

import json
import random
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Literal

from mus_computer.bots.bot_genome import BotGenome
from mus_computer.bots.bot_player import BotPlayer
from mus_computer.bots.mus_maestro_bot import MusMaestroBot
from mus_computer.bots.random_decision_bot import RandomDecisionBot
from mus_computer.game.game import Game
from mus_computer.game.match import Match
from mus_computer.game.team import Team
from mus_computer.training.config import TrainingConfig
from mus_computer.training.game_runner import TrainingGameRunner, build_genome_strategies
from mus_computer.training.genome_generator import CustomGeneticGenomeGenerator


MATCHES_PER_OPPONENT = 100
OpponentKind = Literal["random_genes", "random_decisions", "mus_maestro"]
OPPONENT_KINDS: tuple[OpponentKind, ...] = (
    "random_genes", "random_decisions", "mus_maestro",
)


@dataclass(frozen=True)
class ValidationAssignment:
    """One candidate, its opponent policy, seat, and reproducible match seed."""

    candidate_index: int
    candidate_team: Literal["A", "B"]
    opponent_kind: OpponentKind
    candidate: BotGenome
    opponent_genome: BotGenome | None
    match_number: int
    seed: int
    wins_to_match: int


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


def _play_validation_match(assignment: ValidationAssignment) -> str:
    """Play fresh, distinctly seeded games until a team wins the match."""
    previous_state = random.getstate()
    try:
        game_index = 0

        def next_game() -> Game:
            nonlocal game_index
            game_seed = assignment.seed + 4 * game_index
            game_index += 1
            random.seed(game_seed)
            return build_validation_game(replace(assignment, seed=game_seed))

        return Match(next_game, assignment.wins_to_match).play().winner
    finally:
        random.setstate(previous_state)


def _results_table(records: list[dict]) -> str:
    """Render only per-winner and average win percentages for the three baselines."""
    labels = ("Random genes", "Random decisions", "Mus maestro")
    lines = [
        "# Winner validation",
        "",
        f"| Winner | {' | '.join(labels)} |",
        "|---|---:|---:|---:|",
    ]
    for record in records:
        percentages = (
            record["benchmarks"][kind]["win_percentage"] for kind in OPPONENT_KINDS
        )
        lines.append(
            f"| {record['index'] + 1} | "
            + " | ".join(f"{percentage:g}%" for percentage in percentages) + " |"
        )
    averages = (
        sum(record["benchmarks"][kind]["win_percentage"] for record in records) / len(records)
        for kind in OPPONENT_KINDS
    )
    lines.append(
        "| Average | "
        + " | ".join(f"{average:.1f}".rstrip("0").rstrip(".") + "%" for average in averages)
        + " |"
    )
    return "\n".join(lines) + "\n"


def validate_winners(
    winners: list[BotGenome], run_dir: Path, seed: int = 0, workers: int = 10,
    output_path: Path | None = None, active_genes: tuple[str, ...] | None = None,
    wins_to_match: int = 4,
) -> dict:
    """Play 100 matches per winner and opponent, split evenly across seats."""
    if not winners:
        raise ValueError("At least one winner is required for validation")
    if type(wins_to_match) is not int or wins_to_match < 1:
        raise ValueError("wins_to_match must be a positive integer")
    generator = CustomGeneticGenomeGenerator(active_genes=active_genes)
    previous_random_state = random.getstate()
    try:
        random.seed(seed)
        random_genomes: list[BotGenome] = []
        seen_genes: set[tuple[float, ...]] = set()
        for _ in range(len(winners) * MATCHES_PER_OPPONENT):
            while True:
                opponent = generator.initial_population(1)[0]
                gene_values = tuple(getattr(opponent, name) for name in generator.active_genes)
                if not gene_values or gene_values not in seen_genes:
                    break
            seen_genes.add(gene_values)
            random_genomes.append(opponent)
    finally:
        random.setstate(previous_random_state)

    assignments: list[ValidationAssignment] = []
    seed_stride = 4 * (2 * wins_to_match - 1) + 1
    for candidate_index, candidate in enumerate(winners):
        for opponent_kind in OPPONENT_KINDS:
            for match_index in range(MATCHES_PER_OPPONENT):
                opponent_genome = (
                    random_genomes[candidate_index * MATCHES_PER_OPPONENT + match_index]
                    if opponent_kind == "random_genes" else None
                )
                candidate_team: Literal["A", "B"] = (
                    "A" if match_index < MATCHES_PER_OPPONENT // 2 else "B"
                )
                assignments.append(ValidationAssignment(
                    candidate_index, candidate_team, opponent_kind, candidate,
                    opponent_genome, match_index + 1,
                    seed + len(assignments) * seed_stride, wins_to_match,
                ))

    with TrainingGameRunner(TrainingConfig(max_concurrent_games=workers)) as runner:
        winners_by_match = runner.map_tasks(_play_validation_match, assignments)
    if len(winners_by_match) != len(assignments):
        raise ValueError("Runner returned the wrong number of validation results")

    records = [
        {
            "index": index,
            "genome": asdict(winner),
            "benchmarks": {
                kind: {"wins": 0, "matches": MATCHES_PER_OPPONENT, "win_percentage": 0.0, "matchups": []}
                for kind in OPPONENT_KINDS
            },
        }
        for index, winner in enumerate(winners)
    ]
    for assignment, winning_team in zip(assignments, winners_by_match):
        if winning_team not in ("A", "B"):
            raise ValueError(f"Unexpected validation winner: {winning_team!r}")
        benchmark = records[assignment.candidate_index]["benchmarks"][assignment.opponent_kind]
        won = winning_team == assignment.candidate_team
        benchmark["wins"] += int(won)
        match_record = {
            "match": assignment.match_number,
            "candidate_team": assignment.candidate_team,
            "seed": assignment.seed,
            "won": won,
        }
        if assignment.opponent_genome is not None:
            match_record["opponent_genome"] = asdict(assignment.opponent_genome)
        benchmark["matchups"].append(match_record)
    for record in records:
        for benchmark in record["benchmarks"].values():
            benchmark["win_percentage"] = 100.0 * benchmark["wins"] / MATCHES_PER_OPPONENT

    report = {
        "seed": seed,
        "active_genes": list(generator.active_genes),
        "matches_per_opponent": MATCHES_PER_OPPONENT,
        "wins_to_match": wins_to_match,
        "winners": records,
    }
    destination = Path(output_path) if output_path is not None else Path(run_dir) / "validation" / "results.md"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(_results_table(records), encoding="utf-8")
    return report
