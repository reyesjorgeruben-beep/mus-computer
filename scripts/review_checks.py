"""Run commit checks with project tools, independent of shell activation."""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON_PATHS = ["src", "scripts", "tests", "api.py", "setup.py"]
CHECKS = {
    "docs": ["-m", "mus_computer.documentation", "check", "--staged"],
    "lint": ["-m", "ruff", "check", *PYTHON_PATHS],
    "format": ["-m", "ruff", "format", "--check", *PYTHON_PATHS],
    "types": ["-m", "mypy"],
}


def run_check(check: str, root: Path = ROOT) -> int:
    if check == "secrets":
        candidates = [root / ".venv/Scripts/gitleaks.exe", root / ".venv/bin/gitleaks"]
        executable = next((str(path) for path in candidates if path.is_file()), None)
        executable = executable or shutil.which("gitleaks")
        if executable is None:
            print(
                "Install Gitleaks in .venv/Scripts, .venv/bin, or on PATH. See AGENTS.md.",
                file=sys.stderr,
            )
            return 2
        arguments = ["git", "--staged", "--redact", "--no-banner"]
    else:
        candidates = [root / ".venv/Scripts/python.exe", root / ".venv/bin/python"]
        executable = next((str(path) for path in candidates if path.is_file()), None)
        if executable is None:
            print(
                'Create .venv, then install tools: python -m pip install -e ".[dev,review]"',
                file=sys.stderr,
            )
            return 2
        arguments = CHECKS[check]
    try:
        return subprocess.run(
            [executable, *arguments], cwd=root, check=False
        ).returncode
    except OSError as error:
        print(f"Could not launch {check} check: {error}", file=sys.stderr)
        return 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("check", choices=[*CHECKS, "secrets"])
    return run_check(parser.parse_args().check)


if __name__ == "__main__":
    raise SystemExit(main())
