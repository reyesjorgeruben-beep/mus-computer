"""Track decision effects as genes are introduced."""

import random
from dataclasses import replace

from mus_computer.bots.bot_genome import BotGenome
from mus_computer.bots.strategies.actions import MusAction
from mus_computer.bots.strategies.mus import GeneCutMusStrategy
from mus_computer.training.constants import USED_GENES
from mus_computer.training.game_runner import GenomeMatchup, build_bot_game


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
            public = game._global_context()
            private = player.decision_context(public, 0)
            probability = player.strategies.mus_strategy.decide(
                public, private, player._personality,
            ).probabilities[MusAction.MUS]
            results.append((tuple(player.cards), probability))
    finally:
        random.setstate(previous_state)

    assert results[0] == results[1]


def test_only_three_cut_genes_are_active_in_training_matchups():
    assert USED_GENES == ["cut_prone", "cut_prone_with_pares", "cut_prone_with_juego"]
    baseline = BotGenome(*([0.5] * 13))
    game = build_bot_game(GenomeMatchup(baseline, baseline, seed=77))
    assert all(isinstance(player.strategies.mus_strategy, GeneCutMusStrategy) for player in game.players_in_order)
