"""Command line entry point for final-winner validation."""

import argparse
from pathlib import Path

from mus_computer.training.validation import load_winners, validate_winners


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate winning genomes against three opponent policies")
    parser.add_argument("--winners", type=Path, required=True, help="Saved winning_genomes/genomes.json")
    parser.add_argument("--seed", type=int, default=0, help="Deterministic opponent and game seed")
    parser.add_argument("--workers", type=int, default=10, help="Concurrent matches (maximum: 16)")
    parser.add_argument("--wins-to-match", type=int, default=4, help="Game wins needed per match (default: 4)")
    parser.add_argument("--out", type=Path, default=None, help="Results Markdown path")
    parser.add_argument("--gene", action="append", default=None, help="Override active genes (repeatable)")
    args = parser.parse_args()

    winners = load_winners(args.winners)
    run_dir = args.winners.parent.parent if args.winners.parent.name == "winning_genomes" else args.winners.parent
    output_path = args.out or run_dir / "validation" / "results.md"
    report = validate_winners(
        winners, run_dir=run_dir, seed=args.seed,
        workers=args.workers, output_path=output_path, wins_to_match=args.wins_to_match,
        active_genes=tuple(args.gene) if args.gene is not None else None,
    )
    for record in report["winners"]:
        scores = ", ".join(
            f"{kind} {benchmark['wins']}/{benchmark['matches']} ({benchmark['win_percentage']:.0f}%)"
            for kind, benchmark in record["benchmarks"].items()
        )
        print(f"Winner {record['index'] + 1}: {scores}")
    print(f"Validation saved to {output_path}")


if __name__ == "__main__":
    main()
