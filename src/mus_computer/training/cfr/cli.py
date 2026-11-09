"""Command-line arguments and the CFR training entry point."""

from __future__ import annotations

import argparse
from pathlib import Path

from .config import CFRConfig
from .trainer import CFRTrainer


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train shared Mus strategy with sampled CFR"
    )
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--exploration", type=float, default=0.1)
    parser.add_argument("--snapshot-every", type=int, default=10)
    parser.add_argument("--run-dir", type=Path, default=Path("docs/training/cfr_runs"))
    args = parser.parse_args()
    trainer = CFRTrainer(
        CFRConfig(args.iterations, args.seed, args.exploration, args.snapshot_every),
        run_dir=args.run_dir,
    )
    trainer.train()
    print(f"Snapshots: {args.run_dir / 'snapshots'}")
