"""Observable information states, action identifiers, and sampled decision records."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass

from mus_computer.bots.strategies.actions import (
    DecisionKind,
    DiscardAction,
    MusAction,
    WagerAction,
)
from mus_computer.bots.strategies.contexts import PlayerDecisionContext
from mus_computer.game.context import GlobalGameContext

Action = MusAction | DiscardAction | WagerAction


def action_name(action: Action) -> str:
    """Give typed actions stable, JSON-compatible identifiers."""
    if isinstance(action, DiscardAction):
        return "discard:" + ",".join(map(str, action.indices))
    return f"{type(action).__name__}:{action.value}"


def information_key(
    kind: DecisionKind,
    public: GlobalGameContext,
    private: PlayerDecisionContext,
    legal: tuple[Action, ...],
) -> str:
    """Describe observable state using the same canonical card order as discards."""
    return json.dumps(
        {
            "kind": kind.value,
            "seat": private.seat,
            "team": private.team_name,
            "cards": [card.value for card in sorted(private.cards, reverse=True)],
            "scores": [public.team_scores["A"], public.team_scores["B"]],
            "mus_exchanges": public.mus_exchanges,
            "phase": public.phase_name.value if public.phase_name else None,
            "wager": None
            if public.wager is None
            else [
                public.wager.current_total,
                public.wager.previous_accepted_total,
                public.wager.offering_team,
                public.wager.ordago_offered,
            ],
            "public_actions": public.public_actions,
            "discard_counts": [
                public.discard_counts.get(entry.player_name, 0)
                for entry in public.seat_order
            ],
            "eligible_seats": public.eligible_seats,
            "legal": [action_name(action) for action in legal],
        },
        separators=(",", ":"),
    )


@dataclass(frozen=True)
class DecisionRecord:
    ordinal: int
    seat: int
    key: str
    actions: tuple[str, ...]
    prior: Mapping[str, float]
    strategy: Mapping[str, float]
    selected: str
    own_reach: float
    opponent_reach: float
    behavior_reach: float
