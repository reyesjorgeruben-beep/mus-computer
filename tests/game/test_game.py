import pytest
from mus_computer.cards.card import Card
from mus_computer.cards.hand import Hand
from mus_computer.game.team import Team
from mus_computer.game.game import Game
from mus_computer.game.phases import Grande, Chica, Pares, Juego, Punto
from tests.conftest import ScriptedPlayer


@pytest.fixture
def game():
    return Game("A1", "A2", "B1", "B2")


def replace_with_scripted(game, mus_votes=None, discards=None, wager_actions=None):
    """Swap out the game's HumanPlayers with ScriptedPlayers sharing the same teams."""
    team_a = game.players_in_order[0].team
    team_b = game.players_in_order[1].team
    mv = mus_votes or [[], [], [], []]
    dc = discards or [[], [], [], []]
    wa = wager_actions or [[0] * 20, [0] * 20, [0] * 20, [0] * 20]
    game.players_in_order = [
        ScriptedPlayer("A1", team_a, mus_votes=mv[0], discards=dc[0], wager_actions=wa[0]),
        ScriptedPlayer("B1", team_b, mus_votes=mv[1], discards=dc[1], wager_actions=wa[1]),
        ScriptedPlayer("A2", team_a, mus_votes=mv[2], discards=dc[2], wager_actions=wa[2]),
        ScriptedPlayer("B2", team_b, mus_votes=mv[3], discards=dc[3], wager_actions=wa[3]),
    ]


class TestGameDealing:
    def test_each_player_gets_four_cards(self, game):
        game._deal_initial_cards()
        assert all(len(p.cards) == 4 for p in game.players_in_order)

    def test_dealing_clears_existing_cards(self, game):
        game._deal_initial_cards()
        game._deal_initial_cards()
        assert all(len(p.cards) == 4 for p in game.players_in_order)

    def test_cards_come_from_deck(self, game):
        before = len(game.deck.cards)
        game._deal_initial_cards()
        assert len(game.deck.cards) == before - 16  # 4 players × 4 cards


class TestGameTeamIdentity:
    def test_team_a_players_share_team_object(self, game):
        a1 = game.players_in_order[0]
        a2 = game.players_in_order[2]
        assert a1.team is a2.team

    def test_team_b_players_share_team_object(self, game):
        b1 = game.players_in_order[1]
        b2 = game.players_in_order[3]
        assert b1.team is b2.team

    def test_teams_are_different_objects(self, game):
        team_a = game.players_in_order[0].team
        team_b = game.players_in_order[1].team
        assert team_a is not team_b


class TestGameMusVoting:
    def test_all_vote_yes(self, game):
        replace_with_scripted(game, mus_votes=[[True], [True], [True], [True]])
        assert game._all_vote_mus() is True

    def test_one_no_returns_false(self, game):
        replace_with_scripted(game, mus_votes=[[False], [True], [True], [True]])
        assert game._all_vote_mus() is False

    def test_first_player_no_short_circuits(self, game):
        replace_with_scripted(game, mus_votes=[[False], [], [], []])
        assert game._all_vote_mus() is False  # no IndexError


class TestGameMusPhase:
    def test_no_mus_cards_unchanged(self, game):
        replace_with_scripted(game, mus_votes=[[False], [False], [False], [False]])
        game._deal_initial_cards()
        original = [list(p.cards) for p in game.players_in_order]
        game._mus_phase()
        assert all(list(p.cards) == original[i] for i, p in enumerate(game.players_in_order))

    def test_mus_discards_and_redraws(self, game):
        # One round of mus: all vote yes, then all vote no. Each discards card 0.
        replace_with_scripted(
            game,
            mus_votes=[[True, False], [True, False], [True, False], [True, False]],
            discards=[[[0]], [[0]], [[0]], [[0]]],
        )
        game._deal_initial_cards()
        game._mus_phase()
        assert all(len(p.cards) == 4 for p in game.players_in_order)


