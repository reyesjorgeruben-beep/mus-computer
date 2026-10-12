# Contextual Bots and Source Package Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Use the parallel wave described below after Task 2. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver an installable, organized Mus game package whose strategic bots make testable decisions from shared public state, private hand statistics, and injectable personality-driven strategies.

**Architecture:** Move runtime code into a `src/mus_computer` package grouped into cards, game, bots, probabilities, and training; keep offline analysis programs in `scripts/tables`. A frozen global context carries public state, each acting bot gets private card statistics, and an injectable portfolio samples normalized distributions over legal actions. The game engine owns wager resolution, phase-order scoring, ordago termination, and the terminal event feed.

**Tech Stack:** Python 3.10+, setuptools/PEP 621, stdlib runtime; pytest 9.0.2 and NumPy for development/table-builder tests, with NumPy exposed only as optional table tooling and a dev dependency.

**Spec:** `docs/superpowers/specs/2026-09-27-contextual-bot-strategies-design.md`

## Global Constraints

- Keep the supported Python floor at 3.10 and add no third-party runtime dependencies.
- Preserve `BotGenome` fields and serialized genome compatibility; do not run genetic training.
- Never place another player's hidden cards or card-derived statistics in `GlobalGameContext`.
- Keep separate `HandStatistics` estimates for Grande, Chica, Pares, Juego, and Punto; Punto uses its actual card comparison rule and keeps ties separate.
- A strategy distribution contains finite, nonnegative values whose sum is 1 within `1e-9`; sampling may choose only legal actions.
- For wager responses, one eligible `quiero` accepts and stops the phase; every eligible defender must say `no quiero` for a fold. Opening raises set totals; counterraises add their amount.
- An accepted ordago immediately ends the match for the phase winner. A refused ordago awards only the last accepted stake and does not concede the match.
- Score folded wager stakes immediately. Queue ordinary phase points and folded Pares/Juego intrinsic points for end-of-hand settlement in Grande, Chica, Pares, Juego/Punto order; stop at the first score event that reaches 40.
- Preserve all pre-existing uncommitted generated files. The probability pickle moved into package data must use the committed `HEAD` blob byte-for-byte; do not include the larger regenerated local copy or generated CSV/HTML changes in task commits.
- Do not read or stage `.env`, `.claude/settings.local.json`, or any generated/local table output.
- Keep `RandomBotPlayer` and the existing four-bot terminal log. Do not add human play or use training results as a success measure.

## Review Focus

1. Hidden-information leakage: tests assert the shared context contains no opponents' cards, while player contexts differ by hand.
2. Punto ties and mano priority: tests compare estimates with direct controlled-hand comparisons and preserve `p_tie` separately.
3. Distribution legality: tests cover non-finite, negative, non-normalized, and currently illegal wager actions.
4. Wager response sequencing: tests prove one eligible acceptance ends the exchange, all eligible defenders must refuse, and teammates are not asked after acceptance.
5. End-of-hand scoring: tests cover ordago, folded Pares/Juego intrinsic points, immediate fold awards, and the first team reaching 40 in phase order.

---

## Task 1: Establish the `src` Package and Migrate Existing Code

**Files:**
- Create: `pyproject.toml`, `src/mus_computer/__init__.py`, `src/mus_computer/__main__.py`, `src/mus_computer/cli.py`, `src/mus_computer/cards/__init__.py`, `src/mus_computer/game/__init__.py`, `src/mus_computer/bots/__init__.py`, `src/mus_computer/bots/strategies/__init__.py`, `src/mus_computer/probabilities/__init__.py`, `src/mus_computer/training/__init__.py`.
- Move runtime modules: `card.py`, `deck.py`, `hand.py` to `src/mus_computer/cards/`; `game.py`, `phases.py`, `player.py`, `player_base.py`, `team.py`, and `wager_session.py` to `src/mus_computer/game/`, renaming `game_context.py` to `src/mus_computer/game/context.py`; `bot_player.py`, `random_bot_player.py`, `bot_genome.py`, `bot_game_state.py` to `src/mus_computer/bots/`; `probability_tables.py` to `src/mus_computer/probabilities/tables.py`; `genetic_trainer.py` to `src/mus_computer/training/genetic_trainer.py`; `constants.py` and `utils.py` to `src/mus_computer/`.
- Move table programs: `build_tables.py`, `compute_expected_points.py`, `compute_ep_postmus.py`, `compute_hand_distribution.py`, `compute_best_discards.py`, `compute_best_discards_corrected.py`, and `export_tables.py` to `scripts/tables/` with `scripts/__init__.py`, `scripts/tables/__init__.py`, and `scripts/tables/paths.py` for repository-root output defaults.
- Move existing tests into `tests/cards/`, `tests/game/`, `tests/bots/`, `tests/probabilities/`, and `tests/training/`. Keep shared fixtures in `tests/conftest.py` and update all imports, including private test imports from the table builder.
- Modify: root `api.py` to become a thin compatibility wrapper; `.gitignore`; `.github/workflows/tests.yml`; `tests/conftest.py`.
- Test: `tests/test_package_layout.py` and `tests/test_cli.py` before migration; move existing tests into their responsibility folders.
- Create: `src/mus_computer/probabilities/data/probability_tables.pkl` from the committed blob and package it as read-only data.

