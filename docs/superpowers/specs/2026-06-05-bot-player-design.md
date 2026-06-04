# Bot Player Design

## Overview

A parametric bot player for the mus card game whose behavior is entirely controlled by a
13-gene flat vector (`BotGenome`). Win probabilities are computed analytically from
precomputed lookup tables. Every decision (mus vote, discards, wager) starts from a
table-derived probability and is then shifted by the genome parameters and a discretized
game state signal. The genome is the unit of evolution in a genetic algorithm trained by
bot-vs-bot tournament play.

---

## 1. Probability Tables

### Motivation

Suits do not affect any mus phase outcome — Grande/Chica compare card values, Pares counts
value matches, Juego sums juego values. Two hands with the same value multiset are
strategically identical. This reduces the 91,390 possible 4-card hands to approximately
**715 canonical hands** (distinct sorted value-tuples), making full precomputation
practical.

### Structure

For each canonical hand and each of the four contested phases (Grande, Chica, Pares,
Juego), we precompute:

```
P(win | my_canonical_hand, phase)
```

computed by comparing the hand against every possible opponent 4-card hand drawn from the
full 40-card deck, weighted by multiplicity. Result: a `dict[tuple[int,...], dict[str,
float]]` with 715 entries.

For Pares and Juego, hands that cannot play those phases receive `win_prob = 0.0` (they
lose by default if the phase is played, so the bot should account for that when the phase
is still contested).

### Storage

Tables are computed once via a build script and saved to `probability_tables.pkl`. At
startup the bot loads the pickle; the build script is re-run only when card values change.
Lookup is `O(1)` per decision.

### Accuracy note

Tables are computed against the full deck, ignoring the 4 cards already in our own hand.
This introduces a small (~10%) error on the margin. This is acceptable: the noise is
dominated by personality parameters and opponent behavior, and it keeps tables static and
reusable across all hands.

---

## 2. BotGenome — the 13-gene flat vector

All genes are `float` in `[0, 1]`. The genome is a plain dataclass; no hidden structure.

```python
@dataclass
class BotGenome:
    # --- Mus voting (2 genes) ---
    mus_eagerness: float
    # Base willingness to vote yes to mus (request card exchange).
    # 0 = almost never requests mus; 1 = always eager to exchange.

    mus_risk_sensitivity: float
    # How strongly the improvement delta (our expected gain vs. opponent expected gain
    # from doing mus) shifts the mus vote.
    # 0 = ignores improvement analysis entirely; 1 = fully driven by improvement delta.

    # --- Discard strategy (5 genes) ---
    w_grande: float    # weight for Grande win-prob when evaluating hand strength
    w_chica: float     # weight for Chica win-prob
    w_pares: float     # weight for Pares win-prob
    w_juego: float     # weight for Juego win-prob
    discard_aggressiveness: float
    # Bias toward discarding more cards during mus.
    # 0 = keep the hand; 1 = swap aggressively for potentially stronger hands.

    # --- Wagering (4 genes) ---
    bluff_rate: float
    # Probability of acting as if win_prob >= raise_threshold even when it is not.
    # 0 = never bluffs; 1 = always bets as if holding a strong hand.

    risk_factor: float
    # Scales the raise amount when the bot decides to raise.
    # 0 = minimum legal raise; 1 = maximum raise the rules allow.

    fold_threshold: float
    # Win probability below which the bot normally folds.
    # Subject to bluff_rate override.

    raise_threshold: float
    # Win probability above which the bot raises rather than calls.

    # --- Game state sensitivity (2 genes) ---
    score_urgency_sensitivity: float
    # How much the score tier differential shifts all decisions.
    # 0 = ignores scores entirely; 1 = fully adjusts based on urgency.

    position_preference: float
    # 0 = mano-preferring: more aggressive (higher bets, more no-mus) when first to act,
    #     exploiting the tiebreaker advantage.
    # 1 = last-preferring: more aggressive when last to act,
    #     exploiting the information advantage.
    # Intermediate values blend both tendencies proportionally.
```

