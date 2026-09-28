from dataclasses import FrozenInstanceError

import pytest

from mus_computer.cards.card import Card
from mus_computer.game.context import GlobalGameContext, WagerState
from mus_computer.bots.strategies.contexts import (
    HandStatistics, OutcomeProbability, PlayerDecisionContext,
)
from mus_computer.game.team import Team
from mus_computer.game.wager_session import WagerSession
from tests.conftest import ScriptedPlayer


def test_global_context_copies_public_mappings_and_has_no_hidden_cards():
    scores = {"A": 4, "B": 7}
    discards = {"Bot 1": 2}
    context = GlobalGameContext(
        team_scores=scores, mus_exchanges=1, phase_name="Grande",
        wager=WagerState(2, 1, "A", False),
        public_actions=("Bot 1: envida",), discard_counts=discards,
        seat_order=(("Bot 1", "A"), ("Bot 2", "B")),
        mano_seat=0, eligible_seats=(0, 1),
    )
    scores["A"] = 99
    discards["Bot 1"] = 99
    assert context.team_scores["A"] == 4
    assert context.discard_counts["Bot 1"] == 2
    assert not hasattr(context, "hand") and not hasattr(context, "cards")
    with pytest.raises(TypeError):
        context.team_scores["A"] = 10
    with pytest.raises(FrozenInstanceError):
        context.phase_name = "Chica"


def test_private_context_keeps_own_cards_and_freezes_statistics():
    outcomes = {"Grande": OutcomeProbability(0.6, 0.1, 0.3)}
    expected = {"Grande": 0.7}
    statistics = HandStatistics(outcomes, expected)
    intrinsic = {"Pares": 2}
    options = {(0,): statistics}
    private = PlayerDecisionContext(
        "Bot 1", "A", 0, (Card.R,) * 4, "Grande", True,
        intrinsic, statistics, options,
    )
    outcomes["Grande"] = OutcomeProbability(0, 0, 1)
    expected["Grande"] = 99
    intrinsic["Pares"] = 99
    options[(0,)] = HandStatistics({}, {})
    assert private.statistics.phase_outcomes["Grande"].p_win == 0.6
    assert private.statistics.expected_points["Grande"] == 0.7
    assert private.intrinsic_points["Pares"] == 2
    assert private.discard_options[(0,)] is statistics
    with pytest.raises(TypeError):
        private.discard_options[(0,)] = statistics


def test_public_context_rejects_terminal_hand_display_events():
    with pytest.raises(ValueError):
        GlobalGameContext(
            team_scores={"A": 0, "B": 0}, mus_exchanges=0,
            phase_name="Grande", wager=None,
            public_actions=("Hands | Bot 1: R R R R",), discard_counts={},
            seat_order=(("Bot 1", "A"),), mano_seat=0, eligible_seats=(0,),
        )


def test_wager_prompt_sees_prior_public_actions():
    team_a, team_b = Team("A"), Team("B")
    seen = []

    class Recorder(ScriptedPlayer):
        def wager_action(self, prompt):
            seen.append(prompt.global_context.public_actions)
            return super().wager_action(prompt)

    players = [
        Recorder("A1", team_a, wager_actions=[2]),
        Recorder("B1", team_b, wager_actions=[0]),
    ]
    WagerSession(players, 1, "Grande", {"A": 0, "B": 0}, (team_a, team_b)).run()
    assert seen == [(), ("Grande | A1: envida",)]
