# Reusable training experiments implementation plan

> Execute inline with `superpowers:executing-plans`. This PR is stacked on the phase-specific CFR-GLM PR; it must not include that PR's diff in its own review boundary.

**Goal:** Let Codex run a complete, repeatable training/comparison cycle, inspect the evidence, make at least one deliberate follow-up attempt, and retain a reproducible champion without rewriting orchestration for each bot design.

**Architecture:** An additive `training/experiments/` package owns orchestration, immutable artifact references, paired full-match evaluation and champion selection. Versioned design adapters own training, checkpoint interpretation and player construction. The evaluator consumes `PlayerBase` factories, never model-specific coefficient structures or private trainer methods.

**Tech stack:** Python 3.10 standard library, existing game/Match classes, pytest and project review tools. Keep reporting optional and preserve all existing entry points.

## Phase 0: source/API discovery (completed)

- Read root `AGENTS.md` and `log.md`. Applicable decisions: phase-specific CFR isolation; dependency-free runtime imports; retain snapshots needed to resume/rebuild analysis; do not commit generated training output.
- `cfr/trainer.py`: `CFRTrainer(config, strategies=..., run_dir=...)`, `train()`, `from_snapshot(path, ...)`, `save_snapshot(iteration)`. `CFRConfig` includes `policy="glm"|"tabular"`, iterations, seed and GLM projection learning rate. Use these public methods in the CFR adapter.
- `cfr/policy.py`: `CFRPolicy.from_snapshot({"information_states": ...})` dispatches tabular/GLM snapshots; evaluate frozen average strategies. `DecisionController(..., exploration=0, average=True, record=False)` and `CFRBotPlayer(...)` provide existing inference.
- `game/game.py:46` / `game/match.py:21`: `Game.from_players(players)` and `Match(game_factory, wins_to_match).play()`. Evaluate complete normal games to 40 or accepted ordago, optionally first-to-N games; do not substitute the coefficient trainer's simplified hand utility.
- `coefficient_cfr/validation.py:32-113`: copy public A/B/A/B construction, per-seat RNGs, same-seed side swaps and fresh teams per game. It already records individual match scores. Leave this module unchanged.
- `training/game_runner.py:215`: `TrainingGameRunner.map_tasks(worker, tasks)` is an optional existing process-pool seam. Serializable specs must cross process boundaries; live `StrategyPortfolio` objects contain mapping proxies.
- Static opponents: `RandomDecisionBot`, `MusMaestroBot`, `BotPlayer` with `StrategyPortfolio.default()`. Optional random coefficient opponent uses existing `CoefficientBot` and a single fixed `Coefficients.random(Random(seed))` sample for a paired comparison.
- No generic experiment orchestration, artifact registry or champion selection exists. `validation/winners.py` balances seats but uses distinct seeds/opponents; do not label those records paired evidence.

## Scope and small interfaces

Create only `src/mus_computer/training/experiments/` modules, focused tests, this plan and usage documentation. Existing trainers/game code require no behavior changes. Add a brief link and the experiment workflow rule to existing documentation; use the already ignored `training_runs/` root for runtime output.

The interfaces are structural `Protocol`s, independent of CFR:

```python
class PlayerFactory(Protocol):
    def __call__(self, name: str, team: Team, player_id: int, seed: int) -> PlayerBase: ...

class DesignAdapter(Protocol):
    version: str
    def train(self, config: Mapping[str, Any], *, seed: int, run_dir: Path) -> Path: ...
    def load(self, checkpoint: Path, config: Mapping[str, Any]) -> PlayerFactory: ...
```

