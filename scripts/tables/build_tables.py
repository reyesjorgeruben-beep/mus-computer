from itertools import combinations_with_replacement, combinations, permutations as iperms
from collections import Counter
from math import comb
import pickle
from pathlib import Path
from mus_computer.cards.card import Card
from mus_computer.constants import cards_space
from mus_computer.cards.hand import Hand
from mus_computer.game.phases import Grande, Chica, Pares, Juego, Punto

PHASES = [Grande, Chica, Pares, Juego]
EP_MANO_PHASES = ['Grande', 'Chica', 'Pares', 'Juego', 'Punto']
from scripts.tables.paths import TABLE_PATH


def canonical(cards):
    return tuple(sorted(cards, reverse=True))


def _multiplicity(hand: tuple, deck: dict) -> int:
    counts = Counter(hand)
    result = 1
    for card, n in counts.items():
        available = deck[card]
        if n > available:
            return 0
        result *= comb(available, n)
    return result


def all_canonical_hands(deck: dict = None) -> dict:
    """Returns {canonical_hand: multiplicity} for all distinct 4-card hands in the deck."""
    if deck is None:
        deck = cards_space
    cards_list = list(deck.keys())
    hands = {}
    for combo in combinations_with_replacement(cards_list, 4):
        c = canonical(combo)
        if c not in hands:
            mult = _multiplicity(c, deck)
            if mult > 0:
                hands[c] = mult
    return hands


def _report_progress(i: int, total: int, label: str) -> None:
    prev = i * 100 // total
    curr = (i + 1) * 100 // total
    for milestone in (25, 50, 75, 100):
        if prev < milestone <= curr:
            print(f"  {label}: {milestone}%")


def _build_win_tables(all_hands: dict) -> dict:
    tables = {}
    hands_list = list(all_hands.keys())
    total = len(hands_list)
    for i, my_hand in enumerate(hands_list):
        entry = {}
        for phase_cls in PHASES:
            p_win_count = 0
            p_tie_count = 0
            total_w = 0
            for opp_hand, opp_mult in all_hands.items():
                result = phase_cls.play(Hand(list(my_hand)), Hand(list(opp_hand)))
                if result > 0:
                    p_win_count += opp_mult
                elif result == 0:
                    p_tie_count += opp_mult
                total_w += opp_mult
            entry[phase_cls.__name__] = {
                "p_win": p_win_count / total_w,
                "p_tie": p_tie_count / total_w,
                "p_loss": (total_w - p_win_count - p_tie_count) / total_w,
            }
        tables[my_hand] = entry
        _report_progress(i, total, "win tables")
    return tables


def _multiplicity_subset(cards_tuple: tuple, available: dict) -> int:
    counts = Counter(cards_tuple)
    result = 1
    for card, n in counts.items():
        avail = available.get(card, 0)
        if n > avail:
            return 0
        result *= comb(avail, n)
    return result


def _mult_from_counts(counts: dict, available: dict) -> int:
    result = 1
    for card, n in counts.items():
        avail = available.get(card, 0)
        if n > avail:
            return 0
        result *= comb(avail, n)
    return result


def _draw_expected_p_win(kept: tuple, n_draw: int, remaining_counts: dict, tables: dict) -> dict:
    """Analytical expected p_win per phase after drawing n_draw cards to fill kept."""
    if n_draw == 0:
        new_hand = canonical(kept)
        return {p.__name__: tables[new_hand][p.__name__]["p_win"] for p in PHASES}
    draw_totals = {p.__name__: 0.0 for p in PHASES}
    weight_total = 0
    for draw_combo in combinations_with_replacement(list(remaining_counts.keys()), n_draw):
        draw_mult = _multiplicity_subset(draw_combo, remaining_counts)
        if draw_mult == 0:
            continue
        new_hand = canonical(list(kept) + list(draw_combo))
        for phase_cls in PHASES:
            draw_totals[phase_cls.__name__] += tables[new_hand][phase_cls.__name__]["p_win"] * draw_mult
        weight_total += draw_mult
    if weight_total == 0:
        return {p.__name__: 0.0 for p in PHASES}
    return {k: v / weight_total for k, v in draw_totals.items()}