**Interfaces:**
- `mus_computer.cards` exports `Card`, `Deck`, and `Hand`.
- `mus_computer.game` exports `Game`, `Team`, `PlayerBase`, `HumanPlayer`, and phase classes.
- `mus_computer.bots` exports `BotPlayer` and `RandomBotPlayer`.
- `mus_computer.probabilities.tables.load_tables(path: str | Path | None = None) -> dict` loads an explicit file when supplied, otherwise reads the packaged pickle through `importlib.resources`.
- `mus_computer.cli.build_default_game(on_action=None) -> Game` creates the four random bot seats; `mus_computer.cli.main(argv=None) -> int` drives the match. `python -m mus_computer` and `python api.py` both start it.
- Analysis commands run as `python -m scripts.tables.<module>` after editable install. Their default generated output path is the repository root, never `src/`.
- `python api.py` stays compatible; the package runner is added in Task 5.

- [ ] **Step 1: Write the failing package import and table-resource test**

Create `tests/test_package_layout.py` and `tests/test_cli.py`:

```python
def test_public_modules_import_from_the_package():
    from mus_computer.cards import Card, Deck, Hand
    from mus_computer.game import Game, Pares
    from mus_computer.bots import BotPlayer, RandomBotPlayer
    from mus_computer.probabilities.tables import load_tables
    from mus_computer.cli import build_default_game

    assert Card.A.value == "A"
    assert Deck is not None and Hand is not None
    assert Game is not None and Pares is not None
    assert BotPlayer is not None and RandomBotPlayer is not None
    game = build_default_game()
    assert [player.name for player in game.players_in_order] == ["Bot 1", "Bot 2", "Bot 3", "Bot 4"]
    assert [player.team.name for player in game.players_in_order] == ["A", "B", "A", "B"]
```

In `tests/test_cli.py`, launch `[sys.executable, "-m", "mus_computer", "--help"]` and assert exit code 0 and `usage:` in stdout.

- [ ] **Step 2: Run the test to verify the package is missing**

Run: `python -m pytest tests/test_package_layout.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'mus_computer'`.

- [ ] **Step 3: Add package metadata and perform the source migration**

Add setuptools package discovery from `src`, `requires-python = ">=3.10"`, an empty runtime dependency list, a `tables` extra for NumPy and a `dev` extra containing `pytest==9.0.2` plus NumPy for the offline builder tests, pytest paths/`slow` marker configuration, package data `probabilities/data/*.pkl`, and a `mus-computer = "mus_computer.cli:main"` script entry point. Move the modules listed above, convert internal imports to package imports, update grouped tests, and update the table scripts to use `scripts.tables.*` imports and `paths.py` output paths. Move the existing four-random-bot runner into `cli.py`, add `__main__.py`, and reduce root `api.py` to the compatibility call.

For the lookup resource, write the stdout bytes of `git show HEAD:probability_tables.pkl` into the package data path with a binary-safe Python write; do not use PowerShell text redirection. Leave the existing modified root `probability_tables.pkl` untouched as a local artifact, remove only its tracked index entry, and add `/probability_tables.pkl` to `.gitignore`. Do not move, stage, or regenerate `tables_report.html`, `tables_summary.csv`, `tables_discard_insights_corrected.csv`, or other local analysis outputs.

- [ ] **Step 4: Install and verify the migrated public imports and runner**

Run: `python -m pip install -e ".[dev]"`; then `python -m pytest tests/test_package_layout.py tests/test_cli.py -q`.
Expected: PASS for package exports, the A/B/A/B default roster, and `python -m mus_computer --help`.

- [ ] **Step 5: Add failing package-resource and explicit-path coverage**

