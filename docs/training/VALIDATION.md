# Final winner validation

Validation plays each saved winner in 100 independent matches against each of three opponent policies. A match uses fresh games until one team wins four games by default; `--wins-to-match` can change that target. For each policy, the candidate occupies Team A in 50 matches and Team B in 50 matches. Every match and its games have distinct deterministic seeds, and one process pool runs all matches.

| Report key | Opponent policy |
|---|---|
| `random_genes` | A newly sampled genome for every match, using the same Mus, discard, and wager strategies as the candidate. Only active genes vary, and active gene combinations are unique across the validation run. |
| `random_decisions` | Uniform choice among legal Mus and wager actions and all 16 discard subsets of a four-card hand. |
| `mus_maestro` | Always votes Mus, discards all cards after an exchange, passes without an offer, and folds when answering an offer. It never raises. |

```sh
python -m mus_computer.training.validation --winners docs/training/experiments/example/winning_genomes/genomes.json --seed 42 --workers 10 --wins-to-match 4
```

The command writes `docs/training/experiments/example/validation/results.md` by default. Use `--out PATH` to change the location. The table has one row per winning genome plus an average row, showing only win percentages against the three opponent policies. The Python return value still contains the underlying matchup details for programmatic inspection.

Use repeatable `--gene NAME` flags to override `USED_GENES` when the training run used a custom active-gene set. The training CLI passes its configured active genes to validation automatically, including the empty set selected by `--no-genes`.

In Python, call `validate_winners(winners, run_dir, seed=42, workers=10, active_genes=("bluff_rate",), wins_to_match=4)` after training. Omit `active_genes` to use `USED_GENES`, or pass `()` for a neutral baseline. With no active genes, random-gene opponents all have the same neutral genome, so uniqueness does not apply. Percentages now move in one-point steps per winner because each faces 100 matches per opponent.
