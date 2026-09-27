from game import Game
from random_bot_player import RandomBotPlayer
from team import Team

if __name__ == "__main__":
    team_a = Team("A")
    team_b = Team("B")
    players_in_order = [
        RandomBotPlayer("Bot 1", team_a),
        RandomBotPlayer("Bot 2", team_b),
        RandomBotPlayer("Bot 3", team_a),
        RandomBotPlayer("Bot 4", team_b),
    ]
    game = Game.from_players(players_in_order, on_action=print)
    game.play()
