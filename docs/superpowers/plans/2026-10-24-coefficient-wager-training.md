# Coefficient wager training implementation plan

**Goal:** Train one shared set of ten wager coefficients over 1,000 batches of 16 independent, no-mus hands, updating only after each complete batch.

**Architecture:** Enumerate the bounded wager tree for each lance. Propagate a distribution of scores across the hand, removing accepted ordago and 40-point branches. Compute exact local action advantages against frozen opponents, and take one averaged multiplicative coefficient update per batch. This is parameterized self-play policy improvement inspired by CFR, not tabular CFR or regression CFR.

**Scope:** One hand per evaluation, random starting scores in 10..28, four players, no mus/discards. Ten nonnegative endpoint action weights (losing/winning × fold/pass/match/bet/raise), interpolated by private pre-mus hand strength and normalized over legal actions. Bet means two; raising that bet means ordago. Both opposing teammates may respond. Settle each lance immediately in this simplified trainer; the normal game retains its deferred showdown accounting. Ordago fills the winner's remaining distance to 40. Utility is the hand's change in score difference, capped at 40. All coefficients are frozen until all 16 hands finish. Exact expected hand utility is used for action comparisons, including surviving later lances.

## Files and checks

- [x] `training/coefficient_cfr/policy.py`: ten coefficients, legal distributions, analytic local gradients, bounded multiplicative update. Test normalization, action masks, interpolation, and finite differences.
- [x] `training/coefficient_cfr/tree.py`: exact four-seat wager tree; folding one teammate leaves the other a response; opening bet -> response ordago -> fold/match. Test probability conservation, stakes, and termination.
- [x] `training/coefficient_cfr/round.py`: seeded physical deals and existing pre-mus estimates, lance eligibility/ties/intrinsic scoring, score-distribution survival and exact action values/penalties. Test early termination, weighted continuation, and gradient against unilateral finite differences.
- [x] `training/coefficient_cfr/trainer.py` and `__main__.py`: deterministic process pool, one averaged update per batch, JSON coefficients/metrics/configuration. Test frozen inputs, arithmetic averaging, reproducibility and process execution.
- [x] Switch default training entry point and document approximations and reproducible commands. Run focused and regression tests; execute all 1,000 batches × 16 hands and report actual metrics.

## Review focus

- Do not differentiate both teams' zero-sum utilities through shared opponent parameters; take each acting team's local gradient with opponents held fixed.
- Only private pre-mus estimates determine actions; full dealt hands are used for scoring alone.
- Track a separate score state for each surviving branch; do not multiply an unconditional future expectation by an unrelated survival scalar.
- Starting scores vary every deal; accepted ordago and scores reaching 40 have no future lances.
- Keep process workers pure and deterministic and avoid global random state; no learning inside a worker.
- Ten parameters cannot encode score, seat, teammate, or public-response-dependent strategy; report this limitation and do not claim an equilibrium.

## Execution evidence

- Completed 1,000 batches of 16 hands with 16 worker processes, seed 7, learning rate 0.1.
- Held-out 32-pair evaluation versus initial policy: +1.7066 piedras per hand, approximate 95% half-width 0.6473.
- Maximum terminal-probability error across training: 1.11e-15.
- Independent review found no important issues; finite differences across both teams and nonuniform policies agreed within 4.51e-6.
- Generated metrics and an inspectable hand are in training_runs/coefficient_cfr_seed7/.
