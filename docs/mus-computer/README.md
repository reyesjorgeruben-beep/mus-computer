# Mus computer: current technical reference

This folder records the current table model and the assumptions agreed for the next bot iteration. It describes the local working tree, including the generated probability table and the post-mus analysis files.

The project has four related parts:

1. A 40-card Mus game model and scoring code in the repository root.
2. Offline combinatorial calculations that generate lookups for the 330 possible four-card rank hands.
3. A prototype bot and genetic trainer.
4. Reports and CSV exports for inspecting the generated tables.

The immediate milestone is a complete 2v2 game played by four random bots, with a live terminal log of their cards, actions, and scoring. Runtime Mus repeats until a player says `corta`; the analytical post-Mus tables continue to use a one-exchange approximation. See the [roadmap](TODO.md).

## Current table state

The local probability_tables.pkl contains entries for all 330 canonical hands. Each hand entry currently includes:

- Per-phase head-to-head win, tie, and loss probabilities.
- Expected win probabilities for each retained subset after drawing replacements.
- The pre-mus team expected-points table, ep_mano.
- The post-mus expected-points table, ep_mano_postmus.
- Baseline and post-mus-aware best-discard summaries.

The pickle also has marginal hand distributions, including hand_distribution_post_mus. See the [lookup table index](lookup-tables/README.md) for the outputs and their assumptions.

These outputs exist, but several calculations still need validation against the intended model. The discard builders restore the player's exact discarded copies to the draw pool. The post-mus expected-points worker uses aggregate final-hand probabilities together with physical multiplicity as a deliberate working assumption; its effect on the marginal weights is documented for later review. The optimized expected-points calculation uses an unordered opponent-pair shortcut for a fixed mano hand in seat 0.

## Runtime game rules

- Four players occupy alternating A/B/A/B seats, with four cards each.
- Mus voting proceeds in seat order. If anyone says `corta`, play starts with the current hands. If all players say `mus`, each may discard zero to four cards and draw replacements; then Mus voting repeats.
- When the draw stock cannot satisfy a requested draw, shuffle the discard pile into the stock. Discards remain available between exchanges within the hand.
- Play Grande, Pequeña (Chica in code), Pares, and Juego; use the existing Punto fallback when nobody qualifies for Juego.
- Wagers are handled for the two teams. One player's envida or counter-envida is made for their pair. A single eligible opponent saying `quiero` accepts the current total and ends that phase's wagering; every eligible opponent on that team must say `no quiero` to decline it. The opening offer is a total (`envida 1` keeps the base point in play; bare `envida` defaults to 2). A later `envida N` adds N to the current offer. A declined raise awards the previously accepted stake to the offering team.
- Normal phase points are added to the score after Juego or Punto finishes. A declined wager's already accepted stake is awarded immediately.
- Begin a new hand with Mus after those phases. The match ends as soon as a team reaches 40 points.

## Analytical table-model scope

- Cards are grouped by rank; suits do not affect the modeled decisions.
- The deck has eight A cards, eight R cards, and four of each other rank.
- The current post-Mus distribution models one discard-and-replacement exchange. After the initial deal, 24 cards remain in the stock; at most 16 replacements are needed in that modeled exchange.
- Players who Mus are modeled as taking the best discard from the expected-points table. The resulting distribution is a proxy for hands after Mus, not a model of each player's probability of voting Mus.
- The fixed +0.5 expected wager contribution applies only to Pares and Juego when both teams have a qualifying hand. Grande and Chica award their base point to the best hand whether or not anyone wagers, so they receive no +0.5 adjustment. See [Team expected points](lookup-tables/team-expected-points.md).

## Reading older design notes

The documents under docs/superpowers are historical design and implementation artifacts. Some details there describe earlier plans rather than current code. This folder is the current reference for the table pipeline and labels what is implemented, assumed, or still to be checked.

## Repository status

The table artifacts and the post-mus analysis scripts are local work. At the time of this review, local dev is two commits ahead of origin/dev and has uncommitted table/report changes. The GitHub branch does not yet include this complete table state.
