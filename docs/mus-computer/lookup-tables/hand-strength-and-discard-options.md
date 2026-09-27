# Hand strength and discard-option tables

## What they expose

For each of the 330 canonical four-card hands:

- Grande, Chica, Pares, and Juego entries with p_win, p_tie, and p_loss.
- For each unique retained subset, expected per-phase p_win after drawing back to four cards.
- Per-hand best attainable improvement by phase, plus an average opponent improvement by phase.

The runtime accessors are in probability_tables.py. The builder is build_tables.py.

## Construction

### Phase probabilities

For each canonical hand and phase, the builder compares it against every canonical four-card opponent hand. Each opponent hand contributes its physical-card multiplicity. The weighted win, tie, and loss totals are normalized into probabilities.

The current reference opponent distribution is a full-deck hand distribution. It is not conditioned on removing the caller's known cards. These values are therefore exact for that reference distribution, rather than exact conditional odds given a known hand.

Pares and Juego are scored here as hand comparisons even for hands that would not qualify to participate in those phases. In live play, only qualifying players can wager in Pares or Juego.

### Discard options

For a starting hand, the builder enumerates all retained subsets, deduplicating identical rank hands. For each option it enumerates possible draw rank compositions, weights them by the number of physical card combinations, completes the hand, and averages the phase win probabilities of that completed hand. No random samples are used in this calculation. A one-player marginal can integrate over unknown opponents, but this does not make independently combining four such marginals an exact model of the joint deal.

The average opponent improvement table is a deal-frequency-weighted mean of the per-hand improvement values.

## One-exchange draw assumption

At rank level, remove the player's original four cards from the deck before enumerating replacement draws. The exact physical cards in that initial hand, including the discarded ones, cannot return during this exchange. Other copies of the same ranks remain drawable. This marginal model integrates over the identities of the other players' hidden cards; it does not model the joint stock and draw sequence for all four seats.

Let C_r be the full-deck count of rank r, h_r the count in the player's original hand, and d_r the count in a proposed draw. The available count is A_r = C_r - h_r. A draw composition has physical weight:

    weight(draw | h) = product over ranks r of choose(A_r, d_r)

The probability is that weight divided by choose(36, n_draw), since 36 cards remain after conditioning on the player's initial four. This automatically allows another copy of a discarded rank while excluding the exact physical copy dealt initially.

The current builders first remove the original hand, then add the discarded counts back. Their pool is therefore full deck minus kept cards, and it overstates the availability of each discarded rank by restoring those exact copies. The live BotPlayer sampler removes the full current hand and does not restore discards, so it follows the one-player marginal pool more closely than the lookup builders do.

## Runtime status

BotPlayer uses win_prob and average opponent improvement. It does not use the precomputed discard_options table; vote_mus and choose_discards still sample replacement hands.
