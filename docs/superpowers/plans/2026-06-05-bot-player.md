# Bot Player Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a parametric `BotPlayer` driven by a 13-gene genome, backed by precomputed win-probability tables, playable in the existing `Game` class, and evolvable by a `GeneticTrainer`.

**Architecture:** Win probabilities for each phase are precomputed analytically against all 330 canonical hands and stored in a pickle. `BotPlayer` loads those tables at startup and uses them plus a `BotGenome` vector and discretised game state to make decisions in `vote_mus`, `choose_discards`, and `wager_action`. A `GeneticTrainer` runs bot-vs-bot tournaments and evolves populations of genomes using tournament selection, uniform crossover, and Gaussian mutation.

**Tech Stack:** Python 3.10, dataclasses, pickle, itertools, random, multiprocessing (trainer only). No new pip dependencies.

**Spec:** `docs/superpowers/specs/2026-06-05-bot-player-design.md`

---

## Open questions — review before starting

> These were unresolved at design time. Resolve each before implementing the affected task.

1. **Max raise amount** (affects Task 6, `wager_action`): What is the legal maximum raise per betting action in mus? The plan uses `current_bet` as the cap (doubling each raise). Confirm or correct this before Task 6.
2. **Tie resolution in Grande/Chica** (affects Task 1): `Phase.play` returns `0` on a tie. In the real game ties go to mano. The tables store `p_tie` separately so the bot can add it when it has mano position — but confirm this is how the existing `Game._resolve_phase` works (it currently uses `>= 0` as a win, implying player-0 / earlier-in-order wins ties).
3. **Punto phase probability** (affects Task 6): `Punto` has no table entry. The plan uses the `Grande` table as a proxy. Confirm this is acceptable or add a dedicated `Punto` entry to the tables.
4. **Opponent improvement precomputation scope** (affects Task 1): The spec says to precompute average opponent improvement per phase as a scalar. This plan does so using full enumeration in `build_tables.py`. If build time exceeds ~60 seconds, switch to sampling 500 hands per discard subset.

---

## File structure

| File | Action | Responsibility |
|---|---|---|
| `build_tables.py` | Create | One-off script: enumerate all canonical hands, compute win probs + avg opp improvement, save to `probability_tables.pkl` |
| `probability_tables.py` | Create | Load/cache pickle; `canonical()`, `lookup()`, `win_prob()`, `avg_opp_improvement_per_phase()` |
| `bot_genome.py` | Create | `BotGenome` dataclass (13 genes), `random_genome()`, `crossover()`, `mutate()` |
| `bot_game_state.py` | Create | `ScoreTier` enum, `BotGameState` dataclass, `get_score_tier()`, `compute_urgency()`, `compute_position_signal()` |
| `player_base.py` | Modify | Add no-op `set_round_state()` |
| `game_context.py` | Modify | Add `position`, `n_players`, `opponent_discard_counts` fields |
| `wager_session.py` | Modify | Accept `discard_counts` dict; pass `position`, `n_players`, `opponent_discard_counts` into `GameContext` |
| `game.py` | Modify | Track discard counts per player during mus; call `set_round_state()` before mus and before wagering; pass `discard_counts` to `WagerSession` |
| `bot_player.py` | Create | `BotPlayer(PlayerBase)`: `set_round_state()`, `vote_mus()`, `choose_discards()`, `wager_action()`, internal helpers |
| `genetic_trainer.py` | Create | `GeneticTrainer`: `evolve()`, `evaluate_population()`, `save_population()`, `load_population()` |
| `tests/test_probability_tables.py` | Create | Unit tests for table build + lookup |
| `tests/test_bot_genome.py` | Create | Unit tests for genome operations |
| `tests/test_bot_game_state.py` | Create | Unit tests for state utils |
| `tests/test_bot_player.py` | Create | Unit tests for BotPlayer decisions |
| `tests/test_genetic_trainer.py` | Create | Unit tests for GA operations |

---

## Task 1: Probability tables

**Files:**
- Create: `build_tables.py`
- Create: `probability_tables.py`
- Create: `tests/test_probability_tables.py`

The deck has 8 distinct card values (A×8, 4×4, 5×4, 6×4, 7×4, S×4, C×4, R×8 = 40 cards).
All canonical 4-card hands are multisets of size 4 from 8 values = **330 distinct hands**.
`canonical(cards)` = `tuple(sorted(cards, reverse=True))` (strongness descending, same as `Hand.__init__`).

For each canonical hand we store:
- `{"Grande": {"p_win": f, "p_tie": f}, "Chica": {...}, "Pares": {...}, "Juego": {...}}`

Plus a top-level key `"_avg_opp_phase_improvements"` = `{"Grande": f, "Chica": f, "Pares": f, "Juego": f}` representing the average per-phase improvement an opponent can achieve through optimal discards (used in `vote_mus`).

- [ ] **Step 1.1: Write failing tests**

```python
# tests/test_probability_tables.py
import pytest
from card import Card
from probability_tables import canonical, load_tables, win_prob, avg_opp_improvement_per_phase

def test_canonical_sorts_descending():
    cards = [Card.A, Card.R, Card._4]
    result = canonical(cards)
    assert result == (Card.R, Card._4, Card.A)

def test_canonical_handles_duplicates():
    cards = [Card.A, Card.A, Card.R, Card.R]
    result = canonical(cards)
    assert result == (Card.R, Card.R, Card.A, Card.A)

def test_tables_contain_330_hands():
    tables = load_tables()
    hand_keys = [k for k in tables if k != "_avg_opp_phase_improvements"]
    assert len(hand_keys) == 330

def test_tables_have_all_phases():
    tables = load_tables()
    key = next(k for k in tables if k != "_avg_opp_phase_improvements")
    assert set(tables[key].keys()) == {"Grande", "Chica", "Pares", "Juego"}

def test_tables_probabilities_sum_to_one():
    tables = load_tables()
    key = next(k for k in tables if k != "_avg_opp_phase_improvements")
    for phase in ["Grande", "Chica", "Pares", "Juego"]:
        entry = tables[key][phase]
        total = entry["p_win"] + entry["p_tie"] + entry["p_loss"]
        assert abs(total - 1.0) < 1e-6

def test_four_aces_low_grande_win_prob():
    # Four aces (weakest card) should rarely win Grande
    hand = (Card.A, Card.A, Card.A, Card.A)
    prob = win_prob(hand, "Grande", is_mano=False)
    assert prob < 0.05

def test_four_kings_high_grande_win_prob():
    # Four kings (strongest card) should almost always win Grande
    hand = (Card.R, Card.R, Card.R, Card.R)
    prob = win_prob(hand, "Grande", is_mano=False)
    assert prob > 0.95

def test_four_aces_high_chica_win_prob():
    # Four aces (weakest card) win Chica (lowest hand wins)
    hand = (Card.A, Card.A, Card.A, Card.A)
    prob = win_prob(hand, "Chica", is_mano=False)
    assert prob > 0.95

def test_mano_adds_tie_probability():
    hand = (Card.R, Card._7, Card._4, Card.A)
    prob_no_mano = win_prob(hand, "Grande", is_mano=False)
    prob_mano = win_prob(hand, "Grande", is_mano=True)
    assert prob_mano >= prob_no_mano

def test_hand_without_pares_has_zero_pares_win_prob():
    hand = (Card.R, Card._7, Card._4, Card.A)  # no pairs
    prob = win_prob(hand, "Pares", is_mano=False)
    assert prob == 0.0

def test_avg_opp_improvement_per_phase_returns_all_phases():
    improvements = avg_opp_improvement_per_phase()
    assert set(improvements.keys()) == {"Grande", "Chica", "Pares", "Juego"}

def test_avg_opp_improvement_non_negative():
    improvements = avg_opp_improvement_per_phase()
    for phase, val in improvements.items():
        assert val >= 0.0, f"{phase} improvement should be non-negative"
```

- [ ] **Step 1.2: Run tests to verify they fail**

