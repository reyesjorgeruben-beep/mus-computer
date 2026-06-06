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


def discard_options(cards) -> dict:
    """Returns {canonical_kept: {phase_name: expected_p_win}} for all discard choices."""
    tables = load_tables()
    key = canonical(cards)
    entry = tables.get(key, {})
    return entry.get("discard_options", {})


def best_discard(cards, phase_weights: dict) -> tuple:
    """
    Returns the canonical kept-hand that maximises weighted expected p_win.
    phase_weights: {phase_name: weight} — need not be normalised.
    """
    options = discard_options(cards)
    if not options:
        return canonical(cards)
    total_w = sum(phase_weights.values()) or 1.0
    best_key = max(
        options,
        key=lambda kept: sum(
            phase_weights.get(p, 0) / total_w * options[kept].get(p, 0.0)
            for p in phase_weights
        ),
    )
    return best_key


def post_mus_win_prob(cards, phase_name: str, phase_weights: dict) -> float:
    """Expected p_win for phase_name after discarding optimally given phase_weights."""
    options = discard_options(cards)
    if not options:
        return win_prob(cards, phase_name)
    kept = best_discard(cards, phase_weights)
    return options[kept].get(phase_name, 0.0)


def hand_gainance(cards, phase_weights: dict) -> float:
    """
    Weighted expected improvement in p_win from the optimal discard.
    Returns (post_mus_weighted_win - current_weighted_win), clipped to >= 0.
    """
    options = discard_options(cards)
    if not options:
        return 0.0
    key = canonical(cards)
    total_w = sum(phase_weights.values()) or 1.0

    def weighted(option_dict):
        return sum(
            phase_weights.get(p, 0) / total_w * option_dict.get(p, 0.0)
            for p in phase_weights
        )

    current = weighted({p: win_prob(cards, p) for p in phase_weights})
    best = max(weighted(opt) for opt in options.values())
    return max(0.0, best - current)