Extend `tests/test_package_layout.py` with assertions that `load_tables()` reads non-empty packaged data and that a temporary pickle containing `{"fixture": 1}` is returned by `load_tables(path)`. Expected before the loader change: `FileNotFoundError` for the default resource and `TypeError` for the explicit path.

- [ ] **Step 6: Implement packaged and override table loading**

Load default bytes from `importlib.resources.files("mus_computer.probabilities").joinpath("data", "probability_tables.pkl")`; load an explicit `path` with `Path.open("rb")`. Cache the default package result and explicit paths independently so one test override cannot contaminate later lookups.

- [ ] **Step 7: Update CI installation and run the migrated suite**

Change the workflow to `python -m pip install -e ".[dev]"`, then run `python -m pytest tests/ -v`. Expected: all migrated existing tests plus package/resource tests pass.

- [ ] **Step 8: Verify artifact preservation and commit only Task 1 files**

Run `git status --short` and `git diff --stat`; confirm the pre-existing report/summary modifications and corrected CSV remain unstaged and that the packaged pickle hash equals `git rev-parse HEAD:probability_tables.pkl`. Commit only source moves, tests, packaging config, CI, ignore rules, and the unchanged table blob relocation.

---

## Task 2: Define Shared and Private Decision Contexts

**Files:**
- Modify: `src/mus_computer/game/context.py` to replace the wager-only `GameContext` with immutable `GlobalGameContext` and `WagerState`; update all consumers and tests to the shared context.
- Create: `src/mus_computer/bots/strategies/contexts.py` with immutable `OutcomeProbability`, `HandStatistics`, and `PlayerDecisionContext`.
- Create: `src/mus_computer/probabilities/estimates.py` with table-backed hand and discard statistics plus Punto enumeration.
- Create: `src/mus_computer/bots/strategies/actions.py` with `DecisionKind`, `MusAction`, `DiscardAction`, `WagerAction`, `ActionDistribution`, and `legal_wager_actions(wager_state)`.
- Test: `tests/game/test_decision_contexts.py`, `tests/probabilities/test_hand_statistics.py`, `tests/bots/test_action_distribution.py`.

**Interfaces:**
- `GlobalGameContext(team_scores: Mapping[str, int], mus_exchanges: int, phase_name: str | None, wager: WagerState | None, public_actions: tuple[str, ...], discard_counts: Mapping[str, int], seat_order: tuple[tuple[str, str], ...], mano_seat: int, eligible_seats: tuple[int, ...])` copies and freezes its mappings and stores public action records only. It replaces the old wager-only `GameContext` rather than coexisting with another global snapshot type.
- `WagerState(current_total: int, previous_accepted_total: int, offering_team: str | None, ordago_offered: bool)` carries the public current wager state.
- `PlayerDecisionContext(player_name: str, team_name: str, seat: int, cards: tuple[Card, ...], phase_name: PhaseName | None, eligible: bool, intrinsic_points_by_phase: Mapping[PhaseName, int], statistics: HandStatistics, discard_options: tuple[DiscardOption, ...])` contains only the acting player's cards, derived statistics, and discard alternatives. Each `DiscardOption` pairs a `DiscardAction(indices)` with its resulting `HandStatistics`; the tuple always contains at least one option. When alternatives are not estimated, that option keeps all cards.
- `HandStatistics(outcomes_by_phase: Mapping[PhaseName, OutcomeProbability], expected_points_by_phase: Mapping[PhaseName, float])` maps Grande, Chica, Pares, Juego, and Punto to `OutcomeProbability(p_win, p_tie, p_loss)` and estimated points.
- `ActionDistribution[ActionT](probabilities: Mapping[ActionT, float])` copies and freezes its mapping, rejects missing mass, values below zero, non-finite values, or totals outside `1e-9`; `sample(rng: random.Random, legal_actions: Collection[ActionT]) -> ActionT` rejects positive probability on an illegal action and never returns an illegal action. Each distribution contains one hashable action type: Mus and wager enums or `DiscardAction`.
- `WagerAction`: `ORDAGO`, `RAISE_5`, `RAISE_4`, `RAISE_3`, `RAISE_2`, `MATCH_OR_PASS`, `FOLD`; `MusAction`: `MUS`, `CORTA`.
- `DecisionKind`: `MUS`, `DISCARD`, or `WAGER`; each BotPlayer strategy method consumes `(GlobalGameContext, PlayerDecisionContext, BotPersonality)` and returns an `ActionDistribution` of `MusAction`, `DiscardAction`, or `WagerAction` respectively. `choose_discards` converts the selected `DiscardAction` to the original card-index tuple required by the game.
- `legal_wager_actions(wager_state)` includes `FOLD` only during a response; before an offer, `MATCH_OR_PASS` means `paso`, and during a response it means `quiero`.

