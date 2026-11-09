"""Context-specific probability pairs with independent re-bid and ordago gates."""

import math
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum, IntEnum


class Action(IntEnum):
    FOLD = 0
    PASS = 1
    MATCH = 2
    BET = 3
    RAISE = 4
    ORDAGO = 5


class Stage(str, Enum):
    OPEN = "open"
    OFFER = "offer"
    COUNTER = "counter"
    ORDAGO = "ordago"


PARAMETERS = ("fold", "pass", "match", "bet", "rebid", "ordago")
PARAMETER_COUNT = 2 * len(PARAMETERS)
PAIRS = ((0, 2), (1, 3))


@dataclass(frozen=True)
class Coefficients:
    """Six probabilities per losing/winning case, not a shared pool of weights.

    Pass/bet and fold/match each sum to one. Re-bid and ordago are independent
    Bernoulli probabilities. Hand strength mixes predictions from the two
    endpoints, without rescaling or modifying the stored coefficients.
    """

    losing: tuple[float, ...] = (0.5, 0.5, 0.5, 0.5, 0.5, 0.1)
    winning: tuple[float, ...] = (0.5, 0.5, 0.5, 0.5, 0.5, 0.1)

    def __post_init__(self):
        for name in ("losing", "winning"):
            row = tuple(getattr(self, name))
            if (
                len(row) != 6
                or any(not math.isfinite(x) or not 0 <= x <= 1 for x in row)
                or any(abs(row[a] + row[b] - 1) > 1e-9 for a, b in PAIRS)
            ):
                raise ValueError("Six probabilities required: fold+match=1, pass+bet=1")
            object.__setattr__(self, name, row)

    def _mixed(self, p_win):
        if not math.isfinite(p_win) or not 0 <= p_win <= 1:
            raise ValueError("Win probability must be in [0, 1]")
        return tuple(
            (1 - p_win) * a + p_win * b for a, b in zip(self.losing, self.winning)
        )

    def distribution(self, p_win: float, stage: Stage) -> dict[Action, float]:
        fold, pass_, match, bet, rebid, ordago = self._mixed(p_win)
        if stage is Stage.OPEN:
            return {
                Action.PASS: pass_,
                Action.BET: bet * (1 - ordago),
                Action.ORDAGO: bet * ordago,
            }
        if stage is Stage.OFFER:
            return {
                Action.FOLD: (1 - rebid) * fold,
                Action.MATCH: (1 - rebid) * match,
                Action.RAISE: rebid * (1 - ordago),
                Action.ORDAGO: rebid * ordago,
            }
        if stage is Stage.COUNTER:
            # Calling and further numeric raises are excluded after a counter-
            # raise. Only the re-bid-and-ordago branch stays aggressive.
            return {Action.FOLD: 1 - rebid * ordago, Action.ORDAGO: rebid * ordago}
        if stage is Stage.ORDAGO:
            return {Action.FOLD: fold, Action.MATCH: match}
        raise ValueError(f"Unknown wager stage: {stage}")

    def gradient(
        self, p_win: float, stage: Stage, values: Mapping[Action, float]
    ) -> tuple[float, ...]:
        """Exact derivative in paired-log-weight / independent-logit coordinates."""
        fold, _pass, match, bet, rebid, ordago = self._mixed(p_win)
        partial = [0.0] * 6
        if stage is Stage.OPEN:
            partial[1] = values[Action.PASS]
            partial[3] = (1 - ordago) * values[Action.BET] + ordago * values[
                Action.ORDAGO
            ]
            partial[5] = bet * (values[Action.ORDAGO] - values[Action.BET])
        elif stage is Stage.OFFER:
            partial[0] = (1 - rebid) * values[Action.FOLD]
            partial[2] = (1 - rebid) * values[Action.MATCH]
            partial[4] = (
                (1 - ordago) * values[Action.RAISE]
                + ordago * values[Action.ORDAGO]
                - fold * values[Action.FOLD]
                - match * values[Action.MATCH]
            )
            partial[5] = rebid * (values[Action.ORDAGO] - values[Action.RAISE])
        elif stage is Stage.COUNTER:
            difference = values[Action.ORDAGO] - values[Action.FOLD]
            partial[4], partial[5] = ordago * difference, rebid * difference
        elif stage is Stage.ORDAGO:
            partial[0], partial[2] = values[Action.FOLD], values[Action.MATCH]
        else:
            raise ValueError(f"Unknown wager stage: {stage}")
        gradient = []
        for feature, row in ((1 - p_win, self.losing), (p_win, self.winning)):
            local = [0.0] * 6
            for a, b in PAIRS:
                baseline = row[a] * partial[a] + row[b] * partial[b]
                for i in (a, b):
                    local[i] = feature * row[i] * (partial[i] - baseline)
            for i in (4, 5):
                local[i] = feature * row[i] * (1 - row[i]) * partial[i]
            gradient.extend(local)
        return tuple(gradient)

    def updated(self, gradient: tuple[float, ...], rate: float) -> "Coefficients":
        if (
            len(gradient) != PARAMETER_COUNT
            or not math.isfinite(rate)
            or rate <= 0
            or any(not math.isfinite(g) for g in gradient)
        ):
            raise ValueError(
                "Update requires twelve finite derivatives and a positive rate"
            )
        rows = []
        bounded = lambda p: max(1e-6, min(1 - 1e-6, p))
        for index, row in enumerate((self.losing, self.winning)):
            updated = list(row)
            for a, b in (*PAIRS, (4, None), (5, None)):
                # Pair log odds or a Bernoulli logit: no cross-context rescaling.
                p = bounded(row[a])
                change = gradient[index * 6 + a] - (
                    gradient[index * 6 + b] if b is not None else 0
                )
                logit = math.log(p / (1 - p)) + rate * change
                p = bounded(1 / (1 + math.exp(-max(-30, min(30, logit)))))
                updated[a] = p
                if b is not None:
                    updated[b] = 1 - p
            rows.append(tuple(updated))
        return Coefficients(*rows)

    @classmethod
    def random(cls, rng) -> "Coefficients":
        rows = []
        for _ in range(2):
            fold, pass_, rebid, ordago = (rng.random() for _ in range(4))
            rows.append((fold, pass_, 1 - fold, 1 - pass_, rebid, ordago))
        return cls(*rows)

    def as_dict(self) -> dict:
        return {
            name: dict(zip(PARAMETERS, row))
            for name, row in (("losing", self.losing), ("winning", self.winning))
        }
