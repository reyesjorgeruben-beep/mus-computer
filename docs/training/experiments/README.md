# Training experiments

Each training run gets a new folder here. Its `README.md` records the settings and links to `charts/index.html`, `winning_genomes/genomes.json`, `validation/results.md`, and `snapshots/`. New validation files are compact tables of each winner's win percentage over 100 matches against each of the three baseline bots. The charts are interactive Plotly HTML files. Generated experiment folders are Git ignored, while this index and older written experiment notes remain tracked.

Run `python -m mus_computer.training.genetic_trainer` from this repository to create a uniquely named dated folder automatically. Use `--experiment-name DESCRIPTION` to name a run `YYYY-MM-DD_DESCRIPTION`, for example `2026-10-17_testing_bluff_genomes`. The old `--run-dir` flag is accepted as an alias for the description, not a filesystem path. A name already in use is rejected so existing results are not overwritten.
