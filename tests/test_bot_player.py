import random
import pytest
from card import Card
from team import Team
from bot_genome import BotGenome, random_genome
from bot_player import BotPlayer

TEAM_A = Team("A")
TEAM_B = Team("B")
WIN_SCORE = 40


def _bot(genome: BotGenome = None) -> BotPlayer:
    g = genome or random_genome()
    bot = BotPlayer("bot", TEAM_A, g)
    bot.receive_cards([Card.R, Card.R, Card.R, Card.R])
    bot.set_round_state(
        team_scores={"A": 0, "B": 0},
        my_team_name="A",
        position=0,
        n_players=4,
        opponent_discard_counts=[0, 0],
        mus_rounds_completed=0,
    )
    return bot


def test_bot_player_is_player_base():
    from player_base import PlayerBase
    assert isinstance(_bot(), PlayerBase)


def test_vote_mus_returns_bool():
    bot = _bot()
    result = bot.vote_mus()
    assert isinstance(result, bool)


def test_vote_mus_weak_hand_more_likely_yes():
    """Bot with very weak Grande hand (all aces) should vote yes to mus more often
    than one with a very strong hand (all kings)."""
    random.seed(42)
    genome = BotGenome(
        mus_eagerness=0.1,
        mus_risk_sensitivity=0.5,
        w_grande=0.5, w_chica=0.2, w_pares=0.2, w_juego=0.1,
        discard_aggressiveness=0.5,
        bluff_rate=0.0, risk_factor=0.5,
        fold_threshold=0.3, raise_threshold=0.7,
        score_urgency_sensitivity=0.5,
        position_preference=0.5,
    )

    def vote_rate(cards):
        yes = 0
        for _ in range(200):
            bot = BotPlayer("b", TEAM_A, genome)
            bot.receive_cards(cards)
            bot.set_round_state({"A": 0, "B": 0}, "A", 0, 4, [0, 0], 0)
            if bot.vote_mus():
                yes += 1
        return yes / 200

    weak_rate = vote_rate([Card.A, Card.A, Card.A, Card.A])
    strong_rate = vote_rate([Card.R, Card.R, Card.R, Card.R])
    assert weak_rate > strong_rate


def test_choose_discards_returns_valid_indices():
    random.seed(0)
    bot = _bot()
    discards = bot.choose_discards()
    assert isinstance(discards, list)
    assert all(0 <= i < 4 for i in discards)
    assert len(discards) == len(set(discards))


def test_choose_discards_keeps_all_kings():
    """Bot with w_grande=1 and low aggressiveness should keep four kings."""
    random.seed(0)
    genome = BotGenome(
        mus_eagerness=0.5, mus_risk_sensitivity=0.5,
        w_grande=1.0, w_chica=0.0, w_pares=0.0, w_juego=0.0,
        discard_aggressiveness=0.0,
        bluff_rate=0.0, risk_factor=0.5,
        fold_threshold=0.2, raise_threshold=0.8,
        score_urgency_sensitivity=0.0, position_preference=0.5,
    )
    bot = BotPlayer("b", TEAM_A, genome)
    bot.receive_cards([Card.R, Card.R, Card.R, Card.R])
    bot.set_round_state({"A": 0, "B": 0}, "A", 0, 4, [0, 0], 0)
    assert bot.choose_discards() == []


def test_wager_action_folds_when_prob_very_low():
    """Bot with fold_threshold=0.95 and no bluff should fold with worst Grande hand."""
    random.seed(0)
    genome = BotGenome(
        mus_eagerness=0.5, mus_risk_sensitivity=0.0,
        w_grande=1.0, w_chica=0.0, w_pares=0.0, w_juego=0.0,
        discard_aggressiveness=0.0,
        bluff_rate=0.0, risk_factor=0.5,
        fold_threshold=0.95,
        raise_threshold=0.99,
        score_urgency_sensitivity=0.0, position_preference=0.5,
    )
    bot = BotPlayer("b", TEAM_A, genome)
    bot.receive_cards([Card.A, Card.A, Card.A, Card.A])
    bot.set_round_state({"A": 0, "B": 0}, "A", 0, 4, [0, 0], 0)

    from game_context import GameContext
    ctx = GameContext(
        phase_name="Grande",
        team_scores={"A": 0, "B": 0},
        current_bet=1, previous_bet=0,
        hand=bot.cards, position=0, n_players=4,
    )
    result = bot.wager_action(ctx)
    assert result < 0


def test_wager_action_raises_when_prob_high():
    """Bot with raise_threshold=0.1 should raise with best Grande hand."""
    random.seed(0)
    genome = BotGenome(
        mus_eagerness=0.5, mus_risk_sensitivity=0.0,
        w_grande=1.0, w_chica=0.0, w_pares=0.0, w_juego=0.0,
        discard_aggressiveness=0.0,
        bluff_rate=0.0, risk_factor=0.5,
        fold_threshold=0.05, raise_threshold=0.10,
        score_urgency_sensitivity=0.0, position_preference=0.5,
    )
    bot = BotPlayer("b", TEAM_A, genome)
    bot.receive_cards([Card.R, Card.R, Card.R, Card.R])
    bot.set_round_state({"A": 0, "B": 0}, "A", 0, 4, [0, 0], 0)

    from game_context import GameContext
    ctx = GameContext(
        phase_name="Grande",
        team_scores={"A": 0, "B": 0},
        current_bet=1, previous_bet=0,
        hand=bot.cards, position=0, n_players=4,
    )
    result = bot.wager_action(ctx)
    assert result > 0


def test_wager_action_bluffs_at_high_bluff_rate():
    """Bot with bluff_rate=1.0 should raise regardless of hand."""
    random.seed(0)
    genome = BotGenome(
        mus_eagerness=0.5, mus_risk_sensitivity=0.0,
        w_grande=1.0, w_chica=0.0, w_pares=0.0, w_juego=0.0,
        discard_aggressiveness=0.0,
        bluff_rate=1.0,
        risk_factor=0.5,
        fold_threshold=0.3, raise_threshold=0.7,
        score_urgency_sensitivity=0.0, position_preference=0.5,
    )
    bot = BotPlayer("b", TEAM_A, genome)
    bot.receive_cards([Card.A, Card.A, Card.A, Card.A])
    bot.set_round_state({"A": 0, "B": 0}, "A", 0, 4, [0, 0], 0)

    from game_context import GameContext
    ctx = GameContext(
        phase_name="Grande",
        team_scores={"A": 0, "B": 0},
        current_bet=1, previous_bet=0,
        hand=bot.cards, position=0, n_players=4,
    )
    result = bot.wager_action(ctx)
    assert result > 0