### Genetic operations

**Crossover** — uniform: for each gene independently, take value from parent A or parent B
with equal probability.

**Mutation** — Gaussian noise: `gene += N(0, σ)` where `σ = 0.05`, clipped to `[0, 1]`.
Each gene is mutated independently with probability `mutation_rate = 0.15`.

**Elite preservation** — top 5% of population copied unchanged to next generation.

---

## 3. Game State Discretization

### ScoreTier

Scores are bucketed into four tiers based on fraction of `WIN_SCORE` (40):

```python
class ScoreTier(Enum):
    EARLY    = 0   # < 25%  (< 10 points)
    MID      = 1   # 25–60% (10–23 points)
    LATE     = 2   # 60–85% (24–33 points)
    CRITICAL = 3   # > 85%  (≥ 34 points)
```

### Urgency signal

```python
def compute_urgency(my_tier: ScoreTier, opp_tier: ScoreTier) -> float:
    """
    Returns a value in [-1, 1].
    Positive = opponent is closer to winning → we need to be more aggressive.
    Negative = we are closer to winning → we can be more conservative.
    """
    return (opp_tier.value - my_tier.value) / 3.0
```

### Position signal

```python
def compute_position_signal(position: int, n_players: int, position_preference: float) -> float:
    """
    Returns a value in [-1, 1] representing how favorable the current position is
    given the bot's positional preference.
    position 0 = mano (first to act), position n-1 = last.

    A mano-preferring bot (preference=0) gets a positive signal when position=0.
    A last-preferring bot (preference=1) gets a positive signal when position=n-1.
    """
    normalized_pos = position / (n_players - 1)          # 0.0 (mano) → 1.0 (last)
    preferred_pos = position_preference                    # 0.0 (mano) → 1.0 (last)
    return 1.0 - 2.0 * abs(normalized_pos - preferred_pos)
```

### BotGameState

```python
@dataclass
class BotGameState:
    my_score_tier: ScoreTier
    opponent_score_tier: ScoreTier
    position: int                        # 0-based index in betting order
    n_players: int                       # total players in this betting round
    opponent_discard_counts: List[int]   # cards each opponent discarded in mus
    mus_rounds_completed: int            # how many mus rounds happened this hand
```

### Passing state to the bot

`vote_mus()` and `choose_discards()` have no context parameter in the `PlayerBase`
interface. The `Game` class calls `player.set_round_state(state: BotGameState)` at two
points each hand:

1. **Before the first mus vote** — `opponent_discard_counts` is `[]` (no discards yet).
   Subsequent mus votes within the same hand see `opponent_discard_counts` populated with
   counts from the previous mus round, updated after each round completes.
2. **Before wagering begins** — `opponent_discard_counts` holds the final totals from all
   mus rounds.

`PlayerBase` gains a default no-op `set_round_state()`. `BotPlayer` overrides it to store
state internally.

`GameContext` gains two optional fields used during `wager_action()`:

```python
@dataclass
class GameContext:
    phase_name: str
    team_scores: Dict[str, int]
    current_bet: int
    previous_bet: int
    hand: List[Card]
    position: int = 0                          # position in betting order this action
    opponent_discard_counts: List[int] = field(default_factory=list)
```

---

## 4. Decision Formulas

### 4.1 Hand strength

The **weighted phase strength** is the core signal used in mus and discard decisions:

```
phase_probs = {
    "Grande": table[canonical(hand)]["Grande"],
    "Chica":  table[canonical(hand)]["Chica"],
    "Pares":  table[canonical(hand)]["Pares"],
    "Juego":  table[canonical(hand)]["Juego"],
}

weights = [w_grande, w_chica, w_pares, w_juego]  # from genome, not normalized
hand_strength = sum(w * p for w, p in zip(weights, phase_probs.values()))
               / sum(weights)   # normalize to [0, 1]
```

