# compute_ep_postmus.py

"""
Compute the per-phase mano expected-points table weighted by the post-mus hand
distribution and save it into probability_tables.pkl under the key "ep_mano_postmus".

Identical structure to compute_expected_points.py / _ep_mano_worker, but each
hand h3 / hx / hy is weighted by:

    w = deck_multiplicity(hand | remaining_deck) * postmus_prob[hand]

Deck exclusion is fully preserved (you cannot deal the same physical card to two
seats), but the relative weight of each valid assignment is rescaled by how
probable that hand is after the mus discard phase.

Requires:
  - probability_tables.pkl with ep_mano populated
  - probability_tables.pkl["hand_distribution_post_mus"] (run compute_hand_distribution.py)

Usage:
    python compute_ep_postmus.py
    python compute_ep_postmus.py --output my_tables.pkl
"""
import argparse
import pickle
import sys
import time
from collections import Counter
from pathlib import Path

import multiprocessing as _mp

from build_tables import (
    TABLE_PATH,
    EP_MANO_PHASES,
    all_canonical_hands,
    _mult_from_counts,
    _precompute_hand_props,
    _precompute_phase_ranks,
)
from constants import cards_space


def _ep_mano_postmus_worker(args):
    """Per-phase expected-points for h1 as seat 0 (mano), weighted by post-mus distribution.

    Same phase logic as _ep_mano_worker.  The only difference is that each
    hand h3 / hx / hy carries an additional factor of postmus_dist[hand] so
    that the integral is over the post-mus hand distribution rather than the
    uniform deal distribution.
    """
    import numpy as np
    h1, hands_list, deck, postmus_dist = args
    N = len(hands_list)
    hand_counters = {h: dict(Counter(h)) for h in hands_list}
    hand_cnt_list = [hand_counters[h] for h in hands_list]
    props = _precompute_hand_props(hands_list)
    phase_ranks = _precompute_phase_ranks(hands_list, props)

    INDEP_PHASES = ['Grande', 'Chica', 'Pares']

    rank_arrs = {
        phase: np.array([phase_ranks[phase][h] for h in hands_list], dtype=np.int32)
        for phase in EP_MANO_PHASES
    }
    has_pares_arr   = np.array([props[h]['has_pares']    for h in hands_list], dtype=np.bool_)
    has_juego_arr   = np.array([props[h]['has_juego']    for h in hands_list], dtype=np.bool_)
    pares_score_arr = np.array([props[h]['pares_score']  for h in hands_list], dtype=np.float64)
    juego_pts_arr   = np.array([props[h]['juego_points'] for h in hands_list], dtype=np.float64)
    postmus_arr     = np.array([postmus_dist.get(h, 0.0) for h in hands_list], dtype=np.float64)

    acc = {phase: {
        'total_weight': 0.0, 'winA_weight': 0.0, 'winB_weight': 0.0,
        'teamA_points_sum': 0.0, 'teamB_points_sum': 0.0,
        'both_when_A_sum': 0.0, 'both_when_B_sum': 0.0,
    } for phase in INDEP_PHASES}

    acc_jp = {
        'total_weight':      0.0,
        'winA_weight':       0.0, 'winB_weight':       0.0,
        'winA_juego_weight': 0.0, 'winB_juego_weight': 0.0,
        'winA_punto_weight': 0.0, 'winB_punto_weight': 0.0,
        'teamA_JP_sum':      0.0, 'teamB_JP_sum':      0.0,
        'teamA_Juego_sum':   0.0, 'teamB_Juego_sum':   0.0,
        'both_when_A_sum':   0.0, 'both_when_B_sum':   0.0,
    }

    D1 = dict(deck)
    for c, n in hand_counters[h1].items():
        D1[c] -= n
    p_h1 = props[h1]

    for h3 in hands_list:
        wh3_deck = _mult_from_counts(hand_counters[h3], D1)
        if not wh3_deck:
            continue
        ph3 = postmus_dist.get(h3, 0.0)
        if not ph3:
            continue
        wh3 = wh3_deck * ph3

        p_h3 = props[h3]
        D2 = dict(D1)
        for c, n in hand_counters[h3].items():
            D2[c] -= n

        # Per-(h1, h3) champion info for independent phases
        phase_h3 = {}
        for phase in INDEP_PHASES:
            rk = phase_ranks[phase]
            rh1, rh3 = rk[h1], rk[h3]
            champA_is_h3 = rh3 > rh1
            rank_champA  = rh3 if champA_is_h3 else rh1
            if phase == 'Pares':
                tA_has = p_h1['has_pares'] or p_h3['has_pares']
                tA_pts = float(p_h1['pares_score'] + p_h3['pares_score'])
            else:
                tA_has = True
                tA_pts = 1.0
            phase_h3[phase] = (champA_is_h3, rank_champA, tA_has, tA_pts)

        # JP champion info for Juego and Punto sub-phases
        rh1_j, rh3_j = phase_ranks['Juego'][h1], phase_ranks['Juego'][h3]
        cA_h3_j      = rh3_j > rh1_j
        rA_j         = rh3_j if cA_h3_j else rh1_j
        tA_juego_pts = float(p_h1['juego_points'] + p_h3['juego_points'])
        tA_has_juego = p_h1['has_juego'] or p_h3['has_juego']

        rh1_p, rh3_p = phase_ranks['Punto'][h1], phase_ranks['Punto'][h3]
        cA_h3_p      = rh3_p > rh1_p
        rA_p         = rh3_p if cA_h3_p else rh1_p

        # Collect valid opponent pairs, weighting by post-mus probability
        ix_list, iy_list, w_list = [], [], []
        for i_x in range(N):
            wx_deck = _mult_from_counts(hand_cnt_list[i_x], D2)
            if not wx_deck:
                continue
            px = postmus_arr[i_x]
            if not px:
                continue
            D2x = dict(D2)
            for c, n in hand_cnt_list[i_x].items():
                D2x[c] -= n
            bwx = wh3 * wx_deck * px
            for i_y in range(i_x, N):
                wy_deck = _mult_from_counts(hand_cnt_list[i_y], D2x)
                if not wy_deck:
                    continue
                py = postmus_arr[i_y]
                if not py:
                    continue
                ix_list.append(i_x)
                iy_list.append(i_y)
                w_list.append(bwx * wy_deck * py)

        if not ix_list:
            continue

        ix = np.array(ix_list, dtype=np.int32)
        iy = np.array(iy_list, dtype=np.int32)
        w  = np.array(w_list,  dtype=np.float64)

        # --- Independent phases (Grande, Chica, Pares) ---
        for phase in INDEP_PHASES:
            champA_is_h3, rank_champA, tA_has, tA_pts = phase_h3[phase]

            rx = rank_arrs[phase][ix]
            ry = rank_arrs[phase][iy]
            rank_stronger = np.maximum(rx, ry)
            seat_mult     = np.where(rx != ry, 2, 1)
            total_w       = w * seat_mult

            B_strict = rank_stronger > rank_champA
            B_tie    = np.bool_(champA_is_h3) & (rank_stronger == rank_champA)
            A_wins   = ~B_strict & ~B_tie

            if phase == 'Pares':
                tB_pts   = pares_score_arr[ix] + pares_score_arr[iy]
                both_arr = np.bool_(tA_has) & (has_pares_arr[ix] | has_pares_arr[iy])
            else:
                tB_pts   = np.ones(len(ix), dtype=np.float64)
                both_arr = None

            a = acc[phase]
            a['total_weight'] += float(total_w.sum())

            if B_strict.any():
                wB = total_w[B_strict]
                a['winB_weight']      += float(wB.sum())
                a['teamB_points_sum'] += float((wB * tB_pts[B_strict]).sum())
                if both_arr is not None:
                    a['both_when_B_sum'] += float((wB * both_arr[B_strict]).sum())

            if B_tie.any():
                wB_t  = w[B_tie]
                seats = seat_mult[B_tie]
                wA_t  = wB_t * (seats - 1)
                a['winB_weight']      += float(wB_t.sum())
                a['teamB_points_sum'] += float((wB_t * tB_pts[B_tie]).sum())
                if both_arr is not None:
                    a['both_when_B_sum'] += float((wB_t * both_arr[B_tie]).sum())
                a['winA_weight']      += float(wA_t.sum())
                a['teamA_points_sum'] += float(wA_t.sum()) * tA_pts
                if both_arr is not None:
                    a['both_when_A_sum'] += float((wA_t * both_arr[B_tie]).sum())

            if A_wins.any():
                wA = total_w[A_wins]
                a['winA_weight']      += float(wA.sum())
                a['teamA_points_sum'] += float(wA.sum()) * tA_pts
                if both_arr is not None:
                    a['both_when_A_sum'] += float((wA * both_arr[A_wins]).sum())

        # --- Combined JP phase ---
        deal_has_juego = (
            np.bool_(tA_has_juego) | has_juego_arr[ix] | has_juego_arr[iy]
        )

        rx_jp = np.where(deal_has_juego, rank_arrs['Juego'][ix], rank_arrs['Punto'][ix])
        ry_jp = np.where(deal_has_juego, rank_arrs['Juego'][iy], rank_arrs['Punto'][iy])
        cA_jp = np.where(deal_has_juego, cA_h3_j, cA_h3_p).astype(np.bool_)
        rA_jp = np.where(deal_has_juego, rA_j,    rA_p)

        rank_stronger_jp = np.maximum(rx_jp, ry_jp)
        seat_mult_jp     = np.where(rx_jp != ry_jp, 2, 1)
        total_w_jp       = w * seat_mult_jp

        B_strict_jp = rank_stronger_jp > rA_jp
        B_tie_jp    = cA_jp & (rank_stronger_jp == rA_jp)
        A_wins_jp   = ~B_strict_jp & ~B_tie_jp

        tA_JP_pts    = np.where(deal_has_juego, tA_juego_pts, 1.0)
        tB_JP_pts    = np.where(deal_has_juego, juego_pts_arr[ix] + juego_pts_arr[iy], 1.0)
        tA_Juego_pts = np.where(deal_has_juego, tA_juego_pts, 0.0)
        tB_Juego_pts = np.where(deal_has_juego, juego_pts_arr[ix] + juego_pts_arr[iy], 0.0)

        both_juego = np.bool_(tA_has_juego) & (has_juego_arr[ix] | has_juego_arr[iy])

        a = acc_jp
        a['total_weight'] += float(total_w_jp.sum())

        if B_strict_jp.any():
            m  = B_strict_jp
            wB = total_w_jp[m]
            a['winB_weight']       += float(wB.sum())
            a['teamB_JP_sum']      += float((wB * tB_JP_pts[m]).sum())
            a['teamB_Juego_sum']   += float((wB * tB_Juego_pts[m]).sum())
            a['both_when_B_sum']   += float((wB * both_juego[m]).sum())
            mj = m & deal_has_juego;  mp = m & ~deal_has_juego
            if mj.any(): a['winB_juego_weight'] += float(total_w_jp[mj].sum())
            if mp.any(): a['winB_punto_weight'] += float(total_w_jp[mp].sum())

        if B_tie_jp.any():
            m     = B_tie_jp
            wB_t  = w[m]
            seats = seat_mult_jp[m]
            wA_t  = wB_t * (seats - 1)
            a['winB_weight']       += float(wB_t.sum())
            a['teamB_JP_sum']      += float((wB_t * tB_JP_pts[m]).sum())
            a['teamB_Juego_sum']   += float((wB_t * tB_Juego_pts[m]).sum())
            a['both_when_B_sum']   += float((wB_t * both_juego[m]).sum())
            a['winA_weight']       += float(wA_t.sum())
            a['teamA_JP_sum']      += float((wA_t * tA_JP_pts[m]).sum())
            a['teamA_Juego_sum']   += float((wA_t * tA_Juego_pts[m]).sum())
            a['both_when_A_sum']   += float((wA_t * both_juego[m]).sum())
            mj = m & deal_has_juego;  mp = m & ~deal_has_juego
            if mj.any():
                a['winB_juego_weight'] += float(w[mj].sum())
                a['winA_juego_weight'] += float((w[mj] * (seat_mult_jp[mj] - 1)).sum())
            if mp.any():
                a['winB_punto_weight'] += float(w[mp].sum())
                a['winA_punto_weight'] += float((w[mp] * (seat_mult_jp[mp] - 1)).sum())

        if A_wins_jp.any():
            m  = A_wins_jp
            wA = total_w_jp[m]
            a['winA_weight']       += float(wA.sum())
            a['teamA_JP_sum']      += float((wA * tA_JP_pts[m]).sum())
            a['teamA_Juego_sum']   += float((wA * tA_Juego_pts[m]).sum())
            a['both_when_A_sum']   += float((wA * both_juego[m]).sum())
            mj = m & deal_has_juego;  mp = m & ~deal_has_juego
            if mj.any(): a['winA_juego_weight'] += float(total_w_jp[mj].sum())
            if mp.any(): a['winA_punto_weight'] += float(total_w_jp[mp].sum())

    # --- Build result ---
    result = {}

    for phase in INDEP_PHASES:
        a  = acc[phase]
        tw = a['total_weight']
        wA = a['winA_weight']
        wB = a['winB_weight']
        eA = a['teamA_points_sum'] / tw if tw else 0.0
        eB = a['teamB_points_sum'] / tw if tw else 0.0
        entry = {
            'prob_A_wins':                  wA / tw if tw else 0.0,
            'prob_B_wins':                  wB / tw if tw else 0.0,
            'expected_A_points':            eA,
            'expected_B_points':            eB,
            'expected_net_A':               eA - eB,
            'expected_total_winner_points': eA + eB,
        }
        if phase == 'Pares':
            entry['prob_both_given_A_wins'] = a['both_when_A_sum'] / wA if wA else 0.0
            entry['prob_both_given_B_wins'] = a['both_when_B_sum'] / wB if wB else 0.0
        result[phase] = entry

    a    = acc_jp
    tw   = a['total_weight']
    wA_j = a['winA_juego_weight']
    wB_j = a['winB_juego_weight']
    wA_p = a['winA_punto_weight']

    j_eA  = a['teamA_Juego_sum'] / tw if tw else 0.0
    j_eB  = a['teamB_Juego_sum'] / tw if tw else 0.0
    jp_eA = a['teamA_JP_sum']    / tw if tw else 0.0
    jp_eB = a['teamB_JP_sum']    / tw if tw else 0.0
    p_eA  = jp_eA - j_eA
    p_eB  = jp_eB - j_eB

    result['Juego'] = {
        'prob_A_wins':                  wA_j / tw if tw else 0.0,
        'prob_B_wins':                  wB_j / tw if tw else 0.0,
        'expected_A_points':            j_eA,
        'expected_B_points':            j_eB,
        'expected_net_A':               j_eA - j_eB,
        'expected_total_winner_points': j_eA + j_eB,
        'prob_both_given_A_wins':       a['both_when_A_sum'] / wA_j if wA_j else 0.0,
        'prob_both_given_B_wins':       a['both_when_B_sum'] / wB_j if wB_j else 0.0,
    }
    result['Punto'] = {
        'prob_A_wins':                  wA_p / tw if tw else 0.0,
        'prob_B_wins':                  a['winB_punto_weight'] / tw if tw else 0.0,
        'expected_A_points':            p_eA,
        'expected_B_points':            p_eB,
        'expected_net_A':               p_eA - p_eB,
        'expected_total_winner_points': p_eA + p_eB,
    }
    return h1, result


