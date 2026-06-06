"""
Correctness tests for _ep_mano_worker / _build_ep_mano_table.

Uses small synthetic decks for deterministic outcomes and a pure-Python
brute-force reference that mirrors the algorithm without numpy tricks.
Does NOT require probability_tables.pkl.

Deck catalogue
--------------
MONO_DECK   {R:16}          — one canonical hand (R,R,R,R); all ties → mano wins all phases
RA_DECK     {R:4, A:16}     — h1=(R,R,R,R) exhausts R's; all opponents forced to (A,A,A,A)
LOW_DECK    {A:4,4:4,5:4,6:4} — max card sum = 24 < 31, so no hand has Juego
JUEGO_DECK  {R:8, A:8}      — mix: (R,R,R,A)=31 best juego; (A,A,A,A) no juego
MINI_DECK   {A:8,4:4,5:4,6:4} — 35 canonical hands; brute-force cross-check of all hands
Full deck   cards_space       — production deck; single-hand brute-force vs worker (@slow)
"""
import pytest
from collections import Counter

from card import Card
from build_tables import (
    build_tables,
    all_canonical_hands,
    canonical,
    _precompute_hand_props,
    _precompute_phase_ranks,
    _mult_from_counts,
    _ep_mano_worker,
    EP_MANO_PHASES,
)

# ---------------------------------------------------------------------------
# Deck definitions
# ---------------------------------------------------------------------------

MONO_DECK  = {Card.R: 16}
RA_DECK    = {Card.R: 4, Card.A: 16}
LOW_DECK   = {Card.A: 4, Card._4: 4, Card._5: 4, Card._6: 4}
JUEGO_DECK = {Card.R: 8, Card.A: 8}
MINI_DECK  = {Card.A: 8, Card._4: 4, Card._5: 4, Card._6: 4}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def mono_tables():
    return build_tables(MONO_DECK, include_expected_points=True)


@pytest.fixture(scope="module")
def ra_tables():
    return build_tables(RA_DECK, include_expected_points=True)


@pytest.fixture(scope="module")
def low_tables():
    return build_tables(LOW_DECK, include_expected_points=True)


@pytest.fixture(scope="module")
def low_hands():
    return all_canonical_hands(LOW_DECK)


@pytest.fixture(scope="module")
def juego_tables():
    return build_tables(JUEGO_DECK, include_expected_points=True)


@pytest.fixture(scope="module")
def mini_tables():
    return build_tables(MINI_DECK, include_expected_points=True)


@pytest.fixture(scope="module")
def mini_hands():
    return all_canonical_hands(MINI_DECK)


# ---------------------------------------------------------------------------
# Brute-force reference implementation
# Pure-Python O(N^4), no numpy — used to cross-check the vectorised worker.
# ---------------------------------------------------------------------------