class TestGamePlayersForPhase:
    def test_grande_all_four_players(self, game):
        game._deal_initial_cards()
        assert len(game._players_that_can_play(Grande)) == 4

    def test_chica_all_four_players(self, game):
        game._deal_initial_cards()
        assert len(game._players_that_can_play(Chica)) == 4

    def test_pares_none_without_pairs(self, game):
        for p in game.players_in_order:
            p.cards = [Card.A, Card.R, Card._5, Card._7]
        assert game._players_that_can_play(Pares) == []

    def test_pares_only_pair_holders(self, game):
        team_a = game.players_in_order[0].team
        for p in game.players_in_order:
            if p.team is team_a:
                p.cards = [Card.R, Card.R, Card._5, Card._7]
            else:
                p.cards = [Card.A, Card.R, Card._5, Card._7]
        result = game._players_that_can_play(Pares)
        assert len(result) == 2
        assert all(p.team is team_a for p in result)

    def test_juego_none_without_juego(self, game):
        for p in game.players_in_order:
            p.cards = [Card.A, Card._4, Card._5, Card._6]  # sum=16
        assert game._players_that_can_play(Juego) == []

    def test_juego_detected(self, game):
        for p in game.players_in_order:
            p.cards = [Card.R, Card.R, Card.R, Card.A]  # 31
        assert len(game._players_that_can_play(Juego)) == 4


class TestGameContested:
    def test_contested_when_both_teams(self, game):
        assert game._is_contested(game.players_in_order) is True

    def test_not_contested_single_team(self, game):
        team_a_players = [p for p in game.players_in_order if p.team.name == "A"]
        assert game._is_contested(team_a_players) is False


class TestGameResolvePhase:
    def test_team_a_wins_grande(self, game):
        team_a = game.players_in_order[0].team
        p = game.players_in_order
        p[0].cards = [Card.R, Card.R, Card.R, Card.C]   # A1: best overall
        p[1].cards = [Card.R, Card.R, Card.S, Card._7]  # B1
        p[2].cards = [Card.R, Card.R, Card.C, Card._7]  # A2
        p[3].cards = [Card.S, Card.S, Card._7, Card._6] # B2
        assert game._resolve_phase(Grande) is team_a

    def test_team_b_wins_grande(self, game):
        team_b = game.players_in_order[1].team
        p = game.players_in_order
        p[0].cards = [Card.A, Card.A, Card.A, Card._4]
        p[1].cards = [Card.R, Card.R, Card.R, Card.C]   # B1: best
        p[2].cards = [Card.A, Card.A, Card._4, Card._5]
        p[3].cards = [Card.R, Card.R, Card.S, Card._7]
        assert game._resolve_phase(Grande) is team_b

    def test_a2_is_team_a_champion(self, game):
        team_a = game.players_in_order[0].team
        p = game.players_in_order
        p[0].cards = [Card.A, Card.A, Card.A, Card._4]  # A1: weak
        p[1].cards = [Card.R, Card.S, Card._7, Card._6] # B1
        p[2].cards = [Card.R, Card.R, Card.C, Card._7]  # A2: team A champion
        p[3].cards = [Card.S, Card.S, Card._6, Card._5] # B2
        assert game._resolve_phase(Grande) is team_a

    def test_team_b_wins_chica(self, game):
        team_b = game.players_in_order[1].team
        p = game.players_in_order
        p[0].cards = [Card.R, Card.R, Card.R, Card.C]   # high cards (bad for Chica)
        p[1].cards = [Card.A, Card.A, Card.A, Card._4]  # B1: best (low)
        p[2].cards = [Card.R, Card.C, Card.S, Card._7]
        p[3].cards = [Card.A, Card.A, Card._4, Card._5]
        assert game._resolve_phase(Chica) is team_b


