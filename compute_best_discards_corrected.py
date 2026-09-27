"""
compute_best_discards_corrected.py

Identical to compute_best_discards.py, except that the expected-net-A scalars
are derived from ep_mano_postmus (post-mus weighted distribution) instead of
ep_mano (uniform deal distribution).

Results are stored under separate keys so existing data is never overwritten:

    tables[hand]["best_discards_corrected"]
    tables[hand]["no_discard_stats_corrected"]

Requires ep_mano_postmus to be populated first (run compute_ep_postmus.py).

Usage:
    python compute_best_discards_corrected.py
    python compute_best_discards_corrected.py --input my_tables.pkl --output out.pkl
"""
import argparse
import pickle
import sys
import time
from itertools import combinations, combinations_with_replacement
from pathlib import Path

from build_tables import TABLE_PATH, all_canonical_hands, canonical, _multiplicity_subset
from constants import cards_space


_EP_PHASES    = ['Grande', 'Chica', 'Pares', 'Juego', 'Punto']
_PHASE_BESTS  = ['Grande', 'Chica', 'Pares', 'Juego']   # Punto omitted; Juego uses JP metric


def _option_scalars(kept: tuple, n_draw: int, remaining_draw: dict, tables: dict):
    """
    Summary scalars for keeping `kept` (canonical sub-hand) and drawing n_draw cards.
    Uses ep_mano_postmus for expected-net-A values.

    Returns a dict with keys:
        total_net_A, total_action, net_per_phase, juego_punto_net_A
    or None if ep_mano_postmus is unavailable for any reachable hand.
    """
    if n_draw == 0:
        ep = tables.get(kept, {}).get("ep_mano_postmus")
        if ep is None:
            return None
        net    = {p: ep[p]["expected_net_A"] for p in _EP_PHASES}
        action = sum(ep[p]["expected_A_points"] + ep[p]["expected_B_points"]
                     for p in _EP_PHASES)
    else:
        cards_avail = [c for c, cnt in remaining_draw.items() if cnt > 0]
        net_sums   = {p: 0.0 for p in _EP_PHASES}
        action_sum = 0.0
        total_w    = 0

        for draw in combinations_with_replacement(cards_avail, n_draw):
            w = _multiplicity_subset(draw, remaining_draw)
            if not w:
                continue
            new_hand = canonical(list(kept) + list(draw))
            ep = tables.get(new_hand, {}).get("ep_mano_postmus")
            if ep is None:
                continue
            for p in _EP_PHASES:
                net_sums[p] += ep[p]["expected_net_A"] * w
            action_sum += sum(
                (ep[p]["expected_A_points"] + ep[p]["expected_B_points"]) * w
                for p in _EP_PHASES
            )
            total_w += w

        if not total_w:
            return None
        net    = {p: net_sums[p] / total_w for p in _EP_PHASES}
        action = action_sum / total_w

    return {
        'total_net_A':       sum(net.values()),
        'total_action':      action,
        'net_per_phase':     net,
        'juego_punto_net_A': net['Juego'] + net['Punto'],
    }