```
cd C:\Users\jorge\Documents\Programming\Personal\claudia\mus_computer
.venv\Scripts\python -m pytest tests/test_probability_tables.py -v
```

Expected: `ModuleNotFoundError: No module named 'probability_tables'`

- [ ] **Step 1.3: Write `build_tables.py`**

```python
# build_tables.py
from itertools import combinations_with_replacement
from collections import Counter
from math import comb
import pickle
from pathlib import Path
from card import Card
from constants import cards_space
from hand import Hand
from phases import Grande, Chica, Pares, Juego

PHASES = [Grande, Chica, Pares, Juego]
TABLE_PATH = Path(__file__).parent / "probability_tables.pkl"


def canonical(cards):
    return tuple(sorted(cards, reverse=True))


def _multiplicity(hand: tuple) -> int:
    counts = Counter(hand)
    result = 1
    for card, n in counts.items():
        available = cards_space[card]
        if n > available:
            return 0
        result *= comb(available, n)
    return result


def all_canonical_hands() -> dict:
    """Returns {canonical_hand: multiplicity} for all 330 distinct hands."""
    cards_list = list(cards_space.keys())
    hands = {}
    for combo in combinations_with_replacement(cards_list, 4):
        c = canonical(combo)
        if c not in hands:
            mult = _multiplicity(c)
            if mult > 0:
                hands[c] = mult
    return hands


def _build_win_tables(all_hands: dict) -> dict:
    """
    For each canonical hand, compute p_win, p_tie, p_loss against a random
    opponent hand (weighted by multiplicity) for each phase.
    """
    tables = {}
    for my_hand in all_hands:
        entry = {}
        for phase_cls in PHASES:
            p_win_count = 0
            p_tie_count = 0
            total = 0
            for opp_hand, opp_mult in all_hands.items():
                result = phase_cls.play(Hand(list(my_hand)), Hand(list(opp_hand)))
                if result > 0:
                    p_win_count += opp_mult
                elif result == 0:
                    p_tie_count += opp_mult
                total += opp_mult
            entry[phase_cls.__name__] = {
                "p_win": p_win_count / total,
                "p_tie": p_tie_count / total,
                "p_loss": (total - p_win_count - p_tie_count) / total,
            }
        tables[my_hand] = entry
    return tables


def _expected_strength_after_best_discard(my_hand: tuple, tables: dict, all_hands: dict) -> dict:
    """
    For each phase, compute the expected p_win achievable by the hand after
    optimal discarding. Enumerates all discard subsets; for each, samples
    all possible replacement draws weighted by availability.

    Returns {phase_name: best_expected_p_win}.
    """
    from itertools import combinations

    remaining_counts = dict(cards_space)
    for card in my_hand:
        remaining_counts[card] -= 1

    def draw_weight_p_win(kept: tuple, n_draw: int) -> dict:
        """Average p_win over all weighted replacement draws of n_draw cards."""
        if n_draw == 0:
            new_hand = canonical(kept)
            return {p.__name__: tables[new_hand][p.__name__]["p_win"] for p in PHASES}

        # Enumerate all canonical replacement multisets of size n_draw from remaining
        available_cards = [c for c, cnt in remaining_counts.items() for _ in range(cnt)]
        # Use weighted enumeration instead of full draw
        draw_totals = {p.__name__: 0.0 for p in PHASES}
        weight_total = 0

        for draw_combo in combinations_with_replacement(list(remaining_counts.keys()), n_draw):
            draw_mult = _multiplicity_subset(draw_combo, remaining_counts)
            if draw_mult == 0:
                continue
            new_hand = canonical(list(kept) + list(draw_combo))
            for phase_cls in PHASES:
                draw_totals[phase_cls.__name__] += (
                    tables[new_hand][phase_cls.__name__]["p_win"] * draw_mult
                )
            weight_total += draw_mult

        if weight_total == 0:
            return {p.__name__: 0.0 for p in PHASES}
        return {k: v / weight_total for k, v in draw_totals.items()}

    best = {p.__name__: 0.0 for p in PHASES}
    indices = list(range(4))
    for r in range(5):
        for discard_idx in combinations(indices, r):
            kept = tuple(c for i, c in enumerate(my_hand) if i not in discard_idx)
            # Temporarily adjust remaining_counts for discards
            for c in my_hand:
                if my_hand.index(c) in discard_idx:
                    remaining_counts[c] += 1
            result = draw_weight_p_win(kept, r)
            for c in my_hand:
                if my_hand.index(c) in discard_idx:
                    remaining_counts[c] -= 1
            for phase_name, val in result.items():
                if val > best[phase_name]:
                    best[phase_name] = val
    return best


def _multiplicity_subset(cards_tuple: tuple, available: dict) -> int:
    counts = Counter(cards_tuple)
    result = 1
    for card, n in counts.items():
        avail = available.get(card, 0)
        if n > avail:
            return 0
        result *= comb(avail, n)
    return result


def _build_avg_opp_improvement(all_hands: dict, tables: dict) -> dict:
    """
    For each phase, compute the weighted average improvement an opponent achieves
    through optimal discarding.

    avg_improvement[phase] = weighted_avg(best_p_win_after_discard - current_p_win)
    """
    total_weight = sum(all_hands.values())
    phase_sums = {p.__name__: 0.0 for p in PHASES}

    for hand, mult in all_hands.items():
        current = {p.__name__: tables[hand][p.__name__]["p_win"] for p in PHASES}
        best = _expected_strength_after_best_discard(hand, tables, all_hands)
        for phase_cls in PHASES:
            name = phase_cls.__name__
            phase_sums[name] += (best[name] - current[name]) * mult

    return {name: val / total_weight for name, val in phase_sums.items()}


def build_and_save():
    print("Enumerating canonical hands...")
    all_hands = all_canonical_hands()
    print(f"  {len(all_hands)} canonical hands found")

    print("Computing win probability tables...")
    tables = _build_win_tables(all_hands)

    print("Computing average opponent improvement per phase...")
    avg_improvement = _build_avg_opp_improvement(all_hands, tables)
    tables["_avg_opp_phase_improvements"] = avg_improvement

    with open(TABLE_PATH, "wb") as f:
        pickle.dump(tables, f)
    print(f"Saved to {TABLE_PATH}")
    return tables


if __name__ == "__main__":
    build_and_save()
```

- [ ] **Step 1.4: Write `probability_tables.py`**

```python
# probability_tables.py
import pickle
from pathlib import Path
from typing import List

_TABLES = None
_TABLE_PATH = Path(__file__).parent / "probability_tables.pkl"


def canonical(cards) -> tuple:
    """Canonical form of a hand: tuple sorted by strongness descending."""
    return tuple(sorted(cards, reverse=True))


def load_tables() -> dict:
    global _TABLES
    if _TABLES is None:
        if not _TABLE_PATH.exists():
            raise FileNotFoundError(
                f"Probability tables not found at {_TABLE_PATH}. "
                "Run: python build_tables.py"
            )
        with open(_TABLE_PATH, "rb") as f:
            _TABLES = pickle.load(f)
    return _TABLES


def lookup(cards, phase_name: str) -> dict:
    """Returns {'p_win': f, 'p_tie': f, 'p_loss': f} for the hand and phase."""
    tables = load_tables()
    key = canonical(cards)
    if key not in tables:
        return {"p_win": 0.0, "p_tie": 0.0, "p_loss": 1.0}
    return tables[key][phase_name]


def win_prob(cards, phase_name: str, is_mano: bool = False) -> float:
    """
    Effective win probability.
    is_mano=True adds tie probability (mano wins ties).
    """
    entry = lookup(cards, phase_name)
    base = entry["p_win"]
    if is_mano:
        base += entry["p_tie"]
    return base


def avg_opp_improvement_per_phase() -> dict:
    """
    Returns {phase_name: float} — average improvement achievable by an
    opponent through optimal discarding, per phase. Precomputed at build time.
    """
    tables = load_tables()
    return tables["_avg_opp_phase_improvements"]
```

- [ ] **Step 1.5: Generate the tables**