def _brute_force_ep_mano(h1: tuple, deck: dict) -> dict:
    """Pure-Python O(N^4) reference matching _ep_mano_worker semantics exactly.

    Juego and Punto share one JP phase: Juego fires when any player holds Juego,
    otherwise Punto fires (1 tanto).  Punto expected points = JP - Juego by subtraction.
    """
    all_hands = all_canonical_hands(deck)
    hands_list = sorted(all_hands.keys())
    hc    = {h: dict(Counter(h)) for h in hands_list}
    props = _precompute_hand_props(hands_list)
    ranks = _precompute_phase_ranks(hands_list, props)

    D1 = dict(deck)
    for c, n in hc[h1].items():
        D1[c] -= n

    INDEP = ['Grande', 'Chica', 'Pares']
    acc = {ph: dict(tw=0.0, wA=0.0, wB=0.0, ptA=0.0, ptB=0.0, bA=0.0, bB=0.0)
           for ph in INDEP}
    jp = dict(tw=0.0,
              wA=0.0,   wB=0.0,
              wA_j=0.0, wB_j=0.0,
              wA_p=0.0, wB_p=0.0,
              ptA_JP=0.0, ptB_JP=0.0,
              ptA_J=0.0,  ptB_J=0.0,
              bA=0.0, bB=0.0)
    p1 = props[h1]

    for h3 in hands_list:
        wh3 = _mult_from_counts(hc[h3], D1)
        if not wh3:
            continue
        p3 = props[h3]
        D2 = dict(D1)
        for c, n in hc[h3].items():
            D2[c] -= n

        for ix, hx in enumerate(hands_list):
            wx = _mult_from_counts(hc[hx], D2)
            if not wx:
                continue
            D2x = dict(D2)
            for c, n in hc[hx].items():
                D2x[c] -= n
            px = props[hx]

            for iy, hy in enumerate(hands_list):
                if iy < ix:
                    continue
                wy = _mult_from_counts(hc[hy], D2x)
                if not wy:
                    continue
                py = props[hy]

                base_w = wh3 * wx * wy

                # --- Independent phases ---
                for phase in INDEP:
                    rk = ranks[phase]
                    rh1v, rh3v = rk[h1], rk[h3]
                    rxv, ryv   = rk[hx], rk[hy]

                    champA_is_h3  = rh3v > rh1v
                    rank_champA   = rh3v if champA_is_h3 else rh1v
                    rank_stronger = max(rxv, ryv)
                    seat_mult     = 2 if rxv != ryv else 1
                    total_w       = base_w * seat_mult

                    B_strict = rank_stronger > rank_champA
                    B_tie    = champA_is_h3 and (rank_stronger == rank_champA)

                    if phase == 'Pares':
                        tA_pts = float(p1['pares_score'] + p3['pares_score'])
                        tB_pts = float(px['pares_score'] + py['pares_score'])
                        both   = (p1['has_pares'] or p3['has_pares']) and \
                                 (px['has_pares'] or py['has_pares'])
                    else:
                        tA_pts, tB_pts, both = 1.0, 1.0, False

                    a = acc[phase]
                    a['tw'] += total_w
                    if B_strict:
                        a['wB']  += total_w
                        a['ptB'] += total_w * tB_pts
                        if both: a['bB'] += total_w
                    elif B_tie:
                        a['wB']  += base_w
                        a['ptB'] += base_w * tB_pts
                        if both: a['bB'] += base_w
                        wA_t = float(base_w * (seat_mult - 1))
                        if wA_t:
                            a['wA']  += wA_t
                            a['ptA'] += wA_t * tA_pts
                            if both: a['bA'] += wA_t
                    else:
                        a['wA']  += total_w
                        a['ptA'] += total_w * tA_pts
                        if both: a['bA'] += total_w

                # --- Combined JP phase ---
                deal_has_juego = (p1['has_juego'] or p3['has_juego'] or
                                  px['has_juego'] or py['has_juego'])

                if deal_has_juego:
                    rk_jp = ranks['Juego']
                    tA_pts_jp = float(p1['juego_points'] + p3['juego_points'])
                    tB_pts_jp = float(px['juego_points'] + py['juego_points'])
                    tA_pts_j  = tA_pts_jp
                    tB_pts_j  = tB_pts_jp
                else:
                    rk_jp = ranks['Punto']
                    tA_pts_jp, tB_pts_jp = 1.0, 1.0
                    tA_pts_j,  tB_pts_j  = 0.0, 0.0

                rh1v, rh3v = rk_jp[h1], rk_jp[h3]
                rxv, ryv   = rk_jp[hx], rk_jp[hy]

                champA_is_h3  = rh3v > rh1v
                rank_champA   = rh3v if champA_is_h3 else rh1v
                rank_stronger = max(rxv, ryv)
                seat_mult     = 2 if rxv != ryv else 1
                total_w       = base_w * seat_mult

                B_strict = rank_stronger > rank_champA
                B_tie    = champA_is_h3 and (rank_stronger == rank_champA)

                both = ((p1['has_juego'] or p3['has_juego']) and
                        (px['has_juego'] or py['has_juego']))

                jp['tw'] += total_w
                if B_strict:
                    jp['wB']     += total_w
                    jp['ptB_JP'] += total_w * tB_pts_jp
                    jp['ptB_J']  += total_w * tB_pts_j
                    if deal_has_juego: jp['wB_j'] += total_w
                    else:              jp['wB_p'] += total_w
                    if both: jp['bB'] += total_w
                elif B_tie:
                    jp['wB']     += base_w
                    jp['ptB_JP'] += base_w * tB_pts_jp
                    jp['ptB_J']  += base_w * tB_pts_j
                    if deal_has_juego: jp['wB_j'] += base_w
                    else:              jp['wB_p'] += base_w
                    if both: jp['bB'] += base_w
                    wA_t = float(base_w * (seat_mult - 1))
                    if wA_t:
                        jp['wA']     += wA_t
                        jp['ptA_JP'] += wA_t * tA_pts_jp
                        jp['ptA_J']  += wA_t * tA_pts_j
                        if deal_has_juego: jp['wA_j'] += wA_t
                        else:              jp['wA_p'] += wA_t
                        if both: jp['bA'] += wA_t
                else:
                    jp['wA']     += total_w
                    jp['ptA_JP'] += total_w * tA_pts_jp
                    jp['ptA_J']  += total_w * tA_pts_j
                    if deal_has_juego: jp['wA_j'] += total_w
                    else:              jp['wA_p'] += total_w
                    if both: jp['bA'] += total_w

    out = {}
    for phase in INDEP:
        a = acc[phase]
        tw = a['tw']; wA = a['wA']; wB = a['wB']
        eA = a['ptA'] / tw if tw else 0.0
        eB = a['ptB'] / tw if tw else 0.0
        entry = {
            'prob_A_wins':                  wA / tw if tw else 0.0,
            'prob_B_wins':                  wB / tw if tw else 0.0,
            'expected_A_points':            eA,
            'expected_B_points':            eB,
            'expected_net_A':               eA - eB,
            'expected_total_winner_points': eA + eB,
        }
        if phase == 'Pares':
            entry['prob_both_given_A_wins'] = a['bA'] / wA if wA else 0.0
            entry['prob_both_given_B_wins'] = a['bB'] / wB if wB else 0.0
        out[phase] = entry

    tw   = jp['tw']
    wA_j = jp['wA_j'];  wB_j = jp['wB_j']
    wA_p = jp['wA_p'];  wB_p = jp['wB_p']
    j_eA  = jp['ptA_J']  / tw if tw else 0.0
    j_eB  = jp['ptB_J']  / tw if tw else 0.0
    jp_eA = jp['ptA_JP'] / tw if tw else 0.0
    jp_eB = jp['ptB_JP'] / tw if tw else 0.0
    p_eA  = jp_eA - j_eA
    p_eB  = jp_eB - j_eB

    out['Juego'] = {
        'prob_A_wins':                  wA_j / tw if tw else 0.0,
        'prob_B_wins':                  wB_j / tw if tw else 0.0,
        'expected_A_points':            j_eA,
        'expected_B_points':            j_eB,
        'expected_net_A':               j_eA - j_eB,
        'expected_total_winner_points': j_eA + j_eB,
        'prob_both_given_A_wins':       jp['bA'] / wA_j if wA_j else 0.0,
        'prob_both_given_B_wins':       jp['bB'] / wB_j if wB_j else 0.0,
    }
    out['Punto'] = {
        'prob_A_wins':                  wA_p / tw if tw else 0.0,
        'prob_B_wins':                  wB_p / tw if tw else 0.0,
        'expected_A_points':            p_eA,
        'expected_B_points':            p_eB,
        'expected_net_A':               p_eA - p_eB,
        'expected_total_winner_points': p_eA + p_eB,
    }
    return out


