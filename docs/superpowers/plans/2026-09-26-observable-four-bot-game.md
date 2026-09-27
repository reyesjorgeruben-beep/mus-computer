# Observable Four-Bot Mus Game — Implementation Plan

**Design:** `docs/superpowers/specs/2026-09-26-observable-four-bot-game-design.md`

## Goal

Run a full 2v2 Mus match from `python api.py` with four random bots, live readable action logs, repeated Mus exchanges, correct card recycling, and a 40-point finish.

## Shared interface contract

- `Game.from_players(players_in_order, on_action=None)` accepts exactly four `PlayerBase` objects in A/B/A/B order. Seats 0 and 2 share one team; seats 1 and 3 share the other.
- `on_action` is optional and accepts one complete human-readable string per event. When omitted, simulation remains silent.
- `RandomBotPlayer(name, team)` implements `vote_mus()`, `choose_discards()`, and `wager_action(context)` using random legal actions; it has no genome or table dependency.
- The terminal runner creates `Bot 1` in A, `Bot 2` in B, `Bot 3` in A, and `Bot 4` in B, then passes `print` as `on_action`.
- No worker edits files assigned to another worker. The workers share the repository, so they must preserve one another's changes.

## Parallel tasks

### Task 1 — Game lifecycle, deck, logging, and trainer seats

**Owner:** Game-engine worker

**Files:** `game.py`, `deck.py`, `wager_session.py`, `genetic_trainer.py`

- Add `Game.from_players(...)` with the shared contract and preserve the existing name-based constructor.
- Implement repeated Mus voting. Emit the action for each vote; stop asking after the first `corta`. If every player says `mus`, ask each for discards (including zero), put discarded cards in the deck's discard pile, draw replacements, then vote again.
- Keep the discard pile across Mus exchanges within a hand. If the draw stock has fewer cards than a player's requested draw, combine stock and discard pile, shuffle, then fulfill the complete draw.
- Emit a readable line when the stock is replenished from discards.
- Emit all four current hands after the initial deal and after each complete Mus exchange, using `card.value` for readable ranks.
- Preserve the phase order and Punto fallback. Emit readable phase, wager, outcome, and score events through the callback.
- Stop the remaining phases as soon as a team reaches 40. Return the winning `Team` from `play()`.
- Update the trainer's bot game builder and team attribution to use alternating A/B/A/B seats and the public game factory. Do not turn on action logs in training.

### Task 2 — Random bot

**Owner:** Bot-policy worker

**Files:** create `random_bot_player.py`

- Implement `RandomBotPlayer(PlayerBase)` independently of `BotGenome` and probability tables.
- Vote Mus randomly.
- Pick a uniformly random discard count from zero through the current hand size, then return unique valid indices.
- Randomly choose fold, pass/call, or a small positive raise using the `PlayerBase` wager protocol.
- Do not print from inside the player. `Game` owns the action feed so bot-only games can run silently without a callback.

### Task 3 — Four-bot terminal runner

**Owner:** Terminal-runner worker

**Files:** `api.py`

- Construct four `RandomBotPlayer` instances in alternating A/B/A/B order.
- Start the complete match automatically when run as a script and pass `print` as the action callback.
- Keep the output focused on current hands, public actions, phase results, score, and winner. Do not request human input.
- Use labels `Pequeña` for the `Chica` phase and Mus terms such as `mus`, `corta`, `paso`, `envida`, and `quiero` in user-facing output.

## Integration ownership

The primary agent owns `docs/mus-computer/TODO.md`, `docs/mus-computer/README.md`, and the integration review. After the parallel tasks finish, review the shared interface and changed files together. Do not run or add tests in this task; report any unverified behavior clearly.

## Acceptance checklist

- The runner starts four bots and needs no keyboard input.
- Mus continues through successful exchanges until a player says `corta`.
- A player can keep all cards; discarded cards recycle into the stock when needed.
- The match starts a new hand after the phases and ends at 40 points.
- Each bot's hand is printed after the initial deal and every complete Mus exchange.
- Action, phase, wager, score, and winner lines are emitted in order.
- Stock replenishment is reported when it occurs.
- The game engine and trainer use the same alternating team seat order.
