"""Strategy-facing personality interface retained for future bot policies."""

from typing import Protocol

from mus_computer.game.phases import PhaseName


class BotPersonality(Protocol):
    """Preference interface retained by injectable strategies.

    ``BotGenome`` is the built-in implementation. The current built-in
    strategies ignore the legacy fields; composed policies may use new ones.
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

    @property
    def cut_prone(self) -> float: ...

    @property
    def cut_prone_with_pares(self) -> float: ...

    @property
    def cut_prone_with_juego(self) -> float: ...


FIXED_PHASE_WEIGHTS = {
    PhaseName.GRANDE: 0.25,
    PhaseName.CHICA: 0.25,
    PhaseName.PARES: 0.25,
    PhaseName.JUEGO: 0.25,
}