# ---------------------------------------------------------------------------
# Scenario 1: MONO_DECK {R:16} — single hand, every phase is a mano tie-win
# ---------------------------------------------------------------------------

def test_mono_deck_mano_wins_all_phases(mono_tables):
    """Only one canonical hand exists; every phase ties → mano (Team A) takes 100%.

    (R,R,R,R) has Juego (sum=40≥31), so Juego fires for every deal.
    Punto never fires → prob_A_wins(Punto) == 0 and expected_net_A(Punto) == 0.
    """
    hand = canonical([Card.R, Card.R, Card.R, Card.R])
    ep = mono_tables[hand]["ep_mano"]
    for phase in ['Grande', 'Chica', 'Pares', 'Juego']:
        assert ep[phase]["prob_A_wins"]    == pytest.approx(1.0, abs=1e-9), phase
        assert ep[phase]["prob_B_wins"]    == pytest.approx(0.0, abs=1e-9), phase
        assert ep[phase]["expected_net_A"] >  0,                            phase
    # Punto never fires when all hands have Juego
    assert ep["Punto"]["prob_A_wins"]    == pytest.approx(0.0, abs=1e-9)
    assert ep["Punto"]["expected_net_A"] == pytest.approx(0.0, abs=1e-9)


def test_mono_deck_pares_both_teams_always_have_pares(mono_tables):
    """(R,R,R,R) is duples; A always wins Pares → prob_both_given_A_wins must equal 1."""
    hand = canonical([Card.R, Card.R, Card.R, Card.R])
    ep = mono_tables[hand]["ep_mano"]["Pares"]
    assert ep["prob_both_given_A_wins"] == pytest.approx(1.0, abs=1e-9)


