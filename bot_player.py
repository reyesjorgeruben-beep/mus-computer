import random
from itertools import combinations
from typing import List
from player_base import PlayerBase
from bot_genome import BotGenome
from bot_game_state import (
    BotGameState, ScoreTier, get_score_tier,
    compute_urgency, compute_position_signal,
)
from probability_tables import canonical, win_prob, avg_opp_improvement_per_phase
from game_context import GameContext
from team import Team
from constants import cards_space

WIN_SCORE = 40
_PHASE_NAMES = ["Grande", "Chica", "Pares", "Juego"]
_URGENCY_SCALE = 0.20
_POSITION_SCALE = 0.10
_DISCARD_SAMPLES = 300
_IMPROVEMENT_SAMPLES = 80


class BotPlayer(PlayerBase):
    def __init__(self, name: str, team: Team, genome: BotGenome):
        super().__init__(name, team)
        self._genome = genome
        self._state: BotGameState | None = None

    def set_round_state(
        self,
        team_scores: dict,
        my_team_name: str,
        position: int,
        n_players: int,
        opponent_discard_counts: list,
        mus_rounds_completed: int,
    ) -> None:
        my_score = team_scores.get(my_team_name, 0)
        opp_score = max(
            (v for k, v in team_scores.items() if k != my_team_name),
            default=0,
        )
        self._state = BotGameState(
            my_score_tier=get_score_tier(my_score, WIN_SCORE),
            opponent_score_tier=get_score_tier(opp_score, WIN_SCORE),
            position=position,
            n_players=n_players,
            opponent_discard_counts=opponent_discard_counts,
            mus_rounds_completed=mus_rounds_completed,
        )

    def _phase_weights(self) -> dict:
        g = self._genome
        raw = {
            "Grande": g.w_grande,
            "Chica": g.w_chica,
            "Pares": g.w_pares,
            "Juego": g.w_juego,
        }
        total = sum(raw.values()) or 1.0
        return {k: v / total for k, v in raw.items()}

    def _hand_strength(self, cards) -> float:
        weights = self._phase_weights()
        is_mano = (
            self._state is not None
            and self._state.position == 0
            and self._genome.position_preference < 0.5
        )
        total = 0.0
        for phase_name, w in weights.items():
            total += w * win_prob(cards, phase_name, is_mano=is_mano)
        return total

    def _game_signal(self) -> float:
        if self._state is None:
            return 0.0
        urgency = compute_urgency(self._state.my_score_tier, self._state.opponent_score_tier)
        pos_sig = compute_position_signal(
            self._state.position,
            self._state.n_players,
            self._genome.position_preference,
        )
        return (
            self._genome.score_urgency_sensitivity * urgency * _URGENCY_SCALE
            + pos_sig * _POSITION_SCALE
        )

    def _remaining_deck(self) -> List:
        counts = dict(cards_space)
        for c in self.cards:
            counts[c] -= 1
        return [c for c, n in counts.items() for _ in range(n)]

    def _sample_replacements(self, kept, n_draw, n_samples) -> List[float]:
        remaining = self._remaining_deck()
        if n_draw == 0:
            return [self._hand_strength(list(kept))]
        strengths = []
        for _ in range(n_samples):
            drawn = random.sample(remaining, n_draw)
            strengths.append(self._hand_strength(list(kept) + drawn))
        return strengths

    def _best_expected_strength(self, n_samples: int) -> float:
        best = self._hand_strength(self.cards)
        for r in range(1, 5):
            for discard_idx in combinations(range(len(self.cards)), r):
                kept = [c for i, c in enumerate(self.cards) if i not in discard_idx]
                strengths = self._sample_replacements(kept, r, n_samples)
                expected = sum(strengths) / len(strengths)
                if expected > best:
                    best = expected
        return best

    def vote_mus(self) -> bool:
        g = self._genome
        hand_strength = self._hand_strength(self.cards)
        best_expected = self._best_expected_strength(n_samples=_IMPROVEMENT_SAMPLES)
        improvement_ours = max(0.0, best_expected - hand_strength)
        weights = self._phase_weights()
        avg_improvements = avg_opp_improvement_per_phase()
        improvement_opp = sum(weights[p] * avg_improvements[p] for p in _PHASE_NAMES)
        improvement_delta = improvement_ours - improvement_opp
        improvement_signal = improvement_delta * g.mus_risk_sensitivity
        game_signal = self._game_signal()
        adjusted_strength = max(0.0, min(1.0, hand_strength - improvement_signal + game_signal))
        stop_mus_prob = adjusted_strength * (1.0 - g.mus_eagerness)
        return random.random() > stop_mus_prob

    def choose_discards(self) -> List[int]:
        g = self._genome
        best_score = -1.0
        best_indices: List[int] = []
        for r in range(5):
            for discard_idx in combinations(range(len(self.cards)), r):
                kept = [c for i, c in enumerate(self.cards) if i not in discard_idx]
                strengths = self._sample_replacements(kept, r, _DISCARD_SAMPLES)
                expected = sum(strengths) / len(strengths)
                penalty = (1.0 - g.discard_aggressiveness) * r * 0.04
                score = expected - penalty
                if score > best_score:
                    best_score = score
                    best_indices = list(discard_idx)
        return best_indices

    def wager_action(self, context: GameContext) -> int:
        g = self._genome
        phase_name = context.phase_name
        effective_phase = "Grande" if phase_name == "Punto" else phase_name
        is_mano = context.position == 0 and g.position_preference < 0.5
        base_prob = win_prob(context.hand, effective_phase, is_mano=is_mano)
        if self._state is not None:
            urgency = compute_urgency(self._state.my_score_tier, self._state.opponent_score_tier)
            pos_sig = compute_position_signal(context.position, context.n_players, g.position_preference)
        else:
            urgency = 0.0
            pos_sig = 0.0
        modifier = (
            g.score_urgency_sensitivity * urgency * _URGENCY_SCALE
            + pos_sig * _POSITION_SCALE
        )
        adjusted_prob = max(0.0, min(1.0, base_prob + modifier))
        if random.random() < g.bluff_rate:
            adjusted_prob = max(adjusted_prob, g.raise_threshold + 0.01)
        if adjusted_prob < g.fold_threshold:
            return -1
        if adjusted_prob < g.raise_threshold:
            return 0
        min_raise = 1
        max_raise = max(1, context.current_bet)
        raise_amount = round(min_raise + g.risk_factor * (max_raise - min_raise))
        return raise_amount
