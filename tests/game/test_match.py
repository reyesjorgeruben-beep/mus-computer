"""A match counts wins across independent games."""

from types import SimpleNamespace

import pytest

from mus_computer.game.match import Match


def test_match_stops_at_target_and_reports_both_game_win_counts():
    outcomes = iter(("A", "B", "B", "A", "B", "A"))
    games = []

    class StubGame:
        def __init__(self, winner):
            self.winner = winner

        def play(self):
            return SimpleNamespace(name=self.winner)

    def new_game():
        game = StubGame(next(outcomes))
        games.append(game)
        return game

    result = Match(new_game, wins_to_match=3).play()

    assert (result.winner, result.wins_a, result.wins_b) == ("B", 2, 3)
    assert not hasattr(result, "victory_reason")
    assert len(games) == 5
    assert len({id(game) for game in games}) == 5


@pytest.mark.parametrize("wins_to_match", [0, -1, 1.5, True])
def test_match_rejects_invalid_win_target(wins_to_match):
    with pytest.raises(ValueError, match="wins_to_match"):
        Match(lambda: None, wins_to_match)
