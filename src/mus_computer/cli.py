"""Run a four-bot Mus match from the terminal."""

import argparse
from collections.abc import Callable

from mus_computer.bots.random_bot_player import RandomBotPlayer
from mus_computer.game.game import Game
from mus_computer.game.team import Team


def build_default_game(on_action: Callable[[str], None] | None = None) -> Game:
    team_a = Team("A")
    team_b = Team("B")
    players = [
        RandomBotPlayer("Bot 1", team_a),
        RandomBotPlayer("Bot 2", team_b),
        RandomBotPlayer("Bot 3", team_a),
        RandomBotPlayer("Bot 4", team_b),
    ]
    return Game.from_players(players, on_action=on_action)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Play a Mus match with four bots")
    parser.parse_args(argv)
    build_default_game(on_action=print).play()
    return 0
