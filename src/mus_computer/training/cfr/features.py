"""Small declarative betting features from own estimates and public events."""

import re
from collections.abc import Mapping
from dataclasses import dataclass

from mus_computer.bots.strategies.contexts import PlayerDecisionContext
from mus_computer.game.context import GlobalGameContext
from mus_computer.game.phases import PhaseName

PREVIOUS_LANCES = {
    PhaseName.GRANDE: (),
    PhaseName.CHICA: (PhaseName.GRANDE,),
    PhaseName.PARES: (PhaseName.GRANDE, PhaseName.CHICA),
    PhaseName.JUEGO: (PhaseName.GRANDE, PhaseName.CHICA, PhaseName.PARES),
    PhaseName.PUNTO: (PhaseName.GRANDE, PhaseName.CHICA, PhaseName.PARES),
}
BETTING_STAGES = ("opening", "response", "counter_raise", "ordago_response")
OFFER = re.compile(r"(?:ordago|envida(?: [2-5](?: \(total \d+\))?)?)\Z")


@dataclass(frozen=True)
class BettingFeatures:
    block: str
    values: Mapping[str, float]


def feature_names(phase: PhaseName) -> tuple[str, ...]:
    return ("baseline", "hand_strength") + tuple(
        f"opponent_wager_{previous.value}" for previous in PREVIOUS_LANCES[phase]
    )


def betting_features(
    public: GlobalGameContext, private: PlayerDecisionContext
) -> BettingFeatures:
    """Count only emitted envida/ordago offers, never calls, folds or passes.

    Team identity comes from public seat labels, not position or hidden cards.
    Repeated offers remain a single binary indicator. Juego and Punto are
    alternatives, so neither uses the other's events.
    """
    phase = public.phase_name or private.phase_name
    if phase is None:
        raise ValueError("Betting features require a lance")
    teams = {entry.player_name: entry.team_name for entry in public.seat_order}
    offers: list[tuple[str, str]] = []
    for event in public.public_actions:
        label, separator, message = event.partition(" | ")
        player, colon, action = message.rpartition(": ")
        if separator and colon and player in teams and OFFER.fullmatch(action):
            offers.append(("Chica" if label == "Pequeña" else label, player))
    wager = public.wager
    if wager is None or wager.offering_team is None:
        stage = "opening"
    elif wager.ordago_offered:
        stage = "ordago_response"
    elif sum(label == phase.value for label, _ in offers) >= 2:
        stage = "counter_raise"
    else:
        stage = "response"
    values = {
        "baseline": 1.0,
        "hand_strength": 1.0 - private.statistics.outcomes_by_phase[phase].p_loss,
    }
    for previous in PREVIOUS_LANCES[phase]:
        values[f"opponent_wager_{previous.value}"] = float(
            any(
                label == previous.value and teams[player] != private.team_name
                for label, player in offers
            )
        )
    return BettingFeatures(f"{phase.value}/{stage}", values)
