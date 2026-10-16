# Training workspace

This branch starts with a throughput baseline before changing bot policies or fitness. The first workload is a complete `Game` with four `RandomBotPlayer` seats. `Game` still creates public and private decision contexts at each prompt. The runner supplies no action callback, so bot actions do not print to the terminal; only the benchmark test prints timing summaries.

## Layout

| Path | Purpose |
|---|---|
| `src/mus_computer/training/config.py` | Initial concurrency cap and timing targets |
| `src/mus_computer/training/game_runner.py` | Silent random baseline and genome matchup games, plus reusable process pool |
| `src/mus_computer/training/genome_generator.py` | Replaceable population creation and winner driven genome variation |
| `src/mus_computer/training/constants.py` | Maximum concurrent game count |
| `tests/training/test_game_runner.py` | Real game, process, silence, cap, and opt-in timing checks |
| `docs/training/experiments/` | Templates and notes for future training runs |
| `src/mus_computer/training/genetic_trainer.py` | Schedules matchups, scores wins, and asks the generator for the next population |
| `src/mus_computer/training/reporting/` | Snapshot summaries and offline Plotly charts |

## Genome training flow

See [GENES.md](GENES.md) for the staged gene tracker.

Pass `gen_generator=` to `GeneticTrainer` to replace the default `CustomGeneticGenomeGenerator`. The generator provides `initial_population(size)` and `next_generation(population, fitness)`. `USED_GENES` in `src/mus_computer/training/constants.py` contains `cut_prone`, `cut_prone_with_pares`, and `cut_prone_with_juego`. Genome matchups compose `GeneCutMusStrategy` with the unchanged discard and wager policies. Ordinary bots without an injected strategy portfolio retain the fixed Mus policy. See [GENES.md](GENES.md) for the exact cut formula.

Configure a bot by constructing one complete `StrategyPortfolio(mus_strategy=..., discard_strategy=..., wagers_by_phase=...)` and passing it as `strategies=` to `BotPlayer`. `build_bot_game` shows the three concrete policies used for genome matchups. Every policy is required at construction; there is no replacement step.

When genes are active, the trainer pairs the population into games. `games_per_eval` adds pairing rounds before generating the next population. The top 50% by win rate are alpha. The generator shuffles them into pairs and averages each active gene to create one child per pair, then creates a varied copy of every alpha with an independent additive change from -0.10 to +0.10 per active gene. It fills the remaining slots with randomly selected beta genomes, varied from -0.15 to +0.15 per active gene. Values are clamped to [0, 1]. One game per genome gives only binary fitness and is too noisy to establish learning; compare candidates over multiple games and against a fixed baseline before interpreting trends.

The trainer owns one runner object from initialization. `evolve()` opens its process pool, warms the configured workers once, then reuses them for every generation. The genomes change between generations, but the worker processes and their loaded lookup tables remain alive. An individual call to `evaluate_population()` opens and closes that same runner if it is not already open. Pass `runner=` to the constructor to supply another runner.

A 100-generation run of 20 genomes with eight pairing rounds per generation can use `python -m mus_computer.training.genetic_trainer --pop 20 --gen 100 --games 8 --seed 0`. The three cut genes then affect Mus decisions in genome matchups. The same pool runs all rounds and generations.

`evolve()` returns the top half of the final population by win rate. The CLI writes them to `winning_genomes.json` (or the path supplied with `--out`). With no active genes, those genomes are identical and are only a fixed-policy baseline. A single-round average win rate is always 0.5 because each game has one winner and one loser; it is not an improvement measure across generations.

Each `GenomeMatchup(team_a, team_b, seed)` seats one genome in both A seats and the other in both B seats. `build_bot_game` creates the four contextual `BotPlayer` instances, and `TrainingGameRunner.play_matchups` runs those games without printing actions. The trainer derives a distinct game seed from `--seed`, generation number, and matchup number; the default starting seed is 0. Each bot receives a separate random stream derived from its game's seed. The runner restores the caller's global random state after a local game, and `evolve()` restores it after a full seeded run.

Within a game, the first seat rotates after every completed hand (after Juego or Punto), so each player becomes mano in turn. All four seats retain their original team membership. The game stops before rotating if the hand produces a winner.

## Snapshots and charts

Install reporting support with `python -m pip install -e ".[reporting]"`. A CLI run writes full population snapshots every `--snapshot` generations and at the final generation. Each snapshot stores the generation number, active gene names, and every bot's personality in `--run-dir/snapshots/`. The CLI then writes `--run-dir/winning_genomes.json`, an overview chart, and one mean plus p5–p95 chart per active gene under `--run-dir/charts/`. With no active genes, the index explains that the run is a fixed baseline and no gene charts are generated. Open `charts/index.html` in a browser to navigate the interactive charts. They use a local Plotly JavaScript file and work offline. Rebuild charts from saved snapshots with `generate_charts(run_dir)` from `mus_computer.training.reporting`.

For a fixed baseline, use `python -m mus_computer.training.genetic_trainer --pop 64 --gen 1 --games 8 --workers 16 --no-genes --run-dir training_runs/baseline`. Add a gene to `USED_GENES` only after restoring its decision effect and adding a behavior check. Compare its winners against the baseline under repeated seat-balanced matchups. `training_runs/`, standalone `winning_genomes*.json`, and legacy `population_gen*.json` are Git ignored.

`GameResult.victory_reason` records whether the match ended by points or ordago, which helps compare training experiments. `worker_pid` is the operating system process ID returned by `os.getpid()`; it helps verify whether a batch used multiple worker processes. `_prepare_worker` loads the lookup table once in each worker before its first game. `warm_up()` explicitly starts every configured worker before a timed full-pool benchmark. Small batches can run directly without waiting for the whole pool.

## Target and measurement

The maximum concurrency cap is 16 games; the CLI defaults to ten workers. A single random-bot game has a 0.6-second latency ceiling. A batch of ten games on an already started, warmed process pool has a 0.6-second target. At a sustained rate, ten games per 0.6 seconds corresponds to 100 games per 6 seconds or 1,000 games per minute. Pool startup and table loading are excluded from the batch measurement because a training run reuses the pool; they still matter to short one-off commands.

Run the functional tests:

```sh
python -m pytest tests/training/test_game_runner.py -q
```

Run the live timing checks and show measured values:

```sh
RUN_TRAINING_PERF=1 python -m pytest tests/training/test_game_runner.py -q -m performance -s
```

In PowerShell, set `$env:RUN_TRAINING_PERF = '1'` before the pytest command. The timing tests are opt-in because shared CI machines and background load can vary. They use fixed game seeds, real contexts, and real games; a failed threshold is a performance finding, not a reason to loosen the target. Random bots often offer ordago early, so this baseline can be much faster than games involving trained policies. Measure those separately before claiming the target for training.

## Next training steps

1. Record experiment parameters and outcomes under `docs/training/experiments/`.
2. Define fitness and opponent selection for contextual `BotPlayer` genomes.
3. Benchmark a representative trained-policy game mix, including games that reach 40 points.
