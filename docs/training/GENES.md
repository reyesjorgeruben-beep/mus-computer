# Gene introduction tracker

`USED_GENES` in `src/mus_computer/training/constants.py` contains the three cut genes below. Genome matchups compose `GeneCutMusStrategy`, the existing discard strategy, and `HandStrengthWagerStrategy`. An ordinary `BotPlayer` without an injected portfolio still uses its fixed Mus and wager policies. Legacy genome fields remain in the interface and at 0.5 in new default training populations.

The first wager layer is gene-free. For the current phase, it uses the hand table's `p_loss`. On an opening turn it passes with probability `p_loss` and offers 2 with probability `1 - p_loss`. When answering an opponent's offer, including ordago, it folds with probability `p_loss` and matches with probability `1 - p_loss`; it never raises that offer. The non-loss branch includes ties. These table estimates describe the bot's own hand, not its teammate's hand. Later wager genes can adjust this baseline distribution.

The cut probability is `cut_prone` when this bot has neither Pares nor Juego. Otherwise it is `juego * cut_prone_with_juego + (1 - juego * cut_prone_with_juego) * pares * cut_prone_with_pares`, where `juego` and `pares` are 1 when this bot's hand has that feature and 0 otherwise. The policy uses the hand's intrinsic phase points to determine those flags. It does not use phase win estimates, teammate points, score, or prior Mus exchanges.

| Gene | Status | Intended effect to verify when reintroduced |
|---|---|---|
| `cut_prone` | Active in composed Mus policy | Cut probability with neither Pares nor Juego. |
| `cut_prone_with_pares` | Active in composed Mus policy | Cut probability contribution when the hand has Pares. |
| `cut_prone_with_juego` | Active in composed Mus policy | Cut probability contribution when the hand has Juego. |
| `mus_eagerness` | Inactive | Higher value raises the probability of voting Mus on the same hand. |
| `mus_risk_sensitivity` | Inactive | Higher value favors Mus when estimated improvement after discarding is positive. |
| `w_grande` | Inactive | Changes Grande's relative importance when judging a hand or discard. |
| `w_chica` | Inactive | Changes Chica's relative importance. |
| `w_pares` | Inactive | Changes Pares' relative importance. |
| `w_juego` | Inactive | Changes Juego's relative importance. |
| `discard_aggressiveness` | Inactive | Changes discard choices when estimated values tie. |
| `bluff_rate` | Inactive | Changes betting drive and the weight of matching an offered ordago. |
| `risk_factor` | Inactive | Changes the mix of raise sizes and ordago offers. |
| `fold_threshold` | Inactive | Changes folding below a confidence threshold. |
| `raise_threshold` | Inactive | Changes confidence-driven raising. |
| `score_urgency_sensitivity` | Inactive | Changes the response to a score gap. |
| `position_preference` | Inactive | Changes how seat position affects decisions. |

The fixed default Mus and discard policies use equal phase weights. Discard ties prefer fewer discarded cards. Score, seat, hand estimates, and current wager state still affect the fixed default policies; the composed cut policy follows only the three cut genes and the Pares/Juego flags. In genome matchups, the new wager baseline uses only the current phase's loss estimate and whether there is an offer to answer.