```
cd C:\Users\jorge\Documents\Programming\Personal\claudia\mus_computer
.venv\Scripts\python build_tables.py
```

Expected output (approximate):
```
Enumerating canonical hands...
  330 canonical hands found
Computing win probability tables...
Computing average opponent improvement per phase...
Saved to ...probability_tables.pkl
```

- [ ] **Step 1.6: Add table fixture to `tests/conftest.py`**

Open `tests/conftest.py` and add at the top (after existing imports):

```python
import subprocess, sys
from pathlib import Path

@pytest.fixture(scope="session", autouse=True)
def ensure_probability_tables():
    table_path = Path(__file__).parent.parent / "probability_tables.pkl"
    if not table_path.exists():
        subprocess.run(
            [sys.executable, str(Path(__file__).parent.parent / "build_tables.py")],
            check=True,
        )
```

- [ ] **Step 1.7: Run tests to verify they pass**

```
.venv\Scripts\python -m pytest tests/test_probability_tables.py -v
```

Expected: all 11 tests PASS.

- [ ] **Step 1.8: Commit**

```bash
git add build_tables.py probability_tables.py tests/test_probability_tables.py tests/conftest.py
git commit -m "feat: add analytical win-probability table build script and loader"
```

---

## Task 2: BotGenome

**Files:**
- Create: `bot_genome.py`
- Create: `tests/test_bot_genome.py`

- [ ] **Step 2.1: Write failing tests**

```python
# tests/test_bot_genome.py
import pytest
from bot_genome import BotGenome, random_genome, crossover, mutate

def test_random_genome_genes_in_range():
    g = random_genome()
    for field in g.__dataclass_fields__:
        val = getattr(g, field)
        assert 0.0 <= val <= 1.0, f"{field}={val} out of [0,1]"

def test_random_genome_returns_botgenome():
    assert isinstance(random_genome(), BotGenome)

def test_crossover_genes_from_parents():
    import random
    random.seed(42)
    parent_a = BotGenome(*([0.0] * 13))
    parent_b = BotGenome(*([1.0] * 13))
    child = crossover(parent_a, parent_b)
    for field in child.__dataclass_fields__:
        val = getattr(child, field)
        assert val in (0.0, 1.0), f"{field}={val} should come from a parent"

def test_crossover_returns_botgenome():
    a = random_genome()
    b = random_genome()
    assert isinstance(crossover(a, b), BotGenome)

def test_mutate_stays_in_range():
    import random
    random.seed(0)
    g = BotGenome(*([0.5] * 13))
    for _ in range(100):
        m = mutate(g, mutation_rate=1.0, sigma=0.5)
        for field in m.__dataclass_fields__:
            val = getattr(m, field)
            assert 0.0 <= val <= 1.0, f"{field}={val} out of [0,1]"

def test_mutate_with_rate_zero_returns_unchanged():
    g = BotGenome(*([0.3] * 13))
    m = mutate(g, mutation_rate=0.0, sigma=0.5)
    assert g == m

def test_genome_has_13_fields():
    assert len(BotGenome.__dataclass_fields__) == 13
```

- [ ] **Step 2.2: Run to verify failure**

```
.venv\Scripts\python -m pytest tests/test_bot_genome.py -v
```

Expected: `ModuleNotFoundError: No module named 'bot_genome'`

- [ ] **Step 2.3: Write `bot_genome.py`**

```python
# bot_genome.py
import random
from dataclasses import dataclass, astuple, fields


@dataclass
class BotGenome:
    # Mus voting
    mus_eagerness: float            # [0,1] base willingness to vote yes to mus
    mus_risk_sensitivity: float     # [0,1] weight of improvement_delta on mus vote

    # Discard strategy
    w_grande: float                 # [0,1] weight for Grande phase
    w_chica: float                  # [0,1] weight for Chica phase
    w_pares: float                  # [0,1] weight for Pares phase
    w_juego: float                  # [0,1] weight for Juego phase
    discard_aggressiveness: float   # [0,1] bias toward swapping more cards

    # Wagering
    bluff_rate: float               # [0,1] prob of acting strong when hand is weak
    risk_factor: float              # [0,1] scales raise amount (0=min, 1=max)
    fold_threshold: float           # [0,1] win_prob below which bot folds
    raise_threshold: float          # [0,1] win_prob above which bot raises

    # Game state sensitivity
    score_urgency_sensitivity: float  # [0,1] how much score tier shifts decisions
    position_preference: float        # 0=mano-preferring, 1=last-preferring


def random_genome() -> BotGenome:
    return BotGenome(*[random.random() for _ in range(13)])


def crossover(a: BotGenome, b: BotGenome) -> BotGenome:
    """Uniform crossover: each gene taken independently from parent A or B."""
    genes = [
        getattr(a, f.name) if random.random() < 0.5 else getattr(b, f.name)
        for f in fields(a)
    ]
    return BotGenome(*genes)


def mutate(genome: BotGenome, mutation_rate: float = 0.15, sigma: float = 0.05) -> BotGenome:
    """Gaussian mutation clipped to [0, 1] applied independently per gene."""
    import random as _r
    genes = []
    for f in fields(genome):
        val = getattr(genome, f.name)
        if _r.random() < mutation_rate:
            val = max(0.0, min(1.0, val + _r.gauss(0, sigma)))
        genes.append(val)
    return BotGenome(*genes)
```

- [ ] **Step 2.4: Run tests to verify they pass**

```
.venv\Scripts\python -m pytest tests/test_bot_genome.py -v
```

Expected: all 7 tests PASS.

- [ ] **Step 2.5: Commit**

```bash
git add bot_genome.py tests/test_bot_genome.py
git commit -m "feat: add BotGenome dataclass with crossover and mutation"
```

---

## Task 3: BotGameState utilities

**Files:**
- Create: `bot_game_state.py`
- Create: `tests/test_bot_game_state.py`

- [ ] **Step 3.1: Write failing tests**

```python
# tests/test_bot_game_state.py
import pytest
from bot_game_state import ScoreTier, get_score_tier, compute_urgency, compute_position_signal

WIN_SCORE = 40

def test_score_tier_early():
    assert get_score_tier(0, WIN_SCORE) == ScoreTier.EARLY
    assert get_score_tier(9, WIN_SCORE) == ScoreTier.EARLY

def test_score_tier_mid():
    assert get_score_tier(10, WIN_SCORE) == ScoreTier.MID
    assert get_score_tier(23, WIN_SCORE) == ScoreTier.MID

def test_score_tier_late():
    assert get_score_tier(24, WIN_SCORE) == ScoreTier.LATE
    assert get_score_tier(33, WIN_SCORE) == ScoreTier.LATE

def test_score_tier_critical():
    assert get_score_tier(34, WIN_SCORE) == ScoreTier.CRITICAL
    assert get_score_tier(39, WIN_SCORE) == ScoreTier.CRITICAL

def test_urgency_zero_when_equal():
    assert compute_urgency(ScoreTier.MID, ScoreTier.MID) == 0.0

def test_urgency_positive_when_opponent_ahead():
    u = compute_urgency(ScoreTier.EARLY, ScoreTier.CRITICAL)
    assert u > 0.0

def test_urgency_negative_when_we_are_ahead():
    u = compute_urgency(ScoreTier.CRITICAL, ScoreTier.EARLY)
    assert u < 0.0

def test_urgency_range():
    u = compute_urgency(ScoreTier.EARLY, ScoreTier.CRITICAL)
    assert -1.0 <= u <= 1.0

def test_position_signal_mano_preferring_at_mano():
    # position_preference=0 (mano-preferring), position=0 (mano) → positive signal
    sig = compute_position_signal(0, 4, 0.0)
    assert sig > 0.0

def test_position_signal_mano_preferring_at_last():
    # position_preference=0 (mano-preferring), position=3 (last) → negative signal
    sig = compute_position_signal(3, 4, 0.0)
    assert sig < 0.0

def test_position_signal_last_preferring_at_last():
    # position_preference=1 (last-preferring), position=3 (last) → positive signal
    sig = compute_position_signal(3, 4, 1.0)
    assert sig > 0.0

def test_position_signal_last_preferring_at_mano():
    # position_preference=1 (last-preferring), position=0 (mano) → negative signal
    sig = compute_position_signal(0, 4, 1.0)
    assert sig < 0.0

def test_position_signal_neutral_at_midpoint():
    # position_preference=0.5 (no preference), position=1.5 is impossible with int,
    # but signal at position=0 and position=3 should be symmetric
    sig_mano = compute_position_signal(0, 4, 0.5)
    sig_last = compute_position_signal(3, 4, 0.5)
    assert abs(sig_mano - sig_last) < 1e-9
```