- [ ] **Step 1: Add failing immutability and distribution tests**

Test that mutating the source dictionary after context construction does not change the context; item assignment into a context mapping raises `TypeError`; valid distributions sample only a supplied legal action; positive mass on an illegal action, negative, NaN, infinity, and sum-0.9 distributions raise `ValueError`.

- [ ] **Step 2: Run focused tests to verify missing types and validation**

Run: `python -m pytest tests/game/test_decision_contexts.py tests/bots/test_action_distribution.py -q`
Expected: FAIL because the context/action modules and validators do not yet exist.

- [ ] **Step 3: Implement immutable shared/private types and action distribution validation**

Copy mapping inputs before wrapping them read-only. Keep public history as action/event records that exclude the `Hands | ...` display messages. Derive legal wager categories from whether `WagerState` has an active offer; fold is excluded before an offer.

- [ ] **Step 4: Add failing statistics and Punto comparison tests**

Use controlled hands with a known Punto win, loss, and tie; compare `p_win`, `p_loss`, and `p_tie` to exact weighted enumeration over the 40-card rank multiplicities after blocking the acting player's four cards. Assert mano changes only tie-as-win expected points, not `p_tie`. Add a discard-option test keyed by original card indices.

- [ ] **Step 5: Implement hand statistics and Punto estimation**

Read Grande/Chica/Pares/Juego values from the bundled table. Compute Punto by enumerating unique opponent rank multisets with physical multiplicity and calling `Punto.play`; cache by canonical acting hand. Estimate points using `p_win` plus `p_tie` only when the acting seat has mano priority, multiplied by that phase's base point plus the acting hand's intrinsic phase points. Mark these as estimates and never include opponent cards.

- [ ] **Step 6: Run focused tests and commit Task 2**

Run: `python -m pytest tests/game/test_decision_contexts.py tests/probabilities/test_hand_statistics.py tests/bots/test_action_distribution.py -q`
Expected: PASS, including the hidden-information and Punto cases. Commit context, probability-estimate, action-contract, and test files only.

---

## Parallel Wave After Task 2

Tasks 3, 4, and 5 have distinct file ownership and may run concurrently. All consume the exact interfaces defined in Task 2; none may rename or edit another task's files. Each worker must preserve other agents' shared-worktree changes.

## Task 3: Implement Injectable Bot Strategy Portfolios

**Files:**
- Create: `src/mus_computer/bots/strategies/portfolio.py`, `mus.py`, `discard.py`, and `wagers.py`.
- Modify: `src/mus_computer/bots/bot_player.py` and `src/mus_computer/bots/__init__.py`.
- Test: `tests/bots/test_contextual_strategies.py`.

**Interfaces:**
- `BotPersonality` is a type alias of `BotGenome`; preserve every existing field and JSON shape.
- `StrategyPortfolio(mus, discard, wagers_by_phase)` stores one Mus strategy, one discard strategy, and distinct wager strategies for Grande, Chica, Pares, Juego, and Punto.
- Every strategy receives `(GlobalGameContext, PlayerDecisionContext, BotPersonality)` and returns an `ActionDistribution` over legal actions.
- `BotPlayer(name, team, genome: BotGenome, strategies: StrategyPortfolio | None = None, rng: random.Random | None = None)` owns the portfolio and implements `take_decision(kind: DecisionKind, global_context, player_context)`; it returns `MusAction`, `DiscardAction`, or `WagerAction`. The game-facing `choose_discards` method returns the selected action's card-index tuple.
- Remove `BotPlayer.set_round_state` and its cached `_state`; decision data is supplied afresh to each strategy call.

- [ ] **Step 1: Write deterministic injected-strategy tests**

Add a fixed strategy returning a one-hot `ActionDistribution`. Assert one-hot `MUS` votes mus, one-hot `CORTA` stops mus, a one-hot discard tuple returns those indices, and one-hot `ORDAGO`, `RAISE_2`–`RAISE_5`, `MATCH_OR_PASS`, and `FOLD` each return their matching typed intent in a legal state. Assert the portfolio has a different wager strategy instance for every phase and changes to one phase's statistics reach only that phase's strategy.

- [ ] **Step 2: Run focused tests to verify the strategy API is missing**