class TestGamePlayAllPhases:
    def test_grande_winner_gets_points(self, game):
        replace_with_scripted(game, wager_actions=[[0] * 20] * 4)
        p = game.players_in_order
        team_a = p[0].team
        # Give team A best hands for all phases
        p[0].cards = [Card.R, Card.R, Card.R, Card.C]
        p[1].cards = [Card.A, Card.A, Card.A, Card._4]
        p[2].cards = [Card.R, Card.C, Card.S, Card._7]
        p[3].cards = [Card.A, Card.A, Card._4, Card._5]
        initial_a = team_a.points
        game._play_all_phases()
        assert team_a.points > initial_a

    def test_no_players_for_pares_skips_phase(self, game):
        replace_with_scripted(game, wager_actions=[[0] * 20] * 4)
        for p in game.players_in_order:
            p.cards = [Card.A, Card.R, Card._5, Card._7]  # no pairs
        team_a = game.players_in_order[0].team
        team_b = game.players_in_order[1].team
        before_a = team_a.points
        before_b = team_b.points
        game._play_all_phases()
        # Pares phase was skipped; Grande/Chica still scored
        assert (team_a.points + team_b.points) > (before_a + before_b)

    def test_juego_absent_adds_punto(self, game):
        replace_with_scripted(game, wager_actions=[[0] * 20] * 4)
        for p in game.players_in_order:
            p.cards = [Card.A, Card._4, Card._5, Card._6]  # no juego (sum=16)
        # Should not raise; Punto replaces Juego
        game._play_all_phases()

    def test_normal_phase_points_wait_until_after_punto(self, game):
        replace_with_scripted(game, wager_actions=[[0] * 20 for _ in range(4)])
        for player in game.players_in_order:
            player.cards = [Card.A, Card._4, Card._5, Card._6]
        events = []
        game.on_action = events.append

        game._play_all_phases()

        punto_index = events.index("Punto begins")
        score_indices = [i for i, event in enumerate(events) if "| Score " in event]
        assert score_indices
        assert all(i > punto_index for i in score_indices)
        assert (game.teams[0].points, game.teams[1].points) == (3, 0)

    def test_fully_declined_raise_scores_before_later_phases(self, game):
        replace_with_scripted(
            game,
            wager_actions=[
                [1] + [0] * 20,
                [-1] + [0] * 20,
                [0] * 20,
                [-1] + [0] * 20,
            ],
        )
        for player in game.players_in_order:
            player.cards = [Card.A, Card._4, Card._5, Card._6]
        events = []
        game.on_action = events.append

        game._play_all_phases()

        immediate_score = "Team A +1 | Score A 1 - B 0"
        assert immediate_score in events
        assert events.index("Grande | A1: envida 1") < events.index("Grande | B1: no quiero")
        assert events.index("Grande | B1: no quiero") < events.index("Grande | B2: no quiero")
        assert events.index("Grande | B2: no quiero") < events.index(immediate_score)
        next_phase_index = next(
            i for i, event in enumerate(events)
            if event.endswith(" begins") and event != "Grande begins"
        )
        assert events.index(immediate_score) < next_phase_index
        punto_index = events.index("Punto begins")
        later_score_indices = [
            i for i, event in enumerate(events)
            if "| Score " in event and event != immediate_score
        ]
        assert all(i > punto_index for i in later_score_indices)


