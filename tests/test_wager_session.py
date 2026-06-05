import pytest
from team import Team
from card import Card
from wager_session import WagerSession
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
    return WagerSession(players, base_bet, "Grande", {"A": 0, "B": 0}).run()


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
        assert bet == 3  # 1 + 2

    def test_a1_folds_after_b1_raises(self, teams):
        team_a, team_b = teams
        # A1 passes, B1 raises, A1 folds
        a1 = ScriptedPlayer("A1", team_a, wager_actions=[0, -1])
        b1 = ScriptedPlayer("B1", team_b, wager_actions=[2])
        winner, bet = run([a1, b1])
        assert winner is team_b
        assert bet == 3

    def test_fold_with_base_bet_zero(self, teams):
        team_a, team_b = teams
        players = make_players(team_a, team_b, [1], [-1])
        winner, bet = run(players, base_bet=0)
        assert winner is team_a
        assert bet == 1

    def test_fold_returns_current_bet_at_fold_time(self, teams):
        team_a, team_b = teams
        # A1 raises 3, B1 raises 2, A1 folds
        a1 = ScriptedPlayer("A1", team_a, wager_actions=[3, -1])
        b1 = ScriptedPlayer("B1", team_b, wager_actions=[2])
        winner, bet = run([a1, b1])
        assert winner is team_b
        assert bet == 1 + 3 + 2  # base + a1_raise + b1_raise


class TestWagerSessionRaiseAndCall:
    def test_raise_then_call_is_showdown(self, teams):
        team_a, team_b = teams
        # A1 raises 2, B1 calls, back to A1 (raiser) → showdown
        a1 = ScriptedPlayer("A1", team_a, wager_actions=[2])
        b1 = ScriptedPlayer("B1", team_b, wager_actions=[0])
        winner, bet = run([a1, b1])
        assert winner is None
        assert bet == 3

    def test_raise_amount_accumulated(self, teams):
        team_a, team_b = teams
        # A1 raises 5, B1 calls
        a1 = ScriptedPlayer("A1", team_a, wager_actions=[5])
        b1 = ScriptedPlayer("B1", team_b, wager_actions=[0])
        _, bet = run([a1, b1])
        assert bet == 6  # base 1 + raise 5

    def test_counter_raise_then_call(self, teams):
        team_a, team_b = teams
        # A1 raises 2, B1 raises 3, A1 calls → showdown
        a1 = ScriptedPlayer("A1", team_a, wager_actions=[2, 0])
        b1 = ScriptedPlayer("B1", team_b, wager_actions=[3])
        winner, bet = run([a1, b1])
        assert winner is None
        assert bet == 1 + 2 + 3  # 6


class TestWagerSessionFourPlayers:
    def test_b1_raises_team_a_both_call(self, teams):
        team_a, team_b = teams
        # A1 passes, B1 raises 2, A2 calls, B2 calls, back to B1 → showdown
        a1 = ScriptedPlayer("A1", team_a, wager_actions=[0, 0])
        b1 = ScriptedPlayer("B1", team_b, wager_actions=[2])
        a2 = ScriptedPlayer("A2", team_a, wager_actions=[0])
        b2 = ScriptedPlayer("B2", team_b, wager_actions=[0])
        winner, bet = WagerSession([a1, b1, a2, b2], 1, "Grande", {}).run()
        assert winner is None
        assert bet == 3

    def test_fold_in_four_player_game(self, teams):
        team_a, team_b = teams
        # A1 raises, B1 folds
        a1 = ScriptedPlayer("A1", team_a, wager_actions=[2])
        b1 = ScriptedPlayer("B1", team_b, wager_actions=[-1])
        a2 = ScriptedPlayer("A2", team_a, wager_actions=[])
        b2 = ScriptedPlayer("B2", team_b, wager_actions=[])
        winner, bet = WagerSession([a1, b1, a2, b2], 1, "Grande", {}).run()
        assert winner is team_a


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

        WagerSession([a1, b1], 1, "Grande", {}).run()

        # First call: base bet=1, prev=0
        assert received_contexts[0] == (1, 0)
        # After A1 raises by 2: bet=3, prev=1
        assert received_contexts[1] == (3, 1)


def test_wager_session_passes_position_to_context():
    from wager_session import WagerSession
    from team import Team
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
    ).run()

    assert 0 in captured_positions
    assert 1 in captured_positions


def test_wager_session_passes_n_players_to_context():
    from wager_session import WagerSession
    from team import Team
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
    ).run()

    assert all(n == 2 for n in captured)