def _build_ep_mano_postmus_table(all_hands: dict, deck: dict, postmus_dist: dict,
                                  progress_cb=None, workers: int = None) -> dict:
    """Per-phase expected-points table weighted by post-mus distribution. Parallelized per h1."""
    import time as _time
    hands_list = sorted(all_hands.keys())
    N = len(hands_list)
    n_workers = workers or _mp.cpu_count()
    tasks = [(h1, hands_list, deck, postmus_dist) for h1 in hands_list]
    t_start = _time.time()
    result = {}
    print(f"  launching {n_workers} workers for {N} tasks...", flush=True)
    with _mp.Pool(processes=n_workers) as pool:
        for done, (h1, phase_data) in enumerate(
                pool.imap_unordered(_ep_mano_postmus_worker, tasks), 1):
            result[h1] = phase_data
            elapsed = _time.time() - t_start
            eta = elapsed / done * (N - done) if done else 0
            print(f"  {done}/{N} ({done*100//N}%)  elapsed {elapsed:.0f}s  ETA {eta:.0f}s",
                  flush=True)
            if progress_cb:
                progress_cb(done, N)
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Compute per-phase mano expected-points table weighted by post-mus distribution"
    )
    parser.add_argument("--output", type=Path, default=TABLE_PATH,
                        help="Pickle to update (default: probability_tables.pkl)")
    args = parser.parse_args()

    if not args.output.exists():
        print(f"ERROR: {args.output} not found. Run build_tables.py first.", file=sys.stderr)
        sys.exit(1)

    print("Loading existing tables...")
    with open(args.output, "rb") as f:
        tables = pickle.load(f)

    if "hand_distribution_post_mus" not in tables:
        print("ERROR: hand_distribution_post_mus not found in pickle. "
              "Run compute_hand_distribution.py first.", file=sys.stderr)
        sys.exit(1)

    postmus_dist = tables["hand_distribution_post_mus"]
    print(f"  Loaded post-mus distribution: {len(postmus_dist)} hands with non-zero probability")
    print(f"  Total probability mass: {sum(postmus_dist.values()):.6f}")

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

    print("Computing post-mus per-phase mano expected-points table...")
    result = _build_ep_mano_postmus_table(
        all_hands, cards_space, postmus_dist, progress_cb=progress_cb
    )

    print("Attaching ep_mano_postmus to tables...")
    for hand, phase_data in result.items():
        tables[hand]["ep_mano_postmus"] = phase_data

    print(f"Saving to {args.output}...")
    with open(args.output, "wb") as f:
        pickle.dump(tables, f)
    print(f"Done. Total time: {time.time() - start:.0f}s")


if __name__ == "__main__":
    main()
