"""Commit checks must use project tools even outside an activated shell."""

from subprocess import CompletedProcess

import pytest

from scripts import review_checks


@pytest.mark.parametrize(
    ("check", "arguments"),
    [
        (
            "lint",
            ["-m", "ruff", "check", "src", "scripts", "tests", "api.py", "setup.py"],
        ),
        (
            "format",
            [
                "-m",
                "ruff",
                "format",
                "--check",
                "src",
                "scripts",
                "tests",
                "api.py",
                "setup.py",
            ],
        ),
        ("types", ["-m", "mypy"]),
    ],
)
def test_python_checks_use_project_interpreter_with_empty_path(
    tmp_path, monkeypatch, check, arguments
):
    python = tmp_path / ".venv" / "Scripts" / "python.exe"
    python.parent.mkdir(parents=True)
    python.touch()
    monkeypatch.setenv("PATH", "")
    calls = []

    def run(command, *, cwd, check):
        calls.append((command, cwd, check))
        return CompletedProcess(command, 7)

    monkeypatch.setattr(review_checks.subprocess, "run", run)
    assert review_checks.run_check(check, tmp_path) == 7
    assert calls == [([str(python), *arguments], tmp_path, False)]


def test_secrets_use_project_gitleaks_with_empty_path(tmp_path, monkeypatch):
    scanner = tmp_path / ".venv" / "Scripts" / "gitleaks.exe"
    scanner.parent.mkdir(parents=True)
    scanner.touch()
    monkeypatch.setenv("PATH", "")
    calls = []

    def run(command, *, cwd, check):
        calls.append(command)
        return CompletedProcess(command, 0)

    monkeypatch.setattr(review_checks.subprocess, "run", run)
    assert review_checks.run_check("secrets", tmp_path) == 0
    assert calls == [[str(scanner), "git", "--staged", "--redact", "--no-banner"]]


def test_missing_environment_reports_install_command(tmp_path, capsys):
    assert review_checks.run_check("lint", tmp_path) == 2
    assert ".[dev,review]" in capsys.readouterr().err


def test_posix_project_environment_is_supported(tmp_path, monkeypatch):
    python = tmp_path / ".venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.touch()
    calls = []

    def run(command, *, cwd, check):
        calls.append(command)
        return CompletedProcess(command, 0)

    monkeypatch.setattr(review_checks.subprocess, "run", run)
    assert review_checks.run_check("types", tmp_path) == 0
    assert calls == [[str(python), "-m", "mypy"]]
