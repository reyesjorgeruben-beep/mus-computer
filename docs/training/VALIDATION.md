# Final winner validation

After training, the validation command plays each saved winner in ten **independent single games** against ten newly sampled random genomes. The winner is team A for five games and team B for five. Each game uses a distinct deterministic seed. The same process pool runs all matchups.

```sh
python -m mus_computer.training.validation --winners training_runs/example/winning_genomes.json --seed 42 --workers 10
```

The command writes `training_runs/example/validation/results.json` by default. Use `--out PATH` to change the location. The JSON records each winner's wins and percentage, the active genes, and each opponent genome, seat, and game seed for reproduction. Random opponents vary only the genes in `USED_GENES`; inactive genes remain at 0.5.

Use repeatable `--gene NAME` flags to override `USED_GENES` when the training run used a custom active-gene set. For example, `--gene cut_prone --gene cut_prone_with_pares`. The training CLI passes its configured active genes to validation automatically, including the empty set selected by `--no-genes`.

In Python, call `validate_winners(winners, run_dir, seed=42, workers=10, active_genes=("cut_prone",))` after training. Omit `active_genes` to use `USED_GENES`, or pass `()` for a neutral baseline. The function returns the same report it writes to disk. Ten games per winner are a quick diagnostic; the resulting percentages have substantial sampling noise.
