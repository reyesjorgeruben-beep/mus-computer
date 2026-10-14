"""Strategy-facing personality interface and phase preference weights."""

from typing import Protocol

from mus_computer.game.phases import PhaseName


class BotPersonality(Protocol):
    """Preference interface consumed by injectable strategies.

    ``BotGenome`` is the built-in implementation. Strategies depend on these
    preference fields rather than on the genetic representation or its
    serialization and can therefore accept other compatible personality types.
    Values are expected to use the genome's normalized 0-to-1 scale.
    """

    @property
    def mus_eagerness(self) -> float: ...

    @property
    def mus_risk_sensitivity(self) -> float: ...

    @property
    def w_grande(self) -> float: ...

    @property
    def w_chica(self) -> float: ...

    @property
    def w_pares(self) -> float: ...

    @property
    def w_juego(self) -> float: ...

    @property
    def discard_aggressiveness(self) -> float: ...

    @property
    def bluff_rate(self) -> float: ...

    @property
    def risk_factor(self) -> float: ...

    @property
    def fold_threshold(self) -> float: ...

    @property
    def raise_threshold(self) -> float: ...

    @property
    def score_urgency_sensitivity(self) -> float: ...

    @property
    def position_preference(self) -> float: ...


def phase_utility_weights(personality: BotPersonality) -> dict[PhaseName, float]:
    """Normalize the personality's four phase-preference genes.

    These weights express policy utility; they do not change the underlying
    probabilities or expected-point estimates in ``HandStatistics``.
    """
    weights = {
        PhaseName.GRANDE: max(0.0, personality.w_grande),
        PhaseName.CHICA: max(0.0, personality.w_chica),
        PhaseName.PARES: max(0.0, personality.w_pares),
        PhaseName.JUEGO: max(0.0, personality.w_juego),
    }
    total = sum(weights.values())
    if total == 0:
        return {phase: 0.25 for phase in weights}
    return {phase: weight / total for phase, weight in weights.items()}