- A design spec is `adapter="package.module:Class"` plus JSON configuration. Resolve trusted local adapter classes through `importlib`; do not add a central switch for each new trained model.
- The adapter returns its native checkpoint path inside its run directory. It controls algorithm-specific budgets and continuation; the generic runner never guesses how iterations, generations or batches relate.
- A successful artifact has a versioned JSON manifest containing adapter/version/config, training seed, relative checkpoint path and SHA-256, git revision/source provenance, metrics/checkpoint references, and inference mode. Publish the manifest only after training succeeds. Never overwrite a completed run directory.
- A champion pointer references an artifact manifest plus its SHA-256. Verify pointer, manifest, native checkpoint hash and adapter version before loading. Keep prior artifacts and promotion history. New designs add adapters; core evaluator/runner stay unchanged.
- Adapter versions are an inference compatibility contract, not just metadata. Preserve frozen inference for supported versions; schema/policy changes need a new versioned loader. A saved checkpoint does not freeze arbitrary future source changes. Record the source revision and fail clearly when the matching inference implementation is unavailable; do not silently reinterpret an old champion with new behavior.
- Initial adapters: existing CFR (tabular and GLM configs) and existing static strategies. Add one independent test adapter to prove the runner does not depend on CFR fields. Coefficient/genetic training adapters are future small plugins, not trainer rewrites in this PR.

## Experiment lifecycle

1. **Bootstrap once:** train the reference design with an explicit budget and seed, save its artifact, and explicitly initialize `champion.json`. If a valid champion already exists, load it without retraining or overwriting it.
2. **Attempt 1:** train the challenger from a declared spec and budget. Evaluate trained champion and challenger separately against the identical static suite and directly against each other, using the same paired seeds within each matchup. Keep the champion frozen across attempts.
3. **Inspect:** save raw per-match results and compact JSON/Markdown summaries: wins/losses, per-pair outcomes, sample sizes, static-suite deltas, head-to-head results, training budget, seeds, runtime and numerical/serialization failures. Clearly separate training diagnostics from full-game playing strength.
4. **Attempt 2 or later:** Codex must read the previous report, make an evidence-based design/config change or document why a replication is needed, and run the full training/comparison pipeline again. Require a parent-report reference and written rationale. Do not hardcode an optimizer or promise that the second attempt improves.
5. **Confirm:** choose a challenger using development results, freeze its artifact, and evaluate it once on a separate held-out seed namespace. Do not tune on this confirmation set or let training/checkpoint selection consume it.
6. **Promote explicitly:** promotion requires a successful confirmation, at least two recorded attempts, the unchanged champion identity, the configured minimum number of pairs, a head-to-head improvement threshold and no material observed static-baseline regression. A tie, failure, insufficient sample or stale champion leaves the champion unchanged. Selection thresholds are configuration, recorded in the report before confirmation.

Promotion defaults are an implementation decision: explicit command, minimum 32 paired seeds for confirmation, challenger head-to-head win rate at least 55%, and no static-suite win-rate drop greater than 5 percentage points. These observed thresholds are screening rules, not a statistical proof of superiority. Report uncertainty using paired observations; never count two side-swapped matches as independent samples. Stronger statistical selectors can implement a later selection-policy interface without changing training/evaluation adapters.

## Task 1: artifacts and adapter boundary

**Files:** create `experiments/contracts.py`, `experiments/adapters.py`, `experiments/__init__.py`; test `tests/training/test_experiment_pipeline.py`.

- [ ] Write failing tests for loading a custom module adapter, native artifact round-trip, unsupported version, corrupt/missing checkpoint, escaping checkpoint path and overwrite refusal.
- [ ] Implement declarative specs, public protocols, validation and hashed artifact references. Keep Python 3.10 imports dependency-free. Configuration errors must surface before starting expensive training.
- [ ] Implement CFR adapter using the documented public checkpoint/training interface. Preserve its default portfolio, private hand estimates, average-policy deployment and seeded RNGs. Static adapters build existing bots; they do not invent new baselines.
- [ ] Run focused tests; verify the existing CFR and coefficient/genetic tests stay unchanged.

## Task 2: generic paired evaluation

**Files:** create `experiments/evaluation.py`; extend focused tests.

