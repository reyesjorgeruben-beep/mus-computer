import pickle
from functools import lru_cache
from importlib import resources
from pathlib import Path

from mus_computer.cards.card import Card


class _TableUnpickler(pickle.Unpickler):
    """Map the committed table's former Card module to its package location."""

    def find_class(self, module: str, name: str):
        if module == "card" and name == "Card":
            return Card
        return super().find_class(module, name)


def canonical(cards) -> tuple:
    return tuple(sorted(cards, reverse=True))


@lru_cache(maxsize=1)
def _load_packaged_tables() -> dict:
    resource = resources.files("mus_computer.probabilities").joinpath(
        "data", "probability_tables.pkl"
    )
    with resource.open("rb") as file:
        return _TableUnpickler(file).load()


@lru_cache(maxsize=16)
def _load_tables_at_path(path: str) -> dict:
    with Path(path).open("rb") as file:
        return _TableUnpickler(file).load()


def load_tables(path: str | Path | None = None) -> dict:
    if path is None:
        return _load_packaged_tables()
    return _load_tables_at_path(str(Path(path).resolve()))


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