def _compute_discard_options(my_hand: tuple, tables: dict, remaining_counts: dict) -> dict:
    """
    Returns {canonical_kept: {phase_name: expected_p_win}} for all unique discard choices.
    remaining_counts must already reflect my_hand cards removed from the deck.
    """
    seen: dict = {}
    indices = list(range(len(my_hand)))
    for r in range(len(my_hand) + 1):
        for discard_idx in combinations(indices, r):
            kept = tuple(c for i, c in enumerate(my_hand) if i not in discard_idx)
            kept_key = canonical(kept)
            if kept_key in seen:
                continue
            for i, c in enumerate(my_hand):
                if i in discard_idx:
                    remaining_counts[c] += 1
            result = _draw_expected_p_win(kept, r, remaining_counts, tables)
            for i, c in enumerate(my_hand):
                if i in discard_idx:
                    remaining_counts[c] -= 1
            seen[kept_key] = result
    return seen


def _build_discard_options_table(all_hands: dict, tables: dict, deck: dict = None) -> dict:
    """
    Returns {canonical_hand: {canonical_kept: {phase_name: expected_p_win}}}
    for every hand in all_hands.
    """
    if deck is None:
        deck = cards_space
    discard_table = {}
    hands_list = list(all_hands.keys())
    total = len(hands_list)
    for i, my_hand in enumerate(hands_list):
        remaining_counts = dict(deck)
        for card in my_hand:
            remaining_counts[card] -= 1
        discard_table[my_hand] = _compute_discard_options(my_hand, tables, remaining_counts)
        _report_progress(i, total, "discard options")
    return discard_table


def _build_avg_opp_improvement(all_hands: dict, discard_table: dict) -> dict:
    total_weight = sum(all_hands.values())
    phase_sums = {p.__name__: 0.0 for p in PHASES}
    hands_list = list(all_hands.keys())
    total = len(hands_list)
    for i, (hand, mult) in enumerate(all_hands.items()):
        options = discard_table[hand]
        for phase_cls in PHASES:
            name = phase_cls.__name__
            best_val = max(opt[name] for opt in options.values())
            current_val = options[canonical(list(hand))][name]
            phase_sums[name] += (best_val - current_val) * mult
        _report_progress(i, total, "avg opp improvement")
    return {name: val / total_weight for name, val in phase_sums.items()}


def _attach_discard_data(tables: dict, discard_table: dict) -> None:
    """Attach discard_options and avg_phase_improvement to each hand entry in-place."""
    for hand, options in discard_table.items():
        tables[hand]["discard_options"] = options
        kept_all = canonical(list(hand))
        tables[hand]["avg_phase_improvement"] = {
            p.__name__: max(opt[p.__name__] for opt in options.values())
                        - options[kept_all][p.__name__]
            for p in PHASES
        }


def _precompute_hand_props(hands_list: list) -> dict:
    props = {}
    for h in hands_list:
        hand = Hand(list(h))
        counts = Counter(h)
        paired_cards = tuple(c for c in h if counts[c] > 1)  # h already sorted desc
        props[h] = {
            'grande_key': h,
            'chica_key': h[::-1],
            'has_pares': hand.has_pares,
            'pares_big_score': hand.pares_big_score,
            'pares_score': Pares.calculate_points(hand),
            'pares_paired_cards': paired_cards,
            'has_juego': hand.has_juego,
            'juego_rank': hand.get_juego_score(),
            'juego_points': Juego.calculate_points(hand),
            'punto_value': hand.juego,
        }
    return props


