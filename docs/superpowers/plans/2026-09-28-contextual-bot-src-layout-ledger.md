# Execution Ledger: Contextual Bots and `src` Layout

Plan: `2026-09-28-contextual-bot-src-layout.md`

- Starting commit: `3e2ab54` (`docs: define contextual bot package structure`)
- Working branch: `feat/contextual-bot-strategies`
- Existing user-owned local outputs at start: modified `probability_tables.pkl`, `tables_report.html`, `tables_summary.csv`; untracked `.claude/` and `tables_discard_insights_corrected.csv`.
- Preserve those files and do not stage them. Never inspect `.env` or `.claude/settings.local.json`.
- Ruling: Continue in the existing feature branch because it is already separate from `master` and contains the approved spec; retain the current checkout so the generated local files remain visible for protection. Cost if wrong: weaker filesystem isolation than a linked worktree, mitigated by scoped task ownership and exact staging.
- Ruling: Place the migrated legacy context at `src/mus_computer/game/context.py`, matching the approved package tree and Task 2 interface. Cost if wrong: a path rename and import adjustment, with no data or behavior loss.
- Ruling: Declare NumPy only in the optional table-tooling and development extras because existing builder tests import it; keep runtime dependencies empty. Cost if wrong: a small additional development install dependency, with no impact on normal package users.
- Ruling: Keep standard modern `pyproject.toml` packaging and accept the local pip 21.2/PyPI certificate failure as an environment limitation; the legacy editable fallback was verified, and clean installs use modern pip/setuptools. Cost if wrong: users on similarly old environments need to update packaging tools before the documented editable install works.
- Ruling: Retain the small `setup.py` legacy install fallback despite duplicated packaging metadata, because it provides a verified path for this workspace's old pip; keep both metadata blocks synchronized. Cost if wrong: metadata drift until the old-tooling fallback is removed.

## Task Records

- Ruling: Pass each player's absolute seat to private-context construction instead of rejecting duplicate player names. This preserves valid rosters and keeps eligibility tied to seat identity. Cost if wrong: the context-construction method now requires callers to supply seat identity; all Game and WagerSession call sites and tests were updated.
- Ruling: Expose the implicit one-point accepted stake in opening WagerState snapshots, including Pares/Juego where their nominal phase base is zero. This keeps public context and the human prompt aligned with the amount awarded when an opening wager is declined. Cost if wrong: opening context consumers see `previous_accepted_total=1` before any player has wagered; this matches the engine's existing fallback stake.

- Task 5: complete in `84450fb`; root README and technical docs describe the package and initial active milestone. Follow-up roadmap completion recorded in `dbe50fe`.
- Task 1: complete in `d6e75e7`; task review approved. Full non-slow suite: 275 passed, 1 slow test deselected. Reviewer noted only the parked metadata duplication above.
- Task 2: committed as `450df3c`, with ordago legality fix `a5bda23`; review approved. Focused tests: 18 passed, then 13 passed for the fix. The full suite did not finish after several minutes in the existing exhaustive `test_ep_mano` calculation, with no failures reported. Task 4 must replace temporary `WagerPrompt` snapshot placeholders with the Game's complete seat order and current Mus count.
- Task 2 review found pending-ordago legality too broad. Ruling: while an ordago is outstanding, only accept (`MATCH_OR_PASS`) and refuse (`FOLD`) are legal. Cost if wrong: the strategy contract would reject a counterraise that the rules allow; the approved rule defines ordago as accept/refuse only. Fixed in `a5bda23`.
- Packaging follow-up committed as `61be8b5`: setuptools build requirement is now 64+ for editable PEP 660 support, matching the README's pip/setuptools prerequisites.
- Task 3: complete in `c15eeb9`; task review approved after changing discard aggressiveness to a tie-breaker only. Bot suite: 53 passed; scoped re-review: 19 contextual strategy tests passed.
- Task 4: complete in `f203a53`; task review and scoped re-review approved after fixing duplicate-name seat resolution, human stake prompts, the Pequeña event label, and wager documentation. Game suite: 161 passed; scoped re-review: 103 passed.
- Integration fix: the CLI regression test exposed an import cycle from `actions.py` through eager `game` package exports. A type-only `WagerState` import removed the runtime cycle; `tests/test_cli.py` and combined game/bot tests passed.
- Final non-slow suite: 343 passed, 1 slow test deselected. `python -m mus_computer --help` passed; a complete random-bot match logged all four hands and public actions and ended with an ordago winner. The excluded exhaustive probability test was not run.
- Generated/local outputs (`tables_report.html`, `tables_summary.csv`, `tables_discard_insights_corrected.csv`, `.claude/`, and the root probability pickle) remain outside task commits.
- Ruling: Build discard-option estimates only for players that consume them; random bots still receive their private hand context but can use empty discard alternatives. Cost if wrong: a strategy that forgets to declare this capability would miss post-draw estimates; tests will cover the strategic-player path while the default random runner avoids unnecessary enumeration.
- Ruling: A fold awards the previously accepted stake immediately and does not separately queue that phase's ordinary base point; only eligible winning-team Pares/Juego intrinsic points are deferred. Cost if wrong: a mistaken interpretation would shift a folded phase by one duplicate point; this follows the user's “points already in play” rule.
