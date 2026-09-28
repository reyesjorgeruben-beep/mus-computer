from mus_computer.cards.card import Card as C
from mus_computer.game.game import Game
from mus_computer.game.team import Team
from tests.conftest import ScriptedPlayer


def test_real_mus_history_full_seats_and_private_hands_reach_each_decision():
    seen=[]
    class Recorder(ScriptedPlayer):
        def vote_mus(self, shared, private):
            seen.append(("mus",shared,private))
            return super().vote_mus(shared,private)
        def choose_discards(self, shared, private):
            seen.append(("discard",shared,private))
            return super().choose_discards(shared,private)
        def wager_action(self, shared, private):
            seen.append(("wager",shared,private))
            return super().wager_action(shared,private)
    a,b=Team("A"),Team("B")
    players=[Recorder(str(i),a if i%2==0 else b,mus_votes=[True,False],
                      discards=[[]],wager_actions=[0]*5) for i in range(4)]
    hands=[[C._7,C._7,C._4,C._5],[C.A,C._4,C._5,C._6],
           [C.A,C._4,C._5,C._7],[C._4,C._4,C._5,C._6]]
    for p,h in zip(players,hands): p.cards=h
    events=[]
    game=Game.from_players(players,events.append)
    game._emit_hands()
    game._mus_phase()
    game._play_all_phases()
    assert any(e.startswith("Hands |") for e in events)
    for kind,shared,private in seen:
        assert shared.seat_order==(("0","A"),("1","B"),("2","A"),("3","B"))
        assert private.cards==tuple(hands[private.seat])
        assert not any(e.startswith("Hands |") for e in shared.public_actions)
        assert not hasattr(shared,"cards")
        if kind=="wager":
            assert shared.mus_exchanges==1
            assert "Mus | 0: corta" in shared.public_actions
            if shared.phase_name=="Pares":
                assert shared.eligible_seats==(0,3)
                assert private.seat in (0,3)
    assert any(shared.phase_name=="Pares" for _,shared,_ in seen)


def test_duplicate_teammate_names_keep_absolute_seats_and_phase_eligibility():
    seen=[]
    class Recorder(ScriptedPlayer):
        def vote_mus(self, shared, private):
            seen.append(("mus",self,private))
            return super().vote_mus(shared,private)
        def choose_discards(self, shared, private):
            seen.append(("discard",self,private))
            return super().choose_discards(shared,private)
        def wager_action(self, shared, private):
            seen.append((shared.phase_name,self,private))
            return super().wager_action(shared,private)
    a,b=Team("A"),Team("B")
    players=[Recorder("same" if i%2==0 else str(i), a if i%2==0 else b,
                      mus_votes=[True,False],discards=[[]],wager_actions=[0]*5)
             for i in range(4)]
    for player in players:
        player.cards=[C.A,C._4,C._5,C._6]
    players[2].cards=[C._7,C._7,C._4,C._5]
    players[3].cards=[C._4,C._4,C._5,C._6]
    game=Game.from_players(players)
    game._mus_phase()
    game._play_all_phases()
    for phase,player,private in seen:
        assert private.seat==next(i for i,p in enumerate(players) if p is player)
        assert private.eligible
    assert [(private.seat,private.eligible) for phase,_,private in seen if phase=="Pares"]==[(2,True),(3,True)]