# ---------------------------------------------------------------------------
# Scenario 2: RA_DECK {R:4, A:16}
# h1=(R,R,R,R) exhausts all 4 R cards; D1={R:0,A:16} → h3=x=y=(A,A,A,A) forced.
#
# Grande: (R,R,R,R) champion A, (A,A,A,A) opponents → A wins 100 %
# Chica:  (A,A,A,A) is h3 (best Chica), ties Team B's (A,A,A,A)
#         → B_tie with seat_mult=1 → B wins 100 %
# Pares:  duples-of-R > duples-of-A → A wins 100 %
# Juego:  (R,R,R,R) sum=40 has juego; (A,A,A,A) sum=4 has none → A wins 100 %
# Punto:  40 > 4 → A wins 100 %
# ---------------------------------------------------------------------------

def test_best_grande_wins_grande_with_certainty(ra_tables):
    hand = canonical([Card.R, Card.R, Card.R, Card.R])
    assert ra_tables[hand]["ep_mano"]["Grande"]["prob_A_wins"] == pytest.approx(1.0, abs=1e-9)


def test_worst_chica_loses_chica_with_certainty(ra_tables):
    """(R,R,R,R) is the worst Chica hand; teammate (A,A,A,A) is best but ties Team B → B wins."""
    hand = canonical([Card.R, Card.R, Card.R, Card.R])
    ep = ra_tables[hand]["ep_mano"]["Chica"]
    assert ep["prob_A_wins"] == pytest.approx(0.0, abs=1e-9)
    assert ep["prob_B_wins"] == pytest.approx(1.0, abs=1e-9)


def test_best_pares_wins_pares_with_certainty(ra_tables):
    hand = canonical([Card.R, Card.R, Card.R, Card.R])
    assert ra_tables[hand]["ep_mano"]["Pares"]["prob_A_wins"] == pytest.approx(1.0, abs=1e-9)


def test_juego_hand_beats_no_juego_with_certainty(ra_tables):
    hand = canonical([Card.R, Card.R, Card.R, Card.R])
    assert ra_tables[hand]["ep_mano"]["Juego"]["prob_A_wins"] == pytest.approx(1.0, abs=1e-9)


def test_juego_hand_punto_never_fires(ra_tables):
    """(R,R,R,R) has Juego: deal_has_juego is always True, so Punto never fires."""
    hand = canonical([Card.R, Card.R, Card.R, Card.R])
    ep = ra_tables[hand]["ep_mano"]["Punto"]
    assert ep["prob_A_wins"] == pytest.approx(0.0, abs=1e-9)
    assert ep["prob_B_wins"] == pytest.approx(0.0, abs=1e-9)


def test_best_punto_wins_punto_with_certainty(low_tables):
    """In LOW_DECK no hand has Juego, so Punto always fires.
    (6,6,6,6) has the best Punto (sum=24); after it uses all four 6s the remaining
    deck only has A/4/5 cards whose best Punto sum is 20, so h1=(6,6,6,6) wins 100%.
    """
    hand = canonical([Card._6, Card._6, Card._6, Card._6])
    assert low_tables[hand]["ep_mano"]["Punto"]["prob_A_wins"] == pytest.approx(1.0, abs=1e-9)


