# Final winner validation

Validation plays each saved winner in ten independent games against each of three opponent policies. For each policy, the winner occupies Team A five times and Team B five times. Every game has a distinct deterministic seed, and one process pool runs all games.

| Report key | Opponent policy |
|---|---|
| `random_genes` | A newly sampled genome using the same Mus, discard, and wager strategies as the candidate. Only active genes vary. |
| `random_decisions` | Uniform choice among legal Mus and wager actions and all 16 discard subsets of a four-card hand. |
| `mus_maestro` | Always votes Mus, discards all cards after an exchange, passes without an offer, and folds when answering an offer. It never raises. |

```sh
python -m mus_computer.training.validation --winners training_runs/example/winning_genomes.json --seed 42 --workers 10
```

The command writes `training_runs/example/validation/results.json` by default. Use `--out PATH` to change the location. Each winner has a `benchmarks` object with separate `wins`, `games`, `win_percentage`, and `matchups` for the three policies. Each matchup records the candidate's team, seed, and outcome; random-gene matchups also record the opponent genome. The report includes the active genes and games per opponent.

Use repeatable `--gene NAME` flags to override `USED_GENES` when the training run used a custom active-gene set. The training CLI passes its configured active genes to validation automatically, including the empty set selected by `--no-genes`.

In Python, call `validate_winners(winners, run_dir, seed=42, workers=10, active_genes=("cut_prone",))` after training. Omit `active_genes` to use `USED_GENES`, or pass `()` for a neutral baseline. Ten games per opponent are a quick diagnostic, so percentages remain noisy.
