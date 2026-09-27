# Mus computer roadmap

## Active milestone: observable four-bot game

**Goal:** Run a complete 2v2 Mus game with four random bots and show a readable, live terminal log of their actions and the score. Human-controlled seats and strategic bot decisions come later.

### Agreed runtime rules

- Four players sit in alternating team order: A, B, A, B. Each hand starts with four cards per player.
- Mus voting proceeds in seat order. The first `corta` stops Mus and starts Grande with the current hands. If everyone says `mus`, each player may discard zero to four cards and draw replacements; voting then repeats.
- The draw stock is replenished by shuffling the discard pile into it whenever the stock cannot satisfy a requested draw. Discards remain available between exchanges within a hand.
- Play Grande, Pequeña (the code calls this Chica), Pares, then Juego. Keep the existing Punto fallback when nobody qualifies for Juego.
- A wager is a team action: one envida speaks for the pair, one eligible `quiero` accepts, and all eligible players on the answering team must say `no quiero` to decline. The opening offer is a total: 1 keeps the base point in play and bare `envida` defaults to 2. A later envida adds its amount. A declined raise awards the earlier accepted stake.
- Apply ordinary phase points together after Juego or Punto. Award a declined wager's accepted stake immediately.
- Start a new hand with Mus after the phases. Stop the match as soon as either team reaches 40 points.
- Random bots choose actions without strategy. The terminal log shows every bot's hand after the initial deal and each completed Mus exchange, as well as public actions and scores.

### Milestone phases

1. **Game lifecycle and rules:** Accept an injected four-player roster in A/B/A/B order; support repeated Mus, discard-pile reshuffles, phase ordering, and ending immediately at 40. Emit an optional action stream for the terminal runner, including visible stock replenishment.
2. **Random bot:** Implement a `PlayerBase` that randomly votes Mus, chooses any discard count from zero to four, and passes, raises, or folds during wagers.
3. **Four-bot terminal runner:** Start four named bots automatically and print each bot's hand after the deal and completed exchanges, plus readable lines for votes, discards, phases, wagers, score changes, and winner. Use Mus terms such as `mus`, `corta`, `paso`, `envida`, and `quiero`.
4. **Integration:** Keep the strategic bot/trainer compatible with the shared seat order and ensure the bot-only runner is silent when no action callback is supplied.

### Parallel work packages

- **Game engine:** `game.py`, `deck.py`, `wager_session.py`, and `genetic_trainer.py`. Add `Game.from_players(players_in_order, on_action=None)`, where the four seats are A/B/A/B and `on_action` receives a complete log line.
- **Random policy:** Add `random_bot_player.py`, implementing the existing `PlayerBase` interface without changing `BotPlayer`.
- **Terminal runner:** Update `api.py` to construct Bot 1 (A), Bot 2 (B), Bot 3 (A), and Bot 4 (B), then pass `print` as the action callback.

### Later milestones

- Add human-versus-bots setup and human action prompts.
- Replace random choices with table-informed bot decisions and improve tournament evaluation.

## Table-model backlog

The analytical post-Mus tables remain a one-exchange approximation; that assumption does not limit runtime gameplay, which repeats Mus until someone says `corta`.

- [x] Generate the 330 canonical-hand probability and expected-points artifacts.
- [x] Generate the one-exchange post-Mus distribution and post-Mus-aware discard summaries.
- [ ] Align replacement-card enumeration with the table's one-exchange model: draw from the marginal pool after removing the player's original four cards. Other copies of a discarded rank remain available; the exact initial copies do not return during that modeled exchange.
- [x] Document the wager convention: +0.5 applies only to Pares/Juego when both teams have a qualifying hand; Grande/Chica award their base point regardless of wagering.
- [ ] Revisit post-Mus weighting: compare compatibility-ratio weighting or source-conditioned transitions with the current physical-multiplicity weighting.
- [ ] Extend expected-points tables to fixed hands in seats 1, 2, and 3, preserving seat order and tie priority.
- [ ] Compare the unordered opponent-pair formula against independent ordered-seat enumeration.
- [ ] Rebuild tables and compare them with independent small-deck and rule-level references after model fixes.
- [ ] Declare table-generation dependencies, including NumPy, for local and CI runs.
