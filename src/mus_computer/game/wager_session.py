"""Team wager negotiation shared by every phase."""
from dataclasses import dataclass
from enum import Enum
from mus_computer.game.context import GlobalGameContext, SeatOrderEntry, WagerState
from mus_computer.game.phases import PhaseName
from mus_computer.game.team import Team
from mus_computer.bots.strategies.actions import WagerAction, legal_wager_actions


class WagerOutcome(str, Enum):
    SHOWDOWN = "showdown"
    DECLINED = "declined"
    ORDAGO_ACCEPTED = "ordago_accepted"


@dataclass(frozen=True)
class WagerResult:
    outcome: WagerOutcome
    offering_team: Team | None
    accepted_stake: int | None

    @property
    def points(self) -> int:
        """Legacy numeric award; accepted ordago has no numeric stake."""
        return self.accepted_stake if self.accepted_stake is not None else 0

    @property
    def winner_team(self) -> Team | None:
        """Legacy fold winner; showdown winners require card resolution."""
        return self.offering_team if self.outcome is WagerOutcome.DECLINED else None

    def __iter__(self):
        # Retain tuple unpacking for callers migrating from the original API.
        yield self.winner_team
        yield self.points


class WagerSession:
    def __init__(self, players, base_bet, phase_name, team_scores, teams,
                 discard_counts=None, on_action=None, phase_label=None,
                 players_in_order=None, mus_exchanges=0, public_actions=(), mano_seat=0):
        self.players = list(players)
        if len(teams) != 2 or teams[0] is teams[1]:
            raise ValueError("WagerSession requires two distinct teams.")
        if any(player.team not in teams for player in players):
            raise ValueError("Every wagering player must belong to a supplied team.")
        self.teams = teams
        self.base_bet = base_bet
        self.phase_name = PhaseName(phase_name)
        self.team_scores = team_scores
        self.discard_counts = discard_counts or {}
        self.on_action = on_action
        self.phase_label = phase_label or self.phase_name.value
        self.public_actions = list(public_actions)
        self.players_in_order = list(players_in_order if players_in_order is not None else players)
        self.mus_exchanges = mus_exchanges
        self.mano_seat = mano_seat

    def _emit(self, message):
        event = f"{self.phase_label} | {message}"
        self.public_actions.append(event)
        if self.on_action is not None:
            self.on_action(event)

    def run(self):
        if not self.players:
            raise ValueError("WagerSession requires eligible players.")
        current = self.base_bet
        accepted = max(self.base_bet, 1)
        offering_team = None
        ordago = False
        responders = []
        next_player = 0
        while True:
            if offering_team is None:
                if next_player == len(self.players):
                    return WagerResult(WagerOutcome.SHOWDOWN, None, self.base_bet)
                player = self.players[next_player]
                next_player += 1
            else:
                player = responders.pop(0)
            wager = WagerState(current, accepted,
                               offering_team.name if offering_team else None, ordago)
            shared = GlobalGameContext(
                self.team_scores, self.mus_exchanges, self.phase_name, wager,
                tuple(self.public_actions), self.discard_counts,
                tuple(SeatOrderEntry(p.name, p.team.name) for p in self.players_in_order),
                self.mano_seat,
                tuple(i for i,p in enumerate(self.players_in_order) if p in self.players),
            )
            seat = next(i for i, seated in enumerate(self.players_in_order) if seated is player)
            action = player.wager_action(shared, player.decision_context(shared, seat))
            if not isinstance(action, WagerAction) or action not in legal_wager_actions(wager):
                raise ValueError(f"{player.name} chose an illegal wager action: {action!r}.")
            if action is WagerAction.MATCH_OR_PASS:
                self._emit(f"{player.name}: {'quiero' if offering_team else 'paso'}")
                if offering_team is not None:
                    return WagerResult(WagerOutcome.ORDAGO_ACCEPTED if ordago else WagerOutcome.SHOWDOWN,
                                       offering_team, None if ordago else current)
                continue
            if action is WagerAction.FOLD:
                self._emit(f"{player.name}: no quiero")
                if not responders:
                    return WagerResult(WagerOutcome.DECLINED, offering_team, accepted)
                continue
            was_offered = offering_team is not None
            if was_offered:
                accepted = current
            offering_team = player.team
            if action is WagerAction.ORDAGO:
                ordago = True
                self._emit(f"{player.name}: ordago")
            else:
                amount = int(action.value.rsplit("_", 1)[1])
                current = current + amount if was_offered else amount
                label = (f"envida {amount} (total {current})" if was_offered else
                         "envida" if amount == 2 else f"envida {amount}")
                self._emit(f"{player.name}: {label}")
            responders = [p for p in self.players if p.team is not offering_team]
            if not responders:
                raise ValueError("An offer requires an eligible opposing player.")