- [ ] **Step 3.2: Run to verify failure**

```
.venv\Scripts\python -m pytest tests/test_bot_game_state.py -v
```

Expected: `ModuleNotFoundError: No module named 'bot_game_state'`

- [ ] **Step 3.3: Write `bot_game_state.py`**

```python
# bot_game_state.py
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict


class ScoreTier(Enum):
    EARLY    = 0   # < 25% of win score (< 10 points at WIN_SCORE=40)
    MID      = 1   # 25–60% (10–23)
    LATE     = 2   # 60–85% (24–33)
    CRITICAL = 3   # > 85%  (>= 34)


def get_score_tier(score: int, win_score: int) -> ScoreTier:
    ratio = score / win_score
    if ratio < 0.25:
        return ScoreTier.EARLY
    if ratio < 0.60:
        return ScoreTier.MID
    if ratio < 0.85:
        return ScoreTier.LATE
    return ScoreTier.CRITICAL


def compute_urgency(my_tier: ScoreTier, opp_tier: ScoreTier) -> float:
    """
    Returns value in [-1, 1].
    Positive = opponent closer to winning → we need more aggression.
    Negative = we are closer to winning → we can be conservative.
    """
    return (opp_tier.value - my_tier.value) / 3.0


def compute_position_signal(position: int, n_players: int, position_preference: float) -> float:
    """
    Returns value in [-1, 1].
    position_preference=0: positive signal at mano (first), negative at last.
    position_preference=1: positive signal at last, negative at mano.
    """
    if n_players <= 1:
        return 0.0
    normalized_pos = position / (n_players - 1)   # 0.0=mano, 1.0=last
    preferred_pos = position_preference
    return 1.0 - 2.0 * abs(normalized_pos - preferred_pos)


@dataclass
class BotGameState:
    my_score_tier: ScoreTier
    opponent_score_tier: ScoreTier
    position: int
    n_players: int
    opponent_discard_counts: List[int] = field(default_factory=list)
    mus_rounds_completed: int = 0
```

- [ ] **Step 3.4: Run tests to verify they pass**

```
.venv\Scripts\python -m pytest tests/test_bot_game_state.py -v
```

Expected: all 13 tests PASS.

- [ ] **Step 3.5: Commit**

```bash
git add bot_game_state.py tests/test_bot_game_state.py
git commit -m "feat: add BotGameState, ScoreTier, urgency and position signal utils"
```

---

## Task 4: Extend PlayerBase and GameContext

**Files:**
- Modify: `player_base.py`
- Modify: `game_context.py`
- Modify: `tests/test_game_context.py` (add new-field tests)
- Modify: `tests/test_player_base.py` (add set_round_state test)

- [ ] **Step 4.1: Write failing tests**

Add to `tests/test_game_context.py`:

```python
def test_game_context_has_position_field():
    from game_context import GameContext
    from card import Card
    ctx = GameContext(
        phase_name="Grande",
        team_scores={"A": 0, "B": 0},
        current_bet=1,
        previous_bet=0,
        hand=[Card.A],
        position=2,
        n_players=4,
        opponent_discard_counts=[1, 2],
    )
    assert ctx.position == 2
    assert ctx.n_players == 4
    assert ctx.opponent_discard_counts == [1, 2]

def test_game_context_position_defaults_to_zero():
    from game_context import GameContext
    ctx = GameContext(
        phase_name="Chica",
        team_scores={"A": 0, "B": 0},
        current_bet=1,
        previous_bet=0,
        hand=[],
    )
    assert ctx.position == 0
    assert ctx.n_players == 1
    assert ctx.opponent_discard_counts == []
```

Add to `tests/test_player_base.py`:

```python
def test_player_base_set_round_state_is_noop():
    from tests.conftest import ScriptedPlayer
    from team import Team
    player = ScriptedPlayer("p", Team("A"), votes=[], discards=[], wagers=[])
    # Should not raise
    player.set_round_state(
        team_scores={"A": 0, "B": 0},
        my_team_name="A",
        position=0,
        n_players=4,
        opponent_discard_counts=[],
        mus_rounds_completed=0,
    )
```

- [ ] **Step 4.2: Run to verify failure**

```
.venv\Scripts\python -m pytest tests/test_game_context.py tests/test_player_base.py -v -k "position or set_round_state"
```

Expected: `TypeError` on GameContext (unexpected keyword argument) and `AttributeError` on PlayerBase.

- [ ] **Step 4.3: Update `game_context.py`**

Replace the file content:

```python
# game_context.py
from dataclasses import dataclass, field
from typing import List, Dict
from card import Card


@dataclass
class GameContext:
    phase_name: str
    team_scores: Dict[str, int]
    current_bet: int
    previous_bet: int
    hand: List[Card]
    position: int = 0
    n_players: int = 1
    opponent_discard_counts: List[int] = field(default_factory=list)
```

- [ ] **Step 4.4: Update `player_base.py`**

Add the `set_round_state` method before the abstract methods:

```python
    def set_round_state(
        self,
        team_scores: dict,
        my_team_name: str,
        position: int,
        n_players: int,
        opponent_discard_counts: list,
        mus_rounds_completed: int,
    ) -> None:
        """Called by Game before mus phase and before wagering. No-op by default."""
        pass
```

- [ ] **Step 4.5: Run tests to verify they pass**

```
.venv\Scripts\python -m pytest tests/test_game_context.py tests/test_player_base.py -v
```

Expected: all tests PASS (including existing ones).

- [ ] **Step 4.6: Commit**

```bash
git add game_context.py player_base.py tests/test_game_context.py tests/test_player_base.py
git commit -m "feat: extend GameContext with position/discard fields; add PlayerBase.set_round_state no-op"
```

---

## Task 5: Extend Game and WagerSession

**Files:**
- Modify: `game.py`
- Modify: `wager_session.py`
- Modify: `tests/test_game.py` (add discard-tracking and state-notification tests)
- Modify: `tests/test_wager_session.py` (add position-in-context test)

- [ ] **Step 5.1: Write failing tests**

Add to `tests/test_game.py`:

```python
def test_game_calls_set_round_state_before_mus(mocker):
    """Game must call set_round_state on all players before mus voting begins."""
    from game import Game
    from bot_player import BotPlayer
    from bot_genome import random_genome
    from team import Team

    team_a = Team("A")
    team_b = Team("B")
    bot = BotPlayer("bot1", team_a, random_genome())
    spy = mocker.spy(bot, "set_round_state")

    # Run just enough to trigger mus (patch play to stop after 1 hand)
    # We test that set_round_state was called with position=0 for the first player
    # This requires pytest-mock: pip install pytest-mock
    # If unavailable, skip with: pytest.importorskip("pytest_mock")
    pytest.importorskip("pytest_mock")
    # (full integration test omitted — covered by test_wager_session_passes_position below)
```

> **Note:** The full game integration test is complex to mock. The position-in-context test is more tractable via WagerSession directly:

Add to `tests/test_wager_session.py`:

