# Best Discards Computation — Design Spec

**Date:** 2026-06-06
**Script:** `compute_best_discards.py`
**Depends on:** `probability_tables.pkl` with `ep_mano` populated (run `compute_expected_points.py` first)

---

## Goal

Produce a rich per-hand discard summary stored back into `probability_tables.pkl`, replacing the current `discard_options` structure (which uses 1v1 `p_win` as its metric) with expected tantos derived from the 4-player `ep_mano` table.

---

## Inputs and outputs

**Input:** `probability_tables.pkl`
- Must contain `tables[hand]["ep_mano"]` for every hand.
- Script skips any hand where `ep_mano` is missing and warns to stderr.

**Output:** same `probability_tables.pkl` with two new keys per hand:
- `tables[hand]["best_discards"]`
- `tables[hand]["no_discard_stats"]`

---

## Core computation per hand

For each of the 330 canonical hands:

1. **Enumerate all kept subsets** — all 32 subsets of the 4 cards (keeping 0–4 cards), deduplicated by canonical form. This is the same enumeration as the existing `_compute_discard_options`.

2. **For each kept subset, compute weighted-average ep_mano after drawing:**
   - `n_draw = 4 - len(kept)`
   - Enumerate all `combinations_with_replacement` over the remaining deck (deck minus `hand` minus any cards re-added by the discard)
   - Weight each draw outcome by `_mult_from_counts(draw_combo, remaining_deck)`
   - Look up `tables[new_hand]["ep_mano"]` for the completed hand
   - Compute weighted averages of all ep_mano fields across draw outcomes

3. **Derive summary scalars** from the averaged ep_mano:
   - `total_net_A` = `sum(expected_net_A[phase] for phase in [Grande, Chica, Pares, Juego, Punto])`
   - `total_action` = `sum(expected_A_points[phase] + expected_B_points[phase] for phase in all 5 phases)`
   - `juego_punto_net_A` = `expected_net_A[Juego] + expected_net_A[Punto]`
   - per-phase `net_A[phase]` for Grande, Chica, Pares

---

## Data written per hand

### `tables[hand]["best_discards"]`

```python
{
    "top10_net": [
        {
            "kept": <canonical tuple>,
            "total_net_A": float,
            "net_per_phase": {
                "Grande": float, "Chica": float, "Pares": float,
                "Juego": float, "Punto": float
            }
        },
        # … up to 10 entries, sorted descending by total_net_A
        # "keep all 4" is EXCLUDED from this list
    ],

    "best_by_phase": {
        # Each value is the kept hand that maximises that phase's metric
        "Grande": {"kept": <tuple>, "net_A": float},
        "Chica":  {"kept": <tuple>, "net_A": float},
        "Pares":  {"kept": <tuple>, "net_A": float},
        "Juego":  {"kept": <tuple>, "net_A": float},
        # Juego metric = net_A[Juego] + net_A[Punto]; label stays "Juego"
        # Punto is NOT a separate best_by_phase entry
    },

    "max_action_kept": {"kept": <tuple>, "total_action": float},
    "min_action_kept": {"kept": <tuple>, "total_action": float},
}
```

### `tables[hand]["no_discard_stats"]`

Baseline for the option of keeping all 4 cards (no discard).

```python
{
    "rank": int,          # position of "keep all" among ALL options sorted by total_net_A (1 = best)

    "improvement_by_phase": {
        # For each phase: best_by_phase[phase].net_A  –  no_discard.net_A (for that phase's metric)
        "Grande": float,
        "Chica":  float,
        "Pares":  float,
        "Juego":  float,  # uses juego_punto_net_A for both sides of the delta
    },

    "delta_total_net_vs_best": float,
    # top10_net[0].total_net_A – no_discard.total_net_A
    # (0.0 if "keep all" is already the best option)

    "action_vs_max": float,
    # max_action_kept.total_net_A – no_discard.total_net_A
    # positive = high-variance discard is better for your team in net terms

    "action_vs_min": float,
    # no_discard.total_net_A – min_action_kept.total_net_A
    # positive = you are already doing better in net than the low-variance play
}
```

---

## Script structure

```
compute_best_discards.py
├── load pickle
├── guard: warn if ep_mano missing for any hand
├── for each hand (progress log per hand):
│   ├── enumerate kept subsets
│   ├── for each kept: weighted-average ep_mano after draw → summary scalars
│   ├── build best_discards entry
│   └── build no_discard_stats entry
└── save pickle
```

No multiprocessing needed — the computation is O(330 × 32 × small draw combos) with pure dict lookups. Expected runtime: seconds.

---

## Edge cases

- **`ep_mano` missing for a hand:** skip that hand, print warning, continue. Do not abort.
- **Fewer than 10 valid discard options** (e.g., mono-deck in tests): `top10_net` has fewer than 10 entries — this is fine.
- **"Keep all" is already the best option:** `rank = 1`, `delta_total_net_vs_best = 0.0`.
- **Ties in ranking:** stable sort; "keep all" is excluded from `top10_net` regardless of rank.
- **`n_draw = 0` (keep all 4):** no draw enumeration; `new_hand = canonical(kept)`, ep_mano looked up directly.

---

## What this replaces / does not replace

- **Does not touch** `discard_options` (the existing p_win-based structure). That key stays in the pickle for backward compatibility with the current `BotPlayer`.
- `BotPlayer.choose_discards()` currently uses Monte Carlo sampling, not the table at all. Wiring the new table into the bot is a separate task.
