"""Model-independent, side-swapped full matches with pair-level statistics."""

from __future__ import annotations

import hashlib
import math
import random
from collections.abc import Mapping
from statistics import stdev
from typing import Any

from mus_computer.game.game import Game
from mus_computer.game.match import Match
from mus_computer.game.team import Team

from .contracts import PlayerFactory, load_artifact


def seed_for(seed: int, *parts: object) -> int:
    text = ":".join(map(str, (seed, *parts)))
    return int.from_bytes(hashlib.sha256(text.encode()).digest()[:8], "big")


def _match(
    left: PlayerFactory,
    right: PlayerFactory,
    left_team: str,
    pair_seed: int,
    wins_to_match: int,
) -> dict:
    previous = random.getstate()
    try:
        index = 0

        def next_game() -> Game:
            nonlocal index
            game_index = index
            index += 1
            random.seed(seed_for(pair_seed, "deck", game_index))
            teams = (Team("A"), Team("B"))
            players = []
            for seat in range(4):
                team = teams[seat % 2]
                factory = left if team.name == left_team else right
                players.append(
                    factory(
                        f"{team.name}{seat // 2 + 1}",
                        team,
                        seat,
                        seed_for(pair_seed, "action", game_index, seat),
                    )
                )
            return Game.from_players(players)

        result = Match(next_game, wins_to_match).play()
        return {
            "left_team": left_team,
            "seed": pair_seed,
            "winner": result.winner,
            "wins_a": result.wins_a,
            "wins_b": result.wins_b,
        }
    finally:
        random.setstate(previous)


def paired_matches(
    left: Mapping,
    right: Mapping,
    *,
    pairs: int,
    seed: int,
    wins_to_match: int = 1,
    namespace: str = "development",
) -> dict:
    if type(pairs) is not int or pairs < 1:
        raise ValueError("At least one seed pair is required")
    if type(wins_to_match) is not int or wins_to_match < 1:
        raise ValueError("Match target must be a positive integer")
    _, left_factory = load_artifact(left)
    _, right_factory = load_artifact(right)
    records = []
    for pair in range(pairs):
        pair_seed = seed_for(seed, namespace, pair)
        for team in ("A", "B"):
            record = _match(left_factory, right_factory, team, pair_seed, wins_to_match)
            records.append({"pair": pair, **record})
    return _summarize(records)


def _summarize(records: list[dict]) -> dict:
    pairs = len(records) // 2
    scores = [
        sum(row["winner"] == row["left_team"] for row in records[i : i + 2]) / 2
        for i in range(0, len(records), 2)
    ]
    wins = sum(record["winner"] == record["left_team"] for record in records)
    return {
        "wins": wins,
        "matches": 2 * pairs,
        "win_rate": wins / (2 * pairs),
        "pair_scores": scores,
        "pair_standard_error": stdev(scores) / math.sqrt(pairs) if pairs > 1 else None,
        "records": records,
    }


def validate_evidence(report: dict) -> None:
    """Reject edited aggregates and incomplete or mispaired match evidence."""
    comparisons = report["comparisons"]
    pairs, target = report["pairs"], report["wins_to_match"]
    if type(pairs) is not int or pairs < 1 or type(target) is not int or target < 1:
        raise ValueError("Invalid evidence budget")
    if set(comparisons["baselines"]) != set(report["baselines"]):
        raise ValueError("Missing baseline evidence")
    series = [comparisons["head_to_head"]]
    for result in comparisons["baselines"].values():
        series.extend((result["champion"], result["challenger"]))
        differences = [
            b - a
            for a, b in zip(
                result["champion"]["pair_scores"], result["challenger"]["pair_scores"]
            )
        ]
        error = stdev(differences) / math.sqrt(pairs) if pairs > 1 else None
        if (
            result["delta"]
            != result["challenger"]["win_rate"] - result["champion"]["win_rate"]
            or result["delta_pair_standard_error"] != error
        ):
            raise ValueError("Inconsistent baseline evidence")
    for item in series:
        rows = item["records"]
        if len(rows) != 2 * pairs:
            raise ValueError("Incomplete match evidence")
        for index, row in enumerate(rows):
            if (
                row["pair"] != index // 2
                or row["left_team"] != ("A" if index % 2 == 0 else "B")
                or row["seed"]
                != seed_for(report["evaluation_seed"], report["namespace"], index // 2)
                or type(row["wins_a"]) is not int
                or type(row["wins_b"]) is not int
                or min(row["wins_a"], row["wins_b"]) < 0
                or max(row["wins_a"], row["wins_b"]) != target
                or min(row["wins_a"], row["wins_b"]) >= target
                or row["winner"] != ("A" if row["wins_a"] == target else "B")
            ):
                raise ValueError("Invalid paired match evidence")
        if item != _summarize(rows):
            raise ValueError("Inconsistent match evidence aggregates")


def compare(
    champion: Mapping,
    challenger: Mapping,
    baselines: Mapping[str, Mapping],
    *,
    pairs: int,
    seed: int,
    wins_to_match: int,
    namespace: str,
) -> dict:
    options: dict[str, Any] = {
        "pairs": pairs,
        "seed": seed,
        "wins_to_match": wins_to_match,
        "namespace": namespace,
    }
    print(f"{namespace}: challenger vs champion ({pairs} pairs)", flush=True)
    head = paired_matches(challenger, champion, **options)
    benchmarks = {}
    for name, baseline in baselines.items():
        print(
            f"{namespace}: both candidates vs {name} ({pairs} pairs each)", flush=True
        )
        champion_result = paired_matches(champion, baseline, **options)
        challenger_result = paired_matches(challenger, baseline, **options)
        differences = [
            b - a
            for a, b in zip(
                champion_result["pair_scores"], challenger_result["pair_scores"]
            )
        ]
        benchmarks[name] = {
            "champion": champion_result,
            "challenger": challenger_result,
            "delta": challenger_result["win_rate"] - champion_result["win_rate"],
            "delta_pair_standard_error": stdev(differences) / math.sqrt(pairs)
            if pairs > 1
            else None,
        }
    return {"head_to_head": head, "baselines": benchmarks}
