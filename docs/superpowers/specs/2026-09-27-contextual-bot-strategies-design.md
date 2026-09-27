# Contextual Bot Decision Strategies

## Goal

Give each bot a consistent view of public game state, a private hand analysis derived from its own cards, and injectable decision strategies controlled by player personality parameters. Make wager choices phase-specific and probabilistic so deterministic one-action strategies can be tested before any strategy training begins.

This slice also fixes score settlement so the first team to reach 40 in phase order wins, and so a folded Pares/Juego wager does not suppress the wager-winning team's intrinsic hand points.

## Current Code

- `GameContext` is created by `WagerSession` only for wager decisions. Mus votes and discards receive no context.
- `Game._notify_players_round_state()` separately sends round state, and `BotPlayer` caches a compressed version in `BotGameState`.
- `BotPlayer` already uses a `BotGenome` and lookup-table probabilities, but its strategy is embedded in the player class. `api.py` currently runs `RandomBotPlayer`.
- The lookup tables expose per-hand win/tie/loss values for Grande, Chica, Pares, and Juego. They do not expose a per-hand Punto estimate. Punto currently falls back to Grande in `BotPlayer`.
- A folded wager is paid immediately. For Pares/Juego, the fold branch skips all intrinsic phase points.
- Normal phase awards are queued until after Juego/Punto, then all applied without stopping at 40. If both teams reach 40, `play()` selects by team-list order rather than score-event order.

## Data Passed to Decisions

Every decision receives an immutable pair of contexts and the bot's personality parameters. The two contexts have different visibility.

### Shared global context

`GlobalGameContext` contains only state available to every player:

- exact current score for each team;
- completed Mus exchanges in the current hand;
- current phase and active wager state, if any;
- public action/response history for this hand;
- public discard counts and stable seat order/mano information;
- the eligible seats for the current phase, where applicable.

It never contains any player's hand or statistics derived from another player's hidden hand. The same global snapshot is supplied to each player at the same decision point.

### Per-player private context

`PlayerDecisionContext` contains only the acting player's private hand and derived data:

- player/team identity and stable seat;
- the acting player's cards;
- phase eligibility and intrinsic points from those cards;
- `HandStatistics` from the probability provider: win, tie, and loss estimates by phase, plus estimated points by phase;
- discard alternatives and their expected post-draw phase estimates when the decision is a discard.

Keep raw cards distinct from `HandStatistics` so tests can inject controlled statistics without changing the hand. Statistics must be marked as estimates. The initial win/tie/loss values use the existing lookup tables against an unknown opponent hand; they do not claim to model the exact opposing team or reveal its cards. The expected-points value is an initial per-hand estimate derived from the probability estimate and that hand's intrinsic phase points. Team-level lookup outputs with fixed seat assumptions are not reused as general per-player estimates.

Add a Punto lookup estimate using Punto's actual comparison rule. Preserve tie probability separately; the acting player's seat/mano determines whether a tie is a win for decision purposes.

### Player personality

Keep decision parameters separate from both contexts. Reuse `BotGenome` as the first `BotPersonality` representation to preserve existing saved-genome compatibility. Strategies receive it explicitly; they do not read hidden bot state or cache scores from an earlier call. No genetic training or genome-schema changes are part of this slice.

## Strategy Portfolio and Outputs

Each bot owns an injectable `StrategyPortfolio` containing:

- a Mus-vote strategy;
- a discard strategy;
- a wager strategy for each wagerable phase: Grande, Chica, Pares, Juego, and Punto.

Each strategy receives `GlobalGameContext`, `PlayerDecisionContext`, and `BotPersonality`. Wager strategies are separate objects by phase so they can evolve independently while sharing a common interface. Mus and discard strategies use the same portfolio pattern.

Strategies return validated probability distributions over legal actions. Probabilities must be finite and nonnegative and sum to 1 within a small numeric tolerance. The player samples exactly one action from the returned distribution. A one-hot distribution therefore produces a deterministic action without mocking the sampler.

### Wager action categories

Use typed actions rather than overloading raw integers inside strategies:

- `ORDAGO`;
- `RAISE_5`, `RAISE_4`, `RAISE_3`, `RAISE_2`;
- `MATCH_OR_PASS`;
- `FOLD`.

`MATCH_OR_PASS` maps to `paso` before any wager is open and `quiero` when responding to an offer. `FOLD` has probability zero before an offer. The distribution still sums to 1 over the available actions. The game adapter preserves existing ordinary wager semantics: on an opening offer, raise 2 means a total stake of 2; on a counterraise, the same action adds 2 to the offered total. An accepted offer is accepted by one eligible player; a declined offer is declined only when every eligible defender has said `no quiero`.

The action selection returns a typed wager intent. `WagerSession` adapts ordinary intents to its existing stake resolution and handles ordago explicitly; strategies do not implement wager accounting themselves.

### Ordago resolution

Ordago is a match-level wager, but declining it does not concede the match:

- If accepted by one eligible defender, stop further wager responses immediately, resolve the phase by the cards, and make the phase winner the match winner. This ends the match even if neither numeric score has reached 40.
- If every eligible defender declines, the team that offered ordago wins only the last accepted wager stake, just as with an ordinary refused raise. If no raise has been accepted, this is the existing one-point stake already in play. The match continues unless that award takes a team to 40.
- An accepted ordago records a match winner independently of the ordinary numeric score total; the final event reports the ordago result rather than claiming the team reached 40.

## Phase Award and Match Resolution

- A folded wager awards the last accepted wager stake immediately to the offering team, as already specified. If this makes that team reach 40, the game ends immediately.
- On a folded Pares or Juego wager, also compute intrinsic points for the wager-winning team's eligible hands. Queue those points with the normal end-of-hand phase awards; do not discard them because the wager ended without a showdown. The folding team does not get these intrinsic points from that folded contest.
- Keep ordinary phase points queued until Juego/Punto finishes. Then settle the awards in phase order: Grande, Chica, Pares, then Juego or Punto. Check the score after each award and stop at the first team reaching 40. If both teams would cross 40 in one hand, the first award in that order decides the match.
- Preserve the event order: folded wager points are recorded immediately; deferred phase awards are recorded during ordered end-of-hand settlement.

## Testing

Tests use real context objects with injected statistics/strategies, not mocked player internals:

- the same global context is visible to each player while private hand statistics differ;
- changes in exact team scores, Mus count, or one phase probability affect only strategies that consume that input;
- each phase selects its own wager strategy;
- one-hot distributions for ordago, raises 2–5, match/pass, and fold produce the matching legal player action;
- accepting an ordago resolves the phase immediately and ends the match for that phase winner; refusing it awards only the last accepted stake and does not end the match;
- illegal or malformed distributions fail clearly; legal distributions sum to 1;
- opening and counterraise semantics map correctly, with only phase-eligible players responding;
- folded Pares/Juego payouts include the immediate accepted stake and the wager-winning team's deferred intrinsic points (Pares 1/2/3 and Juego 2/3);
- first-to-40 tests cover immediate folded-wager awards and deferred phase-order awards;
- Punto probabilities agree with direct comparisons under controlled hands and include ties.

Do not run training games as a measure of strategy quality in this slice.

## Scope Boundaries

- No learned policy, parameter optimization, or genetic-trainer execution.
- No use of opponent private cards or hidden-card-derived statistics.
- No broader game-rule changes beyond the stated fold bonus and first-to-40 ordering.
- Keep `RandomBotPlayer` available as a simple baseline; the strategy portfolio applies to the strategic bot and does not require changing the terminal runner unless needed to demonstrate the new player.
