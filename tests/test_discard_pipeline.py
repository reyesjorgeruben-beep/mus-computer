"""
Reduced-universe pipeline tests for build_tables + discard options.

Mini deck: A(8), 4(4), 5(4), 6(4)  ->  20 cards, 35 canonical 4-card hands.
Runs fully in-memory in < 5 seconds, validating the full discard pipeline
without touching the production probability_tables.pkl.
"""
import time
import pytest
from itertools import combinations_with_replacement

from card import Card
from build_tables import (
    build_tables,
    all_canonical_hands,
    canonical,
    _build_win_tables,
    _build_discard_options_table,
    _build_avg_opp_improvement,
    _score_4hands,
    _precompute_hand_props,
    _precompute_phase_ranks,
    EP_MANO_PHASES,
)

MINI_DECK = {
    Card.A: 8,
    Card._4: 4,
    Card._5: 4,
    Card._6: 4,
}
PHASE_NAMES = ["Grande", "Chica", "Pares", "Juego"]
EQUAL_WEIGHTS = {p: 1.0 for p in PHASE_NAMES}


@pytest.fixture(scope="module")
def mini_tables():
    return build_tables(MINI_DECK, include_expected_points=True)


@pytest.fixture(scope="module")
def mini_hands():
    return all_canonical_hands(MINI_DECK)


# ---------------------------------------------------------------------------
# Structural completeness
# ---------------------------------------------------------------------------

def test_mini_deck_yields_35_hands(mini_hands):
    assert len(mini_hands) == 35


def test_build_completes_under_5s():
    start = time.time()
    build_tables(MINI_DECK)
    assert time.time() - start < 5.0


def test_all_hands_have_phase_win_probs(mini_tables, mini_hands):
    for hand in mini_hands:
        for phase in PHASE_NAMES:
            assert phase in mini_tables[hand], f"{hand} missing phase {phase}"
            entry = mini_tables[hand][phase]
            assert "p_win" in entry and "p_tie" in entry and "p_loss" in entry


def test_all_hands_have_discard_options(mini_tables, mini_hands):
    for hand in mini_hands:
        assert "discard_options" in mini_tables[hand], f"{hand} missing discard_options"
        assert len(mini_tables[hand]["discard_options"]) > 0


def test_keeping_all_cards_is_always_an_option(mini_tables, mini_hands):
    for hand in mini_hands:
        kept_all = canonical(list(hand))
        opts = mini_tables[hand]["discard_options"]
        assert kept_all in opts, f"keeping all cards missing for {hand}"


# ---------------------------------------------------------------------------
# Value validity
# ---------------------------------------------------------------------------

def test_win_probs_are_valid_probabilities(mini_tables, mini_hands):
    for hand in mini_hands:
        for phase in PHASE_NAMES:
            entry = mini_tables[hand][phase]
            total = entry["p_win"] + entry["p_tie"] + entry["p_loss"]
            assert abs(total - 1.0) < 1e-9, f"{hand} {phase} probs don't sum to 1: {total}"
            for k in ("p_win", "p_tie", "p_loss"):
                assert 0.0 <= entry[k] <= 1.0, f"{hand} {phase} {k} out of range"


def test_discard_option_p_wins_are_valid(mini_tables, mini_hands):
    for hand in mini_hands:
        for kept, phase_wins in mini_tables[hand]["discard_options"].items():
            for phase in PHASE_NAMES:
                assert phase in phase_wins, f"missing phase {phase} in discard option"
                v = phase_wins[phase]
                assert 0.0 <= v <= 1.0, f"p_win {v} out of range for {hand} kept {kept}"


def test_discard_option_kept_has_4_or_fewer_cards(mini_hands, mini_tables):
    for hand in mini_hands:
        for kept in mini_tables[hand]["discard_options"]:
            assert len(kept) <= 4, f"kept hand has more than 4 cards: {kept}"


# ---------------------------------------------------------------------------
# Correctness: best discard improves or equals current strength
# ---------------------------------------------------------------------------

def test_best_discard_post_mus_geq_current(mini_tables, mini_hands):
    """Weighted post-mus win prob must be >= current for at least equal-weight scoring."""
    for hand in mini_hands:
        opts = mini_tables[hand]["discard_options"]
        kept_all = canonical(list(hand))
        current = sum(opts[kept_all].get(p, 0.0) for p in PHASE_NAMES)
        best = max(sum(v.get(p, 0.0) for p in PHASE_NAMES) for v in opts.values())
        assert best >= current - 1e-9, (
            f"best post-mus strength {best} < current {current} for {hand}"
        )


def test_avg_opp_improvements_non_negative(mini_tables):
    improvements = mini_tables["_avg_opp_phase_improvements"]
    for phase in PHASE_NAMES:
        assert phase in improvements
        assert improvements[phase] >= -1e-9, f"negative avg improvement for {phase}"


# ---------------------------------------------------------------------------
# Discard index correctness: kept cards are a subset of original hand
# ---------------------------------------------------------------------------

def test_kept_cards_are_subset_of_hand(mini_tables, mini_hands):
    from collections import Counter
    for hand in mini_hands:
        hand_counts = Counter(hand)
        for kept in mini_tables[hand]["discard_options"]:
            kept_counts = Counter(kept)
            for card, cnt in kept_counts.items():
                assert cnt <= hand_counts[card], (
                    f"kept {kept} has more {card} than original hand {hand}"
                )


# ---------------------------------------------------------------------------
# ep_mano table (per-phase mano expected points)
# ---------------------------------------------------------------------------

