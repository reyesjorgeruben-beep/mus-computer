import pytest
from mus_computer.game.team import Team
from mus_computer.cards.card import Card
from mus_computer.game.wager_session import WagerSession
from tests.conftest import ScriptedPlayer


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
        players = make_players(team_a, team_b, [1], [-1])
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
            def wager_action(self, context):
                received_contexts.append((context.current_bet, context.previous_bet))
                return super().wager_action(context)

        a1 = RecordingPlayer("A1", team_a, wager_actions=[2, 0])
        b1 = RecordingPlayer("B1", team_b, wager_actions=[0])

        WagerSession([a1, b1], 1, "Grande", {}, teams=(team_a, team_b)).run()

        # First call: base bet=1, prev=0
        assert received_contexts[0] == (1, 0)
        # After A1 opens at 2: current=2, previous accepted stake=1
        assert received_contexts[1] == (2, 1)


def test_wager_session_passes_position_to_context():
    from mus_computer.game.wager_session import WagerSession
    from mus_computer.game.team import Team
    from tests.conftest import ScriptedPlayer

    captured_positions = []

    class PositionCapturingPlayer(ScriptedPlayer):
        def wager_action(self, context):
            captured_positions.append(context.position)
            return 0

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
    from tests.conftest import ScriptedPlayer

    captured = []

    class CapturingPlayer(ScriptedPlayer):
        def wager_action(self, context):
            captured.append(context.n_players)
            return 0

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
    @pytest.mark.parametrize("opening_action", [0, -1])
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

    def test_opening_one_point_offer_keeps_base_stake(self, teams):
        team_a, team_b = teams
        events = []
        players = [
            ScriptedPlayer("A1", team_a, wager_actions=[1]),
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

        assert (winner, points) == (None, 1)
        assert events == ["Grande | A1: envida 1", "Grande | B1: quiero"]

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
