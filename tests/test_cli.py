import subprocess
import sys


def test_package_module_exposes_help():
    result = subprocess.run(
        [sys.executable, "-m", "mus_computer", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout.lower()
