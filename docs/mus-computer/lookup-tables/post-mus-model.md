# Post-mus hand distribution and expected points

## What they expose

- hand_distribution_post_mus: a probability mass over canonical final hands after the deterministic best-discard Mus proxy.
- ep_mano_postmus: expected phase points for a fixed mano hand against the post-mus marginal hand model.

The distribution is stored at the top level of the bundled `src/mus_computer/probabilities/data/probability_tables.pkl`. The expected-points table is stored per hand.

## Agreed model

The current iteration models one Mus exchange only. Sixteen cards are dealt initially, leaving 24 cards in the stock. Even if all four players discard all four cards, at most 16 replacements are needed. The first exchange therefore does not exhaust the stock, so discards do not need to be recycled during this modeled exchange.

Each starting hand uses the best-discard choice exposed by the discard-value table. This creates a post-mus distribution that favors hands retained or completed by that strategy. The distribution is a proxy: it does not model the probability that each initial hand votes Mus, the chance all four players agree, or variations in player policy.

## Distribution construction

`scripts/tables/compute_hand_distribution.py`:

1. Computes the initial deal probability of each canonical hand from its physical multiplicity.
2. Reads the best-discard option and compares its expected net points with keeping all four cards.
3. Treats a hand with positive discard gain as a Mus hand and applies its best discard. Other hands do not enter the conditional post-mus distribution.
4. Renormalizes the initial deal probabilities over the hands classified as taking Mus.
5. Enumerates possible completed hands and sums their weighted probabilities into hand_distribution_post_mus.

Thus the result is conditional on the proxy's deterministic Mus selection. It is not the unconditional distribution of all hands after every deal, nor a joint distribution for all four seats. The source-to-final relation is:

    q(h_final) = sum over source hands h0 of
        P(h0 | proxy takes Mus) * P(h_final | h0, best discard)

The source hand is used to choose the discard and its draw pool, then marginalized when q is stored. A dense source/final table would have at most 330 * 330 = 108,900 entries (about 0.83 MiB for float64 values), so that one-player table is practical if a later policy needs it. Modeling correlated source hands and replacement draws across all four seats is the much larger problem. For this iteration, assume seats can be represented by the final marginal q without retaining their source hands.

The current transition pool is full deck minus the kept subset. Under the agreed one-exchange marginal, use full deck minus the original four-card hand: another physical card of a discarded rank may be drawn, but the exact physical card dealt initially cannot return during this exchange.

## Expected points after Mus

`scripts/tables/compute_ep_postmus.py` fixes the mano hand and applies the post-mus hand mass to the partner and opponent hand types, while checking that impossible rank multiplicities are excluded. The same phase ranking and point scorer as ep_mano are used.

The stored post-mus marginal q(h) is aggregate probability mass for canonical hand type h; it is not the probability of each individual physical realization of h. The current q was generated using the overinclusive draw pool described above. The formula below documents the current working assumption used when combining q with physical card multiplicity.

Define the physical multiplicity of type h in deck counts D as:

    M(h | D) = product over ranks r of choose(D_r, n_r(h))

If the model's goal were to preserve q(h) as the marginal type probability while enforcing card compatibility, the fraction of realizations of h compatible with remaining deck D would be:

    c(h | D) = M(h | D) / M(h | full deck)

That alternative would give this sequential weight for partner and opponents h3, hx, hy:

    q(h3) * c(h3 | D1)
    * q(hx) * c(hx | D2)
    * q(hy) * c(hy | D3)

where D1 excludes the fixed mano hand, D2 also excludes h3, and D3 also excludes hx.

The current worker instead uses this formula:

    w_current = q(h3) * M(h3 | D1)
              * q(hx) * M(hx | D2)
              * q(hy) * M(hy | D3)

This is an explicit reweighting assumption: it favors types with more compatible physical realizations in the remaining deck. Equivalently, it behaves like a type prior proportional to q(h) * M(h | full deck), followed by physical-card exclusion. It does not preserve q as the resulting marginal. The ratio formula above is the alternative if preserving q is the goal. Both remain product-of-marginals models and omit correlations created by the shared initial deal, discard choices, and replacement stock; compare them before deciding which is the better approximation.

## Current qualitative check

The current stored post-mus marginal has total mass approximately 1. Under that artifact:

- Initial deal: probability of at least one R (king rank) is about 0.607; expected R count is 0.80.
- Post-mus conditional distribution: probability of at least one R is about 0.770; expected R count is about 1.18.

This agrees with the expected qualitative effect: best-discard selection makes kings more common among hands that continue through Mus. It is only a directional sanity check. The current transition restores the exact discarded copies to the draw pool, so these numbers do not validate the agreed one-exchange marginal draw model.

## One-pass correction

The current sequence builds hand_distribution_post_mus from best_discards using ep_mano, then builds ep_mano_postmus, then writes best_discards_corrected from that post-mus expected-points table. The corrected discard table is stored separately; the distribution is not rebuilt from it.

This is a coherent one-pass approximation. A fixed-point iteration is possible later, but it is not required for the first policy that consumes these tables.