# ---------------------------------------------------------------------------
# Scenario 3: LOW_DECK {A:4,4:4,5:4,6:4}
# Many hands exist (AAAA, AA45, 4455, A466 …) but max card sum = 6+6+6+6 = 24 < 31.
# Therefore no hand ever has Juego, so expected Juego points must be 0 for ALL hands.
# ---------------------------------------------------------------------------

def test_no_juego_deck_expected_juego_points_always_zero(low_tables, low_hands):
    """Every hand in LOW_DECK: expected Juego points = 0 because no hand can reach sum≥31."""
    for hand in low_hands:
        ep = low_tables[hand]["ep_mano"]["Juego"]
        assert ep["expected_A_points"] == pytest.approx(0.0, abs=1e-9), f"{hand}"
        assert ep["expected_B_points"] == pytest.approx(0.0, abs=1e-9), f"{hand}"


def test_no_juego_deck_prob_both_given_winner_zero(low_tables, low_hands):
    """With no juego possible, both_given_A_wins and both_given_B_wins must be 0."""
    for hand in low_hands:
        ep = low_tables[hand]["ep_mano"]["Juego"]
        assert ep["prob_both_given_A_wins"] == pytest.approx(0.0, abs=1e-9), f"{hand}"
        assert ep["prob_both_given_B_wins"] == pytest.approx(0.0, abs=1e-9), f"{hand}"


# ---------------------------------------------------------------------------
# Scenario 4: JUEGO_DECK {R:8, A:8} — interesting juego ordering
#
# Hands and juego status:
#   (R,R,R,R) sum=40  has juego (worse: 40 > 31)
#   (R,R,R,A) sum=31  has juego (best: 31 is optimal)
#   (R,R,A,A) sum=22  no juego
#   (R,A,A,A) sum=13  no juego
#   (A,A,A,A) sum=4   no juego
# ---------------------------------------------------------------------------

def test_best_juego_beats_worse_juego_hand(juego_tables):
    """(R,R,R,A)=31 (best juego) must have higher Juego win rate than (R,R,R,R)=40."""
    best  = canonical([Card.R, Card.R, Card.R, Card.A])
    worse = canonical([Card.R, Card.R, Card.R, Card.R])
    p_best  = juego_tables[best]["ep_mano"]["Juego"]["prob_A_wins"]
    p_worse = juego_tables[worse]["ep_mano"]["Juego"]["prob_A_wins"]
    assert p_best > p_worse, f"31-hand prob={p_best:.4f} should exceed 40-hand prob={p_worse:.4f}"


def test_best_juego_beats_no_juego_hand(juego_tables):
    """(R,R,R,A)=31 must have strictly higher Juego win rate than (A,A,A,A) which has no juego."""
    best     = canonical([Card.R, Card.R, Card.R, Card.A])
    no_juego = canonical([Card.A, Card.A, Card.A, Card.A])
    p_best     = juego_tables[best]["ep_mano"]["Juego"]["prob_A_wins"]
    p_no_juego = juego_tables[no_juego]["ep_mano"]["Juego"]["prob_A_wins"]
    assert p_best > p_no_juego, f"juego hand {p_best:.4f} vs no-juego hand {p_no_juego:.4f}"


def test_best_juego_hand_wins_more_than_half_as_mano(juego_tables):
    """(R,R,R,A)=31 dominates all juego comparisons; as mano it should win Juego > 50%."""
    hand = canonical([Card.R, Card.R, Card.R, Card.A])
    prob = juego_tables[hand]["ep_mano"]["Juego"]["prob_A_wins"]
    assert prob > 0.5, f"Best juego hand should win >50% as mano, got {prob:.4f}"


def test_grande_win_rate_monotone_with_card_strength(juego_tables):
    """Grande win prob must fall as hand quality drops: RRRR > RRRA > RRAA."""
    rrrr = canonical([Card.R, Card.R, Card.R, Card.R])
    rrra = canonical([Card.R, Card.R, Card.R, Card.A])
    rraa = canonical([Card.R, Card.R, Card.A, Card.A])
    p = [juego_tables[h]["ep_mano"]["Grande"]["prob_A_wins"] for h in (rrrr, rrra, rraa)]
    assert p[0] > p[1] > p[2], f"Grande win rates not monotone: {p}"


