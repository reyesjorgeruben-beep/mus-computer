# Lookup tables

## What they expose

| Table | Exposes |
|---|---|
| Hand phase probabilities | For each canonical hand, per-phase win, tie, and loss probabilities against the table's reference opponent-hand distribution. |
| Discard options | For each starting hand and each retained sub-hand, expected per-phase win probabilities after replacement draws. |
| ep_mano | For a fixed mano hand, expected team points and win probabilities by phase against three other dealt hands. |
| hand_distribution_post_mus | A marginal distribution over final hands after the deterministic best-discard Mus proxy. |
| ep_mano_postmus | Expected team points by phase when the other hands are drawn from the post-mus marginal model. |
| best_discards | Expected-net-points summaries for every possible retained subset, calculated from ep_mano. |
| best_discards_corrected | A separate summary calculated from ep_mano_postmus. It does not replace or feed back into the existing post-mus distribution. |

## Construction flow

The source files describe a staged pipeline:

1. build_tables.py enumerates canonical hands, hand probabilities, draw options, average opponent improvements, and ep_mano.
2. compute_best_discards.py values each retained subset using ep_mano.
3. compute_hand_distribution.py applies that best-discard rule to the initial deal distribution and writes hand_distribution_post_mus.
4. compute_ep_postmus.py calculates ep_mano_postmus using the post-mus distribution.
5. compute_best_discards_corrected.py revalues retained subsets using ep_mano_postmus and stores the result separately.
6. export_tables.py creates human-readable CSV and HTML reports.

The best-discard and post-mus steps currently make one pass. The corrected discard table does not trigger a second hand-distribution build.

## Exactness labels

- The initial hand-type counts are exact for the configured deck.
- ep_mano and ep_mano_postmus use combinatorial weights and no random sampling. ep_mano currently fixes the evaluated hand in seat 0 and uses an unordered pair of opponent hands; the same pair-reduction approach is used post-mus. The formula and rationale are recorded as the current working assumption, with an ordered-seat cross-check deferred.
- The best-discard averages enumerate rank-composition draw outcomes and weight them by physical-card combinations. The weights are appropriate for the stated pool, but builders currently restore the player's exact discarded copies; the one-exchange marginal pool should exclude the original four cards while retaining other copies of those ranks.
- hand_distribution_post_mus is generated deterministically for the best-discard proxy. Its current transition uses the full deck minus the kept subset, so it includes the player's discarded copies. It also conditions on modeled Mus hands rather than estimating each hand's probability of asking for Mus.
- ep_mano_postmus uses a marginal post-mus hand distribution for the other seats. Its current formula multiplies aggregate type mass by raw remaining-deck multiplicity, thereby reweighting types according to available physical realizations. This is an explicit working assumption to revisit; see [Post-mus model](post-mus-model.md).

## Runtime use

probability_tables.py exposes functions for the per-hand probabilities and discard options. BotPlayer currently uses win_prob and the average opponent improvement value. Its vote_mus and choose_discards paths still sample replacement hands; they do not consume discard_options, ep_mano, or ep_mano_postmus.

Detailed table definitions:

- [Hand probabilities and discard options](hand-strength-and-discard-options.md)
- [Exact enumeration method](enumeration-method.md)
- [Team expected points](team-expected-points.md)
- [Post-mus model](post-mus-model.md)
- [Discard value summaries](discard-value-tables.md)