def _score_4hands(h0, h1, h2, h3, props: dict) -> tuple:
    """Returns (tantos_A, tantos_B). Teams: A={seats 0,2}, B={seats 1,3}."""
    p = [props[h0], props[h1], props[h2], props[h3]]
    tantos = [0.0, 0.0]
    team = [0, 1, 0, 1]
    team_seats = [[0, 2], [1, 3]]

    # Grande: higher canonical tuple wins; iterate seats 0→3, update only on strict win
    w = 0
    for s in (1, 2, 3):
        if p[s]['grande_key'] > p[w]['grande_key']:
            w = s
    tantos[team[w]] += 1

    # Chica: lower reversed tuple wins (smaller cards = better chica)
    w = 0
    for s in (1, 2, 3):
        if p[s]['chica_key'] < p[w]['chica_key']:
            w = s
    tantos[team[w]] += 1

    # Pares
    pares_seats = [s for s in range(4) if p[s]['has_pares']]
    if pares_seats:
        w = pares_seats[0]  # lowest seat first
        for s in pares_seats[1:]:
            ps, pw = p[s]['pares_big_score'], p[w]['pares_big_score']
            if ps > pw or (ps == pw and p[s]['pares_paired_cards'] > p[w]['pares_paired_cards']):
                w = s
        wt = team[w]
        lt = 1 - wt
        tantos[wt] += sum(p[s]['pares_score'] for s in team_seats[wt])
        if any(p[s]['has_pares'] for s in team_seats[lt]):
            tantos[wt] += 0.5

    # Juego or Punto
    juego_seats = [s for s in range(4) if p[s]['has_juego']]
    if juego_seats:
        w = juego_seats[0]
        for s in juego_seats[1:]:
            if p[s]['juego_rank'] > p[w]['juego_rank']:
                w = s
        wt = team[w]
        lt = 1 - wt
        tantos[wt] += sum(p[s]['juego_points'] for s in team_seats[wt])
        if any(p[s]['has_juego'] for s in team_seats[lt]):
            tantos[wt] += 0.5
    else:
        # Punto: higher sum wins
        w = 0
        for s in (1, 2, 3):
            if p[s]['punto_value'] > p[w]['punto_value']:
                w = s
        tantos[team[w]] += 1

    return tantos[0], tantos[1]


def _precompute_phase_ranks(hands_list: list, props: dict) -> dict:
    """Returns {phase_name: {hand: int_rank}} where higher rank = stronger."""
    specs = {
        'Grande': (lambda h: props[h]['grande_key'], False),
        'Chica':  (lambda h: props[h]['chica_key'],  True),
        'Pares':  (lambda h: (props[h]['has_pares'], props[h]['pares_big_score'],
                              props[h]['pares_paired_cards']), False),
        'Juego':  (lambda h: (props[h]['has_juego'], props[h]['juego_rank']), False),
        'Punto':  (lambda h: props[h]['punto_value'], False),
    }
    ranks = {}
    for phase, (key_fn, reverse) in specs.items():
        sorted_hands = sorted(hands_list, key=key_fn, reverse=reverse)
        phase_ranks = {}
        current_rank = 0
        prev_key = None
        for h in sorted_hands:
            k = key_fn(h)
            if k != prev_key:
                current_rank += 1
                prev_key = k
            phase_ranks[h] = current_rank
        ranks[phase] = phase_ranks
    return ranks


def _ep_mano_worker(args):
    """Per-phase expected-points for h1 as seat 0 (mano). Numpy-accelerated phase loop.

    Grande, Chica, Pares are independent phases.
    Juego and Punto share a single JP phase: if any player holds Juego the Juego
    sub-phase fires; otherwise Punto (1 tanto) fires.  Punto is derived by
    subtracting the true-Juego contribution from the combined JP accumulator,
    so neither phase is ever computed over the wrong set of deals.
    """
    import numpy as np
    h1, hands_list, deck = args
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
        wh3 = _mult_from_counts(hand_counters[h3], D1)
        if not wh3:
            continue
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

        # Collect valid pairs
        ix_list, iy_list, w_list = [], [], []
        for i_x in range(N):
            wx = _mult_from_counts(hand_cnt_list[i_x], D2)
            if not wx:
                continue
            D2x = dict(D2)
            for c, n in hand_cnt_list[i_x].items():
                D2x[c] -= n
            bwx = wh3 * wx
            for i_y in range(i_x, N):
                wy = _mult_from_counts(hand_cnt_list[i_y], D2x)
                if not wy:
                    continue
                ix_list.append(i_x)
                iy_list.append(i_y)
                w_list.append(bwx * wy)

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
        # A deal has Juego when any of the 4 seats holds a Juego hand
        deal_has_juego = (
            np.bool_(tA_has_juego) | has_juego_arr[ix] | has_juego_arr[iy]
        )

        # Effective ranks and Team-A champion switch between Juego and Punto
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

        # Points: true Juego points when Juego fires, 1 tanto when Punto fires
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
        'prob_B_wins':                  a['winB_juego_weight'] / tw if tw else 0.0,
        'expected_A_points':            j_eA,
        'expected_B_points':            j_eB,
        'expected_net_A':               j_eA - j_eB,
        'expected_total_winner_points': j_eA + j_eB,
        'prob_both_given_A_wins':       a['both_when_A_sum'] / wA_j if wA_j else 0.0,
        'prob_both_given_B_wins':       a['both_when_B_sum'] / a['winB_juego_weight']
                                        if a['winB_juego_weight'] else 0.0,
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


