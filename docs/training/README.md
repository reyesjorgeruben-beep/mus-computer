# Training workspace

## Shared-strategy Monte Carlo CFR

The current training entry point is `python -m mus_computer.training`. It trains
one tabular action-probability policy through four-seat self-play. All seats use
the same frozen policy during an iteration; the trainer applies their regret
updates together after counterfactual evaluations. It reuses the existing
`Game`, `Deck`, decision contexts, strategy portfolio, legal actions, and
scoring. The fixed neutral `BotGenome` instance only satisfies the existing
bot personality interface; no genes are selected, crossed, or mutated.

Run a small experiment with:

```sh
python -m mus_computer.training --iterations 10 --seed 7 --snapshot-every 5 --run-dir docs/training/cfr_runs/example
```

Install the package first with `python -m pip install -e .`, or set
`PYTHONPATH=src`. Snapshot JSON files contain every visited information state,
its legal actions, cumulative regrets, current action probabilities, and
reach-weighted average probabilities. They also contain iteration count,
sampled game count (including action rollouts), each team's running average
utility, and the average policy's paired win fraction against the preceding
checkpoint. Generated CFR runs are Git ignored.

The trainer samples each deal using the existing random shuffle. It samples
one complete exploratory trajectory, selects one visited decision per player,
then replays the same history once per legal action and samples a continuation
from the frozen current policy. The target action's value is the mean utility
of that continuation sample, so estimates are noisy. The regret increment is
the action value minus the current mixed-policy value, multiplied by the
opponents' target reach divided by the trajectory behavior reach. Selecting
one of a player's visited decisions adds a multiplier equal to the number of
their visited decisions. These factors correct the sampled trajectory to a
counterfactual regret estimate. Average-strategy contributions use own reach
divided by behavior reach. The engine can see all hands to resolve outcomes;
the policy key contains only the acting player's hand and public state.

The table uses full public history within a hand, but the game clears that
history between hands, so this abstraction can merge histories that a player
could remember. The game also has four players in two teams. Do not infer the
usual two-player zero-sum CFR convergence guarantee from these results.

The earlier genetic trainer and its tests remain callable for compatibility
with saved genome experiments. The default training command now uses CFR.

## Earlier genome training and throughput notes

This branch starts with a throughput baseline before changing bot policies or fitness. The first workload is a complete `Game` with four `RandomBotPlayer` seats. `Game` still creates public and private decision contexts at each prompt. The runner supplies no action callback, so bot actions do not print to the terminal; only the benchmark test prints timing summaries.

## Layout

| Path | Purpose |
|---|---|
| `src/mus_computer/training/config.py` | Initial concurrency cap and timing targets |
| `src/mus_computer/training/game_runner.py` | Silent random baseline and genome matchup games, plus reusable process pool |
| `src/mus_computer/game/match.py` | Play fresh games until one team reaches the configured game-win target |
| `src/mus_computer/training/genome_generator.py` | Replaceable population creation and winner driven genome variation |
| `src/mus_computer/training/constants.py` | Maximum concurrent game count |
| `tests/training/test_game_runner.py` | Real game, process, silence, cap, and opt-in timing checks |
| `docs/training/experiments/` | One Git-ignored folder per run, with plots, winners, snapshots, and validation |
| `src/mus_computer/training/genetic_trainer.py` | Schedules matchups, scores wins, and asks the generator for the next population |
| `src/mus_computer/training/reporting/` | Snapshot summaries and offline Plotly charts |

## Genome training flow

See [GENES.md](GENES.md) for the staged gene tracker.

Pass `gen_generator=` to `GeneticTrainer` to replace the default `CustomGeneticGenomeGenerator`. The generator provides `initial_population(size)` and `next_generation(population, fitness)`. `USED_GENES` in `src/mus_computer/training/constants.py` contains `bluff_rate` and `extreme_bluff_rate`. Genome matchups compose `AlwaysCutMusStrategy` with the unchanged discard policy and `ComposedWagerStrategy`, which applies bluff layers after the gene-free `HandStrengthWagerStrategy` baseline. Ordinary bots without an injected strategy portfolio retain the fixed Mus and wager policies. See [GENES.md](GENES.md) for the exact behavior.

Configure a bot by constructing one complete `StrategyPortfolio(mus_strategy=..., discard_strategy=..., wagers_by_phase=...)` and passing it as `strategies=` to `BotPlayer`. `build_bot_game` shows the three concrete policies used for genome matchups. Every policy is required at construction; there is no replacement step.

