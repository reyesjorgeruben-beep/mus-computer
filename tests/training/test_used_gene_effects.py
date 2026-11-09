"""Track decision effects as genes are introduced."""

import random
from dataclasses import replace

from mus_computer.bots.bot_genome import BotGenome
from mus_computer.bots.bot_player import BotPlayer
from mus_computer.bots.strategies.actions import MusAction, WagerAction
from mus_computer.bots.strategies.mus import AlwaysCutMusStrategy
from mus_computer.game.phases import PhaseName
from mus_computer.training.constants import USED_GENES
from mus_computer.training.game_runner import GenomeMatchup, build_bot_game
from tests.conftest import require_bot_players


def test_mus_eagerness_does_not_change_real_game_mus_decision():
    baseline = BotGenome(*([0.5] * 13))
    results = []
    previous_state = random.getstate()
    try:
        for value in (0.0, 1.0):
            genome = replace(baseline, mus_eagerness=value)
            random.seed(77)
            game = build_bot_game(GenomeMatchup(genome, baseline, seed=77))
            game._deal_initial_cards()
            player = game.players_in_order[0]
            assert isinstance(player, BotPlayer)
            public = game._global_context()
            private = player.decision_context(public, 0)
            probability = player.strategies.mus_strategy.decide(
                public,
                private,
                player._personality,
            ).probabilities[MusAction.MUS]
            results.append((tuple(player.cards), probability))
    finally:
        random.setstate(previous_state)

    assert results[0] == results[1]


def test_only_two_bluff_genes_are_active_in_training_matchups():
    assert USED_GENES == ["bluff_rate", "extreme_bluff_rate"]
    baseline = BotGenome(*([0.5] * 13))
    game = build_bot_game(GenomeMatchup(baseline, baseline, seed=77))
    assert all(
        isinstance(player.strategies.mus_strategy, AlwaysCutMusStrategy)
        for player in require_bot_players(game)
    )


def test_training_wager_strategy_responds_to_each_active_gene():
    baseline = BotGenome(*([0.5] * 13))
    game = build_bot_game(GenomeMatchup(baseline, baseline, seed=77))
    game._deal_initial_cards()
    player = game.players_in_order[0]
    assert isinstance(player, BotPlayer)
    public = game._global_context(PhaseName.GRANDE)
    private = player.decision_context(public, 0)
    strategy = player.strategies.wagers_by_phase[PhaseName.GRANDE]
    quiet = replace(baseline, bluff_rate=0, extreme_bluff_rate=0)
    regular = replace(quiet, bluff_rate=1)
    extreme = replace(quiet, extreme_bluff_rate=1)

    distributions = [
        strategy.decide(public, private, genome).probabilities
        for genome in (quiet, regular, extreme)
    ]

    assert distributions[1][WagerAction.RAISE_2] > distributions[0][WagerAction.RAISE_2]
    assert distributions[2][WagerAction.ORDAGO] > 0
