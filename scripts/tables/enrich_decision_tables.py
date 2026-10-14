"""Add complete bot decision estimates to the bundled table artifact."""

import pickle
from pathlib import Path

from mus_computer.probabilities.tables import load_tables
from scripts.tables.build_tables import add_decision_estimates


ROOT = Path(__file__).resolve().parents[2]
PACKAGE_TABLE = ROOT / "src/mus_computer/probabilities/data/probability_tables.pkl"


def enrich() -> None:
    packaged = load_tables(PACKAGE_TABLE)
    add_decision_estimates(packaged)
    temporary = PACKAGE_TABLE.with_suffix(".tmp")
    with temporary.open("wb") as output:
        pickle.dump(packaged, output, protocol=pickle.HIGHEST_PROTOCOL)
    temporary.replace(PACKAGE_TABLE)


if __name__ == "__main__":
    enrich()