Run: `python -m pytest tests/bots/test_contextual_strategies.py -q`
Expected: FAIL because `StrategyPortfolio` and typed strategy interfaces do not exist.

- [ ] **Step 3: Implement strategy protocols, default portfolio, and dispatch**

Keep strategy classes stateless between calls. The default Mus strategy uses current/post-discard estimates and `mus_eagerness`; the discard strategy ranks legal discards by expected points with `discard_aggressiveness` as the tie preference; the phase-specific wager strategy uses only its phase outcome, score/mus/position context, and genome thresholds. It assigns normalized mass across legal fold, match/pass, raises 2–5, and ordago; if all heuristic weights are zero it assigns mass 1 to match/pass. Injected portfolios bypass all defaults.

- [ ] **Step 4: Test legal actions and personality/context sensitivity**

Test that every default distribution validates for opening and response states, that fold is absent before an offer, and that changing scores, Mus exchanges, position, consumed phase probabilities, `mus_eagerness`, `discard_aggressiveness`, or wager thresholds changes the relevant decision distribution. Do not assert tournament win rates.

- [ ] **Step 5: Run focused bot tests and commit Task 3**

Run: `python -m pytest tests/bots/ -q`
Expected: PASS for deterministic injection, strategy selection, old genome serialization, and bot compatibility. Commit bot strategy files and bot tests only.

---

## Task 4: Integrate Contexts, Wagers, and Ordered Scoring

**Files:**
- Modify: `src/mus_computer/game/game.py`, `player_base.py`, `player.py`, and `wager_session.py`; `src/mus_computer/bots/random_bot_player.py` for the expanded decision method signatures.
- Test: `tests/game/test_wager_session.py`, `tests/game/test_game_scoring.py`, and `tests/game/test_decision_context_flow.py`.

**Interfaces:**
- `PlayerBase.vote_mus(global_context, player_context)`, `choose_discards(global_context, player_context)`, and `wager_action(global_context, player_context)` receive fresh snapshots; `HumanPlayer` and `RandomBotPlayer` may ignore the contexts. Both return the typed actions defined in Task 2; RandomBotPlayer samples uniformly from the supplied legal actions.
- `WagerResult(outcome, offering_team, accepted_stake)` uses `WagerOutcome.SHOWDOWN`, `DECLINED`, or `ORDAGO_ACCEPTED`; `accepted_stake` is `None` for accepted ordago, otherwise the numeric stake. `WagerSession.run() -> WagerResult` replaces the old tuple return. `WagerSession` receives `seat_numbers: tuple[int, ...]` aligned with its eligible players so private contexts keep absolute table seats.
- `Game` appends public action records before requesting the next decision, but never puts display-only hand strings/cards in the shared context.

- [ ] **Step 1: Add failing wager-session unit tests with scripted player responses**

Use scripted strategies, not mocked player internals. Add parameterized opening tests for `RAISE_2` through `RAISE_5` setting totals 2 through 5; verify `RAISE_2` accepted by `MATCH_OR_PASS` yields 2 total points; counterraise tests proving each raise adds its number; a refused opening `RAISE_2` awards only the one point already in play; one acceptance stops before a second teammate is queried; and fold tests where one `no quiero` asks the next eligible defender but all eligible refusals fold for the last accepted stake only. Include the concrete sequence opening raise 2, counterraise 3, Bot 1 and Bot 3 refuse, and Team B receives 2 points; assert Bot 4 is not asked after Bot 2 already counterraised for Team B. Assert ineligible players are never asked.

- [ ] **Step 2: Add failing ordago tests**

Test accepted ordago stops responses and returns `ORDAGO_ACCEPTED`; refused ordago returns `DECLINED` with only the previously accepted stake; refusing ordago does not set a match winner.

- [ ] **Step 3: Run wager tests to verify current integer protocol fails the new contract**

Run: `python -m pytest tests/game/test_wager_session.py -q`
Expected: FAIL because `WagerSession` currently accepts integer actions and returns a tuple.

- [ ] **Step 4: Implement typed wager resolution and context handoff**

Adapt each typed intent at the `WagerSession` boundary. Opening `RAISE_n` sets `current_total = n`; a counterraise sets `current_total += n`; `MATCH_OR_PASS` returns a showdown on an offer and records `paso` before an offer; `FOLD` records `no quiero` and only folds after every eligible defender refuses. One eligible `quiero` ends that exchange immediately. An accepted ordago stops the response loop and leaves card resolution to `Game`. `RandomBotPlayer` chooses uniformly from `legal_wager_actions`; `HumanPlayer` translates its existing input into the same typed actions.