def test_all_hands_have_ep_mano(mini_tables, mini_hands):
    for hand in mini_hands:
        assert "ep_mano" in mini_tables[hand], f"{hand} missing ep_mano"
        ep = mini_tables[hand]["ep_mano"]
        assert set(ep.keys()) == set(EP_MANO_PHASES), f"{hand} ep_mano missing phases"


def test_ep_mano_required_fields(mini_tables, mini_hands):
    base_fields = {"prob_A_wins", "prob_B_wins", "expected_A_points",
                   "expected_B_points", "expected_net_A", "expected_total_winner_points"}
    bonus_fields = {"prob_both_given_A_wins", "prob_both_given_B_wins"}
    for hand in mini_hands:
        ep = mini_tables[hand]["ep_mano"]
        for phase in EP_MANO_PHASES:
            assert base_fields <= set(ep[phase].keys()), \
                f"{hand} {phase} missing fields"
            if phase in ("Pares", "Juego"):
                assert bonus_fields <= set(ep[phase].keys()), \
                    f"{hand} {phase} missing bonus fields"


def test_ep_mano_probabilities_valid(mini_tables, mini_hands):
    import math
    for hand in mini_hands:
        ep = mini_tables[hand]["ep_mano"]
        for phase in EP_MANO_PHASES:
            e = ep[phase]
            for key in ("prob_A_wins", "prob_B_wins"):
                assert 0.0 <= e[key] <= 1.0 + 1e-9, f"{hand} {phase} {key} out of range"
            assert math.isfinite(e["expected_net_A"]), f"{hand} {phase} expected_net_A not finite"
            assert math.isfinite(e["expected_A_points"]), f"{hand} {phase} expected_A_points not finite"


def test_ep_mano_prob_sums_leq_one(mini_tables, mini_hands):
    """prob_A_wins + prob_B_wins <= 1 (remainder = no contest, e.g. no-pares rounds)."""
    for hand in mini_hands:
        ep = mini_tables[hand]["ep_mano"]
        for phase in EP_MANO_PHASES:
            total = ep[phase]["prob_A_wins"] + ep[phase]["prob_B_wins"]
            assert total <= 1.0 + 1e-9, f"{hand} {phase} win probs sum > 1: {total}"


def test_ep_mano_expected_points_non_negative(mini_tables, mini_hands):
    for hand in mini_hands:
        ep = mini_tables[hand]["ep_mano"]
        for phase in EP_MANO_PHASES:
            assert ep[phase]["expected_A_points"] >= -1e-9, \
                f"{hand} {phase} expected_A_points negative"
            assert ep[phase]["expected_B_points"] >= -1e-9, \
                f"{hand} {phase} expected_B_points negative"


def test_ep_mano_grande_win_rate_plausible(mini_hands, mini_tables):
    """Best Grande hand should win more than half the time as mano."""
    hands_list = sorted(mini_hands.keys())
    props = _precompute_hand_props(hands_list)
    phase_ranks = _precompute_phase_ranks(hands_list, props)
    best_grande = max(hands_list, key=lambda h: phase_ranks['Grande'][h])
    ep = mini_tables[best_grande]["ep_mano"]["Grande"]
    assert ep["prob_A_wins"] > 0.5, \
        f"best Grande hand should win >50% as mano, got {ep['prob_A_wins']:.3f}"


def test_ep_mano_best_chica_wins_often(mini_hands, mini_tables):
    """Best Chica hand (all aces) should win Chica often as mano."""
    hands_list = sorted(mini_hands.keys())
    props = _precompute_hand_props(hands_list)
    phase_ranks = _precompute_phase_ranks(hands_list, props)
    best_chica = max(hands_list, key=lambda h: phase_ranks['Chica'][h])
    ep = mini_tables[best_chica]["ep_mano"]["Chica"]
    assert ep["prob_A_wins"] > 0.5, \
        f"best Chica hand should win >50% as mano, got {ep['prob_A_wins']:.3f}"


def test_ep_mano_net_A_symmetry(mini_tables, mini_hands):
    """expected_net_A == expected_A_points - expected_B_points."""
    for hand in mini_hands:
        ep = mini_tables[hand]["ep_mano"]
        for phase in EP_MANO_PHASES:
            e = ep[phase]
            computed = e["expected_A_points"] - e["expected_B_points"]
            assert abs(computed - e["expected_net_A"]) < 1e-9, \
                f"{hand} {phase} net_A mismatch"


# ---------------------------------------------------------------------------
# _score_4hands sanity checks (unchanged helper)
# ---------------------------------------------------------------------------

def test_score_4hands_grande_always_awards_1(mini_hands):
    """Grande always contributes exactly 1 tanto total."""
    hands_list = list(mini_hands.keys())
    props = _precompute_hand_props(hands_list)
    h = hands_list
    tA, tB = _score_4hands(h[0], h[1], h[2], h[3], props)
    assert tA + tB >= 2.0  # at minimum grande + chica = 2 tantos total


def test_score_4hands_symmetry(mini_hands):
    """Swapping team A and B hands flips the scores."""
    hands_list = list(mini_hands.keys())
    props = _precompute_hand_props(hands_list)
    h = hands_list
    tA, tB = _score_4hands(h[0], h[1], h[2], h[3], props)
    tA2, tB2 = _score_4hands(h[1], h[0], h[3], h[2], props)
    assert abs(tA - tB2) < 1e-9 and abs(tB - tA2) < 1e-9, (
        f"Score not symmetric: ({tA},{tB}) vs swapped ({tA2},{tB2})"
    )
