import pickle

from mus_computer.bots import BotPlayer, RandomBotPlayer
from mus_computer.cards import Card, Deck, Hand
from mus_computer.cli import build_default_game
from mus_computer.game import Game, Pares
from mus_computer.probabilities.tables import load_tables


def test_public_modules_import_from_the_package():
    assert Card.A.value == "A"
    assert Deck is not None and Hand is not None
    assert Game is not None and Pares is not None
    assert BotPlayer is not None and RandomBotPlayer is not None
    game = build_default_game()
    assert [player.name for player in game.players_in_order] == [
        "Bot 1",
        "Bot 2",
        "Bot 3",
        "Bot 4",
    ]
    assert [player.team.name for player in game.players_in_order] == [
        "A",
        "B",
        "A",
        "B",
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


def test_training_import_does_not_require_optional_dependencies():
    import subprocess
    import sys
    from pathlib import Path

    source = Path(__file__).resolve().parents[1] / "src"
    result = subprocess.run(
        [
            sys.executable,
            "-S",
            "-c",
            (
                "import sys; sys.path.insert(0, sys.argv[1]); "
                "import mus_computer.training.game_runner"
            ),
            str(source),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
