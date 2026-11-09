# Reproducible training experiments

`python -m mus_computer.training.experiments` is an opt-in orchestration CLI.
It leaves existing training commands and algorithms unchanged. It trains native
artifacts, evaluates full matches, records follow-up attempts and explicitly
promotes a challenger only after separate confirmation.

Use the project virtual environment. Keep generated files under ignored
`training_runs/`; do not commit models, snapshots or raw run directories.

## Run a complete cycle

Save a trusted local design JSON, for example
`training_runs/reference.json`:

```json
{
  "adapter": "mus_computer.training.experiments.adapters:CFRAdapter",
  "config": {"policy": "glm", "iterations": 100, "glm_learning_rate": 0.1}
}
```

The adapter controls its native budget. CFR accepts existing `CFRConfig`
options except `seed`, supplied separately. It preserves the default portfolio
and deploys the trained **average** policy with no exploration. The same adapter
supports `policy: "tabular"`. Other algorithms can use different config fields.

```powershell
python -m mus_computer.training.experiments bootstrap --champion training_runs/champion.json --design training_runs/reference.json --run-dir training_runs/reference --seed 7
python -m mus_computer.training.experiments trial --champion training_runs/champion.json --design training_runs/challenger.json --run-dir training_runs/attempt1 --seed 7 --pairs 8 --wins-to-match 1
```

Bootstrap is explicit and refuses an existing champion. Later trials load that
frozen artifact; they never retrain or replace it. Each output directory must
be new. Open `attempt1/development.html` to review the comparison and its
attempt history. JSON remains the authoritative evidence.

Make an evidence-based design/config change, or explain why a replication is
needed, then run the follow-up:

```powershell
python -m mus_computer.training.experiments trial --champion training_runs/champion.json --design training_runs/followup.json --run-dir training_runs/attempt2 --seed 7 --pairs 8 --parent training_runs/attempt1/development.json --rationale "Describe the observed result and the change being tested."
python -m mus_computer.training.experiments confirm --champion training_runs/champion.json --development training_runs/attempt2/development.json --pairs 32
python -m mus_computer.training.experiments promote --champion training_runs/champion.json --confirmation training_runs/attempt2/confirmation.json
```

There is no automatic tuning or source editing. Codex inspects the first report
and chooses the next experiment. A second attempt need not improve. You may
select an earlier, better candidate by replicating that candidate as a recorded
follow-up, then confirming the frozen result. Confirmation requires at least
two linked attempts; do not tune on its results. A confirmation claim is
created **before** evaluation and cannot be reused. Failed confirmation remains
visible; start a fresh development cycle rather than silently retrying it.

Promotion defaults require at least 32 seed pairs, at least 55% challenger wins
head-to-head, and at most a 5 percentage point observed regression against each
static baseline. Declare alternatives with a `--rules` JSON file on the first
trial (`min_pairs`, `win_rate`, `max_regression`); follow-ups inherit them.
These are screening rules, not proof of statistical superiority. A rejected
promotion prints its reasons and exits with status 2; the champion stays intact.
Successful promotion atomically updates the pointer and retains the previous
artifact and confirmation reference in its history. Promotion is never implicit.

## What is compared

Both trained models play the same static suite: the default heuristic
portfolio, uniform random decisions, MusMaestro, and fixed random coefficients.
The coefficient baseline is drawn once from a recorded seed and reused; it is
not retrained. Follow-ups reuse identical baseline artifacts.

For another suite, supply `--baselines` on the first trial with a JSON object
mapping baseline IDs to adapter/config design specs. Follow-ups inherit that
frozen suite. New baseline designs use the same adapter protocol without a
coordinator change.

Each comparison plays both team assignments with the same paired seed. Each
match creates fresh games, teams, players, deck seeds and per-seat action RNGs.
Normal game scoring runs to 40 or accepted ordago; `--wins-to-match` optionally
requires several game victories. Training, development and confirmation use
separate deterministic seed namespaces. Confirmation is additionally keyed to
the frozen challenger artifact, preventing new candidates from automatically
reusing the previous candidate's held-out sample. Same-seed comparisons reduce
noise but do not guarantee identical dealt cards after different decisions.

