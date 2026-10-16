# Gene introduction tracker

`USED_GENES` in `src/mus_computer/training/constants.py` is currently empty. The built-in bot strategies accept a personality argument but do not read any of its fields. New default training populations therefore keep all fields at 0.5. Explicitly supplied genomes can still carry other values, but those values do not affect built-in decisions. Reintroduce one gene at a time with a fixed-state behavior test before adding it to `USED_GENES`; then compare it with the fixed baseline over repeated, seat-balanced games.

| Gene | Status | Intended effect to verify when reintroduced |
|---|---|---|---|
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

Current Mus and discard policies use fixed, equal phase weights. Discard ties prefer fewer discarded cards. Score, seat, hand estimates, and current wager state still affect decisions through fixed policy coefficients.
