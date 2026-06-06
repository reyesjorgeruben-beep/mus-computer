"""
compute_hand_distribution.py

Computes the post-mus hand distribution: the probability of ending with each
canonical hand AFTER the discard phase, given that a player called "Mus"
(i.e. decided to discard).

Only hands where discarding improves expected net (delta_total_net_vs_best > 0)
are considered as possible starting hands — hands a player would keep entirely
are excluded because they would not call Mus in the first place.

Formula (conditional on calling Mus):

    p_final(h_f) = sum_i  p(h_i | calls Mus) * P(h_f | h_i, best_discard(h_i))

where p(h_i | calls Mus) = p_deal(h_i) / sum_{j: discards} p_deal(h_j)

Stores result in probability_tables.pkl under "hand_distribution_post_mus".

Usage:
    python compute_hand_distribution.py
    python compute_hand_distribution.py --input my_tables.pkl --output out.pkl
"""
import argparse
import csv
import pickle
import sys
import time
from collections import defaultdict
from itertools import combinations_with_replacement
from pathlib import Path

from build_tables import TABLE_PATH, all_canonical_hands, canonical, _multiplicity_subset
from constants import cards_space


def _best_kept(hand: tuple, entry: dict) -> tuple:
    """
    Return the kept sub-hand for the best discard strategy.
    Uses delta_total_net_vs_best > 0 to decide whether to discard at all.
    """
    nd = entry.get("no_discard_stats", {})
    bd = entry.get("best_discards", {})
    opts = bd.get("all_options_net", [])
    if opts and nd.get("delta_total_net_vs_best", 0.0) > 0:
        return opts[0]["kept"]
    return hand  # no discard


def _transition(kept: tuple, n_draw: int) -> dict:
    """
    {canonical_new_hand: weight}  weights sum to C(N, n_draw)
    where N = cards remaining after removing `kept` from the full deck.
    """
    remaining = dict(cards_space)
    for card in kept:
        remaining[card] -= 1

    cards_avail = [c for c, cnt in remaining.items() if cnt > 0]
    result: dict = {}
    for draw in combinations_with_replacement(cards_avail, n_draw):
        w = _multiplicity_subset(draw, remaining)
        if w:
            h_f = canonical(list(kept) + list(draw))
            result[h_f] = result.get(h_f, 0) + w
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Compute post-discard hand distribution"
    )
    parser.add_argument("--input",  type=Path, default=TABLE_PATH)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--csv",    type=Path, default=None,
                        help="Optional CSV output path")
    args = parser.parse_args()
    if args.output is None:
        args.output = args.input

    if not args.input.exists():
        print(f"ERROR: {args.input} not found.", file=sys.stderr)
        sys.exit(1)

    print("Loading tables...")
    with open(args.input, "rb") as f:
        tables = pickle.load(f)

    multiplicities = all_canonical_hands(cards_space)
    total_deals    = sum(multiplicities.values())
    all_hands      = sorted(multiplicities.keys())
    n              = len(all_hands)

    # First pass: identify which hands would call Mus (delta > 0 → discard)
    best_kept_map: dict[tuple, tuple] = {}
    for hand in all_hands:
        best_kept_map[hand] = _best_kept(hand, tables.get(hand, {}))

    mus_hands = [h for h in all_hands if len(best_kept_map[h]) < 4]
    no_mus_hands = [h for h in all_hands if len(best_kept_map[h]) == 4]

    p_mus_total = sum(multiplicities[h] / total_deals for h in mus_hands)
    print(f"  Hands that call Mus (discard): {len(mus_hands)}/330")
    print(f"  Hands that keep all (no Mus):  {len(no_mus_hands)}/330")
    print(f"  P(calling Mus) = {p_mus_total:.4f}")

    start = time.time()
    p_initial: dict[tuple, float] = {}
    p_final: dict[tuple, float] = defaultdict(float)

    for i, hand in enumerate(mus_hands):
        p_deal = multiplicities[hand] / total_deals
        p_initial[hand] = p_deal
        p_cond = p_deal / p_mus_total   # conditional on calling Mus

        kept   = best_kept_map[hand]
        n_draw = 4 - len(kept)
        dist   = _transition(kept, n_draw)
        total_w = sum(dist.values())
        if total_w:
            for h_f, w in dist.items():
                p_final[h_f] += p_cond * w / total_w

        if (i + 1) % 66 == 0 or i + 1 == len(mus_hands):
            print(f"  {i+1}/{len(mus_hands)}  elapsed {time.time()-start:.1f}s")

    total_mass = sum(p_final.values())
    print(f"Total probability mass: {total_mass:.8f}  (should be 1.0)")

    tables["hand_distribution_post_mus"] = dict(p_final)

    csv_path = args.csv or args.output.parent / "hand_distribution_post_mus.csv"
    _write_csv(all_hands, p_final, csv_path)

    print(f"Saving pickle to {args.output}...")
    with open(args.output, "wb") as f:
        pickle.dump(tables, f)
    print(f"Done. {time.time()-start:.1f}s total.")


def _hand_str(hand: tuple) -> str:
    return "".join(c.value for c in hand) if hand else "(none)"


def _write_csv(all_hands, p_final, path: Path) -> None:
    rows = []
    for hand in all_hands:
        p = p_final.get(hand, 0.0)
        rows.append({
            "hand":    _hand_str(hand),
            "p_final": round(p, 8),
            "p_pct":   round(p * 100, 4),
        })
    rows.sort(key=lambda r: -r["p_final"])
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"  Written: {path}  ({len(rows)} rows)")


if __name__ == "__main__":
    main()
