import pickle

from mus_computer.cards import Card, Deck, Hand
from mus_computer.game import Game, Pares
from mus_computer.bots import BotPlayer, RandomBotPlayer
from mus_computer.probabilities.tables import load_tables
from mus_computer.cli import build_default_game


def test_public_modules_import_from_the_package():
    assert Card.A.value == "A"
    assert Deck is not None and Hand is not None
    assert Game is not None and Pares is not None
    assert BotPlayer is not None and RandomBotPlayer is not None
    game = build_default_game()
    assert [player.name for player in game.players_in_order] == [
        "Bot 1", "Bot 2", "Bot 3", "Bot 4"
    ]
    assert [player.team.name for player in game.players_in_order] == [
        "A", "B", "A", "B"
    ]


def test_loads_packaged_probability_tables():
    tables = load_tables()
    assert len(tables) > 0
    assert "_avg_opp_phase_improvements" in tables


def test_explicit_table_path_is_independent_of_packaged_cache(tmp_path):
    path = tmp_path / "fixture.pkl"
    path.write_bytes(pickle.dumps({"fixture": 1}))
    assert load_tables(path) == {"fixture": 1}
    assert "_avg_opp_phase_improvements" in load_tables()
