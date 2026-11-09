# Review history

- 2026-11-09 [user] **Dedicated branches and disposable snapshots** — Put each task on a dedicated branch. Remove iteration snapshots only after checking whether resuming or rebuilding analysis needs them.
- 2026-11-09 [user] **Disposable CFR outputs** — The orphaned check, smoke, and stability iteration snapshots have no consumers in the current source or documentation. Remove those files and ignore `docs/training/cfr_runs/`; retain genetic-training snapshots used to rebuild charts.
- 2026-11-09 [user] **Editor commits must locate project tools** — System hooks inherited global Python and could not find Ruff, mypy, or Gitleaks. Route checks through a standard-library launcher that selects `.venv` tools explicitly; verify it without activation. Provide `make format` and `make format-check`, and document GNU Make installation on Windows.
- 2026-11-09 [review] **Keep typing helpers out of runtime dependencies** — A lint fix introduced `typing_extensions.Self` into dependency-free training imports. Use a bound standard-library TypeVar for Python 3.10 and verify the training import with site packages disabled.
