import pickle
from pathlib import Path

_TABLES = None
_TABLE_PATH = Path(__file__).parent / "probability_tables.pkl"


def canonical(cards) -> tuple:
    return tuple(sorted(cards, reverse=True))


def load_tables() -> dict:
    global _TABLES
    if _TABLES is None:
        if not _TABLE_PATH.exists():
            raise FileNotFoundError(
                f"Probability tables not found at {_TABLE_PATH}. Run: python build_tables.py"
            )
        with open(_TABLE_PATH, "rb") as f:
            _TABLES = pickle.load(f)
    return _TABLES


def lookup(cards, phase_name: str) -> dict:
    tables = load_tables()
    key = canonical(cards)
    if key not in tables:
        return {"p_win": 0.0, "p_tie": 0.0, "p_loss": 1.0}
    return tables[key][phase_name]


def win_prob(cards, phase_name: str, is_mano: bool = False) -> float:
    entry = lookup(cards, phase_name)
    base = entry["p_win"]
    if is_mano:
        base += entry["p_tie"]
    return base


def avg_opp_improvement_per_phase() -> dict:
    tables = load_tables()
    return tables["_avg_opp_phase_improvements"]
