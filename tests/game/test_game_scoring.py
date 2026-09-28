import pytest
from mus_computer.cards.card import Card as C
from mus_computer.game.game import Game
from mus_computer.game.team import Team
from mus_computer.bots.strategies.actions import WagerAction as W
from tests.conftest import ScriptedPlayer


def make_game(hands, actions):
    a,b = Team("A"),Team("B")
    players=[ScriptedPlayer(f"Bot {i+1}", a if i%2==0 else b,
                            wager_actions=actions[i]) for i in range(4)]
    for player, cards in zip(players,hands):
        player.cards=list(cards)
    events=[]
    return Game.from_players(players, events.append),events


@pytest.mark.parametrize("hand,intrinsic", [
    ([C._7,C._7,C._4,C._5],1),
    ([C._7,C._7,C._4,C._4],3),
    ([C._7,C._7,C._7,C._4],2),
])
def test_folded_pares_intrinsic_is_deferred(hand,intrinsic):
    low=[C.A,C._4,C._5,C._6]
    game,events=make_game([hand,[C._4,C._4,C._5,C._6],low,low],
        [[0,0,2,0],[0,0,-1,0],[0,0,0],[0,0,0]])
    game._play_all_phases()
    scores=[e for e in events if "| Score" in e]
    assert len(scores)==5
    assert scores[0].startswith("Team A +1 |")
    assert scores[3].startswith(f"Team A +{intrinsic} |")
    assert events.index(scores[0]) < events.index("Juego begins")
    assert events.index(scores[3]) > events.index("Punto begins")


@pytest.mark.parametrize("hand,intrinsic", [([C.R,C.C,C.S,C.A],3),([C.R,C.C,C.S,C._4],2)])
def test_folded_juego_intrinsic_is_deferred(hand,intrinsic):
    low=[C.A,C._4,C._5,C._6]
    game,events=make_game([hand,[C.R,C.C,C.S,C._5],low,low],
        [[0,0,2],[0,0,-1],[0,0],[0,0]])
    game._play_all_phases()
    scores=[e for e in events if "| Score" in e]
    assert len(scores)==4
    assert scores[0].startswith("Team A +1 |")
    assert scores[-1].startswith(f"Team A +{intrinsic} |")


def test_ordered_settlement_stops_at_grande_winner():
    game,events=make_game([[C.R,C.C,C.S,C._7],[C.A,C._4,C._5,C._6],
                          [C.R,C.C,C.S,C._6],[C.A,C._4,C._5,C._7]], [[0]*5 for _ in range(4)])
    game.teams[0].points=game.teams[1].points=39
    game._play_all_phases()
    assert [t.points for t in game.teams]==[40,39]
    assert game.winner is game.teams[0]


def test_immediate_fold_reaches_40_and_skips_remaining_phases():
    game,events=make_game([[C.R,C.C,C.S,C._7]]*4, [[2],[-1],[],[-1]])
    game.teams[0].points=39
    game._play_all_phases()
    assert game.winner is game.teams[0]
    assert len([e for e in events if e.endswith(" begins")])==1


def test_accepted_ordago_ends_play_for_card_winner(monkeypatch):
    game,events=make_game([[C.A,C._4,C._5,C._6],[C.R,C.C,C.S,C._7],
                          [C.A,C._4,C._5,C._7],[C.R,C.C,C.S,C._6]],
                         [[W.ORDAGO],[W.MATCH_OR_PASS],[],[]])
    monkeypatch.setattr(game,"_deal_initial_cards", lambda: None)
    monkeypatch.setattr(game,"_mus_phase", lambda: None)
    assert game.play() is game.teams[1]
    assert [t.points for t in game.teams]==[0,0]
    assert len([e for e in events if e.endswith(" begins")])==1


def test_refused_ordago_scores_only_stake_and_continues():
    game,events=make_game([[C.A,C._4,C._5,C._6]]*4,
                         [[W.ORDAGO,0,0],[-1,0,0],[0,0],[-1,0,0]])
    game._play_all_phases()
    assert [t.points for t in game.teams]==[3,0]
    assert game.winner is None
    assert "Punto begins" in events


def test_folded_pares_awards_both_qualifying_winning_teammates():
    game,events=make_game([[C._7,C._7,C._4,C._5],[C._4,C._4,C._5,C._6],
                          [C.A,C.A,C._6,C._6],[C.A,C._4,C._5,C._6]],
                         [[0,0,2,0],[0,0,-1,0],[0,0,0],[0,0,0]])
    game._play_all_phases()
    scores=[e for e in events if "| Score" in e]
    assert scores[3].startswith("Team A +4 |")


def test_folded_juego_awards_both_qualifying_winning_teammates():
    game,events=make_game([[C.R,C.C,C.S,C.A],[C.R,C.C,C.S,C._5],
                          [C.R,C.C,C.S,C._4],[C.A,C._4,C._5,C._6]],
                         [[0,0,2],[0,0,-1],[0,0],[0,0]])
    game._play_all_phases()
    scores=[e for e in events if "| Score" in e]
    assert scores[-1].startswith("Team A +5 |")


def test_grande_settlement_selects_team_b_before_team_a_chica():
    game,events=make_game([[C.A,C._4,C._5,C._6],[C.R,C.C,C.S,C._7],
                          [C.A,C._4,C._5,C._7],[C.R,C.C,C.S,C._6]], [[0]*5 for _ in range(4)])
    game.teams[0].points=game.teams[1].points=39
    game._play_all_phases()
    assert [t.points for t in game.teams]==[39,40]
    assert game.winner is game.teams[1]
