from typing import Callable, List, Tuple, Optional, Dict
from mus_computer.game.player_base import PlayerBase
from mus_computer.game.team import Team
from mus_computer.game.context import GameContext


class WagerSession:
    """Resolve one team's wager and return either the showdown stake or fold award."""

    def __init__(
        self,
        players: List[PlayerBase],
        base_bet: int,
        phase_name: str,
        team_scores: Dict[str, int],
        teams: tuple[Team, Team],
        discard_counts: Dict[str, int] = None,
        on_action: Callable[[str], None] | None = None,
        phase_label: str | None = None,
    ):
        self.players = players
        if len(teams) != 2 or teams[0] is teams[1]:
            raise ValueError("WagerSession requires two distinct teams.")
        if any(player.team not in teams for player in players):
            raise ValueError("Every wagering player must belong to a supplied team.")
        self.teams = teams
        self.phase_name = phase_name
        self.team_scores = team_scores
        self.base_bet = base_bet
        self.current_bet = base_bet
        self.previous_bet = 0
        self.team_leading_bet: Optional[Team] = None
        self.discard_counts: Dict[str, int] = discard_counts or {}
        self.on_action = on_action
        self.phase_label = phase_label or phase_name

    def _emit(self, message: str) -> None:
        if self.on_action is not None:
            self.on_action(f"{self.phase_label} | {message}")

    def run(self) -> Tuple[Optional[Team], int]:
        """Return (None, stake) for showdown or (offering_team, accepted_stake) on fold."""
        n_players = len(self.players)
        if n_players == 0:
            raise ValueError("WagerSession requires eligible players.")

        next_idx = 0
        passes = 0
        responders: list[int] = []
        accepted_stake = max(self.base_bet, 1)

        for _ in range(40 * n_players):
            if self.team_leading_bet is None:
                idx = next_idx
                next_idx = (next_idx + 1) % n_players
            else:
                idx = responders.pop(0)
            player = self.players[idx]

            opp_discards = [
                self.discard_counts.get(p.name, 0)
                for p in self.players
                if p.team != player.team
            ]

            context = GameContext(
                phase_name=self.phase_name,
                team_scores=self.team_scores,
                current_bet=self.current_bet,
                previous_bet=self.previous_bet,
                hand=list(player.cards),
                position=idx,
                n_players=n_players,
                opponent_discard_counts=opp_discards,
            )

            action = player.wager_action(context)

            if self.team_leading_bet is None:
                if action <= 0:
                    self._emit(f"{player.name}: paso")
                    passes += 1
                    if passes == n_players:
                        return (None, self.base_bet)
                    continue

                self.current_bet = max(self.base_bet, action)
                self.previous_bet = accepted_stake
                self.team_leading_bet = player.team
                label = "envida" if self.current_bet == 2 else f"envida {self.current_bet}"
                self._emit(f"{player.name}: {label}")
            elif action < 0:
                self._emit(f"{player.name}: no quiero")
                if not responders:
                    return (self.team_leading_bet, accepted_stake)
                continue
            elif action == 0:
                self._emit(f"{player.name}: quiero")
                return (None, self.current_bet)
            else:
                accepted_stake = self.current_bet
                self.previous_bet = accepted_stake
                self.current_bet += action
                self.team_leading_bet = player.team
                self._emit(f"{player.name}: envida {action} (total {self.current_bet})")

            responders = [
                candidate_idx
                for candidate_idx, candidate in enumerate(self.players)
                if candidate.team is not self.team_leading_bet
            ]
            if not responders:
                raise ValueError("An offer requires an eligible opposing player.")

        return (None, self.current_bet)