- [ ] Write failing tests for actual full-game evaluation of mixed adapter designs, A/B/A/B team identity, same-seed side swaps, identical static models across both candidates, restored global RNG state and serial reproducibility.
- [ ] Build games only through adapter-loaded player factories and `Game.from_players`; build matches through `Match`. Give each player a deterministic action RNG distinct from deck randomness. Never share mutable player/game state across games.
- [ ] Use disjoint deterministic namespaces for training, development, confirmation and each game index. Apply the same deck/action seed schedule to champion-versus-static and challenger-versus-static comparisons.
- [ ] Persist every matchup's pair ID, candidate side, seed, winner and game-win score. Aggregate from raw records; pair-level statistics must treat the pair as the sampling unit.
- [ ] Start serially; retain `map_tasks`-compatible serializable task/factory boundaries. Multiprocessing, distributed execution and scheduling are optional future executors, not required to prove the design.

## Task 3: attempts, reports and champion lifecycle

**Files:** create `experiments/pipeline.py`, `experiments/__main__.py`; extend focused tests and add `docs/training/EXPERIMENTS.md`.

- [ ] Write failing tests for fresh bootstrap, refusing champion overwrite, two-attempt provenance, changing champion between trial and promotion, failed/insufficient/tied confirmation, and explicit promotion preserving prior artifacts.
- [ ] Add commands for bootstrap, trial, confirmation and promotion. Keep JSON configuration and readable command-line help; existing training entry points retain their current meaning.
- [ ] Write immutable per-run manifests/reports and update the champion pointer atomically only after validation. Interrupted/failed training or evaluation leaves the previous champion intact and records failure when possible. Keep enough checkpoint/native metadata to resume and regenerate analysis.
- [ ] Report partial progress to stdout so a long run can be observed. Bound each run with explicit model budgets and match counts; record elapsed time. Do not introduce a background scheduler, dashboard, arbitrary shell runner, automatic source edits or cloud dependency.
- [ ] Document the Codex workflow in repository guidance: for substantive training-behavior changes, run a budgeted training experiment, inspect results, perform at least one recorded follow-up, and report both attempts. Slow experiments remain opt-in and separate from default unit tests.

## Task 4: exercise the full workflow and hand off

- [ ] Run a cheap real end-to-end smoke using CFR-GLM checkpoints and every initial static adapter; verify snapshot round-trip and repeated evaluation equality.
- [ ] Run a meaningful but bounded local training comparison: bootstrap trained CFR-GLM champion, train challenger, evaluate static/head-to-head development results, then choose and document a follow-up based on those results. Use at least 100 CFR iterations per trained artifact and at least 8 development pairs as the initial local budget; record any budget changes/failures rather than silently shrinking them.
- [ ] Run a separate confirmation of the selected candidate with at least 32 pairs. Retain the champion if promotion gates fail. A failed challenger is useful evidence; do not edit thresholds afterward to manufacture success.
- [ ] Commit only a compact human-readable evidence summary with configs, source revision, seeds, budgets, results and artifact hashes. Keep actual models, raw training runs and snapshots under ignored `training_runs/`; retain them for continuation/reanalysis.
- [ ] Run configured lint/format/mypy/secret hooks and non-slow/non-performance tests. Review the additional PR diff relative to the CFR-GLM branch, apply at most one verified Important repair batch, rerun required gates and review its delta read-only.
- [ ] Stage only framework files/docs, rerun hooks and relevant tests on the staged revision, commit, push and open the second PR with base `refactor/phase-specific-cfr-glm`. Link the first PR; handle CI/review feedback without merging automatically.

## Deferred extensions and anti-pattern guards

- No new training algorithm, score/hand features, charting stack, ML framework, or trainer-wide refactor.
- No model-specific fields in the experiment coordinator; a new adapter owns native serialization and inference.
- No retraining/replacing champion on every attempt; no promotion based solely on self-play reward or beating only a weak static opponent.
- No treating historical checkpoints as executable frozen source. Versioned inference must remain available; arbitrary cross-revision execution can later use an isolated worker implementing the same adapter protocol. Do not claim this first version transparently runs every historical git revision.
- No automatic repeated bot-driven repair loop. The requested experimental follow-up is model evaluation/iteration; repository code review still permits only its single repair batch.
