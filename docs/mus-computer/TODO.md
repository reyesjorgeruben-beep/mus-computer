# Mus Computer roadmap

## Completed milestone: playable four-bot game

The default terminal runner plays a complete 2v2 game with `RandomBotPlayer` in alternating A/B/A/B seats. Its event feed shows each hand after the initial deal and Mus exchanges, plus public actions, wagers, score changes, and the winner. The game repeats Mus votes and exchanges until someone cuts; the draw stock recycles discards when needed. See [how to run it](../../README.md).

- [x] Game lifecycle with injected seats, repeated Mus, phase ordering, discard recycling, and a match target of 40.
- [x] Random bot for Mus, discards, and wager actions.
- [x] Four-bot terminal runner and optional action callback.
- [x] Team wager handling: one eligible acceptance or every eligible defender declining, opening totals, and additive counterraises.

## Completed milestone: package and contextual bot strategies

**Goal:** Keep the game playable from an installable `src/mus_computer` package and make strategic bot decisions from shared public state, each bot's private hand statistics, and its personality parameters. The default four-bot terminal game remains the random baseline.

- [x] Organize runtime modules under `src/mus_computer/`, table programs under `scripts/tables/`, and tests by responsibility. Bundle the committed lookup table as package data and support an explicit lookup path override.
- [x] Define immutable `GlobalGameContext` with public scores, current-hand Mus exchanges, phase and wager state, and action history. Define `PlayerDecisionContext` with only the acting player's cards, phase eligibility, and `HandStatistics` for Grande, Chica, Pares, Juego, and Punto.
- [x] Add validated action distributions and injectable Mus, discard, and phase-specific wager strategies. Preserve existing `BotGenome` parameters as the initial personality representation. Use deterministic one-action tests to verify that injected strategies control decisions.
- [x] Integrate strategy decisions into the game and wager flow. Cover eligible responder order, additive counterraises, accepted/refused `ordago`, immediate folded-wager stakes, and deferred intrinsic Pares/Juego points after a fold.
- [x] Settle deferred awards in Grande, Chica, Pares, Juego/Punto order and stop at the first score event reaching 40. Add focused tests for wagers, folds, ordago, and phase-order winner selection.
- [x] Verify package commands and tests, then document the finished interfaces and behavior.

The [strategy design](../superpowers/specs/2026-09-27-contextual-bot-strategies-design.md) and [implementation plan](../superpowers/plans/2026-09-28-contextual-bot-src-layout.md) define this milestone. No training run or win-rate target is part of it.

Validation to date: `python -m pytest tests/ -q -m "not slow"` passed 343 tests with one slow test deselected. The result does not cover the excluded slow test.

## Table-model backlog

The analytical post-Mus tables remain a one-exchange approximation. Runtime gameplay repeats Mus until someone says `corta`.

- [x] Generate the 330 canonical-hand probability and expected-points artifacts.
- [x] Generate the one-exchange post-Mus distribution and post-Mus-aware discard summaries.
- [ ] Align replacement-card enumeration with the table's one-exchange model: draw from the marginal pool after removing the player's original four cards. Other copies of a discarded rank remain available; the exact initial copies do not return during that modeled exchange.
- [x] Document the wager convention: +0.5 applies only to Pares/Juego when both teams have a qualifying hand; Grande/Chica award their base point regardless of wagering.
- [ ] Revisit post-Mus weighting: compare compatibility-ratio weighting or source-conditioned transitions with the current physical-multiplicity weighting.
- [ ] Extend expected-points tables to fixed hands in seats 1, 2, and 3, preserving seat order and tie priority.
- [ ] Compare the unordered opponent-pair formula against independent ordered-seat enumeration.
- [ ] Rebuild tables and compare them with independent small-deck and rule-level references after model fixes.
- [x] Declare NumPy in the optional table-tooling and development extras, including for CI tests; keep the playable runtime dependency-free.

## Later work

- Add human-controlled seats and terminal prompts.
- Train or tune strategy parameters and evaluate them against suitable baselines.
