"""Run a seat-balanced, ten-game check for every saved winner."""

import json
import random
from dataclasses import asdict
from pathlib import Path

from mus_computer.bots.bot_genome import BotGenome
from mus_computer.training.config import TrainingConfig
from mus_computer.training.game_runner import GenomeMatchup, TrainingGameRunner
from mus_computer.training.genome_generator import CustomGeneticGenomeGenerator


GAMES_PER_WINNER = 10


def load_winners(path: Path) -> list[BotGenome]:
    """Read the list format written by ``GeneticTrainer.save_population``."""
    with Path(path).open(encoding="utf-8") as source:
        saved = json.load(source)
    if not isinstance(saved, list) or not saved:
        raise ValueError("Winners file must contain a nonempty list of genomes")
    return [BotGenome(**genes) for genes in saved]


def validate_winners(
    winners: list[BotGenome], run_dir: Path, seed: int = 0, workers: int = 10,
    output_path: Path | None = None, active_genes: tuple[str, ...] | None = None,
) -> dict:
    """Play ten separate games per winner against newly sampled genomes.

    Every winner occupies team A five times and team B five times. Opponents
    sample active genes uniformly through the configured genome generator;
    inactive genes stay at the neutral 0.5 value. The one process pool is
    shared by every matchup, and the caller's random sequence is preserved.
    """
    if not winners:
        raise ValueError("At least one winner is required for validation")

    generator = CustomGeneticGenomeGenerator(active_genes=active_genes)
    previous_random_state = random.getstate()
    try:
        random.seed(seed)
        opponents = generator.initial_population(len(winners) * GAMES_PER_WINNER)
    finally:
        random.setstate(previous_random_state)

    matchups: list[GenomeMatchup] = []
    assignments: list[tuple[int, int, str, BotGenome]] = []
    for winner_index, winner in enumerate(winners):
        for game_index in range(GAMES_PER_WINNER):
            opponent = opponents[winner_index * GAMES_PER_WINNER + game_index]
            winner_seat = "A" if game_index < GAMES_PER_WINNER // 2 else "B"
            team_a, team_b = (winner, opponent) if winner_seat == "A" else (opponent, winner)
            matchups.append(GenomeMatchup(
                team_a=team_a, team_b=team_b,
                seed=seed + len(matchups), wins_to_match=1,
            ))
            assignments.append((winner_index, game_index, winner_seat, opponent))

    with TrainingGameRunner(TrainingConfig(max_concurrent_games=workers)) as runner:
        results = runner.play_matchups(matchups)
    if len(results) != len(matchups):
        raise ValueError("Runner returned the wrong number of validation results")

    records = [
        {"index": index, "genome": asdict(winner), "wins": 0,
         "games": GAMES_PER_WINNER, "win_percentage": 0.0, "matchups": []}
        for index, winner in enumerate(winners)
    ]
    for matchup, result, (winner_index, game_index, winner_seat, opponent) in zip(
        matchups, results, assignments,
    ):
        if result.winner not in ("A", "B"):
            raise ValueError(f"Unexpected validation winner: {result.winner!r}")
        record = records[winner_index]
        won = result.winner == winner_seat
        record["wins"] += int(won)
        record["matchups"].append({
            "game": game_index + 1,
            "winner_seat": winner_seat,
            "opponent": asdict(opponent),
            "seed": matchup.seed,
            "won": won,
        })
    for record in records:
        record["win_percentage"] = 100.0 * record["wins"] / GAMES_PER_WINNER

    report = {
        "seed": seed,
        "active_genes": list(generator.active_genes),
        "games_per_winner": GAMES_PER_WINNER,
        "winners": records,
    }
    destination = Path(output_path) if output_path is not None else Path(run_dir) / "validation" / "results.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report
