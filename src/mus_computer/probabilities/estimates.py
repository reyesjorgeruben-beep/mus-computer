"""Per-hand estimates from the bundled decision tables.

These are estimates against an unknown opposing hand, not observations of any
opponent's private cards or a full opposing team model.
"""

from collections import Counter
from functools import lru_cache
from itertools import combinations
from types import MappingProxyType

from mus_computer.bots.strategies.contexts import HandStatistics, OutcomeProbability
from mus_computer.cards.card import Card
from mus_computer.cards.hand import Hand
from mus_computer.constants import cards_space
from mus_computer.game.phases import Chica, Grande, Juego, Pares, Punto, PhaseName
from mus_computer.probabilities.tables import canonical, decision_discard_options, lookup


_PHASES = {
    PhaseName.GRANDE: Grande,
    PhaseName.CHICA: Chica,
    PhaseName.PARES: Pares,
    PhaseName.JUEGO: Juego,
    PhaseName.PUNTO: Punto,
}


def _validated_hand(cards: tuple[Card, ...] | list[Card], label: str) -> tuple[Card, ...]:
    if len(cards) != 4:
        raise ValueError(f"{label} requires four cards.")
    key = canonical(cards)
    if any(count > cards_space.get(rank, 0) for rank, count in Counter(key).items()):
        raise ValueError("Hand contains more copies of a card than the deck.")
    return key


def estimate_punto(cards: tuple[Card, ...] | list[Card]) -> OutcomeProbability:
    """Return the precomputed physical opponent-draw outcome for Punto."""
    entry = lookup(_validated_hand(cards, "Punto estimation"), PhaseName.PUNTO.value)
    return OutcomeProbability(entry["p_win"], entry["p_tie"], entry["p_loss"])


@lru_cache(maxsize=512)
def _hand_statistics(cards: tuple[Card, ...], is_mano: bool) -> HandStatistics:
    hand = Hand(list(cards))
    outcomes_by_phase = {}
    expected_points_by_phase = {}
    for name, phase in _PHASES.items():
        entry = lookup(cards, name.value)
        outcome = OutcomeProbability(entry["p_win"], entry["p_tie"], entry["p_loss"])
        outcomes_by_phase[name] = outcome
        points_on_win = phase.base_bet + phase.calculate_points(hand)
        expected_points_by_phase[name] = (outcome.p_win + (outcome.p_tie if is_mano else 0.0)) * points_on_win
    return HandStatistics(outcomes_by_phase, expected_points_by_phase)


def estimate_hand_statistics(
    cards: tuple[Card, ...] | list[Card], is_mano: bool = False,
) -> HandStatistics:
    """Return phase probabilities and simple expected phase points for this hand."""
    return _hand_statistics(_validated_hand(cards, "Hand statistics"), is_mano)


def estimate_discard_options(
    cards: tuple[Card, ...] | list[Card], is_mano: bool = False,
) -> MappingProxyType:
    """Map original card indices to expected statistics after a Mus exchange."""
    _validated_hand(cards, "Discard estimation")
    original = tuple(cards)
    table_options = decision_discard_options(original)
    result = {}
    for n_discarded in range(5):
        for indices in combinations(range(4), n_discarded):
            kept = tuple(card for index, card in enumerate(original) if index not in indices)
            table = table_options[canonical(kept)]
            outcomes_by_phase = {
                phase: OutcomeProbability(
                    table[phase.value]["p_win"],
                    table[phase.value]["p_tie"],
                    table[phase.value]["p_loss"],
                )
                for phase in _PHASES
            }
            points_key = (
                "expected_points_with_priority" if is_mano
                else "expected_points_without_priority"
            )
            result[indices] = HandStatistics(
                outcomes_by_phase,
                {phase: table[phase.value][points_key] for phase in _PHASES},
            )
    return MappingProxyType(result)
