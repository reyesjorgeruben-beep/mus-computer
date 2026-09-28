# Mus Computer

A terminal Mus game for four bots in two teams. Bot 1 and Bot 3 play for Team A; Bot 2 and Bot 4 play for Team B. The default game prints each bot's cards, Mus votes, discards, wagers, score changes, and winner. The four seats currently use `RandomBotPlayer`.

## Install and play

Python 3.10 or newer is required. Editable installs use PEP 660 and need pip 21.3+ and setuptools 64+. If your environment has older packaging tools, update them first. From the repository root:

```sh
python -m pip install -e ".[dev]"
python -m mus_computer
```

`python api.py` remains a compatibility entry point for the same four-bot game. The installed `mus-computer` command also runs it. Run the tests with:

```sh
python -m pytest tests/
```

## How a match works

Each bot receives four cards. In seat order, players say `mus` or `corta`. If everyone says `mus`, each may exchange zero to four cards and the Mus vote repeats. A `corta` starts play with the current hands. The discard pile replenishes the draw deck when needed.

The hand proceeds through Grande, Chica (Pequeña), Pares, and Juego, or Punto when no one has Juego. Wagers are made for a team. One eligible defender's `quiero` accepts a wager; every eligible defender must say `no quiero` to reject it. An opening `envida` sets the total stake (bare `envida` means two points); a later `envida N` adds N to the current offer. A refused offer gives the offering team the previously accepted stake immediately. Other phase awards are settled after Juego or Punto, in phase order. The first team to reach 40 wins. An accepted `ordago` settles the match immediately by the phase's cards; refusing it awards only the previous stake.

The terminal runner is a random-play baseline. A separate contextual bot is under development. Its design calls for public game state, the acting bot's cards and estimated hand statistics, and personality parameters to feed injectable, phase-specific decision strategies. It is not selected by the default runner. The planned estimates use lookup tables; they are not a trained policy.

## Repository layout

| Path | Purpose |
|---|---|
| `src/mus_computer/cards/` | Cards, deck, and hands |
| `src/mus_computer/game/` | Match lifecycle, phases, teams, and wagers |
| `src/mus_computer/bots/` | Random and contextual bot players and strategies |
| `src/mus_computer/probabilities/` | Packaged lookup data and hand estimates |
| `src/mus_computer/training/` | Experimental genetic training code |
| `scripts/tables/` | Offline table builders and exports |
| `tests/` | Unit and game tests |

The bundled probability table is read-only package data. Table generation and reports are separate offline work. The post-Mus analytical model covers one exchange, while the playable game repeats Mus until someone cuts. Several table assumptions still need validation; see the [technical reference](docs/mus-computer/README.md) and [lookup table guide](docs/mus-computer/lookup-tables/README.md).

Offline table builders use NumPy. Install their optional dependencies with `python -m pip install -e ".[tables]"` if you are running them outside the development setup above.

See the [roadmap](docs/mus-computer/TODO.md) for milestone status and the [contextual strategy design](docs/superpowers/specs/2026-09-27-contextual-bot-strategies-design.md) for decision interfaces and scoring rules.