```python
def test_wager_session_passes_position_to_context():
    """WagerSession must set context.position to the player's index in the round."""
    from wager_session import WagerSession
    from team import Team
    from tests.conftest import ScriptedPlayer

    captured_positions = []

    class PositionCapturingPlayer(ScriptedPlayer):
        def wager_action(self, context):
            captured_positions.append(context.position)
            return 0  # always pass

    team_a = Team("A")
    team_b = Team("B")
    p0 = PositionCapturingPlayer("p0", team_a, votes=[], discards=[], wagers=[0, 0])
    p1 = PositionCapturingPlayer("p1", team_b, votes=[], discards=[], wagers=[0, 0])

    WagerSession(
        players=[p0, p1],
        base_bet=1,
        phase_name="Grande",
        team_scores={"A": 0, "B": 0},
        discard_counts={},
    ).run()

    assert 0 in captured_positions
    assert 1 in captured_positions

def test_wager_session_passes_n_players_to_context():
    from wager_session import WagerSession
    from team import Team
    from tests.conftest import ScriptedPlayer

    captured = []

    class CapturingPlayer(ScriptedPlayer):
        def wager_action(self, context):
            captured.append(context.n_players)
            return 0

    team_a, team_b = Team("A"), Team("B")
    p0 = CapturingPlayer("p0", team_a, votes=[], discards=[], wagers=[0])
    p1 = CapturingPlayer("p1", team_b, votes=[], discards=[], wagers=[0])

    WagerSession(
        players=[p0, p1],
        base_bet=1,
        phase_name="Chica",
        team_scores={"A": 0, "B": 0},
        discard_counts={},
    ).run()

    assert all(n == 2 for n in captured)
```

- [ ] **Step 5.2: Run to verify failure**

```
.venv\Scripts\python -m pytest tests/test_wager_session.py -v -k "position or n_players"
```

Expected: `TypeError: WagerSession.__init__() got an unexpected keyword argument 'discard_counts'`

- [ ] **Step 5.3: Update `wager_session.py`**

```python
# wager_session.py
from typing import List, Tuple, Optional, Dict
from player_base import PlayerBase
from team import Team
from game_context import GameContext


class WagerSession:
    def __init__(
        self,
        players: List[PlayerBase],
        base_bet: int,
        phase_name: str,
        team_scores: Dict[str, int],
        discard_counts: Dict[str, int] = None,
    ):
        self.players = players
        self.phase_name = phase_name
        self.team_scores = team_scores
        self.current_bet = base_bet
        self.previous_bet = 0
        self.team_leading_bet: Optional[Team] = None
        self.discard_counts: Dict[str, int] = discard_counts or {}

    def run(self) -> Tuple[Optional[Team], int]:
        last_raiser_idx: Optional[int] = None
        consecutive_passes = 0
        n_players = len(self.players)

        for i in range(40 * n_players):
            idx = i % n_players
            player = self.players[idx]

            if last_raiser_idx is not None and idx == last_raiser_idx:
                return (None, self.current_bet)

            opp_discards = [
                self.discard_counts.get(p.name, 0)
                for p in self.players
                if p.team != player.team
            ]

            context = GameContext(
                phase_name=self.phase_name,
                team_scores=self.team_scores,
                current_bet=self.current_bet,
                previous_bet=self.previous_bet,
                hand=list(player.cards),
                position=idx,
                n_players=n_players,
                opponent_discard_counts=opp_discards,
            )

            action = player.wager_action(context)

            if action < 0:
                opponent_team = next(p.team for p in self.players if p.team != player.team)
                return (opponent_team, self.current_bet)

            if action > 0:
                self.previous_bet = self.current_bet
                self.current_bet += action
                self.team_leading_bet = player.team
                last_raiser_idx = idx
                consecutive_passes = 0
            else:
                consecutive_passes += 1
                if consecutive_passes >= n_players:
                    return (None, self.current_bet)

        return (None, self.current_bet)
```

- [ ] **Step 5.4: Update `game.py`**

Replace `_mus_phase`, `_play_all_phases`, and add `_notify_players_round_state`:

```python
    def _mus_phase(self):
        discard_counts = {p.name: 0 for p in self.players_in_order}
        mus_rounds = 0
        self._notify_players_round_state(discard_counts, mus_rounds)

        while self._all_vote_mus():
            mus_rounds += 1
            for player in self.players_in_order:
                indices = player.choose_discards()
                discard_counts[player.name] += len(indices)
                for idx in sorted(indices, reverse=True):
                    player.throw_card(idx)
                player.receive_cards(self.deck.draw(len(indices)))
            self._notify_players_round_state(discard_counts, mus_rounds)

        self._discard_counts = discard_counts
        self._mus_rounds = mus_rounds

    def _notify_players_round_state(self, discard_counts: dict, mus_rounds: int):
        team_scores = {t.name: t.points for t in self.teams}
        for i, player in enumerate(self.players_in_order):
            opp_discards = [
                discard_counts[p.name]
                for p in self.players_in_order
                if p.team != player.team
            ]
            player.set_round_state(
                team_scores=team_scores,
                my_team_name=player.team.name,
                position=i,
                n_players=len(self.players_in_order),
                opponent_discard_counts=opp_discards,
                mus_rounds_completed=mus_rounds,
            )

    def _play_all_phases(self):
        # Notify players of final discard counts before wagering
        self._notify_players_round_state(
            getattr(self, "_discard_counts", {}),
            getattr(self, "_mus_rounds", 0),
        )
        phases = [Grande, Chica, Pares, Juego]
        while phases:
            phase = phases.pop(0)
            players_in_phase = self._players_that_can_play(phase)

            if not players_in_phase:
                if phase is Juego:
                    phases.insert(0, Punto)
                continue

            winner_team = None
            bet_points = 0

            if self._is_contested(players_in_phase):
                team_scores = {t.name: t.points for t in self.teams}
                winner_team, bet_points = WagerSession(
                    players=players_in_phase,
                    base_bet=phase.base_bet,
                    phase_name=phase.__name__,
                    team_scores=team_scores,
                    discard_counts=getattr(self, "_discard_counts", {}),
                ).run()

            if winner_team is None:
                winner_team = self._resolve_phase(phase)
                for p in self.players_in_order:
                    if p.team is winner_team:
                        bet_points += phase.calculate_points(Hand(p.cards))

            winner_team.points += bet_points
```

Also add `_discard_counts` and `_mus_rounds` initialisation in `play()` before `_deal_initial_cards()`:
```python
    def play(self):
        while all(t.points < WIN_SCORE for t in self.teams):
            self.deck = Deck()
            self._discard_counts = {}
            self._mus_rounds = 0
            self._deal_initial_cards()
            self._mus_phase()
            self._play_all_phases()
        ...
```

- [ ] **Step 5.5: Run all existing tests**

```
.venv\Scripts\python -m pytest tests/ -v
```

Expected: all existing tests PASS, new wager_session tests PASS.

- [ ] **Step 5.6: Commit**

```bash
git add game.py wager_session.py tests/test_game.py tests/test_wager_session.py
git commit -m "feat: track mus discards in Game; pass position/discard context through WagerSession"
```

---

## Task 6: BotPlayer

**Files:**
- Create: `bot_player.py`
- Create: `tests/test_bot_player.py`

- [ ] **Step 6.1: Write failing tests**

