"""BotPlayer consumes the latest public and private snapshots."""

import random

from mus_computer.bots.bot_genome import BotGenome
from mus_computer.bots.bot_player import BotPlayer
from mus_computer.bots.strategies.actions import MusAction, WagerAction
from mus_computer.bots.strategies.contexts import (
    HandStatistics, OutcomeProbability, PlayerDecisionContext,
)
from mus_computer.cards.card import Card
from mus_computer.game.context import GlobalGameContext, WagerState
from mus_computer.game.player_base import PlayerBase
from mus_computer.game.team import Team


PHASES = ("Grande", "Chica", "Pares", "Juego", "Punto")


def _genome(**changes):
    values = dict(
        mus_eagerness=0.5, mus_risk_sensitivity=0.5,
        w_grande=1.0, w_chica=0.0, w_pares=0.0, w_juego=0.0,
        discard_aggressiveness=0.5, bluff_rate=0.0, risk_factor=0.5,
        fold_threshold=0.3, raise_threshold=0.7,
        score_urgency_sensitivity=0.0, position_preference=0.5,
    )
    values.update(changes)
    return BotGenome(**values)


def _contexts(win_probability=0.5, phase=None, wager=None, cards=None):
    cards = cards or (Card.R, Card.R, Card.R, Card.R)
    stats = HandStatistics(
        {name: OutcomeProbability(win_probability, 0.0, 1.0 - win_probability)
         for name in PHASES},
        {name: win_probability * 2 for name in PHASES},
    )
    public = GlobalGameContext(
        {"A": 0, "B": 0}, 0, phase, wager, (), {},
        (("bot", "A"), ("other", "B"), ("mate", "A"), ("opponent", "B")),
        0, (0, 1, 2, 3),
    )
    private = PlayerDecisionContext(
        "bot", "A", 0, cards, phase, True, {}, stats, {(): stats},
    )
    return public, private


def test_bot_player_is_player_base():
    assert isinstance(BotPlayer("bot", Team("A"), _genome()), PlayerBase)


def test_bot_uses_fresh_private_statistics_for_mus():
    bot = BotPlayer("bot", Team("A"), _genome(), rng=random.Random(0))
    public, weak = _contexts(0.1)
    _, strong = _contexts(0.9)
    weak_chance = bot.strategies.mus.decide(public, weak, bot._genome).probabilities[MusAction.MUS]
    strong_chance = bot.strategies.mus.decide(public, strong, bot._genome).probabilities[MusAction.MUS]
    assert weak_chance > strong_chance


def test_conservative_discard_strategy_keeps_strong_hand():
    bot = BotPlayer("bot", Team("A"), _genome(discard_aggressiveness=0.0))
    public, private = _contexts(0.9)
    poor = HandStatistics(
        {name: OutcomeProbability(0.2, 0.0, 0.8) for name in PHASES},
        {name: 0.4 for name in PHASES},
    )
    private = PlayerDecisionContext(
        private.player_name, private.team_name, private.seat, private.cards,
        private.phase_name, private.eligible, private.intrinsic_points,
        private.statistics, {(): private.statistics, (0,): poor},
    )
    assert bot.choose_discards(public, private) == ()


def test_weak_hand_can_fold_a_wager_and_strong_hand_can_raise():
    bot = BotPlayer("bot", Team("A"), _genome(fold_threshold=0.9, raise_threshold=0.2))
    offered, weak = _contexts(0.05, "Grande", WagerState(2, 1, "B"))
    opening, strong = _contexts(0.95, "Grande", WagerState(1, 1, None))
    fold_distribution = bot.strategies.wagers_by_phase["Grande"].decide(
        offered, weak, bot._genome,
    ).probabilities
    raise_distribution = bot.strategies.wagers_by_phase["Grande"].decide(
        opening, strong, bot._genome,
    ).probabilities
    assert fold_distribution[WagerAction.FOLD] > 0
    assert raise_distribution[WagerAction.RAISE_2] > 0


def test_bluff_personality_increases_raises_with_same_weak_hand():
    public, private = _contexts(0.2, "Grande", WagerState(1, 1, None))
    cautious = BotPlayer("bot", Team("A"), _genome(bluff_rate=0.0))
    bluffer = BotPlayer("bot", Team("A"), _genome(bluff_rate=1.0))
    cautious_raise = cautious.strategies.wagers_by_phase["Grande"].decide(
        public, private, cautious._genome,
    ).probabilities[WagerAction.RAISE_2]
    bluff_raise = bluffer.strategies.wagers_by_phase["Grande"].decide(
        public, private, bluffer._genome,
    ).probabilities[WagerAction.RAISE_2]
    assert bluff_raise > cautious_raise