### 4.2 vote_mus()

Goal: return `True` to request mus (exchange cards), `False` to stop.

The decision incorporates three signals: **current hand strength**, **expected improvement
for us if mus continues**, and **expected improvement for opponents if mus continues**.

#### Expected improvement calculation (analytical / Bayesian)

```
expected_improvement_ours = E[hand_strength(hand_after_optimal_discards)] - hand_strength(current_hand)
```

Computed by iterating over all 16 discard subsets, sampling replacement hands from the
remaining deck, and taking the improvement of the best subset. This reuses the same
sampling infrastructure as `choose_discards()` and can be partially cached per canonical
hand.

```
expected_improvement_opponent = E[hand_strength(opponent_hand_after_optimal_discards)]
                               - E[hand_strength(random_opponent_hand)]
```

The opponent's current hand is unknown. We model it as a random 4-card hand drawn from
the remaining 36 cards (full deck minus ours). Their expected improvement is computed as
the average improvement across all canonical hands weighted by the number of ways each
can be formed from the remaining deck. This value is **precomputed and stored** as a
scalar in the probability tables (it depends only on the remaining deck composition,
which we approximate as fixed for simplicity).

```
improvement_delta = expected_improvement_ours - expected_improvement_opponent
```

A positive `improvement_delta` means mus benefits us more than it benefits opponents on
average → more reason to vote yes. A negative delta means opponents are likely to improve
more → more reason to stop mus if we already have a decent hand.

#### Full vote_mus formula

```
urgency         = compute_urgency(my_score_tier, opp_score_tier)
pos_signal      = compute_position_signal(position, n_players, position_preference)
combined_signal = score_urgency_sensitivity * urgency
                + position_preference_scale * pos_signal  # fixed small scale, e.g. 0.15

# improvement_delta ∈ [-1, 1]: positive = mus helps us more than opponents
improvement_signal = improvement_delta * mus_risk_sensitivity

adjusted_strength = clamp(hand_strength - improvement_signal + combined_signal, 0, 1)
# Subtracting improvement_signal: if mus helps us a lot, act as if hand is weaker
# (more willing to request mus); if mus helps opponents more, treat hand as stronger
# (more willing to stop).

# stop_mus_prob: strong adjusted hand + low eagerness → stop
stop_mus_prob = adjusted_strength * (1 - mus_eagerness)
return random() > stop_mus_prob
```

**Intuition:**
- A `mus_eagerness=0` bot always stops when it has a strong hand.
- A `mus_eagerness=1` bot always votes yes regardless of hand.
- High urgency (opponent near win) pushes the bot to accept mus more (seek improvement).
- If mus is analytically better for us than for opponents (`improvement_delta > 0`), the
  bot is more willing to vote yes — independently of raw hand strength.
- A mano-preferring bot with mano position is more willing to stop mus when strong,
  locking in its tiebreaker advantage.

### 4.3 choose_discards()

For each of the 16 discard subsets (powerset of 4 cards):

1. Sample 300 replacement hands from the remaining deck.
2. For each replacement hand, compute `hand_strength` using the tables and genome weights.
3. `expected_strength[subset] = mean(sampled strengths)`.
4. Apply aggressiveness bias: `score[subset] = expected_strength[subset] - discard_aggressiveness * penalty(len(subset))` where `penalty` is a small linearly decreasing function (high aggressiveness removes the penalty for discarding many cards).
5. Return the subset with the highest score.

The sampling uses `opponent_discard_counts` as a soft prior: cards whose value was
discarded more by opponents are slightly less likely to appear as replacement draws
(partial information update).

### 4.4 wager_action()

