# Exact enumeration method

## What it exposes

This is the mathematical basis for the table calculations: canonical rank hands, exact physical-card multiplicities, and weighted expected values without Monte Carlo sampling.

## Canonical hand types

Only rank values affect the modeled lances. A hand is represented as its four ranks sorted in descending order. Repeated ranks are allowed up to the number of physical cards of that rank.

There are eight rank values in the configured deck. The number of four-card multisets before applying card caps is choose(8 + 4 - 1, 4) = 330. The configured caps permit all of those rank multisets, so the current table has 330 canonical hand types.

This collapses many physical deals into one strategically equivalent rank hand. For example, different suits do not create different table rows.

## Physical multiplicity

Let D_r be the number of remaining physical cards of rank r, and let n_r(h) be how many cards of rank r appear in hand h. The number of physical ways to form that rank hand from the remaining deck is:

    multiplicity(h | D) = product over ranks r of choose(D_r, n_r(h))

This is the weight used when combining rank-hand outcomes. It preserves the fact that some rank compositions are more common than others and prevents using more copies of a rank than the deck contains.

## Four-seat deal weighting

For a fixed hand in seat 0, the expected-points worker removes that hand from the deck and considers possible rank hands for the partner and two opponents. Each assigned hand is weighted by the number of physical ways it can be dealt from the cards remaining after earlier hands are removed.

For an ordered assignment h0, h1, h2, h3, its physical-deal weight is the product:

    multiplicity(h0 | D)
    * multiplicity(h1 | D minus h0)
    * multiplicity(h2 | D minus h0 minus h1)
    * multiplicity(h3 | D minus h0 minus h1 minus h2)

When h0 is fixed, its first factor is constant and cancels during normalization. The code uses this sequential remaining-deck calculation.

## Work reduction

The calculation avoids enumerating every physical card deal:

1. It groups physical hands by their canonical rank composition.
2. It precomputes hand properties and phase ranks once.
3. It uses card-count multiplicities to represent all physical realizations of a hand type.
4. It avoids repeating symmetric opponent-hand pairs.
5. It evaluates many comparisons with NumPy arrays and distributes fixed-mano hands across worker processes.

The current expected-points workers fix the known hand in seat 0 (mano) and treat the two opposing hands as an unordered pair. For each pair they use:

    base_weight = M(hx | D) * M(hy | D minus hx)
    pair_factor = 2 if phase_rank(hx) != phase_rank(hy) else 1
    pair_weight = base_weight * pair_factor

They compare the best opposing rank with Team A's best rank. When the pair's ranks differ, the factor of two accounts for the two possible seat orders; in a tie against Team A's third-player hand (zero-based seat 2), the earlier opponent seat can win while the later one loses. When the ranks tie each other, the implementation treats the pair as one best-rank outcome. This is the current first-player/mano working assumption. The pure-Python reference uses the same triangular pair loop and multiplier, so it does not independently establish that the weighting is equivalent to a fully ordered deal. Keep the formula as implemented for now; a later audit should enumerate both opponent seats independently and extend the table to fixed hands in the second, third, and fourth player seats, where seat priority changes.

## Limits of the exactness claim

Exact enumeration does not make the assumptions exact. It means the code exhaustively sums the outcomes admitted by those assumptions.

- The head-to-head probability table uses the full-deck opponent hand multiplicity and does not condition that opponent on the caller's known four cards.
- The expected-points scorer applies +0.5 only in Pares/Juego when both teams qualify. This matches the agreed model. Grande/Chica always award their base point to the best hand and receive no separate +0.5 adjustment.
- The post-mus calculations use a deterministic best-discard proxy and a marginal final-hand distribution.
- A single Mus exchange is assumed. The current game loop can continue through multiple Mus rounds, which is outside this table model.
- For a one-player marginal draw, remove the player's original four physical cards from the deck. Other copies of those ranks remain in the pool. Current builders restore the exact discarded copies and therefore increase the draw probability of those ranks.

The small-deck reference in `tests/probabilities/test_ep_mano.py` checks the vectorized implementation against a pure-Python calculation, but both share the same unordered-pair shortcut. Use an ordered opponent-pair reference and separate known-rule checks to establish correctness.