JSON reports retain raw pair IDs, sides, seeds, winners and game-win scores,
plus artifact references and elapsed time. Summaries report pair-level standard
errors, including paired differences against static bots. Two side-swapped
matches are not counted as independent statistical observations. Reported
standard errors are descriptive, especially at small sample sizes. Training
regret/reward diagnostics remain in native checkpoints; full-game win rates are
the selection evidence.

### HTML is the standard results format

New development and confirmation runs automatically produce a standalone
`.html` report next to the canonical `.json`; the CLI prints the HTML path.
Reports work offline, including comparison bars, configured selection gates,
attempt history, provenance and expandable raw matches. No web hosting,
JavaScript library or reporting dependency is needed. Markdown remains for
project documentation and plans.

Regenerate presentation from existing JSON without changing evidence or
rerunning training:

```powershell
python -m mus_computer.training.experiments report --input training_runs/attempt2/confirmation.json
```

Use `--output path/to/results.html` for a portable copy. Existing output files
are not overwritten. Reports follow hash-checked history and artifact manifests,
so keep those files available for regeneration. Native model payloads need not
be loaded. Local absolute artifact paths are not included in the HTML.
Every attempt retains its evaluation budget, static comparisons and observed
screening failures. Development screening is clearly separate from held-out
promotion. Use `--related earlier/confirmation.json` to retain a separate
historical comparison, without pooling its sample into the current result.

## Add another design without changing orchestration

Implement these Python 3.10 structural protocols in a trusted local module:

```python
class MyAdapter:
    version = "my-inference-v1"

    def train(self, config, *, seed, run_dir):
        # Use your native trainer and save a file or checkpoint directory
        # strictly within run_dir. Return that Path; do not write artifact.json.
        ...

    def load(self, checkpoint, config):
        # Return factory(name, team, player_id, seed) -> existing PlayerBase.
        # Each call must create fresh mutable player state and use the seed.
        ...
```

Then set `adapter` to `your.module:MyAdapter`. Import resolution is for trusted
local Python code, not a sandbox for downloaded plugins. The coordinator never
reads CFR coefficients, assumes a model type, or translates training budgets.
Native continuation and diagnostics belong to the adapter; the generic runner
retains all payload files and hashes them for subsequent loading. It does not
provide a universal interruption/resume API or parallel/distributed scheduler.
Evaluation starts serially; artifact specs and task boundaries can support a
future executor using the existing `TrainingGameRunner.map_tasks` pool.

## Artifact integrity and inference compatibility

Each successful run publishes `artifact.json` **after** training succeeds. It
contains adapter/version/config, training seed, checkpoint path, payload hashes,
git revision and a digest of Python source including uncommitted source changes.
Champion pointers and report links additionally hash the manifest/report.
Loading rejects changed/missing payloads, paths outside the artifact directory
and unsupported adapter versions. Promotion checks raw records against the
aggregates, the frozen candidate, predeclared rules and current champion.
Payload file-set changes are rejected, including files newly added inside a
native checkpoint directory. Loaders must keep mutable caches outside artifacts.

Built-in adapter versions fingerprint their declared inference dependencies;
this includes game constants and bundled probability-table bytes. Source
provenance separately records bundled-data hashes.
training-only CFR edits do not change the inference version. If inference
changes, keep a frozen compatible reader or provide a new versioned adapter.
The framework fails clearly when that reader is unavailable. It does **not**
transparently execute historical git revisions or capture an entire Python
environment. Source provenance supports reproduction; it is not an environment
lockfile or executable source archive. Keep required snapshots and source
revisions available. Additional payload files remain covered by integrity hashes.

Registry updates use an exclusive lock file and atomic replacement. A crashed
process may leave a `.lock` file: check that no experiment owns it before
removing it. Failed training/evaluation records a failure JSON when possible,
without overwriting the champion. Explicit budgets limit iterations and match
counts; adapters and the game engine must terminate. There is no hard wall-clock
timeout for a custom nonterminating bot.

## Validation policy

For substantive training behavior changes, run a bounded real cycle, inspect
the comparison, and record at least one follow-up with its rationale. Confirm
the selected candidate separately and report failed gates honestly. Include a
compact evidence summary in the PR; retain raw runs locally for reanalysis.
Slow experiments are opt-in and are not part of default unit-test execution.

See the [initial local results](EXPERIMENT_RESULTS_2026-11-09.html) for the
100-iteration training cycle, follow-up, exact replication and rejected promotion.
