from dataclasses import FrozenInstanceError
from typing import Any

import pytest

from mus_computer.bots.strategies.actions import DiscardAction
from mus_computer.bots.strategies.contexts import (
    DiscardOption,
    HandStatistics,
    OutcomeProbability,
    PlayerDecisionContext,
)
from mus_computer.cards.card import Card
from mus_computer.game.context import GlobalGameContext, SeatOrderEntry, WagerState
from mus_computer.game.phases import PhaseName
from mus_computer.game.team import Team
from mus_computer.game.wager_session import WagerSession
from tests.conftest import ScriptedPlayer


def test_global_context_copies_public_mappings_and_has_no_hidden_cards():
    scores = {"A": 4, "B": 7}
    discards = {"Bot 1": 2}
    context = GlobalGameContext(
        team_scores=scores,
        mus_exchanges=1,
        phase_name=PhaseName.GRANDE,
        wager=WagerState(2, 1, "A", False),
        public_actions=("Bot 1: envida",),
        discard_counts=discards,
        seat_order=(SeatOrderEntry("Bot 1", "A"), SeatOrderEntry("Bot 2", "B")),
        mano_seat=0,
        eligible_seats=(0, 1),
    )
    scores["A"] = 99
    discards["Bot 1"] = 99
    assert context.team_scores["A"] == 4
    assert context.discard_counts["Bot 1"] == 2
    assert not hasattr(context, "hand") and not hasattr(context, "cards")
    with pytest.raises(TypeError):
        context.team_scores["A"] = 10  # type: ignore[index]  # Test immutability.
    with pytest.raises(FrozenInstanceError):
        context.phase_name = PhaseName.CHICA  # type: ignore[misc]  # Test frozen fields.


def test_private_context_keeps_own_cards_and_freezes_statistics():
    outcomes_by_phase = {PhaseName.GRANDE: OutcomeProbability(0.6, 0.1, 0.3)}
    expected_points_by_phase = {PhaseName.GRANDE: 0.7}
    statistics = HandStatistics(
        outcomes_by_phase=outcomes_by_phase,
        expected_points_by_phase=expected_points_by_phase,
    )
    intrinsic_points_by_phase = {PhaseName.PARES: 2}
    options = [DiscardOption(DiscardAction((0,)), statistics)]
    private = PlayerDecisionContext(
        "Bot 1",
        "A",
        0,
        (Card.R,) * 4,
        PhaseName.GRANDE,
        True,
        intrinsic_points_by_phase,
        statistics,
        options,  # type: ignore[arg-type]  # Test defensive copying of list input.
    )
    outcomes_by_phase[PhaseName.GRANDE] = OutcomeProbability(0, 0, 1)
    expected_points_by_phase[PhaseName.GRANDE] = 99
    intrinsic_points_by_phase[PhaseName.PARES] = 99
    options.append(DiscardOption(DiscardAction((1,)), HandStatistics({}, {})))
    assert private.statistics.outcomes_by_phase[PhaseName.GRANDE].p_win == 0.6
    assert private.statistics.expected_points_by_phase[PhaseName.GRANDE] == 0.7
    assert private.intrinsic_points_by_phase[PhaseName.PARES] == 2
    assert private.discard_options[0].statistics is statistics
    assert private.discard_options[0].action == DiscardAction((0,))
    with pytest.raises(TypeError):
        private.discard_options[0] = options[1]  # type: ignore[index]  # Test immutability.


def test_private_context_requires_distinct_legal_discard_options():
    statistics = HandStatistics({}, {})
    keep_cards = DiscardOption(DiscardAction(()), statistics)
    details: dict[str, Any] = {
        "player_name": "Bot 1",
        "team_name": "A",
        "seat": 0,
        "cards": (Card.R,) * 4,
        "phase_name": None,
        "eligible": True,
        "intrinsic_points_by_phase": {},
        "statistics": statistics,
    }
    with pytest.raises(ValueError, match="at least one"):
        PlayerDecisionContext(**details, discard_options=())
    with pytest.raises(ValueError, match="repeat"):
        PlayerDecisionContext(**details, discard_options=(keep_cards, keep_cards))
    with pytest.raises(ValueError, match="invalid card index"):
        PlayerDecisionContext(
            **details,
            discard_options=(DiscardOption(DiscardAction((4,)), statistics),),
        )
    with pytest.raises(ValueError, match="DiscardOption"):
        PlayerDecisionContext(**details, discard_options={(): statistics})  # type: ignore[arg-type]  # Test invalid options.
    with pytest.raises(TypeError, match="DiscardAction"):
        DiscardOption((0,), statistics)  # type: ignore[arg-type]  # Test invalid action.


def test_public_context_rejects_terminal_hand_display_events():
    with pytest.raises(ValueError):
        GlobalGameContext(
            team_scores={"A": 0, "B": 0},
            mus_exchanges=0,
            phase_name=PhaseName.GRANDE,
            wager=None,
            public_actions=("Hands | Bot 1: R R R R",),
            discard_counts={},
            seat_order=(SeatOrderEntry("Bot 1", "A"),),
            mano_seat=0,
            eligible_seats=(0,),
        )


def test_wager_prompt_sees_prior_public_actions():
    team_a, team_b = Team("A"), Team("B")
    seen = []

    class Recorder(ScriptedPlayer):
        def wager_action(self, global_context=None, player_context=None):
            seen.append(global_context.public_actions)
            return super().wager_action(global_context, player_context)

    players = [
        Recorder("A1", team_a, wager_actions=[2]),
        Recorder("B1", team_b, wager_actions=[0]),
    ]
    for player in players:
        player.cards = [Card.R, Card._7, Card._5, Card.A]
    shared = GlobalGameContext(
        team_scores={"A": 0, "B": 0},
        mus_exchanges=0,
        phase_name=PhaseName.GRANDE,
        wager=None,
        public_actions=(),
        discard_counts={},
        seat_order=(SeatOrderEntry("A1", "A"), SeatOrderEntry("B1", "B")),
        mano_seat=0,
        eligible_seats=(0, 1),
    )
    WagerSession(players, 1, shared, (team_a, team_b)).run()
    assert seen == [(), ("Grande | A1: envida",)]


def test_first_eligible_seat_gets_tie_priority_in_any_phase():
    from mus_computer.probabilities.estimates import estimate_hand_statistics

    player = ScriptedPlayer("B1", Team("B"))
    player.cards = [Card.R] * 4
    shared = GlobalGameContext(
        team_scores={"A": 0, "B": 0},
        mus_exchanges=0,
        phase_name=PhaseName.GRANDE,
        wager=None,
        public_actions=(),
        discard_counts={},
        seat_order=(
            SeatOrderEntry("A1", "A"),
            SeatOrderEntry("B1", "B"),
            SeatOrderEntry("A2", "A"),
            SeatOrderEntry("B2", "B"),
        ),
        mano_seat=0,
        eligible_seats=(1, 2),
    )
    private = player.decision_context(shared, seat=1)
    priority = estimate_hand_statistics(player.cards, is_mano=True)
    assert (
        private.statistics.expected_points_by_phase[PhaseName.GRANDE]
        == priority.expected_points_by_phase[PhaseName.GRANDE]
    )
