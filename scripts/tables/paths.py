"""Default output locations for offline table builders."""

from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
TABLE_PATH = REPOSITORY_ROOT / "probability_tables.pkl"