```
base_prob   = table[canonical(self.cards)][context.phase_name]

urgency     = compute_urgency(my_score_tier, opp_score_tier)
pos_signal  = compute_position_signal(context.position, n_players, position_preference)

modifier    = score_urgency_sensitivity * urgency * URGENCY_SCALE   # e.g. URGENCY_SCALE=0.2
            + pos_signal * position_sensitivity_scale                # e.g. 0.1

adjusted_prob = clamp(base_prob + modifier, 0, 1)

# Bluff override
if random() < bluff_rate:
    adjusted_prob = max(adjusted_prob, raise_threshold + 0.01)

# Decision
if adjusted_prob < fold_threshold:
    return -1                                        # fold
elif adjusted_prob < raise_threshold:
    return 0                                         # call / pass
else:
    min_raise = 1
    max_raise = context.current_bet                  # capped at doubling
    raise_amount = round(min_raise + risk_factor * (max_raise - min_raise))
    return raise_amount
```

**Parameter interaction with game state:**
- `score_urgency_sensitivity=0`: bot bets the same early game and crisis game.
- `score_urgency_sensitivity=1, urgency=1.0`: bot's adjusted_prob jumps +0.2 → more
  likely to raise when opponent is critical.
- `bluff_rate` is independent of game state — it's pure randomness baked into personality.
- `risk_factor` only affects *how much* the bot raises, not *whether* it raises.

---

## 5. Genetic Trainer

### Population and fitness

```python
class GeneticTrainer:
    population_size: int = 100
    generations: int    = 300
    games_per_eval: int = 10       # full games per bot per generation
    elite_fraction: float = 0.05
    survivor_fraction: float = 0.5
    mutation_rate: float = 0.15
    mutation_sigma: float = 0.05
```

**Fitness**: each bot plays `games_per_eval` full games (up to `WIN_SCORE=40`) paired
randomly with other bots from the population. Fitness = win rate across those games.

Teams are assembled by pairing bots from the same generation randomly, so no bot always
plays with the same partner. This prevents co-evolution of partner-specific strategies.

### Selection

Tournament selection: randomly sample 5 bots, pick the highest-fitness one as a parent.
Repeat until the next generation is filled.

### Evolution loop

```
for each generation:
    1. Evaluate fitness for all bots (parallel game runs)
    2. Copy top elite_fraction unchanged
    3. Fill remainder via tournament selection + uniform crossover + Gaussian mutation
    4. Log: best fitness, mean fitness, gene value distributions
```

### Output

After training, save the best genome to `best_genome.json`. The trainer also saves a
snapshot of the full population every 50 generations to enable resuming or analysis.

---

## 6. File Structure

```
mus_computer/
├── bot_genome.py          # BotGenome dataclass, crossover(), mutate(), random_genome()
├── probability_tables.py  # build_tables(), load_tables(), lookup(hand, phase)
├── bot_game_state.py      # ScoreTier, BotGameState, compute_urgency(), compute_position_signal()
├── bot_player.py          # BotPlayer(PlayerBase): all three decision methods
├── genetic_trainer.py     # GeneticTrainer class, run_tournament(), evolve()
├── build_tables.py        # one-off script: computes and saves probability_tables.pkl
│
├── game.py                # modified: tracks discard counts, calls set_round_state()
├── game_context.py        # extended: add position, opponent_discard_counts fields
├── player_base.py         # extended: add default no-op set_round_state()
```

No new external dependencies. Training uses Python's `multiprocessing` for parallel game
evaluation.

---

## 7. Constraints and open questions

- `fold_threshold` and `raise_threshold` should satisfy `fold_threshold < raise_threshold`
  for sensible behavior; the trainer does not enforce this — invalid genomes will just play
  oddly and be selected against naturally.
- The Punto phase (fallback when no one has Juego) is not in the probability tables
  (it's a pure showdown on point count). `wager_action` for Punto falls back to
  Grande-table probabilities as a proxy.
- Mus rules allow a maximum bet depth; the `max_raise` cap in `wager_action` is a
  placeholder — exact rule limits should be confirmed and enforced.
