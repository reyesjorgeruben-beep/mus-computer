"""Enumerate opening, counter-raise, final fold/ordago, and ordago responses."""

from collections import defaultdict
from dataclasses import dataclass

from .policy import Action, Coefficients, Stage


@dataclass(frozen=True)
class Settlement:
    winner: int
    points: int
    ordago: bool = False


@dataclass(frozen=True)
class Decision:
    seat: int
    p_win: float
    stage: Stage
    reach: float
    probabilities: dict[Action, float]
    children: dict[Action, tuple[tuple[Settlement, float], ...]]
    history: tuple[str, ...] = ()


@dataclass(frozen=True)
class WagerTree:
    outcomes: tuple[tuple[Settlement, float], ...]
    decisions: tuple[Decision, ...]


def build_wager_tree(
    eligible: tuple[int, ...],
    win_probabilities: tuple[float, ...],
    policies: tuple[Coefficients, Coefficients],
    base_bet: int,
    winner: int,
    intrinsic: tuple[int, int],
) -> WagerTree:
    """Resolve actual cards externally; the policy sees only each actor's estimate.

    Bet opens at two; one numeric counter-raise makes four. The next response
    is fold or ordago, and ordago itself allows fold or match. A fold
    leaves the other eligible teammate a response, as in WagerSession.
    """
    if not eligible:
        raise ValueError("A wager tree needs eligible seats")
    if len({seat % 2 for seat in eligible}) == 1:
        return WagerTree(((Settlement(winner, intrinsic[winner]), 1.0),), ())
    decisions = []

    def finish(team, points, ordago=False):
        return (
            (Settlement(team, 0 if ordago else points + intrinsic[team], ordago), 1.0),
        )

    def walk(queue, stage, offering, accepted, reach, history=(), current=2):
        if not queue:
            return (
                finish(winner, base_bet)
                if stage is Stage.OPEN
                else finish(offering, accepted)
            )
        seat, remaining = queue[0], queue[1:]
        probabilities = policies[seat % 2].distribution(win_probabilities[seat], stage)
        children = {}
        outcomes: defaultdict[Settlement, float] = defaultdict(float)
        for action, probability in probabilities.items():
            child_reach = reach * probability
            child_history = history + (f"{seat}:{action.name.lower()}",)
            if action is Action.PASS:
                child = walk(
                    remaining, Stage.OPEN, None, accepted, child_reach, child_history
                )
            elif action is Action.BET:
                responders = tuple(s for s in eligible if s % 2 != seat % 2)
                child = walk(
                    responders,
                    Stage.OFFER,
                    seat % 2,
                    max(base_bet, 1),
                    child_reach,
                    child_history,
                )
            elif action is Action.FOLD:
                child = walk(
                    remaining,
                    stage,
                    offering,
                    accepted,
                    child_reach,
                    child_history,
                    current,
                )
            elif action is Action.MATCH:
                child = finish(winner, current, stage is Stage.ORDAGO)
            elif action is Action.RAISE:
                responders = tuple(s for s in eligible if s % 2 != seat % 2)
                child = walk(
                    responders,
                    Stage.COUNTER,
                    seat % 2,
                    current,
                    child_reach,
                    child_history,
                    current + 2,
                )
            else:
                responders = tuple(s for s in eligible if s % 2 != seat % 2)
                previous = max(base_bet, 1) if stage is Stage.OPEN else current
                child = walk(
                    responders,
                    Stage.ORDAGO,
                    seat % 2,
                    previous,
                    child_reach,
                    child_history,
                    current,
                )
            children[action] = child
            for outcome, chance in child:
                outcomes[outcome] += probability * chance
        decisions.append(
            Decision(
                seat,
                win_probabilities[seat],
                stage,
                reach,
                probabilities,
                children,
                history,
            )
        )
        return tuple(outcomes.items())

    outcomes = walk(eligible, Stage.OPEN, None, max(base_bet, 1), 1.0)
    return WagerTree(outcomes, tuple(decisions))