When genes are active, the trainer pairs the population into matches. `games_per_eval` adds pairing rounds before generating the next population, and `wins_to_match` sets how many games a team must win to take each match. The trainer scores match wins, so fitness remains the fraction of pairing rounds won. The top 50% by win rate are alpha. The generator shuffles them into pairs and averages each active gene to create one child per pair, then creates a varied copy of every alpha with an independent additive change from -0.03 to +0.03 per active gene. It fills the remaining slots with randomly selected beta genomes, varied from -0.05 to +0.05 per active gene. These defaults live in `training/constants.py`; pass `alpha_variation=` and `beta_variation=` to `CustomGeneticGenomeGenerator` to override them for one run. Values are clamped to [0, 1]. A single match still gives only binary fitness; compare candidates over multiple matches and against a fixed baseline before interpreting trends.

The trainer owns one runner object from initialization. `evolve()` opens its process pool, warms the configured workers once, then reuses them for every generation. The genomes change between generations, but the worker processes and their loaded lookup tables remain alive. An individual call to `evaluate_population()` opens and closes that same runner if it is not already open. Pass `runner=` to the constructor to supply another runner.

A 100-generation run of 20 genomes with eight pairing rounds per generation and first to three game wins per match can use `python -m mus_computer.training.genetic_trainer --pop 20 --gen 100 --games 8 --wins-to-match 3 --seed 0`. The two bluff genes then affect wagers in genome matchups. The same pool runs all rounds and generations.

`evolve()` returns the top half of the final population by win rate. The CLI writes them to `winning_genomes/genomes.json` inside the experiment (or another filename supplied with `--out` in that folder). With no active genes, those genomes are identical and are only a fixed-policy baseline. A single-round average win rate is always 0.5 because each game has one winner and one loser; it is not an improvement measure across generations.

Each `GenomeMatchup(team_a, team_b, seed, wins_to_match)` seats one genome in both A seats and the other in both B seats. `Match` requests a fresh game for every contest, and `build_bot_game` creates four fresh contextual `BotPlayer` instances each time. `TrainingGameRunner.play_matchups` runs those matches without printing actions. The trainer derives a distinct match seed from `--seed`, generation number, and matchup number; the default starting seed is 0. Each new game has distinct bot random streams derived from its match seed and game index. The runner restores the caller's global random state after a local match, and `evolve()` restores it after a full seeded run. `MatchRunResult.wins_a` and `wins_b` report the game score, such as 2–3. A match has no `victory_reason`; that field belongs to single-game results only.

Within a game, the first seat rotates after every completed hand (after Juego or Punto), so each player becomes mano in turn. All four seats retain their original team membership. The game stops before rotating if the hand produces a winner.

## Snapshots and charts

For older experiments with active cut genes, `mus_decisions.html` evaluates `GeneCutMusStrategy` for every genome in each snapshot under four hand conditions. Current bluff-gene runs use `AlwaysCutMusStrategy` and omit that chart; they include a chart for each bluff gene instead.

Install reporting support with `python -m pip install -e ".[reporting]"`. A CLI run creates a new folder under `docs/training/experiments/` with a short `README.md`, full population snapshots every `--snapshot` generations, final winning genomes in `winning_genomes/`, interactive Plotly charts, and a compact validation table in `validation/results.md`. Validation uses 100 matches per winner and opponent, each first to the training run's `wins_to_match` game target. Open that experiment's `charts/index.html` to inspect the evolution. The charts use a local Plotly JavaScript file and work offline. Rebuild charts from saved snapshots with `generate_charts(run_dir)` from `mus_computer.training.reporting`.

For a fixed baseline, use `python -m mus_computer.training.genetic_trainer --pop 64 --gen 1 --games 8 --workers 16 --no-genes --experiment-name baseline`. The description follows the date in the folder name (`YYYY-MM-DD_baseline`); choose a new description for another run on the same day. Add a gene to `USED_GENES` only after restoring its decision effect and adding a behavior check. Generated experiment folders, legacy `training_runs/`, standalone `winning_genomes*.json`, and legacy `population_gen*.json` are Git ignored.

`GameResult.victory_reason` records whether the deciding game ended by points or ordago. `worker_pid` is the operating system process ID returned by `os.getpid()`; it helps verify whether a batch used multiple worker processes. `_prepare_worker` loads the lookup table once in each worker before its first game. `warm_up()` explicitly starts every configured worker before a timed full-pool benchmark. Small batches can run directly without waiting for the whole pool.

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