```python
# tests/test_bot_player.py
import random
import pytest
from card import Card
from team import Team
from bot_genome import BotGenome, random_genome
from bot_player import BotPlayer

TEAM_A = Team("A")
TEAM_B = Team("B")
WIN_SCORE = 40


def _bot(genome: BotGenome = None) -> BotPlayer:
    g = genome or random_genome()
    bot = BotPlayer("bot", TEAM_A, g)
    bot.receive_cards([Card.R, Card.R, Card.R, Card.R])
    bot.set_round_state(
        team_scores={"A": 0, "B": 0},
        my_team_name="A",
        position=0,
        n_players=4,
        opponent_discard_counts=[0, 0],
        mus_rounds_completed=0,
    )
    return bot


def test_bot_player_is_player_base():
    from player_base import PlayerBase
    assert isinstance(_bot(), PlayerBase)


def test_vote_mus_returns_bool():
    bot = _bot()
    result = bot.vote_mus()
    assert isinstance(result, bool)


def test_vote_mus_weak_hand_more_likely_yes():
    """A bot with very weak hand (all aces for Grande) should vote yes to mus more often
    than a bot with a very strong hand (all kings)."""
    random.seed(42)
    genome = BotGenome(
        mus_eagerness=0.1,
        mus_risk_sensitivity=0.5,
        w_grande=0.5, w_chica=0.2, w_pares=0.2, w_juego=0.1,
        discard_aggressiveness=0.5,
        bluff_rate=0.0, risk_factor=0.5,
        fold_threshold=0.3, raise_threshold=0.7,
        score_urgency_sensitivity=0.5,
        position_preference=0.5,
    )

    def vote_rate(cards):
        yes = 0
        for _ in range(200):
            bot = BotPlayer("b", TEAM_A, genome)
            bot.receive_cards(cards)
            bot.set_round_state({"A": 0, "B": 0}, "A", 0, 4, [0, 0], 0)
            if bot.vote_mus():
                yes += 1
        return yes / 200

    weak_rate = vote_rate([Card.A, Card.A, Card.A, Card.A])  # bad for Grande
    strong_rate = vote_rate([Card.R, Card.R, Card.R, Card.R])  # best for Grande
    assert weak_rate > strong_rate


def test_choose_discards_returns_valid_indices():
    random.seed(0)
    bot = _bot()
    discards = bot.choose_discards()
    assert isinstance(discards, list)
    assert all(0 <= i < 4 for i in discards)
    assert len(discards) == len(set(discards))  # no duplicate indices


def test_choose_discards_keeps_all_kings():
    """Bot with w_grande=1 and low aggressiveness should keep four kings."""
    random.seed(0)
    genome = BotGenome(
        mus_eagerness=0.5, mus_risk_sensitivity=0.5,
        w_grande=1.0, w_chica=0.0, w_pares=0.0, w_juego=0.0,
        discard_aggressiveness=0.0,
        bluff_rate=0.0, risk_factor=0.5,
        fold_threshold=0.2, raise_threshold=0.8,
        score_urgency_sensitivity=0.0, position_preference=0.5,
    )
    bot = BotPlayer("b", TEAM_A, genome)
    bot.receive_cards([Card.R, Card.R, Card.R, Card.R])
    bot.set_round_state({"A": 0, "B": 0}, "A", 0, 4, [0, 0], 0)
    assert bot.choose_discards() == []


def test_wager_action_folds_when_prob_very_low():
    """Bot with fold_threshold=0.9 and no bluff should fold with a losing hand."""
    random.seed(0)
    genome = BotGenome(
        mus_eagerness=0.5, mus_risk_sensitivity=0.0,
        w_grande=1.0, w_chica=0.0, w_pares=0.0, w_juego=0.0,
        discard_aggressiveness=0.0,
        bluff_rate=0.0, risk_factor=0.5,
        fold_threshold=0.95,   # fold unless near-certain win
        raise_threshold=0.99,
        score_urgency_sensitivity=0.0, position_preference=0.5,
    )
    bot = BotPlayer("b", TEAM_A, genome)
    bot.receive_cards([Card.A, Card.A, Card.A, Card.A])  # worst Grande hand
    bot.set_round_state({"A": 0, "B": 0}, "A", 0, 4, [0, 0], 0)

    from game_context import GameContext
    ctx = GameContext(
        phase_name="Grande",
        team_scores={"A": 0, "B": 0},
        current_bet=1, previous_bet=0,
        hand=bot.cards, position=0, n_players=4,
    )
    result = bot.wager_action(ctx)
    assert result < 0  # fold


def test_wager_action_raises_when_prob_high():
    """Bot with raise_threshold=0.1 should raise with the best possible hand."""
    random.seed(0)
    genome = BotGenome(
        mus_eagerness=0.5, mus_risk_sensitivity=0.0,
        w_grande=1.0, w_chica=0.0, w_pares=0.0, w_juego=0.0,
        discard_aggressiveness=0.0,
        bluff_rate=0.0, risk_factor=0.5,
        fold_threshold=0.05, raise_threshold=0.10,
        score_urgency_sensitivity=0.0, position_preference=0.5,
    )
    bot = BotPlayer("b", TEAM_A, genome)
    bot.receive_cards([Card.R, Card.R, Card.R, Card.R])  # best Grande hand
    bot.set_round_state({"A": 0, "B": 0}, "A", 0, 4, [0, 0], 0)

    from game_context import GameContext
    ctx = GameContext(
        phase_name="Grande",
        team_scores={"A": 0, "B": 0},
        current_bet=1, previous_bet=0,
        hand=bot.cards, position=0, n_players=4,
    )
    result = bot.wager_action(ctx)
    assert result > 0  # raise


def test_wager_action_bluffs_at_high_bluff_rate():
    """A bot with bluff_rate=1.0 should always raise regardless of hand."""
    random.seed(0)
    genome = BotGenome(
        mus_eagerness=0.5, mus_risk_sensitivity=0.0,
        w_grande=1.0, w_chica=0.0, w_pares=0.0, w_juego=0.0,
        discard_aggressiveness=0.0,
        bluff_rate=1.0,          # always bluff
        risk_factor=0.5,
        fold_threshold=0.3, raise_threshold=0.7,
        score_urgency_sensitivity=0.0, position_preference=0.5,
    )
    bot = BotPlayer("b", TEAM_A, genome)
    bot.receive_cards([Card.A, Card.A, Card.A, Card.A])  # worst hand
    bot.set_round_state({"A": 0, "B": 0}, "A", 0, 4, [0, 0], 0)

    from game_context import GameContext
    ctx = GameContext(
        phase_name="Grande",
        team_scores={"A": 0, "B": 0},
        current_bet=1, previous_bet=0,
        hand=bot.cards, position=0, n_players=4,
    )
    result = bot.wager_action(ctx)
    assert result > 0  # bluffing → raises
```

- [ ] **Step 6.2: Run to verify failure**

```
.venv\Scripts\python -m pytest tests/test_bot_player.py -v
```

Expected: `ModuleNotFoundError: No module named 'bot_player'`

- [ ] **Step 6.3: Write `bot_player.py`**

