# Phase-specific CFR betting GLM implementation plan

**Goal:** Implement the user's phase-specific additive betting policy within sampled CFR.

**Architecture:** Opt-in `GLMCFRPolicy` extends the policy interface; tabular CFR remains the default. Declarative chronological features use only public wager events and existing private hand estimates. Current and average coefficient dictionaries are independent.

**Tech stack:** Python 3.10 standard library and existing pytest/review tools.

**Spec:** User request in this session: phase-specific GLMs with additive earlier-opponent-wager indicators, limited to betting training.

## Constraints and decisions

- Preserve sampler, game/scoring, regret importance weights and evaluation interfaces.
- Leave coefficient CFR and genetic training untouched. GLM mode uses fixed portfolio mus/discard decisions; only wager records train.
- Use phase/stage/action blocks; stages are opening, response to first offer, response to counter-raise, and ordago response. Each raise size and ordago is a distinct action.
- Hand strength is existing phase `1 - p_loss`; history adds one binary feature per permitted preceding lance.
- Retain per-information-state cumulative regrets and strategy sums to define projection targets. This first version generalizes inference, not training storage.
- One full-batch cross-entropy gradient step per iteration, normalized separately within each phase/stage. Current targets are regret matching weighted by positive regret mass (unit weight on fallback); average targets are accumulated average strategies weighted by their accumulated reach mass. Do not apply sampling weights twice.
- Save model metadata, sufficient statistics, config and trainer RNG state for exact continuation. Existing tabular policy snapshots remain readable.

## Tasks

- [x] Add failing tests for chronological/team-aware features, phase/stage/action separation, legal normalization, weighted projection, and fixed mus/discard behavior.
- [x] Implement `features.py`, `glm_policy.py`, and optional feature transport through the existing controller/record/policy interface.
- [x] Add failing tests for deterministic self-play and checkpoint continuation; integrate opt-in config/CLI and checkpoint restore.
- [x] Document equations, weights, event semantics, approximation and CLI usage; record the durable user decision in `log.md`.
- [x] Run relevant and non-slow/non-performance tests, configured lint/format/type/secret gates, then one scoped review and at most one Important repair batch.

## Review focus

- Own-team actions, unknown names and non-wager events must not activate opponent features.
- Future/current phase events must not enter earlier-lance features.
- Opening and response coefficients must remain separate with unchanged legal masks.
- Reach and counterfactual weights must be preserved exactly once.
- JSON round-trip must preserve independent current/average coefficients and subsequent seeded training.
