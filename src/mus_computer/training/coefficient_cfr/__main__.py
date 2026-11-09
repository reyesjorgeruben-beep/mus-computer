"""Train context-specific wager probabilities, chart them, and validate matches."""

import argparse
from pathlib import Path

from .charts import render_charts
from .trainer import CoefficientTrainer, TrainingConfig
from .validation import validate_coefficients


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--rounds", type=int, default=1000, help="number of frozen batches"
    )
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--workers", type=int, default=16)
    parser.add_argument("--learning-rate", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument(
        "--run-dir", type=Path, default=Path("training_runs/coefficient_cfr_v2")
    )
    parser.add_argument(
        "--validation-matches",
        type=int,
        default=100,
        help="even match count per baseline",
    )
    parser.add_argument("--wins-to-match", type=int, default=4)
    parser.add_argument("--skip-validation", action="store_true")
    args = parser.parse_args()
    if not args.skip_validation and (
        args.validation_matches < 2
        or args.validation_matches % 2
        or args.wins_to_match < 1
    ):
        parser.error(
            "Validation needs an even match count >= 2 and a positive match target"
        )
    trainer = CoefficientTrainer(
        TrainingConfig(
            args.rounds, args.batch_size, args.workers, args.learning_rate, args.seed
        )
    )
    trainer.train(args.run_dir)
    render_charts(trainer.coefficient_history, args.run_dir)
    if not args.skip_validation:
        validate_coefficients(
            trainer.coefficients,
            args.run_dir,
            workers=args.workers,
            matches=args.validation_matches,
            wins_to_match=args.wins_to_match,
            seed=args.seed + 2_000_000,
        )
    print(f"Coefficients: {trainer.coefficients.as_dict()}")
    print(f"Results: {args.run_dir.resolve()}")


if __name__ == "__main__":
    main()
