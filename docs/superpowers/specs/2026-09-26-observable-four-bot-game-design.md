# Observable Four-Bot Mus Game

**Date:** 2026-09-26
**Status:** User-directed first playable slice

## Goal

Run one complete 2v2 Mus match with four randomly acting bots and show a readable terminal feed of what they do. This slice is for observing a game; human-controlled seats and strategic decisions are later work.

## Agreed gameplay

- Seats alternate teams: A, B, A, B. Every player starts each hand with four cards.
- At the start of each hand, players vote on Mus in seat order. The first `corta` ends the Mus offer and phases begin with current hands. If everyone says `mus`, every player may discard zero to four cards and draw the same number, then the Mus vote repeats.
- The deck tracks a discard pile across exchanges in a hand. If the draw stock cannot satisfy a player's entire draw, combine the remaining stock with the discard pile, shuffle, and draw from the replenished stock.
- After Mus ends, play Grande, Pequeña (the existing code name is Chica), Pares, and Juego. Preserve the current Punto fallback when nobody qualifies for Juego.
- Start a new hand after the phases. End the match as soon as either team reaches 40 points.
- Random bots do not inspect probability tables or choose strategically. They randomly vote Mus, select any discard count from zero to four, and pass, raise, or fold in the existing wager interface.

## Terminal behavior

The four-bot runner starts without asking for input. It prints each bot's hand after the initial deal and after every completed Mus exchange, then actions in order as they happen, phase results, score changes, and the winning team. Card ranks use their short values (A, 4, 5, 6, 7, S, C, R). Example action wording:

```text
Hands | Bot 1: R C 7 A
Hands | Bot 2: S 6 4 A
Hands | Bot 3: 7 7 C A
Hands | Bot 4: R S 5 4
Mus | Bot 1: mus
Mus | Bot 2: corta
Grande | Bot 1: paso
Grande | Bot 2: envida 1
Grande | Bot 3: quiero
Team A +1 | Score A 1 - B 0
```

The log reports when the discard pile is shuffled into the stock. A missing action callback keeps game simulations silent.

## Architecture

- Keep the current `PlayerBase` decision interface.
- Add `RandomBotPlayer` in `random_bot_player.py`; leave the existing genome-based `BotPlayer` available.
- Add `Game.from_players(players_in_order, on_action=None)`. It accepts four players in alternating A/B/A/B order, initializes the same game state as the existing constructor, and optionally emits complete action strings through `on_action`.
- Keep the existing name-based `Game(...)` constructor for compatibility.
- Thread the optional action callback into `WagerSession` so votes, discards, phase entry, wagers, outcomes, and scoring share one ordered log.
- Make `api.py` the bot-only entry point for this slice: create Bot 1/A, Bot 2/B, Bot 3/A, Bot 4/B, and run the match with `print` as the callback.
- Update the genetic trainer's game builder to use the public factory and alternating team seats, without enabling logs during training.

## Scope limits

- No human interaction or human-versus-bots setup in this slice.
- No changes to the probability tables, genome strategy, or training algorithm beyond correcting seat assignment for the shared engine.
- The one-exchange post-Mus table model remains an analytical approximation; it does not define runtime Mus rules.

## Completion criteria

- `python api.py` starts a four-bot match without input and reports actions in readable order through the 40-point finish.
- The game can repeat Mus exchanges, including zero-card discards, without losing cards when the stock needs replenishment.
- The printed action sequence shows all four current hands at the deal/exchange checkpoints, uses `mus`/`corta`, Mus phase names, wager actions such as `paso`/`envida`/`quiero`, and reports score results.
- Existing strategic bots can still be constructed in alternating seats through the game factory.
