# Repository instructions

## Branches and generated artifacts

Create a dedicated branch for each task before changing tracked files. Keep unrelated working-tree changes out of the task. Never commit generated training runs or iteration snapshots. Preserve snapshots needed to resume a run or regenerate its analysis; delete only disposable snapshots after checking those uses.

## Code Review Rules

Use standalone, offline HTML as the default human-facing format for training/evaluation results and PR evidence summaries. Retain canonical JSON alongside it; keep Markdown for documentation and plans. Experiment runs emit HTML automatically. Regenerate presentation from saved JSON with `python -m mus_computer.training.experiments report --input <report.json>` instead of rerunning training just to change report format.

For substantive changes to bot-training behavior, use the opt-in experiment workflow in `docs/training/EXPERIMENTS.md`: run a budgeted real training/comparison cycle, inspect its results, perform at least one recorded follow-up with an evidence-based rationale, and separately confirm the selected frozen candidate. Report both attempts, configured budgets and failed selection gates. Keep raw runs/models under ignored `training_runs/` and retain artifacts needed for continuation or reanalysis. This model-experiment iteration does not reset the single code-review repair allowance below. Slow training experiments remain separate from the default test suite.

Read relevant entries in root `log.md` before implementing or reviewing a change. Look for previous fixes and user decisions that touch the same code or behavior. Cite a matching entry when a finding or design decision relies on it.

For substantive code changes made by Codex, use `optimise-review-process` before handoff when available. Otherwise follow this sequence directly. Require the configured lint, format, static type and secret checks to pass before reviewing or committing. Review the scoped diff, apply one batch of verified and in-scope Important fixes, then rerun the checks and review the repair delta read-only once they pass. Run the required checks again on the staged changes before committing. Report failed or unavailable gates as blockers. Stop after that. If the first review needs no changes, report its result and stop. For review-only requests and GitHub PR review jobs, inspect and report only.

Focus on concrete regressions and material risks. Mark findings Important, Nit, or Pre-existing, in that order for handoff. Include only actionable findings with a location, impact and next step. Within Important, put merge blockers first. Separate significant assumptions or design choices made by Codex from findings. Leave remaining findings for human triage and never use bot findings to initiate another fix pass automatically.

Record durable fixes and decisions in root `log.md` using `- YYYY-MM-DD [user|review|incident] **Problem heading** — Short solution or rule. (optional PR/issue)`. Use `[user]` when user feedback drove the change. Add one line per lesson after implementation, deduplicate, and omit private feedback, secrets, and routine edits.

## Review tools and commands

Use the project virtual environment (Python 3.10+). Hooks use `scripts/review_checks.py` to locate `.venv` explicitly, so editor commits do not require shell activation. Activate it for the manual module commands below:

```powershell
. .venv/Scripts/Activate.ps1
python -m pip install -e ".[dev,review]"
python -m pre_commit install
python -m pre_commit validate-config
python -m ruff check src scripts tests api.py setup.py
python -m ruff format --check src scripts tests api.py setup.py
python -m mypy
python -m pytest tests/ -m "not slow and not performance"
python -m pre_commit run --all-files
```

On POSIX use `source .venv/bin/activate`. Install Gitleaks v8.30.1 from its official GitHub release into `.venv/Scripts` on Windows or `.venv/bin` on POSIX, or put it on PATH; verify the release checksum. The hook configuration uses local tools, performs checks only, and never formats or fixes files. `pre_commit install` preserves an existing hook via its migration behavior; do not overwrite another hook runner or `core.hooksPath`.

Use `make format` to apply formatting and `make format-check` to check it. Both select the project virtual environment automatically. On Windows install GNU Make with `winget install --id ezwinports.make --exact --source winget --scope user`, then reopen the terminal to load the updated PATH. Override the interpreter with `make format PYTHON=python3` when needed.

Before review, scan the proposed tracked diff with `git diff --binary HEAD | gitleaks stdin --redact --no-banner`. Also scan the contents of every intended new file with `gitleaks stdin --redact --no-banner` (PowerShell: `Get-Content -Raw -LiteralPath <file> | gitleaks stdin --redact --no-banner`). Include new files in the staged diff before committing, then run `python -m pre_commit run` and the relevant tests on that exact staged revision. Gitleaks checks `git --staged` at commit time; `--all-files` does not make its staged scanner inspect unstaged files. Report secret findings by rule and location only.

There is no approved baseline exemption for existing lint, formatting, or type errors. Report existing failures separately and leave commits and review requests blocked until the required gates pass. Do not perform a repository-wide cleanup without an explicit task for it. Use the full pytest suite when changes affect exhaustive probability calculations; performance tests are opt-in.

GitHub repository: `reyesjorgeruben-beep/mus-computer`. Automatic GitHub review must be enabled and verified in Codex settings under Code review → Repositories → mus-computer → Review code. Prefer the PR-opening or ready-for-review trigger. Do not change personal preferences without authorization. CI and branch protection are managed separately.