def test_chica_win_rate_monotone_with_low_cards(juego_tables):
    """Chica win prob must rise as hand has more low cards: AAAA > RAAA > RRAA."""
    aaaa = canonical([Card.A, Card.A, Card.A, Card.A])
    raaa = canonical([Card.R, Card.A, Card.A, Card.A])
    rraa = canonical([Card.R, Card.R, Card.A, Card.A])
    p = [juego_tables[h]["ep_mano"]["Chica"]["prob_A_wins"] for h in (aaaa, raaa, rraa)]
    assert p[0] > p[1] > p[2], f"Chica win rates not monotone: {p}"


# ---------------------------------------------------------------------------
# Scenario 5a: MINI_DECK (35 hands) — brute-force cross-check for all hands
# Compares every field of _ep_mano_worker against pure-Python reference.
# ---------------------------------------------------------------------------

_COMPARE_FIELDS = (
    'prob_A_wins', 'prob_B_wins',
    'expected_A_points', 'expected_B_points',
    'expected_net_A', 'expected_total_winner_points',
)
_BONUS_FIELDS = ('prob_both_given_A_wins', 'prob_both_given_B_wins')


def test_brute_force_matches_worker_all_mini_hands(mini_tables, mini_hands):
    """
    Pure-Python O(N^4) reference vs numpy worker for every hand in MINI_DECK.
    All 5 phases, all output fields must agree to 1e-9.
    """
    for h1 in mini_hands:
        ref = _brute_force_ep_mano(h1, MINI_DECK)
        tbl = mini_tables[h1]["ep_mano"]
        for phase in EP_MANO_PHASES:
            for key in _COMPARE_FIELDS:
                r, t = ref[phase][key], tbl[phase][key]
                assert abs(r - t) < 1e-9, (
                    f"h1={h1} {phase}.{key}: brute={r:.10f} worker={t:.10f}"
                )
            if phase in ('Pares', 'Juego'):
                for key in _BONUS_FIELDS:
                    r, t = ref[phase][key], tbl[phase][key]
                    assert abs(r - t) < 1e-9, (
                        f"h1={h1} {phase}.{key}: brute={r:.10f} worker={t:.10f}"
                    )


# ---------------------------------------------------------------------------
# Scenario 5b: Full production deck — brute-force for h1=(R,C,C,S) vs pickle
#
# Loads the pre-computed probability_tables.pkl and compares the stored ep_mano
# entry for (R,C,C,S) against a pure-Python O(N^4) reference on all 330 hands.
# No _ep_mano_worker call — this validates the saved table, not the in-memory worker.
# Marked @pytest.mark.slow — run with: pytest -m slow
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_full_deck_brute_force_rccs_vs_saved_table():
    """
    Pure-Python brute-force for h1=(R,C,C,S) on the full 330-hand production deck,
    compared against the ep_mano entry stored in probability_tables.pkl.
    Requires the table to have been built (compute_expected_points.py completed).
    """
    import pickle
    from constants import cards_space
    from build_tables import TABLE_PATH

    if not TABLE_PATH.exists():
        pytest.skip("probability_tables.pkl not found — run build_tables.py first")

    with open(TABLE_PATH, "rb") as f:
        tables = pickle.load(f)

    h1 = canonical([Card.R, Card.C, Card.C, Card.S])

    if "ep_mano" not in tables.get(h1, {}):
        pytest.skip("ep_mano not yet in probability_tables.pkl — run compute_expected_points.py first")

    saved = tables[h1]["ep_mano"]
    ref   = _brute_force_ep_mano(h1, cards_space)

    for phase in EP_MANO_PHASES:
        for key in _COMPARE_FIELDS:
            r, t = ref[phase][key], saved[phase][key]
            assert abs(r - t) < 1e-9, (
                f"phase={phase} key={key}: brute={r:.10f} saved={t:.10f}"
            )
        if phase in ('Pares', 'Juego'):
            for key in _BONUS_FIELDS:
                r, t = ref[phase][key], saved[phase][key]
                assert abs(r - t) < 1e-9, (
                    f"phase={phase} key={key}: brute={r:.10f} saved={t:.10f}"
                )
