"""Per-hand estimates from the bundled tables and physical-card enumeration.

These are estimates against an unknown opposing hand, not observations of any
opponent's private cards or a full opposing team model.
"""

from collections import Counter
from functools import lru_cache
from itertools import combinations, combinations_with_replacement
from math import comb
from types import MappingProxyType

from mus_computer.bots.strategies.contexts import HandStatistics, OutcomeProbability
from mus_computer.cards.card import Card
from mus_computer.cards.hand import Hand
from mus_computer.constants import cards_space
from mus_computer.game.phases import Chica, Grande, Juego, Pares, Punto, PhaseName
from mus_computer.probabilities.tables import canonical, discard_options, lookup


_PHASES = {
    PhaseName.GRANDE: Grande,
    PhaseName.CHICA: Chica,
    PhaseName.PARES: Pares,
    PhaseName.JUEGO: Juego,
    PhaseName.PUNTO: Punto,
}
_RANKS = tuple(cards_space)


def _rank_draws(remaining: Counter, draw_count: int):
    """Yield unique rank draws with their number of physical realizations."""
    for draw in combinations_with_replacement(_RANKS, draw_count):
        multiplicity = Counter(draw)
        if any(count > remaining[rank] for rank, count in multiplicity.items()):
            continue
        weight = 1
        for rank, count in multiplicity.items():
            weight *= comb(remaining[rank], count)
        yield draw, weight


@lru_cache(maxsize=512)
def _punto_for_canonical(cards: tuple[Card, ...]) -> OutcomeProbability:
    remaining = Counter(cards_space)
    remaining.subtract(cards)
    own_hand = Hand(list(cards))
    wins = ties = losses = total = 0
    for opposing_cards, weight in _rank_draws(remaining, 4):
        result = Punto.play(own_hand, Hand(list(opposing_cards)))
        total += weight
        if result > 0:
            wins += weight
        elif result < 0:
            losses += weight
        else:
            ties += weight
    return OutcomeProbability(wins / total, ties / total, losses / total)


def estimate_punto(cards: tuple[Card, ...] | list[Card]) -> OutcomeProbability:
    """Compare a four-card hand with every possible unknown opponent rank draw."""
    if len(cards) != 4:
        raise ValueError("Punto estimation requires four cards.")
    key = canonical(cards)
    if any(Counter(key)[rank] > count for rank, count in cards_space.items()):
        raise ValueError("Hand contains more copies of a card than the deck.")
    return _punto_for_canonical(key)


@lru_cache(maxsize=512)
def _hand_statistics(cards: tuple[Card, ...], is_mano: bool) -> HandStatistics:
    hand = Hand(list(cards))
    outcomes = {}
    expected_points = {}
    for name, phase in _PHASES.items():
        if name is PhaseName.PUNTO:
            outcome = estimate_punto(cards)
        else:
            entry = lookup(cards, name.value)
            outcome = OutcomeProbability(entry["p_win"], entry["p_tie"], entry["p_loss"])
        outcomes[name] = outcome
        points_on_win = phase.base_bet + phase.calculate_points(hand)
        expected_points[name] = (outcome.p_win + (outcome.p_tie if is_mano else 0.0)) * points_on_win
    return HandStatistics(outcomes, expected_points)


def estimate_hand_statistics(
    cards: tuple[Card, ...] | list[Card], is_mano: bool = False,
) -> HandStatistics:
    """Return phase probabilities and simple expected phase points for this hand."""
    if len(cards) != 4:
        raise ValueError("Hand statistics require four cards.")
    return _hand_statistics(canonical(cards), is_mano)


def estimate_discard_options(
    cards: tuple[Card, ...] | list[Card], is_mano: bool = False,
) -> MappingProxyType:
    """Map original card indices to expected statistics after a Mus exchange."""
    if len(cards) != 4:
        raise ValueError("Discard estimation requires four cards.")
    original = tuple(cards)
    remaining = Counter(cards_space)
    remaining.subtract(original)
    table_options = discard_options(original)
    result = {}
    for n_discarded in range(5):
        for indices in combinations(range(4), n_discarded):
            kept = tuple(card for index, card in enumerate(original) if index not in indices)
            if not indices:
                result[indices] = estimate_hand_statistics(original, is_mano)
                continue
            total = 0
            win = {phase: 0.0 for phase in _PHASES}
            tie = {phase: 0.0 for phase in _PHASES}
            expected = {phase: 0.0 for phase in _PHASES}
            for drawn, weight in _rank_draws(remaining, n_discarded):
                stats = estimate_hand_statistics(kept + drawn, is_mano)
                total += weight
                for phase in _PHASES:
                    win[phase] += weight * stats.phase_outcomes[phase].p_win
                    tie[phase] += weight * stats.phase_outcomes[phase].p_tie
                    expected[phase] += weight * stats.expected_points[phase]
            table = table_options.get(canonical(kept), {})
            outcomes = {}
            for phase in _PHASES:
                p_win = table.get(phase.value, win[phase] / total)
                p_tie = min(tie[phase] / total, max(0.0, 1.0 - p_win))
                outcomes[phase] = OutcomeProbability(p_win, p_tie, max(0.0, 1.0 - p_win - p_tie))
            result[indices] = HandStatistics(outcomes, {
                phase: value / total for phase, value in expected.items()
            })
    return MappingProxyType(result)
