import pytest
from team import Team


class TestTeam:
    def test_name_stored(self):
        t = Team("A")
        assert t.name == "A"

    def test_initial_points_zero(self):
        assert Team("A").points == 0

    def test_points_accumulate(self):
        t = Team("B")
        t.points += 5
        t.points += 3
        assert t.points == 8

    def test_two_teams_independent(self):
        a = Team("A")
        b = Team("B")
        a.points += 10
        assert b.points == 0

    def test_identity_not_name(self):
        a1 = Team("A")
        a2 = Team("A")
        assert a1 is not a2
