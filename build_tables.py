from itertools import combinations_with_replacement, combinations
from collections import Counter
from math import comb
import pickle
from pathlib import Path
from card import Card
from constants import cards_space
from hand import Hand
from phases import Grande, Chica, Pares, Juego

PHASES = [Grande, Chica, Pares, Juego]
TABLE_PATH = Path(__file__).parent / "probability_tables.pkl"


def canonical(cards):
    return tuple(sorted(cards, reverse=True))


def _multiplicity(hand: tuple) -> int:
    counts = Counter(hand)
    result = 1
    for card, n in counts.items():
        available = cards_space[card]
        if n > available:
            return 0
        result *= comb(available, n)
    return result


def all_canonical_hands() -> dict:
    """Returns {canonical_hand: multiplicity} for all 330 distinct hands."""
    cards_list = list(cards_space.keys())
    hands = {}
    for combo in combinations_with_replacement(cards_list, 4):
        c = canonical(combo)
        if c not in hands:
            mult = _multiplicity(c)
            if mult > 0:
                hands[c] = mult
    return hands


def _build_win_tables(all_hands: dict) -> dict:
    tables = {}
    for my_hand in all_hands:
        entry = {}
        for phase_cls in PHASES:
            p_win_count = 0
            p_tie_count = 0
            total = 0
            for opp_hand, opp_mult in all_hands.items():
                result = phase_cls.play(Hand(list(my_hand)), Hand(list(opp_hand)))
                if result > 0:
                    p_win_count += opp_mult
                elif result == 0:
                    p_tie_count += opp_mult
                total += opp_mult
            entry[phase_cls.__name__] = {
                "p_win": p_win_count / total,
                "p_tie": p_tie_count / total,
                "p_loss": (total - p_win_count - p_tie_count) / total,
            }
        tables[my_hand] = entry
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


def _expected_strength_after_best_discard(my_hand: tuple, tables: dict, all_hands: dict) -> dict:
    remaining_counts = dict(cards_space)
    for card in my_hand:
        remaining_counts[card] -= 1

    def draw_weight_p_win(kept: tuple, n_draw: int) -> dict:
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

    best = {p.__name__: 0.0 for p in PHASES}
    indices = list(range(4))
    for r in range(5):
        for discard_idx in combinations(indices, r):
            kept = tuple(c for i, c in enumerate(my_hand) if i not in discard_idx)
            for i, c in enumerate(my_hand):
                if i in discard_idx:
                    remaining_counts[c] += 1
            result = draw_weight_p_win(kept, r)
            for i, c in enumerate(my_hand):
                if i in discard_idx:
                    remaining_counts[c] -= 1
            for phase_name, val in result.items():
                if val > best[phase_name]:
                    best[phase_name] = val
    return best


def _build_avg_opp_improvement(all_hands: dict, tables: dict) -> dict:
    total_weight = sum(all_hands.values())
    phase_sums = {p.__name__: 0.0 for p in PHASES}
    for hand, mult in all_hands.items():
        current = {p.__name__: tables[hand][p.__name__]["p_win"] for p in PHASES}
        best = _expected_strength_after_best_discard(hand, tables, all_hands)
        for phase_cls in PHASES:
            name = phase_cls.__name__
            phase_sums[name] += (best[name] - current[name]) * mult
    return {name: val / total_weight for name, val in phase_sums.items()}


def build_and_save():
    print("Enumerating canonical hands...")
    all_hands = all_canonical_hands()
    print(f"  {len(all_hands)} canonical hands found")
    print("Computing win probability tables...")
    tables = _build_win_tables(all_hands)
    print("Computing average opponent improvement per phase...")
    avg_improvement = _build_avg_opp_improvement(all_hands, tables)
    tables["_avg_opp_phase_improvements"] = avg_improvement
    with open(TABLE_PATH, "wb") as f:
        pickle.dump(tables, f)
    print(f"Saved to {TABLE_PATH}")
    return tables


if __name__ == "__main__":
    build_and_save()