def _build_ep_mano_table(all_hands: dict, deck: dict,
                          progress_cb=None, workers: int = None) -> dict:
    """Per-phase expected-points table for seat-0 (mano). Parallelized per h1."""
    import time as _time
    import multiprocessing as _mp
    hands_list = sorted(all_hands.keys())
    N = len(hands_list)
    n_workers = workers or _mp.cpu_count()
    tasks = [(h1, hands_list, deck) for h1 in hands_list]
    t_start = _time.time()
    result = {}
    print(f"  launching {n_workers} workers for {N} tasks...", flush=True)
    with _mp.Pool(processes=n_workers) as pool:
        for done, (h1, phase_data) in enumerate(
                pool.imap_unordered(_ep_mano_worker, tasks), 1):
            result[h1] = phase_data
            elapsed = _time.time() - t_start
            eta = elapsed / done * (N - done) if done else 0
            print(f"  {done}/{N} ({done*100//N}%)  elapsed {elapsed:.0f}s  ETA {eta:.0f}s",
                  flush=True)
            if progress_cb:
                progress_cb(done, N)
    return result


def _ep_worker(args):
    """Worker: process a single i0 slice. Returns partial accumulators."""
    i0, hands_list, deck = args
    hand_counters = {h: dict(Counter(h)) for h in hands_list}
    props = _precompute_hand_props(hands_list)
    N = len(hands_list)

    acc_net = {h: [0.0] * 4 for h in hands_list}
    acc_team = {h: [0.0] * 4 for h in hands_list}
    acc_weight = {h: [0.0] * 4 for h in hands_list}
    valid_combos = 0

    h0 = hands_list[i0]
    hc0 = hand_counters[h0]
    rem = dict(deck)
    for c, n in hc0.items():
        rem[c] -= n

    for i1 in range(i0, N):
        h1 = hands_list[i1]
        if not _multiplicity_subset(h1, rem):
            continue
        hc1 = hand_counters[h1]
        for c, n in hc1.items():
            rem[c] -= n

        for i2 in range(i1, N):
            h2 = hands_list[i2]
            if not _multiplicity_subset(h2, rem):
                continue
            hc2 = hand_counters[h2]
            for c, n in hc2.items():
                rem[c] -= n

            for i3 in range(i2, N):
                h3 = hands_list[i3]
                if not _multiplicity_subset(h3, rem):
                    continue
                valid_combos += 1

                seen_perms: set = set()
                for perm in iperms((h0, h1, h2, h3)):
                    if perm in seen_perms:
                        continue
                    seen_perms.add(perm)
                    p0, p1, p2, p3 = perm

                    r = dict(deck)
                    w = 1
                    for h in (p0, p1, p2, p3):
                        m = _multiplicity_subset(h, r)
                        if not m:
                            w = 0
                            break
                        w *= m
                        for cv, nv in hand_counters[h].items():
                            r[cv] -= nv
                    if not w:
                        continue

                    tA, tB = _score_4hands(p0, p1, p2, p3, props)
                    net_A = tA - tB
                    net_B = -net_A

                    acc_net[p0][0] += net_A * w; acc_team[p0][0] += tA * w; acc_weight[p0][0] += w
                    acc_net[p1][1] += net_B * w; acc_team[p1][1] += tB * w; acc_weight[p1][1] += w
                    acc_net[p2][2] += net_A * w; acc_team[p2][2] += tA * w; acc_weight[p2][2] += w
                    acc_net[p3][3] += net_B * w; acc_team[p3][3] += tB * w; acc_weight[p3][3] += w

            for c, n in hc2.items():
                rem[c] += n

        for c, n in hc1.items():
            rem[c] += n

    return acc_net, acc_team, acc_weight, valid_combos


