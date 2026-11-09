# Training workspace

Use the opt-in [training experiment framework](EXPERIMENTS.md) for champion/
challenger comparisons and recorded follow-up attempts across model designs.

The opt-in [phase-specific CFR betting GLM](CFR_GLM.md) uses the separate
`python -m mus_computer.training.cfr --policy glm` entry point. Tabular CFR
remains its default baseline; the coefficient trainer below is unchanged.

## Context-specific coefficient training (default, version 2)

```sh
python -m mus_computer.training --rounds 1000 --batch-size 16 --workers 16 --seed 7 --run-dir training_runs/coefficient_cfr_v2_seed7
```

This evaluates **16,000 fixed no-Mus hands**, performs 1,000 updates, writes
coefficient evolution charts, and then plays **100 full matches per baseline**.
A match is first to four game wins; each normal game starts at 0 and continues
through fresh hands until 40 points or an accepted ordago. Use `--workers 1` for
serial execution, `--validation-matches` for an even per-baseline match count,
`--wins-to-match` to change the match target, or `--skip-validation` to train only.
No plotting or machine-learning dependency is required.

### Twelve named coefficients with separate purposes

Each winning/losing case has six stored probabilities:

| Coefficients | Interpretation |
|---|---|
| pass / bet | Opening probability pair; sums to one |
| fold / match | Response probability pair when not re-bidding; sums to one |
| rebid | Independent chance of raising an opponent's ordinary bet |
| ordago | Independent chance that an intended bet or re-bid becomes ordago |

There is no six-way normalization. Updating `ordago` or `rebid` does not rescale
the opening or calling pairs. Complementary pairs leave four independent
probability choices per winning/losing case. Initially, pairs are 0.5/0.5,
re-bid is 0.5, and ordago is 0.1. All twelve values are recorded each batch.

A hand's probability of winning combines the two endpoint predictions:
`c = (1 - p_win) * c_losing + p_win * c_winning`, as in the original proposal.
This does not change the stored coefficients or make them functions of hand
strength. It evaluates the policy for an uncertain hand. The existing tables
use only that player's private cards; ties favor the first eligible seat.

For the mixed probabilities `f, p, m, b, r, o`, action probabilities are:

| Public wager situation | Action distribution |
|---|---|
| No bet yet | pass `p`, bet two `b*(1-o)`, ordago `b*o` |
| Facing the opening bet | fold `(1-r)*f`, match `(1-r)*m`, raise two `r*(1-o)`, ordago `r*o` |
| Facing a numeric counter-raise | fold `1-r*o`, ordago `r*o` |
| Facing ordago | fold `f`, match `m` |

These distributions sum to one by construction. The final counter-raise
response excludes matching and further numeric raises, per the simplified
rule. Non-ordago probability goes to folding there. These restrictions belong
to the decision logic, not the coefficients. Both eligible teammates can
respond, so one fold does not automatically fold the team.

### Exact hand evaluation and coefficient updates

Every training hand draws physical cards without replacement and independent
starting scores uniformly from 10 through 28. It covers Grande, Chica, eligible
Pares, and Juego or Punto with the same hands and no Mus or exchanges. Actual
cards determine settlement; policy input never contains opponents' cards.

The evaluator enumerates wager responses and propagates a distribution of
surviving score pairs into each later lance. Accepted ordago or reaching 40
ends that branch. It settles each lance immediately in this simplified model;
the playable game retains its normal deferred showdown accounting.

Utility is the change in your team's score minus the other team's change
during the hand. Scores are capped at 40; ordago fills the winner's remaining
distance to 40. This remains a points-based training proxy, not match-win
probability. Each action's value includes surviving future lances. Reports
compare it with the best legal action against the frozen policy using
`penalty[a] = max(Q) - Q[a]`. Reach-weighted local penalty sums are diagnostics,
not exploitability or a bound on whole-game regret.

All sixteen workers receive identical frozen coefficients. Each actor's exact
local gradient holds other decisions fixed and is weighted by its full path
reach. The main process waits for every hand, averages over the sixteen hands
and both teams, scales by 40, and takes one gradient step. Pair updates use
log odds; re-bid and ordago use independent logits. Small probability bounds
keep exploration available. This is CFR-inspired parameterized policy
improvement, not tabular CFR, regression CFR, or a convergence guarantee.

### Full-match validation and charts

Validation uses the existing `Game` and `Match` classes, with normal scoring
and repeated deals. Candidate bots always cut Mus, preserving the no-Mus
scope. The opponents are:

- The existing `RandomDecisionBot`, sampling uniformly over all legal actions.
- New random coefficient sets using this same version-2 wager policy. Each set
  stays fixed for both opponents and every game in its match, and is reused
  in the paired comparison with sides swapped.
- The existing `MusMaestroBot` baseline: pass/fold wagering and always vote Mus.
  This is the repository's existing conservative baseline, not an external engine.

Each opponent gets 100 matches: 50 from each team side using paired seeds.
`validation.json` records every match's seed, candidate side, game-win score,
random opponent coefficients, and match win rate. Side-swapped matches share
a seed, so they are not treated as independent samples for a confidence interval.
`validation.md` is the readable summary. This replaces the former isolated-hand
piedra-margin comparison as the CLI validation result.

Generated files under the Git-ignored run directory:

- `training.json`: configuration, policy version, final coefficients, all batch
  metrics, and all 1,001 coefficient snapshots (including initialization).
- `coefficients.svg`: two charts, losing and winning, with six named curves each.
- `coefficients.csv`: all twelve curves as numerical data.
- `example_hand.json`: a final-policy hand's initial scores, survival by lance,
  terminal outcome probabilities, and decision histories, strength estimates,
  reach, action values, and best-action penalties.
- `validation.json` / `validation.md`: full-match results against all three baselines.

### Limitations and layout

The hand-strength table describes one unknown opponent, not the opposing team,
and does not update from observed wagers. The policy cannot explicitly adapt
to score, phase, seat, or teammate strength. Training's immediate scoring and
point-based ordago value differ from the normal game's scoring and match-win
objective; full-match validation measures transfer rather than assuming it.
Shared self-play may cycle, and 100 matches per baseline leaves uncertainty.

Implementation lives in `training/coefficient_cfr/`: `policy.py` owns contextual
probabilities and gradients; `tree.py` legal negotiations; `round.py` scoring
and survival; `trainer.py` frozen batches; `bot.py` the normal-game adapter;
`validation.py` full matches; and `charts.py` coefficient history exports.
Earlier version-1 results remain in their separate run folder; their ten
shared action weights are not interchangeable with version-2 coefficients.

## Earlier shared-strategy Monte Carlo CFR

The earlier trainer remains available as `python -m mus_computer.training.cfr`. It trains
one tabular action-probability policy through four-seat self-play. All seats use
the same frozen policy during an iteration; the trainer applies their regret
updates together after counterfactual evaluations. It reuses the existing
`Game`, `Deck`, decision contexts, strategy portfolio, legal actions, and
scoring. The fixed neutral `BotGenome` instance only satisfies the existing
bot personality interface; no genes are selected, crossed, or mutated.

Run a small experiment with:

```sh
python -m mus_computer.training.cfr --iterations 10 --seed 7 --snapshot-every 5 --run-dir docs/training/cfr_runs/example
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
with saved genome experiments. The default training command now uses the
bounded-hand coefficient trainer described above.

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