```python
# bot_player.py
import random
from typing import List
from player_base import PlayerBase
from bot_genome import BotGenome
from bot_game_state import (
    BotGameState, ScoreTier, get_score_tier,
    compute_urgency, compute_position_signal,
)
from probability_tables import canonical, win_prob, avg_opp_improvement_per_phase
from game_context import GameContext
from team import Team
from hand import Hand
from phases import Grande, Chica, Pares, Juego
from constants import cards_space

WIN_SCORE = 40
_PHASE_NAMES = ["Grande", "Chica", "Pares", "Juego"]
_URGENCY_SCALE = 0.20
_POSITION_SCALE = 0.10
_DISCARD_SAMPLES = 300
_IMPROVEMENT_SAMPLES = 80   # lighter sampling for vote_mus improvement estimate


class BotPlayer(PlayerBase):
    def __init__(self, name: str, team: Team, genome: BotGenome):
        super().__init__(name, team)
        self._genome = genome
        self._state: BotGameState | None = None

    # ------------------------------------------------------------------
    # State management
    # ------------------------------------------------------------------

    def set_round_state(
        self,
        team_scores: dict,
        my_team_name: str,
        position: int,
        n_players: int,
        opponent_discard_counts: list,
        mus_rounds_completed: int,
    ) -> None:
        my_score = team_scores.get(my_team_name, 0)
        opp_score = max(
            (v for k, v in team_scores.items() if k != my_team_name),
            default=0,
        )
        self._state = BotGameState(
            my_score_tier=get_score_tier(my_score, WIN_SCORE),
            opponent_score_tier=get_score_tier(opp_score, WIN_SCORE),
            position=position,
            n_players=n_players,
            opponent_discard_counts=opponent_discard_counts,
            mus_rounds_completed=mus_rounds_completed,
        )

    # ------------------------------------------------------------------
    # Core helpers
    # ------------------------------------------------------------------

    def _phase_weights(self) -> dict:
        g = self._genome
        raw = {
            "Grande": g.w_grande,
            "Chica": g.w_chica,
            "Pares": g.w_pares,
            "Juego": g.w_juego,
        }
        total = sum(raw.values()) or 1.0
        return {k: v / total for k, v in raw.items()}

    def _hand_strength(self, cards) -> float:
        """Weighted average of phase win probabilities for the given cards."""
        weights = self._phase_weights()
        is_mano = (
            self._state is not None
            and self._state.position == 0
            and self._genome.position_preference < 0.5
        )
        total = 0.0
        for phase_name, w in weights.items():
            total += w * win_prob(cards, phase_name, is_mano=is_mano)
        return total

    def _game_signal(self) -> float:
        """Combined urgency + position signal scaled to a small modifier."""
        if self._state is None:
            return 0.0
        urgency = compute_urgency(self._state.my_score_tier, self._state.opponent_score_tier)
        pos_sig = compute_position_signal(
            self._state.position,
            self._state.n_players,
            self._genome.position_preference,
        )
        return (
            self._genome.score_urgency_sensitivity * urgency * _URGENCY_SCALE
            + pos_sig * _POSITION_SCALE
        )

    def _remaining_deck(self) -> List:
        """Cards available to draw (full deck minus current hand)."""
        counts = dict(cards_space)
        for c in self.cards:
            counts[c] -= 1
        return [c for c, n in counts.items() for _ in range(n)]

    def _sample_replacements(self, kept, n_draw, n_samples) -> List[float]:
        """Sample n_samples replacement draws; return list of hand strengths."""
        remaining = self._remaining_deck()
        if n_draw == 0:
            return [self._hand_strength(list(kept))]
        strengths = []
        for _ in range(n_samples):
            drawn = random.sample(remaining, n_draw)
            strengths.append(self._hand_strength(list(kept) + drawn))
        return strengths

    # ------------------------------------------------------------------
    # vote_mus
    # ------------------------------------------------------------------

    def vote_mus(self) -> bool:
        g = self._genome
        hand_strength = self._hand_strength(self.cards)

        # Expected improvement for us: best expected strength after optimal discard
        best_expected = self._best_expected_strength(n_samples=_IMPROVEMENT_SAMPLES)
        improvement_ours = max(0.0, best_expected - hand_strength)

        # Expected improvement for opponent (precomputed per-phase average)
        weights = self._phase_weights()
        avg_improvements = avg_opp_improvement_per_phase()
        improvement_opp = sum(
            weights[p] * avg_improvements[p] for p in _PHASE_NAMES
        )

        improvement_delta = improvement_ours - improvement_opp  # positive = mus helps us
        improvement_signal = improvement_delta * g.mus_risk_sensitivity

        game_signal = self._game_signal()

        # Higher adjusted_strength → more likely to stop mus
        adjusted_strength = max(0.0, min(1.0, hand_strength - improvement_signal + game_signal))
        stop_mus_prob = adjusted_strength * (1.0 - g.mus_eagerness)
        return random.random() > stop_mus_prob  # True = vote yes (want mus)

    def _best_expected_strength(self, n_samples: int) -> float:
        from itertools import combinations
        best = self._hand_strength(self.cards)
        for r in range(1, 5):
            for discard_idx in combinations(range(len(self.cards)), r):
                kept = [c for i, c in enumerate(self.cards) if i not in discard_idx]
                strengths = self._sample_replacements(kept, r, n_samples)
                expected = sum(strengths) / len(strengths)
                if expected > best:
                    best = expected
        return best

    # ------------------------------------------------------------------
    # choose_discards
    # ------------------------------------------------------------------

    def choose_discards(self) -> List[int]:
        from itertools import combinations
        g = self._genome
        best_score = -1.0
        best_indices: List[int] = []

        for r in range(5):
            for discard_idx in combinations(range(len(self.cards)), r):
                kept = [c for i, c in enumerate(self.cards) if i not in discard_idx]
                strengths = self._sample_replacements(kept, r, _DISCARD_SAMPLES)
                expected = sum(strengths) / len(strengths)
                # High aggressiveness removes penalty for discarding more cards
                penalty = (1.0 - g.discard_aggressiveness) * r * 0.04
                score = expected - penalty
                if score > best_score:
                    best_score = score
                    best_indices = list(discard_idx)

        return best_indices

    # ------------------------------------------------------------------
    # wager_action
    # ------------------------------------------------------------------

    def wager_action(self, context: GameContext) -> int:
        g = self._genome
        phase_name = context.phase_name

        # Use Grande as proxy for Punto (see open question #3 in plan)
        effective_phase = "Grande" if phase_name == "Punto" else phase_name

        is_mano = context.position == 0 and g.position_preference < 0.5
        base_prob = win_prob(context.hand, effective_phase, is_mano=is_mano)

        # Game state modifier
        if self._state is not None:
            urgency = compute_urgency(
                self._state.my_score_tier,
                self._state.opponent_score_tier,
            )
            pos_sig = compute_position_signal(
                context.position,
                context.n_players,
                g.position_preference,
            )
        else:
            urgency = 0.0
            pos_sig = 0.0

        modifier = (
            g.score_urgency_sensitivity * urgency * _URGENCY_SCALE
            + pos_sig * _POSITION_SCALE
        )
        adjusted_prob = max(0.0, min(1.0, base_prob + modifier))

        # Bluff override
        if random.random() < g.bluff_rate:
            adjusted_prob = max(adjusted_prob, g.raise_threshold + 0.01)

        # Decision
        if adjusted_prob < g.fold_threshold:
            return -1

        if adjusted_prob < g.raise_threshold:
            return 0

        # Raise: scale between 1 and current_bet (doubling cap)
        # ? Open question #1: confirm max legal raise amount
        min_raise = 1
        max_raise = max(1, context.current_bet)
        raise_amount = round(min_raise + g.risk_factor * (max_raise - min_raise))
        return raise_amount
```

- [ ] **Step 6.4: Run tests to verify they pass**

```
.venv\Scripts\python -m pytest tests/test_bot_player.py -v
```

Expected: all tests PASS. (These tests may take a few seconds due to sampling.)

- [ ] **Step 6.5: Run full test suite**

```
.venv\Scripts\python -m pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 6.6: Commit**

```bash
git add bot_player.py tests/test_bot_player.py
git commit -m "feat: implement BotPlayer with table-backed decisions and personality genome"
```

---

## Task 7: GeneticTrainer

**Files:**
- Create: `genetic_trainer.py`
- Create: `tests/test_genetic_trainer.py`

- [ ] **Step 7.1: Write failing tests**

```python
# tests/test_genetic_trainer.py
import pytest
from bot_genome import BotGenome, random_genome
from genetic_trainer import GeneticTrainer, evaluate_game, build_bot_game


def test_trainer_init_creates_population():
    trainer = GeneticTrainer(population_size=10, generations=1, games_per_eval=2)
    population = trainer.initial_population()
    assert len(population) == 10
    assert all(isinstance(g, BotGenome) for g in population)


def test_evaluate_game_returns_winning_team():
    """A full game between 4 random bots should return a winner string."""
    import random
    random.seed(0)
    genomes = [random_genome() for _ in range(4)]
    winner = evaluate_game(genomes)
    assert winner in ("A", "B")


def test_fitness_evaluation_returns_rates_in_range():
    import random
    random.seed(1)
    trainer = GeneticTrainer(population_size=4, generations=1, games_per_eval=2)
    population = trainer.initial_population()
    fitness = trainer.evaluate_population(population)
    assert len(fitness) == 4
    assert all(0.0 <= f <= 1.0 for f in fitness)


def test_next_generation_same_size():
    import random
    random.seed(2)
    trainer = GeneticTrainer(population_size=10, generations=1, games_per_eval=1)
    population = trainer.initial_population()
    fitness = trainer.evaluate_population(population)
    next_gen = trainer.next_generation(population, fitness)
    assert len(next_gen) == 10