def _build_expected_points_table(all_hands: dict, deck: dict,
                                  progress_cb=None, workers: int = None) -> dict:
    """Parallel version: dispatches one task per i0 across CPU cores, merges results."""
    import time as _time
    import multiprocessing as _mp
    hands_list = sorted(all_hands.keys())
    N = len(hands_list)
    n_workers = workers or _mp.cpu_count()
    tasks = [(i0, hands_list, deck) for i0 in range(N)]
    t_start = _time.time()

    acc_net = {h: [0.0] * 4 for h in hands_list}
    acc_team = {h: [0.0] * 4 for h in hands_list}
    acc_weight = {h: [0.0] * 4 for h in hands_list}
    total_combos = 0

    print(f"  launching {n_workers} workers for {N} tasks...", flush=True)
    with _mp.Pool(processes=n_workers) as pool:
        for done, (pnet, pteam, pweight, vc) in enumerate(
                pool.imap_unordered(_ep_worker, tasks), 1):
            total_combos += vc
            for h in hands_list:
                for s in range(4):
                    acc_net[h][s] += pnet[h][s]
                    acc_team[h][s] += pteam[h][s]
                    acc_weight[h][s] += pweight[h][s]
            elapsed = _time.time() - t_start
            eta = elapsed / done * (N - done) if done else 0
            print(f"  {done}/{N} ({done*100//N}%)  "
                  f"{total_combos:,} combos  elapsed {elapsed:.0f}s  ETA {eta:.0f}s",
                  flush=True)
            if progress_cb:
                progress_cb(done, N)

    result = {}
    for h in hands_list:
        result[h] = {}
        for s in range(4):
            w = acc_weight[h][s]
            result[h][s] = {
                "expected_net_tantos": acc_net[h][s] / w if w else 0.0,
                "expected_team_tantos": acc_team[h][s] / w if w else 0.0,
            }
    return result


def build_tables(deck: dict = None, include_expected_points: bool = False) -> dict:
    """Build and return tables dict without writing to disk. Useful for testing.
    include_expected_points runs the heavy O(N^4) enumeration; off by default for fast tests."""
    if deck is None:
        deck = cards_space
    all_hands = all_canonical_hands(deck)
    tables = _build_win_tables(all_hands)
    discard_table = _build_discard_options_table(all_hands, tables, deck)
    _attach_discard_data(tables, discard_table)
    avg_improvement = _build_avg_opp_improvement(all_hands, discard_table)
    tables["_avg_opp_phase_improvements"] = avg_improvement
    if include_expected_points:
        ep_mano = _build_ep_mano_table(all_hands, deck)
        for hand, phase_data in ep_mano.items():
            tables[hand]["ep_mano"] = phase_data
    return tables


def build_and_save(deck: dict = None, output_path=None):
    if deck is None:
        deck = cards_space
    path = output_path if output_path is not None else TABLE_PATH

    print("Enumerating canonical hands...")
    all_hands = all_canonical_hands(deck)
    print(f"  {len(all_hands)} canonical hands found")
    print("Computing win probability tables...")
    tables = _build_win_tables(all_hands)
    print("Computing discard options tables...")
    discard_table = _build_discard_options_table(all_hands, tables, deck)
    _attach_discard_data(tables, discard_table)
    print("Computing average opponent improvement per phase...")
    avg_improvement = _build_avg_opp_improvement(all_hands, discard_table)
    tables["_avg_opp_phase_improvements"] = avg_improvement
    print("Computing per-phase expected points table (mano)...")
    ep_mano = _build_ep_mano_table(all_hands, deck)
    for hand, phase_data in ep_mano.items():
        tables[hand]["ep_mano"] = phase_data
    with open(path, "wb") as f:
        pickle.dump(tables, f)
    print(f"Saved to {path}")
    return tables


if __name__ == "__main__":
    build_and_save()
