"""Explicit opt-in commands for reproducible training experiments."""

import argparse
import json
from pathlib import Path

from .contracts import DesignSpec, read_json
from .pipeline import SelectionRule, bootstrap, confirm, promote, trial
from .reports import write_report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--champion", type=Path, default=Path("training_runs/champion.json")
    )
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("bootstrap", "trial"):
        command = commands.add_parser(name, parents=[common])
        command.add_argument(
            "--design",
            type=Path,
            required=True,
            help="Trusted local adapter/config JSON",
        )
        command.add_argument("--run-dir", type=Path, required=True)
        command.add_argument("--seed", type=int, default=7)
        if name == "trial":
            command.add_argument("--pairs", type=int, default=8)
            command.add_argument("--wins-to-match", type=int, default=1)
            command.add_argument("--parent", type=Path)
            command.add_argument("--rationale", default="")
            command.add_argument(
                "--rules", type=Path, help="Selection rules, declared before evaluation"
            )
            command.add_argument(
                "--baselines",
                type=Path,
                help="Optional baseline ID -> design spec JSON",
            )
    confirmation = commands.add_parser("confirm", parents=[common])
    confirmation.add_argument("--development", type=Path, required=True)
    confirmation.add_argument("--pairs", type=int, default=32)
    promotion = commands.add_parser("promote", parents=[common])
    promotion.add_argument("--confirmation", type=Path, required=True)
    reporting = commands.add_parser(
        "report", help="Regenerate offline HTML from saved JSON; no training"
    )
    reporting.add_argument("--input", type=Path, required=True)
    reporting.add_argument("--output", type=Path)
    reporting.add_argument(
        "--related",
        type=Path,
        action="append",
        default=[],
        help="Include separate historical JSON comparisons",
    )
    args = parser.parse_args()
    if args.command == "bootstrap":
        result = bootstrap(
            args.champion,
            DesignSpec(**read_json(args.design)),
            args.run_dir,
            seed=args.seed,
        )
    elif args.command == "trial":
        result = trial(
            args.champion,
            DesignSpec(**read_json(args.design)),
            args.run_dir,
            seed=args.seed,
            pairs=args.pairs,
            wins_to_match=args.wins_to_match,
            parent=args.parent,
            rationale=args.rationale,
            rules=SelectionRule(**read_json(args.rules)) if args.rules else None,
            baseline_specs={
                name: DesignSpec(**spec)
                for name, spec in read_json(args.baselines).items()
            }
            if args.baselines
            else None,
        )
    elif args.command == "confirm":
        result = confirm(args.champion, args.development, pairs=args.pairs)
    elif args.command == "report":
        result = write_report(args.input, args.output, related=args.related)
    else:
        decision = promote(args.champion, args.confirmation)
        print(json.dumps(decision, indent=2))
        return 0 if decision["promoted"] else 2
    print(
        result.with_suffix(".html") if args.command in {"trial", "confirm"} else result
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
