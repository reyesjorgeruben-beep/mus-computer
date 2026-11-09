"""Seat-balanced full matches against random actions, coefficients, and Maestro."""

import json
import random
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from mus_computer.bots.mus_maestro_bot import MusMaestroBot
from mus_computer.bots.random_decision_bot import RandomDecisionBot
from mus_computer.game.game import Game
from mus_computer.game.match import Match
from mus_computer.game.player_base import PlayerBase
from mus_computer.game.team import Team

from .bot import CoefficientBot
from .policy import Coefficients

OPPONENTS = ("random_decisions", "random_coefficients", "mus_maestro")


@dataclass(frozen=True)
class MatchTask:
    coefficients: Coefficients
    opponent: str
    candidate_team: str
    seed: int
    wins_to_match: int
    opponent_coefficients: Coefficients | None = None


def build_validation_game(task: MatchTask, seed: int) -> Game:
    teams = (Team("A"), Team("B"))
    players = []
    for seat in range(4):
        team = teams[seat % 2]
        name = f"{team.name}{seat // 2 + 1}"
        rng = random.Random(seed + seat + 1)
        player: PlayerBase
        if team.name == task.candidate_team:
            player = CoefficientBot(name, team, task.coefficients, rng)
        elif task.opponent == "random_coefficients":
            if task.opponent_coefficients is None:
                raise ValueError(
                    "Random-coefficient opponent requires a coefficient set"
                )
            player = CoefficientBot(name, team, task.opponent_coefficients, rng)
        elif task.opponent == "random_decisions":
            player = RandomDecisionBot(name, team, rng)
        elif task.opponent == "mus_maestro":
            player = MusMaestroBot(name, team)
        else:
            raise ValueError(f"Unknown opponent: {task.opponent}")
        players.append(player)
    return Game.from_players(players)


def _play_match(task: MatchTask) -> tuple[str, int, int]:
    previous = random.getstate()
    try:
        index = 0

        def next_game():
            nonlocal index
            seed = task.seed + 4 * index
            index += 1
            random.seed(seed)
            return build_validation_game(task, seed)

        result = Match(next_game, task.wins_to_match).play()
        return result.winner, result.wins_a, result.wins_b
    finally:
        random.setstate(previous)


def validate_coefficients(
    coefficients: Coefficients,
    run_dir: Path,
    *,
    workers=16,
    matches=100,
    wins_to_match=4,
    seed=2_000_007,
) -> dict:
    if type(matches) is not int or matches < 2 or matches % 2:
        raise ValueError("Matches per opponent must be an even integer of at least two")
    if (
        type(workers) is not int
        or workers < 1
        or type(wins_to_match) is not int
        or wins_to_match < 1
    ):
        raise ValueError("Workers and match target must be positive integers")
    rng = random.Random(seed)
    tasks = []
    stride = 4 * (2 * wins_to_match - 1) + 1
    for opponent in OPPONENTS:
        for pair in range(matches // 2):
            opponent_coefficients = (
                Coefficients.random(rng) if opponent == "random_coefficients" else None
            )
            pair_seed = seed + (OPPONENTS.index(opponent) * matches + 2 * pair) * stride
            for team in ("A", "B"):
                tasks.append(
                    MatchTask(
                        coefficients,
                        opponent,
                        team,
                        pair_seed,
                        wins_to_match,
                        opponent_coefficients,
                    )
                )
    if workers == 1:
        results = list(map(_play_match, tasks))
    else:
        with ProcessPoolExecutor(max_workers=min(workers, len(tasks))) as executor:
            results = list(executor.map(_play_match, tasks))
    benchmarks = {}
    for opponent in OPPONENTS:
        records = []
        for task, (winner, wins_a, wins_b) in zip(tasks, results):
            if task.opponent == opponent:
                records.append(
                    {
                        "candidate_team": task.candidate_team,
                        "seed": task.seed,
                        "winner": winner,
                        "wins_a": wins_a,
                        "wins_b": wins_b,
                        "opponent_coefficients": (
                            task.opponent_coefficients.as_dict()
                            if task.opponent_coefficients
                            else None
                        ),
                    }
                )
        wins = sum(r["winner"] == r["candidate_team"] for r in records)
        benchmarks[opponent] = {
            "wins": wins,
            "matches": matches,
            "win_percentage": 100 * wins / matches,
            "matchups": records,
        }
        print(f"validation {opponent}: {wins}/{matches} matches won", flush=True)
    report = {
        "policy_version": 2,
        "seed": seed,
        "wins_to_match": wins_to_match,
        "coefficients": coefficients.as_dict(),
        "benchmarks": benchmarks,
    }
    write_validation_report(report, run_dir)
    return report


def write_validation_report(report: dict, run_dir: Path):
    """Persist match win rates; paired matches are not independent CI samples."""
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "validation.json").write_text(
        json.dumps(report, indent=2, allow_nan=False), encoding="utf-8"
    )
    lines = [
        "# Full-match validation",
        "",
        f"First to {report['wins_to_match']} game wins; each game starts at 0 and plays to 40 or accepted ordago.",
        "",
        "| Opponent | Matches won | Win rate |",
        "|---|---:|---:|",
    ]
    for opponent, b in report["benchmarks"].items():
        lines.append(
            f"| {opponent} | {b['wins']}/{b['matches']} | {b['win_percentage']:.1f}% |"
        )
    (run_dir / "validation.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