def test_next_generation_all_botgenome():
    import random
    random.seed(3)
    trainer = GeneticTrainer(population_size=6, generations=1, games_per_eval=1)
    population = trainer.initial_population()
    fitness = trainer.evaluate_population(population)
    next_gen = trainer.next_generation(population, fitness)
    assert all(isinstance(g, BotGenome) for g in next_gen)


def test_save_and_load_population(tmp_path):
    import random
    random.seed(4)
    trainer = GeneticTrainer(population_size=4, generations=1, games_per_eval=1)
    population = trainer.initial_population()
    path = tmp_path / "pop.json"
    trainer.save_population(population, path)
    loaded = trainer.load_population(path)
    assert len(loaded) == 4
    for orig, load in zip(population, loaded):
        assert orig == load
```

- [ ] **Step 7.2: Run to verify failure**

```
.venv\Scripts\python -m pytest tests/test_genetic_trainer.py -v
```

Expected: `ModuleNotFoundError: No module named 'genetic_trainer'`

- [ ] **Step 7.3: Write `genetic_trainer.py`**

```python
# genetic_trainer.py
import json
import random
from dataclasses import asdict, fields
from pathlib import Path
from typing import List, Tuple

from bot_genome import BotGenome, random_genome, crossover, mutate
from bot_player import BotPlayer
from game import Game
from team import Team


def build_bot_game(genomes: List[BotGenome]) -> Game:
    """
    Create a Game wired with 4 BotPlayers (2 per team).
    genomes: [genome_a1, genome_a2, genome_b1, genome_b2]
    """
    team_a = Team("A")
    team_b = Team("B")
    players = [
        BotPlayer("A1", team_a, genomes[0]),
        BotPlayer("A2", team_a, genomes[1]),
        BotPlayer("B1", team_b, genomes[2]),
        BotPlayer("B2", team_b, genomes[3]),
    ]
    game = Game.__new__(Game)
    game.players_in_order = players
    game.teams = [team_a, team_b]
    from deck import Deck
    game.deck = Deck()
    game._discard_counts = {}
    game._mus_rounds = 0
    return game


def evaluate_game(genomes: List[BotGenome]) -> str:
    """
    Play one full game with 4 genomes. Returns winning team name ("A" or "B").
    genomes[0], genomes[1] are team A; genomes[2], genomes[3] are team B.
    """
    game = build_bot_game(genomes)
    from game import WIN_SCORE
    from deck import Deck
    from hand import Hand
    from phases import Grande, Chica, Pares, Juego

    while all(t.points < WIN_SCORE for t in game.teams):
        game.deck = Deck()
        game._discard_counts = {}
        game._mus_rounds = 0
        game._deal_initial_cards()
        game._mus_phase()
        game._play_all_phases()

    return next(t.name for t in game.teams if t.points >= WIN_SCORE)


class GeneticTrainer:
    def __init__(
        self,
        population_size: int = 100,
        generations: int = 300,
        games_per_eval: int = 10,
        elite_fraction: float = 0.05,
        mutation_rate: float = 0.15,
        mutation_sigma: float = 0.05,
        tournament_k: int = 5,
    ):
        self.population_size = population_size
        self.generations = generations
        self.games_per_eval = games_per_eval
        self.elite_fraction = elite_fraction
        self.mutation_rate = mutation_rate
        self.mutation_sigma = mutation_sigma
        self.tournament_k = tournament_k

    def initial_population(self) -> List[BotGenome]:
        return [random_genome() for _ in range(self.population_size)]

    def evaluate_population(self, population: List[BotGenome]) -> List[float]:
        """
        Each genome plays games_per_eval games against random opponents from the
        population. Fitness = win rate.
        Teams are re-randomised each game to avoid partner co-evolution.
        """
        wins = [0] * len(population)
        games = [0] * len(population)

        for genome_idx, genome in enumerate(population):
            for _ in range(self.games_per_eval):
                others = random.sample(
                    [g for i, g in enumerate(population) if i != genome_idx], 3
                )
                # Randomly assign: genome as A1, others fill remaining slots
                order = [genome] + others
                random.shuffle(order)
                genomes_game = order[:4]
                # Ensure our genome is in the game
                if genome not in genomes_game:
                    genomes_game[0] = genome

                winner = evaluate_game(genomes_game)
                # Determine which team our genome is on
                pos = genomes_game.index(genome)
                our_team = "A" if pos < 2 else "B"

                if winner == our_team:
                    wins[genome_idx] += 1
                games[genome_idx] += 1

        return [w / g if g > 0 else 0.0 for w, g in zip(wins, games)]

    def _tournament_select(self, population: List[BotGenome], fitness: List[float]) -> BotGenome:
        candidates = random.sample(list(range(len(population))), min(self.tournament_k, len(population)))
        best = max(candidates, key=lambda i: fitness[i])
        return population[best]

    def next_generation(
        self, population: List[BotGenome], fitness: List[float]
    ) -> List[BotGenome]:
        n = len(population)
        n_elite = max(1, round(n * self.elite_fraction))

        # Elite preservation
        sorted_idx = sorted(range(n), key=lambda i: fitness[i], reverse=True)
        new_gen = [population[i] for i in sorted_idx[:n_elite]]

        # Fill remainder via tournament selection + crossover + mutation
        while len(new_gen) < n:
            parent_a = self._tournament_select(population, fitness)
            parent_b = self._tournament_select(population, fitness)
            child = crossover(parent_a, parent_b)
            child = mutate(child, self.mutation_rate, self.mutation_sigma)
            new_gen.append(child)

        return new_gen

    def evolve(self, snapshot_every: int = 50) -> BotGenome:
        """Run full evolution. Returns best genome found."""
        population = self.initial_population()
        best_genome = population[0]
        best_fitness = 0.0

        for gen in range(self.generations):
            fitness = self.evaluate_population(population)
            top_fitness = max(fitness)
            mean_fitness = sum(fitness) / len(fitness)

            top_idx = fitness.index(top_fitness)
            if top_fitness > best_fitness:
                best_fitness = top_fitness
                best_genome = population[top_idx]

            print(f"Gen {gen+1}/{self.generations} | best={top_fitness:.3f} mean={mean_fitness:.3f}")

            if (gen + 1) % snapshot_every == 0:
                self.save_population(population, Path(f"population_gen{gen+1}.json"))

            population = self.next_generation(population, fitness)

        return best_genome

    def save_population(self, population: List[BotGenome], path) -> None:
        data = [asdict(g) for g in population]
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def load_population(self, path) -> List[BotGenome]:
        with open(path) as f:
            data = json.load(f)
        return [BotGenome(**d) for d in data]
```

- [ ] **Step 7.4: Run tests to verify they pass**

```
.venv\Scripts\python -m pytest tests/test_genetic_trainer.py -v
```

Expected: all tests PASS. (Tests run multiple games; allow ~30s.)

- [ ] **Step 7.5: Run full test suite**

```
.venv\Scripts\python -m pytest tests/ -v
```

Expected: all tests PASS.

- [ ] **Step 7.6: Commit**

```bash
git add genetic_trainer.py tests/test_genetic_trainer.py
git commit -m "feat: add GeneticTrainer with tournament selection and genome evolution"
```

---

## Self-review checklist

- [x] **Spec § 1 (Probability Tables)** → Task 1
- [x] **Spec § 2 (BotGenome)** → Task 2
- [x] **Spec § 3 (Game state discretization)** → Task 3
- [x] **Spec § 3 (Passing state to bot)** → Tasks 4 + 5
- [x] **Spec § 4.1 (Hand strength)** → Task 6 `_hand_strength()`
- [x] **Spec § 4.2 (vote_mus + improvement delta)** → Task 6 `vote_mus()`
- [x] **Spec § 4.3 (choose_discards)** → Task 6 `choose_discards()`
- [x] **Spec § 4.4 (wager_action)** → Task 6 `wager_action()`
- [x] **Spec § 5 (GeneticTrainer)** → Task 7
- [x] **Spec § 6 (File structure)** → all tasks
- [x] **Spec § 7 (Constraints)** → open questions documented
