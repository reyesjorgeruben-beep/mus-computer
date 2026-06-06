# compute_expected_points.py

"""
Compute the per-phase mano expected-points table and save it into probability_tables.pkl.

Usage:
    python compute_expected_points.py
    python compute_expected_points.py --output my_tables.pkl

Progress is logged to the terminal for each of the 330 h1 tasks.
"""
import argparse
import pickle
import sys
import time
from pathlib import Path

from build_tables import TABLE_PATH, all_canonical_hands, _build_ep_mano_table
from constants import cards_space


def main():
    parser = argparse.ArgumentParser(description="Compute per-phase mano expected-points table")
    parser.add_argument("--output", type=Path, default=TABLE_PATH,
                        help="Pickle to update (default: probability_tables.pkl)")
    args = parser.parse_args()

    if not args.output.exists():
        print(f"ERROR: {args.output} not found. Run build_tables.py first.", file=sys.stderr)
        sys.exit(1)

    print("Loading existing tables...")
    with open(args.output, "rb") as f:
        tables = pickle.load(f)

    print("Enumerating canonical hands...")
    all_hands = all_canonical_hands(cards_space)
    print(f"  {len(all_hands)} canonical hands")

    start = time.time()
    last_pct = -1

    def progress_cb(done: int, total: int):
        nonlocal last_pct
        pct = done * 100 // total
        if pct == last_pct:
            return
        last_pct = pct
        elapsed = time.time() - start
        eta = (elapsed / done * (total - done)) if done else 0
        print(f"  {pct:3d}%  [{done}/{total} hands]  elapsed {elapsed:.0f}s  ETA {eta:.0f}s")

    print("Computing per-phase mano expected-points table...")
    result = _build_ep_mano_table(all_hands, cards_space, progress_cb=progress_cb)

    print("Attaching ep_mano to tables...")
    for hand, phase_data in result.items():
        tables[hand]["ep_mano"] = phase_data

    print(f"Saving to {args.output}...")
    with open(args.output, "wb") as f:
        pickle.dump(tables, f)
    print(f"Done. Total time: {time.time() - start:.0f}s")


if __name__ == "__main__":
    main()