def _build_hand_entries(my_hand: tuple, tables: dict, deck: dict):
    """
    Returns (best_discards_corrected, no_discard_stats_corrected) for one hand.
    Either value may be None if data is unavailable.
    """
    remaining = dict(deck)
    for card in my_hand:
        remaining[card] -= 1

    all_options: dict = {}
    for r in range(5):
        for discard_idx in combinations(range(4), r):
            kept     = tuple(c for i, c in enumerate(my_hand) if i not in discard_idx)
            kept_key = canonical(list(kept))
            if kept_key in all_options:
                continue
            remaining_draw = dict(remaining)
            for i in discard_idx:
                remaining_draw[my_hand[i]] += 1
            scalars = _option_scalars(kept_key, r, remaining_draw, tables)
            if scalars is not None:
                all_options[kept_key] = scalars

    if not all_options:
        return None, None

    no_discard_key = canonical(list(my_hand))

    others_sorted = sorted(
        [(k, v) for k, v in all_options.items() if k != no_discard_key],
        key=lambda kv: -kv[1]['total_net_A'],
    )
    all_options_net = [
        {"kept": k, "total_net_A": v['total_net_A'], "net_per_phase": v['net_per_phase']}
        for k, v in others_sorted
    ]

    discard_only = {k: v for k, v in all_options.items() if k != no_discard_key}
    if not discard_only:
        discard_only = all_options

    best_by_phase = {}
    for phase in _PHASE_BESTS:
        if phase == 'Juego':
            metric = lambda v: v['juego_punto_net_A']
        else:
            metric = lambda v, p=phase: v['net_per_phase'][p]
        best_k = max(discard_only, key=lambda k: metric(discard_only[k]))
        best_by_phase[phase] = {"kept": best_k, "net_A": metric(discard_only[best_k])}

    max_k = max(discard_only, key=lambda k: discard_only[k]['total_action'])
    min_k = min(discard_only, key=lambda k: discard_only[k]['total_action'])

    best_discards_corrected = {
        "all_options_net": all_options_net,
        "best_by_phase":   best_by_phase,
        "max_action_kept": {"kept": max_k, "total_action": all_options[max_k]['total_action']},
        "min_action_kept": {"kept": min_k, "total_action": all_options[min_k]['total_action']},
    }

    no_discard_stats_corrected = None
    if no_discard_key in all_options:
        nd         = all_options[no_discard_key]
        all_sorted = sorted(all_options.items(), key=lambda kv: -kv[1]['total_net_A'])
        rank       = next(i + 1 for i, (k, _) in enumerate(all_sorted) if k == no_discard_key)

        improvement_by_phase = {}
        for phase in _PHASE_BESTS:
            nd_val   = nd['juego_punto_net_A']    if phase == 'Juego' else nd['net_per_phase'][phase]
            best_val = best_by_phase[phase]['net_A']
            improvement_by_phase[phase] = best_val - nd_val

        best_discard_net = others_sorted[0][1]['total_net_A'] if others_sorted else nd['total_net_A']

        no_discard_stats_corrected = {
            "rank":                    rank,
            "improvement_by_phase":    improvement_by_phase,
            "delta_total_net_vs_best": best_discard_net - nd['total_net_A'],
            "action_vs_max":           all_options[max_k]['total_net_A'] - nd['total_net_A'],
            "action_vs_min":           all_options[min_k]['total_net_A'] - nd['total_net_A'],
        }

    return best_discards_corrected, no_discard_stats_corrected


def main():
    parser = argparse.ArgumentParser(
        description="Compute best-discard summaries from ep_mano_postmus table"
    )
    parser.add_argument("--input",  type=Path, default=TABLE_PATH)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    if args.output is None:
        args.output = args.input

    if not args.input.exists():
        print(f"ERROR: {args.input} not found. Run build_tables.py first.", file=sys.stderr)
        sys.exit(1)

    print("Loading tables...")
    with open(args.input, "rb") as f:
        tables = pickle.load(f)

    all_hands  = all_canonical_hands(cards_space)
    hands_list = sorted(all_hands.keys())
    n          = len(hands_list)

    missing_ep = [h for h in hands_list if "ep_mano_postmus" not in tables.get(h, {})]
    if missing_ep:
        print(f"WARNING: {len(missing_ep)}/{n} hands missing ep_mano_postmus — "
              "run compute_ep_postmus.py first.", file=sys.stderr)
        if len(missing_ep) == n:
            sys.exit(1)

    print(f"Computing best-discard-corrected entries for {n - len(missing_ep)} hands...")
    start = time.time()

    for i, hand in enumerate(hands_list):
        if "ep_mano_postmus" not in tables.get(hand, {}):
            continue

        best_discards_corrected, no_discard_stats_corrected = _build_hand_entries(
            hand, tables, cards_space
        )

        if best_discards_corrected is not None:
            tables[hand]["best_discards_corrected"] = best_discards_corrected
        if no_discard_stats_corrected is not None:
            tables[hand]["no_discard_stats_corrected"] = no_discard_stats_corrected

        elapsed = time.time() - start
        eta     = elapsed / (i + 1) * (n - i - 1)
        print(f"  {i + 1}/{n} ({(i + 1) * 100 // n}%)  "
              f"elapsed {elapsed:.0f}s  ETA {eta:.0f}s", flush=True)

    print(f"Saving to {args.output}...")
    with open(args.output, "wb") as f:
        pickle.dump(tables, f)
    print(f"Done. {time.time() - start:.0f}s total.")


if __name__ == "__main__":
    main()
