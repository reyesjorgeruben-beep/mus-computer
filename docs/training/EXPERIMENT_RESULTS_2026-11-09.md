# Initial framework validation — 2026-11-09

The framework completed a real training/development/follow-up/confirmation
cycle, then repeated it after the integrity review repairs. **The reference
champion was retained in both cycles.** Final repaired confirmation gave the
selected challenger 33/64 wins, below the unchanged 55% head-to-head threshold.
No thresholds were relaxed after observing results.

## Reproduction and budgets

- Native trainer: existing CFR with `policy="glm"`, default strategy portfolio,
  exploration 0.1, 100 iterations per artifact, average-policy inference.
- Champion projection learning rate: 0.1. Challenger attempts: 0.2, 0.05, then
  an exact replication of 0.2 selected from the development comparisons.
- CLI seed: 7; derived native training seed: `6745809889148634083`.
- Each attempt used 8 development seed pairs and four fixed static artifacts:
  heuristic, random decisions, MusMaestro and seeded random coefficients.
- Selected artifact received 32 fresh confirmation pairs. Every pair swaps
  A/B sides; a match required one complete normal game victory to 40 or ordago.
- There were 432 development games and 576 confirmation games. The four
  training artifacts recorded 7,003 sampled self-play/counterfactual games;
  native checkpoint evaluation games are additional and not included there.
- Generated files are retained locally under ignored
  `training_runs/framework_validation_20261109/`. Use the commands in
  [EXPERIMENTS.md](EXPERIMENTS.md) with the configs above to reproduce.
- Source base revision: `26068f767a84a6b7acdfbdb6c3557c94a12b5458` plus the
  uncommitted framework implementation, subsequently delivered in this PR.
  Native manifests record complete source digests. The champion/attempt 1 used
  `ece9d8581c456fc5bd0b39f2982d4b79e370ce7d08b7bdf708979d6feb3f1001`;
  attempts 2/3 used
  `2bd438a44a6b271df9c1079fc15323efead4e49445d7de16f70afbd5b92b2e52`.
  The orchestration evolved between these runs; the CFR training/inference
  implementation and all inference fingerprints remained unchanged.

## Development evidence

All rates below use 16 games (8 dependent side-swapped pairs). The champion
had 56.25% against the heuristic and random decisions, 100% against MusMaestro,
and 68.75% against random coefficients on this development sample.

| Attempt | Projection rate | Challenger vs champion | Heuristic | Random decisions | MusMaestro | Random coefficients |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 0.2 | 9/16 | 9/16 | 9/16 | 16/16 | 8/16 |
| 2 | 0.05 | 6/16 | 6/16 | 10/16 | 16/16 | 10/16 |
| 3: replication | 0.2 | 9/16 | 9/16 | 9/16 | 16/16 | 8/16 |

Attempt 1's larger projection step regressed 18.75 percentage points against
fixed random coefficients. Attempt 2 tested a gentler step in response. It
partially recovered that baseline but lost more head-to-head and against the
heuristic. Attempt 3 replicated the earlier candidate before confirmation.
Its native checkpoint SHA-256 and **every development match record** exactly
matched attempt 1, demonstrating end-to-end repeatability without claiming an
improvement. Attempt durations including training/evaluation were approximately
34.1, 39.0 and 36.8 seconds on this local machine.

## Initial pre-repair held-out confirmation

The confirmed artifact was frozen before using the separate confirmation seed
namespace. No further training or tuning followed confirmation.

| Comparison | Champion wins | Challenger wins | Challenger minus champion |
|---|---:|---:|---:|
| Head-to-head | 33/64 | 31/64 | Challenger win rate 48.44% |
| Heuristic | 26/64 | 29/64 | +4.69 percentage points |
| Random decisions | 33/64 | 29/64 | -6.25 percentage points |
| MusMaestro | 64/64 | 64/64 | 0 |
| Random coefficients | 33/64 | 32/64 | -1.56 percentage points |

Confirmation took approximately 12.1 seconds. Its head-to-head pair-level
standard error was 0.04191. The original rules required at least 32 pairs,
55% head-to-head wins and no observed baseline regression over 5 percentage
points. The explicit promotion command rejected the challenger and left the
champion pointer and empty promotion history unchanged.

## Final repaired cycle and confirmation

Independent review found two integrity gaps: built-in inference fingerprints
omitted constants/table bytes, and native checkpoint directories could gain
untracked files. The single repair batch added those dependencies, bundled-data
provenance, exact payload file-set validation and five regression cases. It
changed integrity metadata, not the CFR trainer or model probabilities.

The complete bounded cycle was rerun under
`training_runs/framework_validation_20261109_repaired/`; the original files were
preserved without rewriting their manifests. All four native checkpoint hash
sets and every development match record matched the initial cycle exactly.
The corrected fingerprint/manifest identity creates a different recorded
confirmation namespace, so the repaired confirmation is reported separately:

| Comparison | Champion wins | Challenger wins | Challenger minus champion |
|---|---:|---:|---:|
| Head-to-head | 31/64 | 33/64 | Challenger win rate 51.56% |
| Heuristic | 27/64 | 26/64 | -1.56 percentage points |
| Random decisions | 24/64 | 28/64 | +6.25 percentage points |
| MusMaestro | 64/64 | 64/64 | 0 |
| Random coefficients | 32/64 | 31/64 | -1.56 percentage points |

The head-to-head pair-level standard error was 0.04754. Promotion was again
rejected, this time by the head-to-head threshold alone. There was no further
tuning or change in selection rules. The repaired cycle consumed the same
per-artifact training budgets and the same 432 development/576 confirmation
games as the original cycle.

Final runtime source digest:
`4d040822eac4f29e76194e938071a6911bc91ea7d336000cacd06048bb8a746f`.
Bundled probability-table SHA-256:
`548b0f085c8dac333915ee24c88cd3df8f799eaba8261188da22c97a4db68e0b`.
The final suite passed 509 tests (3 slow/performance tests excluded). The
reviewer confirmed both Important findings resolved and found no new actionable
issues in the read-only repair delta.

## Native checkpoint identities and limits

| Model | Sampled training games | Information states | Native checkpoint SHA-256 |
|---|---:|---:|---|
| Champion 0.1 | 1,807 | 1,143 | `e468009d3a4ab84280b9b37f7f816e4a6e9eeb604f7bbb9f071e6effa3a4a82f` |
| Challenger 0.2 / replica | 1,717 each | 1,144 each | `553d2da41673aeb9f23c07c9dda65f9cf73f91fce54c8b821aa4c9fccba8e36d` |
| Follow-up 0.05 | 1,762 | 1,202 | `6d8a16aaa0e3b5b15e22ab3822ea6646564b93fddc290146b9e2d5f8fb3e0ae5` |

These are bounded pipeline checks, not a well-powered learning-quality study.
Only one training seed and one frozen random-coefficient baseline were used.
Observed maximum importance weights ranged from about 5.9e9 to 1.5e10, reflecting
the existing CFR estimator's high variance. The framework did not alter that
estimator or optimize a new model. Small-sample development wins did not survive
held-out confirmation, which is why the reference champion remains selected.