class TestQualifiedPhaseWagers:
    def test_pares_accepted_offer_counts_stake_and_pairs_once(self, game):
        replace_with_scripted(
            game,
            wager_actions=[
                [0, 0, 2, 0],
                [0, 0, 0, 0],
                [0, 0, 0],
                [0, 0, 0],
            ],
        )
        a1, b1, a2, b2 = game.players_in_order
        a1.cards = [Card._7, Card._7, Card._4, Card._5]
        b1.cards = [Card._4, Card._4, Card._5, Card._6]
        a2.cards = b2.cards = [Card.A, Card._4, Card._5, Card._6]
        events = []
        game.on_action = events.append

        game._play_all_phases()

        assert "Pares | A1: envida" in events
        assert "Pares | B1: quiero" in events
        assert not any(event.startswith(("Pares | A2:", "Pares | B2:")) for event in events)
        assert events.count("Pares | Team A wins the phase") == 1
        pares_award = next(i for i, event in enumerate(events) if event.startswith("Team A +3 |"))
        assert pares_award > events.index("Punto begins")
        assert len([event for event in events if "| Score " in event]) == 4

    def test_pares_single_eligible_defender_declines_without_pairs_award(self, game):
        replace_with_scripted(
            game,
            wager_actions=[
                [0, 0, 3, 0],
                [0, 0, -1, 0],
                [0, 0, 0],
                [0, 0, 0],
            ],
        )
        a1, b1, a2, b2 = game.players_in_order
        a1.cards = [Card._7, Card._7, Card._4, Card._5]
        b1.cards = [Card._4, Card._4, Card._5, Card._6]
        a2.cards = b2.cards = [Card.A, Card._4, Card._5, Card._6]
        events = []
        game.on_action = events.append

        game._play_all_phases()

        assert "Pares | B1: no quiero" in events
        assert not any(event.startswith("Pares | B2:") for event in events)
        assert "Pares | Team A wins the wager" in events
        assert "Pares | Team A wins the phase" not in events
        immediate_award = next(i for i, event in enumerate(events) if event.startswith("Team A +1 |"))
        assert events.index("Pares | B1: no quiero") < immediate_award < events.index("Juego begins")
        assert len([event for event in events if "| Score " in event]) == 4

    def test_juego_accepted_offer_counts_stake_and_juego_once(self, game):
        replace_with_scripted(
            game,
            wager_actions=[
                [0, 0, 2],
                [0, 0, 0],
                [0, 0],
                [0, 0],
            ],
        )
        a1, b1, a2, b2 = game.players_in_order
        a1.cards = [Card.R, Card.C, Card.S, Card.A]  # 31: three intrinsic points
        b1.cards = [Card.R, Card.C, Card.S, Card._4]
        a2.cards = b2.cards = [Card.A, Card._4, Card._5, Card._6]
        events = []
        game.on_action = events.append

        game._play_all_phases()

        assert "Juego | A1: envida" in events
        assert "Juego | B1: quiero" in events
        assert not any(event.startswith(("Juego | A2:", "Juego | B2:")) for event in events)
        assert events.count("Juego | Team A wins the phase") == 1
        juego_award = next(i for i, event in enumerate(events) if event.startswith("Team A +5 |"))
        assert juego_award > events.index("Juego | Team A wins the phase")
        assert len([event for event in events if "| Score " in event]) == 3

    def test_juego_two_eligible_defenders_must_both_decline(self, game):
        replace_with_scripted(
            game,
            wager_actions=[
                [0, 0, 2],
                [0, 0, -1],
                [0, 0],
                [0, 0, -1],
            ],
        )
        a1, b1, a2, b2 = game.players_in_order
        a1.cards = [Card.R, Card.C, Card.S, Card.A]
        b1.cards = [Card.R, Card.C, Card.S, Card._4]
        a2.cards = [Card.A, Card._4, Card._5, Card._6]
        b2.cards = [Card.R, Card.C, Card.S, Card._5]
        events = []
        game.on_action = events.append

        game._play_all_phases()

        assert events.index("Juego | B1: no quiero") < events.index("Juego | B2: no quiero")
        assert not any(event.startswith("Juego | A2:") for event in events)
        assert "Juego | Team A wins the wager" in events
        assert "Juego | Team A wins the phase" not in events
        immediate_award = next(i for i, event in enumerate(events) if event.startswith("Team A +1 |"))
        assert events.index("Juego | B2: no quiero") < immediate_award
        assert len([event for event in events if "| Score " in event]) == 3
