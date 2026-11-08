# Contextual coefficients, charts, and match validation

Revision of the initial coefficient experiment following the user's clarified probability semantics.

## Decisions and completed implementation

- [x] Replace the ten shared action weights with twelve named contextual probabilities: pass/bet and fold/match pairs, independent re-bid and ordago, each for winning and losing.
- [x] Preserve the original private-strength mixture for evaluating the two endpoint predictions. Stored coefficients are not changed or rescaled by hand strength.
- [x] Split aggression into an ordinary bet/raise and ordago using the independent ordago coefficient. Allow one numeric counter-raise, then fold or ordago; answering ordago remains fold or match. These are decision rules, not learned restrictions.
- [x] Differentiate all twelve constrained-coordinate parameters analytically; verify local distributions in every stage and unilateral whole-hand derivatives for both teams.
- [x] Record initialization and every batch's coefficients. Export an SVG with twelve curves and numerical CSV history without new dependencies.
- [x] Adapt the policy to existing Game/Match classes, always cutting Mus. Validate against existing RandomDecisionBot, new randomly sampled coefficient sets, and existing MusMaestroBot. Reuse a random coefficient opponent within each entire match and its side-swapped comparison.
- [x] Default to 100 matches per baseline, first to four game wins, balanced across paired team sides. Report match win percentages and full game-win records; do not apply independent-sample confidence intervals to dependent side-swapped pairs.
- [x] Update CLI and training documentation; keep version-1 outputs in a separate run folder.
- [x] Finish the new 1,000 batches of sixteen hands and all 300 full-match validations; inspect charts and saved probability mass.

## Review

Independent review found no important policy, wager, gradient, or live-game issues. It caught inappropriate independent-match uncertainty intervals for paired seeds; those intervals were removed before final delivery. The existing Maestro is the repository's conservative pass/fold baseline, not an external engine.

## Completed run

Seed7, 1,000 batches x16 hands with16 workers, learning rate0.1. Validation first to4 game wins: random decisions56/100, random coefficients62/100, existing MusMaestro100/100. Final regression suite327 passed,5 skipped. Twelve curves with1,001 snapshots are saved under training_runs/coefficient_cfr_v2_seed7/.