- [ ] **Step 5: Add failing phase scoring tests for folds and 40-point ordering**

Test folded Pares winner intrinsic values for pair=1, two pairs=3, and triples=2; folded Juego winner values for 31=3 and other Juego=2; only eligible winning-team hands contribute. Add a case where a fold pays accepted stake immediately and the intrinsic points are still settled if play continues. Add cases where an immediate fold award reaches 40 and where ordered deferred Grande/Chica/Pares/Juego awards make one team cross 40 before the other. Test that accepted ordago ends `Game.play()` for the card winner even below 40, while refused ordago awards only the prior stake and allows the match to continue.

- [ ] **Step 6: Implement context construction, ordago match result, and ordered score settlement**

Build global/private contexts for every Mus vote, discard, and wager response. Reuse one equal global snapshot for players at the same decision point; rebuild it after public state changes. Preserve the terminal callback feed. On accepted ordago, resolve eligible hands and stop the match for the phase winner regardless of numeric score. On a decline, award the previous accepted stake immediately. For folded Pares/Juego, queue intrinsic values for eligible hands of the wager-winning team. At the end of the hand, settle phase award records in order and stop at the first award that reaches 40.

- [ ] **Step 7: Run game/wager and regression tests, then commit Task 4**

Run: `python -m pytest tests/game/ -q`
Expected: PASS for wager response order, ordago outcomes, folds, eligibility, phase-order scoring, first-to-40, and existing game rules. Commit only engine/player changes and game tests.

---

## Task 5: Document the Package and Update the Milestone Roadmap

**Files:**
- Create: root `README.md`.
- Modify: `docs/mus-computer/README.md` and `docs/mus-computer/TODO.md` to keep commands/table references current, remove stale local Git-status claims, and show the four-bot runner as complete with contextual strategies as the active milestone.

**Interfaces:**
- `README.md` documents the installable package entry points and links to detailed design/table docs.
- `docs/mus-computer/TODO.md` marks the four-random-bot runner complete and the contextual-strategy/package work active.

- [ ] **Step 1: Write the root README**

Document Python 3.10+, editable installation (`python -m pip install -e ".[dev]"`), `python -m mus_computer`, `python api.py`, `python -m pytest`, source tree boundaries, 2v2/A-B-A-B and Mus/phase/wager rules, random baseline versus injectable strategic bot, data/table assumptions, and links to `docs/mus-computer/README.md`, `docs/mus-computer/TODO.md`, `docs/mus-computer/lookup-tables/README.md`, and the strategy spec. Label current capabilities and strategy limitations accurately.

- [ ] **Step 2: Update the technical reference and roadmap**

Replace root-module path references with package/script paths and remove obsolete branch/ahead-of-remote statements. Update the roadmap to mark the playable four-random-bot game complete and this strategy/package milestone active.

- [ ] **Step 3: Verify documentation commands and links**

Run `python -m mus_computer --help`, `python -m pytest tests/test_cli.py -q`, and `git diff --check`. Confirm each README link resolves to a file and generated table/report changes remain outside the commit. The parent runs the full suite after Tasks 3, 4, and 5 have all completed.

- [ ] **Step 4: Commit only Task 5 documentation**

Commit the root README and updated technical reference/roadmap. Do not push or merge without a new explicit request.

---

## Dependency and Parallelization Map

```text
Task 1: package migration
   |
Task 2: shared contexts/action contracts
   |
   +----------------------+----------------------+
   |                      |                      |
Task 3: bot strategies  Task 4: game/wagers   Task 5: CLI/docs
   +----------------------+----------------------+
```

Task 2 completes before the parallel wave because it defines the types all three tasks consume. During the wave, Task 3 owns only `bots/`, Task 4 owns only `game/` plus `bots/random_bot_player.py`, and Task 5 owns only CLI/docs files. The parent coordinates their interfaces and verifies the combined suite after they finish.

## Final Integration Verification

After Tasks 3, 4, and 5 commit and the working tree changes are integrated, the parent runs `python -m pytest tests/ -v`, `python -m mus_computer --help`, and one complete `python -m mus_computer` match. The match must end with the 40-point winner message; review the terminal log for hands after deal/exchange, public actions, phase results, and score events. Run `git diff --check`, compare the package pickle's blob hash with `HEAD:probability_tables.pkl`, and confirm no generated/local outputs or `.claude/settings.local.json` entered any task commit. Do not push or merge.
