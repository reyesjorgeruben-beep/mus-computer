# Best-discard value tables

## What they expose

For each starting hand, the discard-value tables expose:

- Expected net team points for each retained subset.
- The retained subset with the highest total expected net points.
- Best retained subsets by phase.
- A keep-all baseline, its rank among options, and its expected gain or loss versus the best discard.
- A total-action measure for comparing higher- and lower-scoring discard options.

The baseline output uses best_discards and no_discard_stats. The post-mus-aware output uses best_discards_corrected and no_discard_stats_corrected.

## How options are valued

For each unique retained subset, the builder enumerates replacement rank combinations, weights them by physical multiplicity, and averages the expected-points entries for each resulting four-card hand.

The total_net_A field is the sum of expected_net_A over Grande, Chica, Pares, Juego, and Punto. For best_by_phase, the Juego entry uses the combined Juego plus Punto value because only one of those lances occurs. The no-discard summary compares keeping the original four cards against the best actual discard option.

This selects a retained hand by expected net points, not by a weighted average of single-opponent win probabilities.

## Baseline and corrected versions

- compute_best_discards.py uses ep_mano, which is based on pre-mus hands.
- compute_best_discards_corrected.py uses ep_mano_postmus and writes separate corrected keys.

The corrected output is one post-mus-aware revaluation. It does not rebuild hand_distribution_post_mus or repeat the pipeline.

## Assumptions and current mismatch

- Every hand uses the same expected-points scorer documented in [Team expected points](team-expected-points.md), including the agreed +0.5 expected wager contribution for contested Pares/Juego.
- The post-mus version assumes opponents' final hands follow the same post-mus marginal distribution, then uses the joint weighting described in [Post-mus model](post-mus-model.md), which is still to be corrected.
- The builders currently add the exact discarded copies back to the replacement pool. For the one-player marginal model, use the full deck minus the original four cards: other copies of those ranks remain drawable, while the physical copies dealt to that player stay unavailable during this exchange.
- A positive delta_total_net_vs_best is used as a deterministic signal that a starting hand takes Mus. This is a useful proxy, not a learned or probabilistic Mus-vote policy.
