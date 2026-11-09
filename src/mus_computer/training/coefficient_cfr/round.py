"""No-mus hands, immediate lance scoring, exact survival and action values."""

import random
from collections import defaultdict
from dataclasses import dataclass
from functools import cache

from mus_computer.cards.hand import Hand
from mus_computer.constants import cards_space
from mus_computer.game.phases import Chica, Grande, Juego, Pares, Punto
from mus_computer.probabilities.tables import win_prob

from .policy import PARAMETER_COUNT, Action, Coefficients, Stage
from .tree import Settlement, WagerTree, build_wager_tree


@dataclass(frozen=True)
class Lance:
    name: str
    tree: WagerTree


@dataclass(frozen=True)
class Round:
    scores: tuple[int, int]
    lances: tuple[Lance, ...]


@dataclass(frozen=True)
class Outcome:
    scores: tuple[int, int]
    reason: str
    probability: float


@dataclass(frozen=True)
class DecisionReport:
    phase: str
    scores: tuple[int, int]
    seat: int
    p_win: float
    stage: Stage
    reach: float
    probabilities: dict[Action, float]
    action_values: dict[Action, float]
    penalties: dict[Action, float]
    history: tuple[str, ...]


@dataclass(frozen=True)
class RoundResult:
    expected_points: tuple[float, float]
    penalties: tuple[float, float]
    team_gradients: tuple[tuple[float, ...], tuple[float, ...]]
    phase_reach: tuple[float, ...]
    outcomes: tuple[Outcome, ...]
    decisions: tuple[DecisionReport, ...] = ()
    starting_scores: tuple[int, int] = (0, 0)
    phase_names: tuple[str, ...] = ()


def _settle(
    scores: tuple[int, int], outcome: Settlement
) -> tuple[tuple[int, int], str | None]:
    updated = list(scores)
    updated[outcome.winner] = (
        40 if outcome.ordago else min(40, updated[outcome.winner] + outcome.points)
    )
    reason = "ordago" if outcome.ordago else "points" if max(updated) >= 40 else None
    return (updated[0], updated[1]), reason


def evaluate_round(
    round_: Round, policies: tuple[Coefficients, Coefficients], *, details: bool = False
) -> RoundResult:
    """Enumerate scores forward; evaluate conditional continuation values backward.

    Each actor's derivative holds every other decision distribution fixed.
    Summing the two teams' local gradients is simultaneous self-play, not
    differentiating the shared parameters through a zero-sum objective.
    """
    if len(round_.scores) != 2 or any(not 0 <= score < 40 for score in round_.scores):
        raise ValueError("Starting scores must be below 40 and nonnegative")

    @cache
    def value(index, scores):
        if index == len(round_.lances):
            return scores[0] - scores[1]
        return sum(
            probability * continuation(index, scores, outcome)
            for outcome, probability in round_.lances[index].tree.outcomes
        )

    def continuation(index, scores, outcome):
        updated, reason = _settle(scores, outcome)
        return updated[0] - updated[1] if reason else value(index + 1, updated)

    live = {round_.scores: 1.0}
    finished: defaultdict[tuple[tuple[int, int], str], float] = defaultdict(float)
    gradients = [[0.0] * PARAMETER_COUNT for _ in range(2)]
    penalties = [0.0, 0.0]
    phase_reach, reports = [], []
    for index, lance in enumerate(round_.lances):
        phase_reach.append(sum(live.values()))
        next_live: defaultdict[tuple[int, int], float] = defaultdict(float)
        for scores, state_reach in live.items():
            for node in lance.tree.decisions:
                team = node.seat % 2
                sign = 1 if team == 0 else -1
                action_values = {
                    a: sign
                    * sum(
                        p * continuation(index, scores, outcome)
                        for outcome, p in children
                    )
                    for a, children in node.children.items()
                }
                # Express values as the change in score difference from the
                # initial hand; this constant shift does not affect derivatives.
                origin = sign * (round_.scores[0] - round_.scores[1])
                action_values = {a: v - origin for a, v in action_values.items()}
                baseline = sum(
                    node.probabilities[a] * v for a, v in action_values.items()
                )
                best = max(action_values.values())
                reach = state_reach * node.reach
                local = policies[team].gradient(node.p_win, node.stage, action_values)
                for component, derivative in enumerate(local):
                    gradients[team][component] += reach * derivative
                penalties[team] += reach * (best - baseline)
                if details:
                    reports.append(
                        DecisionReport(
                            lance.name,
                            scores,
                            node.seat,
                            node.p_win,
                            node.stage,
                            reach,
                            node.probabilities,
                            action_values,
                            {a: best - v for a, v in action_values.items()},
                            node.history,
                        )
                    )
            for outcome, probability in lance.tree.outcomes:
                updated, reason = _settle(scores, outcome)
                mass = state_reach * probability
                if reason:
                    finished[updated, reason] += mass
                else:
                    next_live[updated] += mass
        live = next_live
    for scores, probability in live.items():
        finished[scores, "hand"] += probability
    outcomes = tuple(
        Outcome(scores, reason, p) for (scores, reason), p in sorted(finished.items())
    )
    expected = tuple(
        sum(o.probability * (o.scores[team] - round_.scores[team]) for o in outcomes)
        for team in (0, 1)
    )
    return RoundResult(
        (expected[0], expected[1]),
        (penalties[0], penalties[1]),
        (tuple(gradients[0]), tuple(gradients[1])),
        tuple(phase_reach),
        outcomes,
        tuple(reports),
        round_.scores,
        tuple(lance.name for lance in round_.lances),
    )


def sample_round(
    seed: int,
    coefficients: Coefficients,
    opponent: Coefficients | None = None,
    *,
    details: bool = False,
) -> RoundResult:
    """Sample physical cards and scores; enumerate all actions without sampling them."""
    rng = random.Random(seed)
    deck = [card for card, copies in cards_space.items() for _ in range(copies)]
    rng.shuffle(deck)
    hands = [Hand(deck[seat * 4 : seat * 4 + 4]) for seat in range(4)]
    scores = (rng.randint(10, 28), rng.randint(10, 28))
    policies = (coefficients, opponent if opponent is not None else coefficients)
    lances = []
    phases = (
        Grande,
        Chica,
        Pares,
        Juego if any(Juego.can_play(h) for h in hands) else Punto,
    )
    for phase in phases:
        eligible = tuple(
            seat for seat, hand in enumerate(hands) if phase.can_play(hand)
        )
        if not eligible:
            continue
        winner = eligible[0]
        for seat in eligible[1:]:
            if phase.play(hands[seat], hands[winner]) > 0:
                winner = seat
        intrinsic = tuple(
            sum(phase.calculate_points(hands[s]) for s in eligible if s % 2 == team)
            for team in (0, 1)
        )
        # Pre-mus estimates use only that seat's cards. Ties favor the first
        # eligible seat. These remain single-opponent estimates, not team odds.
        probabilities = tuple(
            win_prob(h.cards, phase.__name__, seat == eligible[0])
            for seat, h in enumerate(hands)
        )
        tree = build_wager_tree(
            eligible,
            probabilities,
            policies,
            phase.base_bet,
            winner % 2,
            (intrinsic[0], intrinsic[1]),
        )
        lances.append(Lance(phase.__name__, tree))
    return evaluate_round(Round(scores, tuple(lances)), policies, details=details)
