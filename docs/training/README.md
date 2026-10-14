# Training workspace

This branch starts with a throughput baseline before changing bot policies or fitness. The first workload is a complete `Game` with four `RandomBotPlayer` seats. `Game` still creates public and private decision contexts at each prompt. The runner supplies no action callback, so bot actions do not print to the terminal; only the benchmark test prints timing summaries.

## Layout

| Path | Purpose |
|---|---|
| `src/mus_computer/training/config.py` | Initial concurrency cap and timing targets |
| `src/mus_computer/training/game_runner.py` | Silent single-game runner and reusable process pool |
| `tests/training/test_game_runner.py` | Real game, process, silence, cap, and opt-in timing checks |
| `docs/training/experiments/` | Templates and notes for future training runs |
| `src/mus_computer/training/genetic_trainer.py` | Existing genetic trainer; not wired to the new runner yet |

## Target and measurement

The initial cap is ten concurrent games. A single random-bot game has a 0.6-second latency ceiling. A batch of ten games on an already started, warmed process pool has a 0.6-second target. At a sustained rate, ten games per 0.6 seconds corresponds to 100 games per 6 seconds or 1,000 games per minute. Pool startup and table loading are excluded from the batch measurement because a training run reuses the pool; they still matter to short one-off commands.

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
3. Connect the existing genetic trainer to the reusable game runner.
4. Benchmark a representative trained-policy game mix, including games that reach 40 points.
