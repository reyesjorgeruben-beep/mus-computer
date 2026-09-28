import pytest
from mus_computer.game.team import Team
from mus_computer.cards.card import Card
from mus_computer.game.wager_session import WagerSession
from tests.conftest import ScriptedPlayer as BaseScriptedPlayer


class ScriptedPlayer(BaseScriptedPlayer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cards = [Card.R, Card._7, Card._5, Card.A]


@pytest.fixture
def teams():
    return Team("A"), Team("B")


def make_players(team_a, team_b, actions_a1, actions_b1, actions_a2=(), actions_b2=()):
    a1 = ScriptedPlayer("A1", team_a, wager_actions=actions_a1)
    b1 = ScriptedPlayer("B1", team_b, wager_actions=actions_b1)
    players = [a1, b1]
    if actions_a2:
        players.append(ScriptedPlayer("A2", team_a, wager_actions=actions_a2))
    if actions_b2:
        players.append(ScriptedPlayer("B2", team_b, wager_actions=actions_b2))
    return players


def run(players, base_bet=1):
    return WagerSession(
        players, base_bet, "Grande", {"A": 0, "B": 0},
        teams=(players[0].team, players[1].team),
    ).run()


class TestWagerSessionAllPass:
    def test_two_players_all_pass(self, teams):
        team_a, team_b = teams
        players = make_players(team_a, team_b, [0, 0], [0, 0])
        winner, bet = run(players)
        assert winner is None
        assert bet == 1

    def test_four_players_all_pass(self, teams):
        team_a, team_b = teams
        players = make_players(team_a, team_b, [0, 0], [0, 0], [0, 0], [0, 0])
        winner, bet = run(players)
        assert winner is None
        assert bet == 1

    def test_all_pass_preserves_base_bet(self, teams):
        team_a, team_b = teams
        players = make_players(team_a, team_b, [0], [0])
        _, bet = run(players, base_bet=3)
        assert bet == 3


class TestWagerSessionFold:
    def test_b1_folds_after_a1_raises(self, teams):
        team_a, team_b = teams
        players = make_players(team_a, team_b, [2], [-1])
        winner, bet = run(players)
        assert winner is team_a
        assert bet == 1  # the opening raise was not accepted

    def test_a1_folds_after_b1_raises(self, teams):
        team_a, team_b = teams
        # A1 passes, B1 raises, A1 folds
        a1 = ScriptedPlayer("A1", team_a, wager_actions=[0, -1])
        b1 = ScriptedPlayer("B1", team_b, wager_actions=[2])
        winner, bet = run([a1, b1])
        assert winner is team_b
        assert bet == 1

    def test_fold_with_base_bet_zero(self, teams):
        team_a, team_b = teams
        players = make_players(team_a, team_b, [2], [-1])
        winner, bet = run(players, base_bet=0)
        assert winner is team_a
        assert bet == 1  # one point is already in play

    def test_fold_returns_last_accepted_bet(self, teams):
        team_a, team_b = teams
        # A1 raises 3, B1 raises 2, A1 folds
        a1 = ScriptedPlayer("A1", team_a, wager_actions=[3, -1])
        b1 = ScriptedPlayer("B1", team_b, wager_actions=[2])
        winner, bet = run([a1, b1])
        assert winner is team_b
        assert bet == 3  # B1's counterraise was not accepted


class TestWagerSessionRaiseAndCall:
    def test_raise_then_call_is_showdown(self, teams):
        team_a, team_b = teams
        # A1 offers a total of 2 and B1 accepts immediately.
        a1 = ScriptedPlayer("A1", team_a, wager_actions=[2])
        b1 = ScriptedPlayer("B1", team_b, wager_actions=[0])
        winner, bet = run([a1, b1])
        assert winner is None
        assert bet == 2

    def test_raise_amount_accumulated(self, teams):
        team_a, team_b = teams
        # A1 raises 5, B1 calls
        a1 = ScriptedPlayer("A1", team_a, wager_actions=[5])
        b1 = ScriptedPlayer("B1", team_b, wager_actions=[0])
        _, bet = run([a1, b1])
        assert bet == 5  # opening action is the offered total

    def test_counter_raise_then_call(self, teams):
        team_a, team_b = teams
        # A1 raises 2, B1 raises 3, A1 calls → showdown
        a1 = ScriptedPlayer("A1", team_a, wager_actions=[2, 0])
        b1 = ScriptedPlayer("B1", team_b, wager_actions=[3])
        events = []
        winner, bet = WagerSession(
            players=[a1, b1],
            teams=(team_a, team_b),
            base_bet=1,
            phase_name="Grande",
            team_scores={"A": 0, "B": 0},
            on_action=events.append,
        ).run()
        assert winner is None
        assert bet == 2 + 3  # later positive actions add increments
        assert events == [
            "Grande | A1: envida",
            "Grande | B1: envida 3 (total 5)",
            "Grande | A1: quiero",
        ]


class TestWagerSessionFourPlayers:
    def test_b1_raises_and_a2_accepts_for_team_a(self, teams):
        team_a, team_b = teams
        # A1 passes, B1 raises 2, A1 declines, and A2 accepts for Team A.
        a1 = ScriptedPlayer("A1", team_a, wager_actions=[0, -1])
        b1 = ScriptedPlayer("B1", team_b, wager_actions=[2])
        a2 = ScriptedPlayer("A2", team_a, wager_actions=[0])
        b2 = ScriptedPlayer("B2", team_b, wager_actions=[])
        winner, bet = WagerSession(
            [a1, b1, a2, b2], 1, "Grande", {}, teams=(team_a, team_b)
        ).run()
        assert winner is None
        assert bet == 2

    def test_fold_in_four_player_game(self, teams):
        team_a, team_b = teams
        # A1 raises, both eligible Team B players fold
        a1 = ScriptedPlayer("A1", team_a, wager_actions=[2])
        b1 = ScriptedPlayer("B1", team_b, wager_actions=[-1])
        a2 = ScriptedPlayer("A2", team_a, wager_actions=[])
        b2 = ScriptedPlayer("B2", team_b, wager_actions=[-1])
        winner, bet = WagerSession(
            [a1, b1, a2, b2], 1, "Grande", {}, teams=(team_a, team_b)
        ).run()
        assert winner is team_a
        assert bet == 1


class TestWagerSessionContext:
    def test_context_passed_with_correct_bet(self, teams):
        """Verify GameContext reflects updated bet amounts."""
        team_a, team_b = teams
        received_contexts = []

        class RecordingPlayer(ScriptedPlayer):
            def wager_action(self, context, private):
                received_contexts.append((context.wager.current_total, context.wager.previous_accepted_total))
                return super().wager_action(context, private)

        a1 = RecordingPlayer("A1", team_a, wager_actions=[2, 0])
        b1 = RecordingPlayer("B1", team_b, wager_actions=[0])

        WagerSession([a1, b1], 1, "Grande", {}, teams=(team_a, team_b)).run()

        # First call: the implicit point is already accepted.
        assert received_contexts[0] == (1, 1)
        # After A1 opens at 2: current=2, previous accepted stake=1
        assert received_contexts[1] == (2, 1)


def test_wager_session_passes_position_to_context():
    from mus_computer.game.wager_session import WagerSession
    from mus_computer.game.team import Team

    captured_positions = []

    class PositionCapturingPlayer(ScriptedPlayer):
        def wager_action(self, context, private):
            captured_positions.append(private.seat)
            return super().wager_action(context, private)

    team_a = Team("A")
    team_b = Team("B")
    p0 = PositionCapturingPlayer("p0", team_a, mus_votes=[], discards=[], wager_actions=[0, 0])
    p1 = PositionCapturingPlayer("p1", team_b, mus_votes=[], discards=[], wager_actions=[0, 0])

    WagerSession(
        players=[p0, p1],
        base_bet=1,
        phase_name="Grande",
        team_scores={"A": 0, "B": 0},
        discard_counts={},
        teams=(team_a, team_b),
    ).run()

    assert 0 in captured_positions
    assert 1 in captured_positions


def test_wager_session_passes_n_players_to_context():
    from mus_computer.game.wager_session import WagerSession
    from mus_computer.game.team import Team

    captured = []

    class CapturingPlayer(ScriptedPlayer):
        def wager_action(self, context, private):
            captured.append(len(context.eligible_seats))
            return super().wager_action(context, private)

    team_a, team_b = Team("A"), Team("B")
    p0 = CapturingPlayer("p0", team_a, mus_votes=[], discards=[], wager_actions=[0])
    p1 = CapturingPlayer("p1", team_b, mus_votes=[], discards=[], wager_actions=[0])

    WagerSession(
        players=[p0, p1],
        base_bet=1,
        phase_name="Chica",
        team_scores={"A": 0, "B": 0},
        discard_counts={},
        teams=(team_a, team_b),
    ).run()

    assert all(n == 2 for n in captured)


class TestTeamWagerResolution:
    @pytest.mark.parametrize("opening_action", [0])
    def test_pass_before_an_offer_allows_next_player_to_open(self, teams, opening_action):
        team_a, team_b = teams
        events = []
        players = [
            ScriptedPlayer("A1", team_a, wager_actions=[opening_action, 0]),
            ScriptedPlayer("B1", team_b, wager_actions=[2]),
        ]

        winner, points = WagerSession(
            players=players,
            teams=(team_a, team_b),
            base_bet=1,
            phase_name="Grande",
            team_scores={"A": 0, "B": 0},
            on_action=events.append,
        ).run()

        assert (winner, points) == (None, 2)
        assert events == [
            "Grande | A1: paso",
            "Grande | B1: envida",
            "Grande | A1: quiero",
        ]

    def test_opening_two_point_offer_sets_total(self, teams):
        team_a, team_b = teams
        events = []
        players = [
            ScriptedPlayer("A1", team_a, wager_actions=[2]),
            ScriptedPlayer("B1", team_b, wager_actions=[0]),
        ]

        winner, points = WagerSession(
            players=players,
            teams=(team_a, team_b),
            base_bet=1,
            phase_name="Grande",
            team_scores={"A": 0, "B": 0},
            on_action=events.append,
        ).run()

        assert (winner, points) == (None, 2)
        assert events == ["Grande | A1: envida", "Grande | B1: quiero"]

    def test_opening_three_point_offer_sets_total_to_three(self, teams):
        team_a, team_b = teams
        events = []
        players = [
            ScriptedPlayer("A1", team_a, wager_actions=[3]),
            ScriptedPlayer("B1", team_b, wager_actions=[0]),
        ]

        winner, points = WagerSession(
            players=players,
            teams=(team_a, team_b),
            base_bet=1,
            phase_name="Grande",
            team_scores={"A": 0, "B": 0},
            on_action=events.append,
        ).run()

        assert (winner, points) == (None, 3)
        assert events == ["Grande | A1: envida 3", "Grande | B1: quiero"]

    def test_one_opponent_accepts_opening_offer_immediately(self, teams):
        team_a, team_b = teams
        events = []
        players = [
            ScriptedPlayer("A1", team_a, wager_actions=[2]),
            ScriptedPlayer("B1", team_b, wager_actions=[0]),
            ScriptedPlayer("A2", team_a, wager_actions=[]),
            ScriptedPlayer("B2", team_b, wager_actions=[]),
        ]

        winner, points = WagerSession(
            players=players,
            teams=(team_a, team_b),
            base_bet=1,
            phase_name="Grande",
            team_scores={"A": 0, "B": 0},
            on_action=events.append,
        ).run()

        assert (winner, points) == (None, 2)
        assert events == ["Grande | A1: envida", "Grande | B1: quiero"]

    def test_one_decline_does_not_decide_for_teammate(self, teams):
        team_a, team_b = teams
        events = []
        players = [
            ScriptedPlayer("A1", team_a, wager_actions=[2]),
            ScriptedPlayer("B1", team_b, wager_actions=[-1]),
            ScriptedPlayer("A2", team_a, wager_actions=[]),
            ScriptedPlayer("B2", team_b, wager_actions=[0]),
        ]

        winner, points = WagerSession(
            players=players,
            teams=(team_a, team_b),
            base_bet=1,
            phase_name="Grande",
            team_scores={"A": 0, "B": 0},
            on_action=events.append,
        ).run()

        assert (winner, points) == (None, 2)
        assert events == [
            "Grande | A1: envida",
            "Grande | B1: no quiero",
            "Grande | B2: quiero",
        ]

    def test_declined_counterraise_awards_last_accepted_offer(self, teams):
        team_a, team_b = teams
        events = []
        players = [
            ScriptedPlayer("A1", team_a, wager_actions=[2, -1]),
            ScriptedPlayer("B1", team_b, wager_actions=[3]),
            ScriptedPlayer("A2", team_a, wager_actions=[-1]),
            ScriptedPlayer("B2", team_b, wager_actions=[]),
        ]

        winner, points = WagerSession(
            players=players,
            teams=(team_a, team_b),
            base_bet=1,
            phase_name="Grande",
            team_scores={"A": 0, "B": 0},
            on_action=events.append,
        ).run()

        assert (winner, points) == (team_b, 2)
        assert events == [
            "Grande | A1: envida",
            "Grande | B1: envida 3 (total 5)",
            "Grande | A1: no quiero",
            "Grande | A2: no quiero",
        ]


@pytest.mark.parametrize("action,total", [("RAISE_2",2),("RAISE_3",3),("RAISE_4",4),("RAISE_5",5)])
def test_typed_opening_raise_totals(teams, action, total):
    from mus_computer.bots.strategies.actions import WagerAction
    a, b = teams
    result = run(make_players(a,b,[WagerAction[action]],[WagerAction.MATCH_OR_PASS]))
    assert result.outcome.value == "showdown"
    assert result.points == total

@pytest.mark.parametrize("accepted", [True, False])
def test_ordago_response(teams, accepted):
    from mus_computer.bots.strategies.actions import WagerAction as A
    a,b = teams
    result = run(make_players(a,b,[A.ORDAGO],[A.MATCH_OR_PASS if accepted else A.FOLD]))
    assert result.outcome.value == ("ordago_accepted" if accepted else "declined")
    assert result.points == (0 if accepted else 1)
    assert result.winner_team is (None if accepted else a)


def test_refused_counter_ordago_keeps_accepted_stake(teams):
    from mus_computer.bots.strategies.actions import WagerAction as A
    a,b=teams
    result=run(make_players(a,b,[A.RAISE_2,A.FOLD],[A.ORDAGO],[A.FOLD],[A.MATCH_OR_PASS]))
    assert result.outcome.value == "declined"
    assert result.winner_team is b
    assert result.points == 2


@pytest.mark.parametrize("phase,base", [("Grande",1),("Chica",1),("Pares",0),("Juego",0),("Punto",1)])
@pytest.mark.parametrize("responses,outcome,points", [
    ([0],"showdown",2), ([-1,0],"showdown",2), ([-1,-1],"declined",1),
])
def test_each_phase_accepts_once_or_requires_all_eligible_refusals(teams,phase,base,responses,outcome,points):
    a,b=teams
    players=[ScriptedPlayer("A1",a,wager_actions=[2]),
             ScriptedPlayer("B1",b,wager_actions=responses[:1]),
             ScriptedPlayer("A2",a,wager_actions=[]),
             ScriptedPlayer("B2",b,wager_actions=responses[1:])]
    result=WagerSession(players,base,phase,{},teams).run()
    assert result.outcome.value==outcome
    assert result.points==points
    assert players[2]._wager_idx==0
    assert players[3]._wager_idx==len(responses)-1


def test_illegal_fold_before_offer_is_rejected(teams):
    from mus_computer.bots.strategies.actions import WagerAction
    a,b=teams
    with pytest.raises(ValueError,match="illegal wager"):
        run(make_players(a,b,[WagerAction.FOLD],[]))


@pytest.mark.parametrize("accepted", [True, False])
def test_wager_result_publishes_offering_team_and_accepted_stake(teams,accepted):
    a,b = teams
    result = run(make_players(a,b,[2],[0 if accepted else -1]))
    assert result.offering_team is a
    assert result.accepted_stake == (2 if accepted else 1)


def test_accepted_ordago_result_has_no_numeric_stake(teams):
    from mus_computer.bots.strategies.actions import WagerAction as A
    a,b = teams
    result = run(make_players(a,b,[A.ORDAGO],[A.MATCH_OR_PASS]))
    assert result.offering_team is a
    assert result.accepted_stake is None
