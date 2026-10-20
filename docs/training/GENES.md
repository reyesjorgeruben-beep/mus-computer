# Gene introduction tracker

`USED_GENES` in `src/mus_computer/training/constants.py` contains `bluff_rate` and `extreme_bluff_rate`. Genome matchups compose `AlwaysCutMusStrategy`, the existing discard strategy, and `ComposedWagerStrategy`. The composed wager policy always starts with the gene-free `HandStrengthWagerStrategy` and applies the raise-2 and ordago layers in that order. An ordinary `BotPlayer` without an injected portfolio still uses its default Mus and wager policies. Inactive genome fields remain at 0.5 in new default training populations.

The first wager layer uses the hand table's `p_loss`. On an opening turn it passes with probability `p_loss` and offers 2 with probability `1 - p_loss`. When answering an opponent's offer, it folds with probability `p_loss` and matches with probability `1 - p_loss`. The non-loss branch includes ties. These table estimates describe the bot's own hand, not its teammate's hand.

The bluff layer moves `p_loss * bluff_rate` from passing or folding to raising 2. The extreme-bluff layer moves `(p_loss - bluff_raise) * extreme_bluff_rate` from the remaining passing or folding probability to offering ordago. Thus both genes can reach 1 without making the action distribution exceed 1. When answering an offered ordago, only fold and match are legal, so the base distribution applies without either bluff layer.

The cut probability is `cut_prone` when this bot has neither Pares nor Juego. Otherwise it is `juego * cut_prone_with_juego + (1 - juego * cut_prone_with_juego) * pares * cut_prone_with_pares`, where `juego` and `pares` are 1 when this bot's hand has that feature and 0 otherwise. The policy uses the hand's intrinsic phase points to determine those flags. It does not use phase win estimates, teammate points, score, or prior Mus exchanges.

| Gene | Status | Intended effect to verify when reintroduced |
|---|---|---|
| `cut_prone` | Inactive; used by `GeneCutMusStrategy` when selected | Cut probability with neither Pares nor Juego. |
| `cut_prone_with_pares` | Inactive; used by `GeneCutMusStrategy` when selected | Cut probability contribution when the hand has Pares. |
| `cut_prone_with_juego` | Inactive; used by `GeneCutMusStrategy` when selected | Cut probability contribution when the hand has Juego. |
| `mus_eagerness` | Inactive | Higher value raises the probability of voting Mus on the same hand. |
| `mus_risk_sensitivity` | Inactive | Higher value favors Mus when estimated improvement after discarding is positive. |
| `w_grande` | Inactive | Changes Grande's relative importance when judging a hand or discard. |
| `w_chica` | Inactive | Changes Chica's relative importance. |
| `w_pares` | Inactive | Changes Pares' relative importance. |
| `w_juego` | Inactive | Changes Juego's relative importance. |
| `discard_aggressiveness` | Inactive | Changes discard choices when estimated values tie. |
| `bluff_rate` | Active in training wager policy | Moves losing-hand probability to raise 2. |
| `extreme_bluff_rate` | Active in training wager policy | Moves remaining losing-hand probability to ordago. |
| `risk_factor` | Inactive | Changes the mix of raise sizes and ordago offers. |
| `fold_threshold` | Inactive | Changes folding below a confidence threshold. |
| `raise_threshold` | Inactive | Changes confidence-driven raising. |
| `score_urgency_sensitivity` | Inactive | Changes the response to a score gap. |
| `position_preference` | Inactive | Changes how seat position affects decisions. |

The fixed default Mus and discard policies use equal phase weights. Discard ties prefer fewer discarded cards. Score, seat, hand estimates, and current wager state still affect the fixed default policies. In genome matchups, Mus always ends immediately, and the wager strategy uses the current phase's loss estimate, the two bluff genes, and the current offer state.
