# Mus Computer: technical reference

This document describes the runtime rules and the lookup table model. The default terminal game has four random bots. Contextual `BotPlayer` strategies are implemented and available through the Python API; their default policy is heuristic and untrained. See the [roadmap](TODO.md) for progress and the [root README](../../README.md) for installation and play commands.

The repository separates the playable game from offline analysis:

1. `src/mus_computer/cards/` and `src/mus_computer/game/` hold the 40-card game and scoring code.
2. `src/mus_computer/bots/` holds the random baseline and strategic bot code.
3. `src/mus_computer/probabilities/` holds lookup access and bundled table data; `scripts/tables/` builds and exports tables offline.
4. `src/mus_computer/training/` holds experimental genetic training code.

## Lookup tables

The bundled probability table covers all 330 canonical four-card rank hands. Entries include per-phase head-to-head win, tie, and loss estimates; replacement-hand estimates for retained subsets; team expected-points tables (`ep_mano` and `ep_mano_postmus`); and baseline and post-Mus-aware discard summaries. It also contains marginal hand distributions, including `hand_distribution_post_mus`. `mus_computer.probabilities.tables.load_tables()` reads the bundled copy, with an explicit file path supported for a local override.

The offline builders under `scripts/tables/` produce the data and human-readable reports. They need the optional NumPy table tooling: `python -m pip install -e ".[tables]"` (or use the root README's `[dev]` setup). For example, run a builder as `python -m scripts.tables.build_tables`. Builders write generated output to an explicit destination or the repository root; they do not modify installed package data by default. See the [lookup table index](lookup-tables/README.md) for the pipeline and its assumptions.

These outputs exist, but several calculations still need validation against the intended model. The discard builders restore the player's exact discarded copies to the draw pool. The post-Mus expected-points worker uses aggregate final-hand probabilities together with physical multiplicity as a working assumption; its effect on marginal weights remains open for review. The optimized expected-points calculation uses an unordered opponent-pair shortcut for a fixed mano hand in seat 0.

## Runtime game rules

- Four players occupy alternating A/B/A/B seats, with four cards each.
- Mus voting proceeds in seat order. If anyone says `corta`, play starts with the current hands. If all players say `mus`, each may discard zero to four cards and draw replacements; then voting repeats.
- When the draw stock cannot satisfy a requested draw, the discard pile is shuffled into it. Discards remain available between exchanges within a hand.
- Play Grande, Pequeña (Chica in code), Pares, and Juego; use Punto when nobody qualifies for Juego.
- A wager is a team action. One player's `envida` speaks for the pair. A single eligible opponent saying `quiero` accepts the current offer and ends wagering; every eligible opponent on that team must say `no quiero` to decline it. One point is already in play; `envida 1` is not a legal opening action. The opening offer sets a total: bare `envida` means 2 points total, including that base point. A later `envida N` adds N to the current offer. A declined offer immediately awards the previously accepted stake to the offering team.
- Ordinary phase awards are settled after Juego or Punto, in Grande, Chica, Pares, Juego/Punto order. A folded Pares or Juego wager still leaves the winning team's eligible intrinsic hand points for that settlement. Score events are checked in order; the first team to reach 40 wins.
- An accepted `ordago` compares the phase's hands and immediately awards the match to the winning team. A refused `ordago` awards only the previous accepted stake and play continues, unless that award reaches 40.

The [contextual strategy design](../superpowers/specs/2026-09-27-contextual-bot-strategies-design.md) specifies the public game context, each player's private hand statistics, personality parameters, and injectable decision strategies. The default terminal runner uses `RandomBotPlayer`; it does not evaluate strategy quality.

## Analytical table-model scope

- Cards are grouped by rank; suits do not affect modeled decisions.
- The deck has eight A cards, eight R cards, and four of each other rank.
- The current post-Mus distribution models one discard-and-replacement exchange. After the initial deal, 24 cards remain in the stock; at most 16 replacements are needed in that modeled exchange. Runtime play may have more exchanges.
- Players who Mus are modeled as taking the best discard from the expected-points table. The resulting distribution is a proxy for hands after Mus, not a model of each player's probability of voting Mus.
- The fixed +0.5 expected wager contribution applies only to Pares and Juego when both teams have a qualifying hand. Grande and Chica award their base point to the best hand whether or not anyone wagers, so they receive no +0.5 adjustment. See [Team expected points](lookup-tables/team-expected-points.md).

Earlier files in `docs/superpowers/` record design and implementation decisions. This document is the reference for the present table pipeline and calls out assumptions that still require checking.
