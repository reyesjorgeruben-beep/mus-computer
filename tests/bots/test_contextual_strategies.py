"""A bot's injected strategies control decisions through fresh contexts."""

import random

import pytest

from mus_computer.bots import BotPlayer
from mus_computer.bots.bot_genome import BotGenome
from mus_computer.bots.strategies.actions import (
    ActionDistribution, DecisionKind, DiscardAction, MusAction, WagerAction,
)
from mus_computer.bots.strategies.contexts import (
    DiscardOption, HandStatistics, OutcomeProbability, PlayerDecisionContext,
)
from mus_computer.bots.strategies.portfolio import StrategyPortfolio
from mus_computer.cards.card import Card
from mus_computer.game.context import GlobalGameContext, WagerState
from mus_computer.game.team import Team


PHASES = ("Grande", "Chica", "Pares", "Juego", "Punto")


class FixedStrategy:
    def __init__(self, action):
        self.action = action

    def decide(self, global_context, player_context, personality):
        return ActionDistribution({self.action: 1.0})


class FixedDrawRandom(random.Random):
    """Use the same explicit draw for every bot decision in a toy scenario."""

    def __init__(self, draw):
        super().__init__()
        self.draw = draw

    def random(self):
        return self.draw


def genome(**changes):
    values = dict(
        mus_eagerness=0.5, mus_risk_sensitivity=0.5,
        w_grande=0.25, w_chica=0.25, w_pares=0.25, w_juego=0.25,
        discard_aggressiveness=0.5, bluff_rate=0.1, risk_factor=0.5,
        fold_threshold=0.3, raise_threshold=0.7,
        score_urgency_sensitivity=0.5, position_preference=0.5,
    )
    values.update(changes)
    return BotGenome(**values)


def global_context(phase=None, wager=None, scores=None, mus_exchanges=0, mano_seat=0):
    return GlobalGameContext(
        team_scores=scores or {"A": 0, "B": 0},
        mus_exchanges=mus_exchanges,
        phase_name=phase,
        wager=wager,
        public_actions=(),
        discard_counts={},
        seat_order=(("Bot 1", "A"), ("Bot 2", "B"), ("Bot 3", "A"), ("Bot 4", "B")),
        mano_seat=mano_seat,
        eligible_seats=(0, 1, 2, 3),
    )


def player_context(phase=None, probabilities=None, options=None, seat=0):
    probabilities = probabilities or {name: 0.5 for name in PHASES}
    stats = HandStatistics(
        {name: OutcomeProbability(value, 0.0, 1.0 - value)
         for name, value in probabilities.items()},
        {name: value * 2 for name, value in probabilities.items()},
    )
    return PlayerDecisionContext(
        player_name="Bot 1", team_name="A", seat=seat,
        cards=(Card.R, Card.R, Card.R, Card.R),
        phase_name=phase, eligible=True, intrinsic_points_by_phase={},
        statistics=stats,
        discard_options=options if options is not None else (DiscardOption(DiscardAction(()), stats),),
    )


def portfolio(mus=MusAction.MUS, discard=DiscardAction((0, 2)), wager=WagerAction.MATCH_OR_PASS):
    return StrategyPortfolio(
        mus=FixedStrategy(mus),
        discard=FixedStrategy(discard),
        wagers_by_phase={name: FixedStrategy(wager) for name in PHASES},
    )


@pytest.mark.parametrize("action", [MusAction.MUS, MusAction.CORTA])
def test_injected_mus_strategy_controls_typed_vote(action):
    bot = BotPlayer("Bot 1", Team("A"), genome(), portfolio(mus=action), random.Random(0))
    public = global_context()
    private = player_context()

    assert bot.take_decision(DecisionKind.MUS, public, private) is action
    assert bot.vote_mus(public, private) is action


def test_injected_discard_strategy_returns_original_card_indices():
    bot = BotPlayer("Bot 1", Team("A"), genome(), portfolio(), random.Random(0))
    public = global_context()
    statistics = player_context().statistics
    private = player_context(options=(
        DiscardOption(DiscardAction((0, 2)), statistics),
        DiscardOption(DiscardAction(()), statistics),
    ))

    assert bot.take_decision(DecisionKind.DISCARD, public, private) == DiscardAction((0, 2))
    assert bot.choose_discards(public, private) == (0, 2)


@pytest.mark.parametrize("action", list(WagerAction))
def test_injected_wager_strategy_returns_exact_typed_intent(action):
    state = WagerState(2, 1, "B", False) if action is WagerAction.FOLD else WagerState(1, 1, None, False)
    bot = BotPlayer("Bot 1", Team("A"), genome(), portfolio(wager=action), random.Random(0))
    public = global_context("Grande", state)
    private = player_context("Grande")

    assert bot.take_decision(DecisionKind.WAGER, public, private) is action
    assert bot.wager_action(public, private) is action


def test_injected_illegal_wager_action_is_rejected():
    bot = BotPlayer("Bot 1", Team("A"), genome(), portfolio(wager=WagerAction.FOLD))
    with pytest.raises(ValueError, match="illegal"):
        bot.wager_action(global_context("Grande", WagerState(1, 1, None)), player_context("Grande"))


def test_injected_portfolio_selects_only_the_current_phase_strategy():
    phases = {
        name: FixedStrategy(WagerAction.RAISE_2 if name == "Pares" else WagerAction.MATCH_OR_PASS)
        for name in PHASES
    }
    selected = StrategyPortfolio(FixedStrategy(MusAction.MUS), FixedStrategy(DiscardAction(())), phases)
    bot = BotPlayer("Bot 1", Team("A"), genome(), selected)

    assert bot.wager_action(global_context("Pares"), player_context("Pares")) is WagerAction.RAISE_2
    assert bot.wager_action(global_context("Grande"), player_context("Grande")) is WagerAction.MATCH_OR_PASS


def test_wager_strategy_interface_allows_a_different_score_policy():
    from mus_computer.bots.strategies.wagers import WagerStrategy

    class ScoreDrivenWagerStrategy(WagerStrategy):
        def decide(self, global_context, player_context, personality):
            action = (
                WagerAction.RAISE_2
                if global_context.team_scores[player_context.team_name] < 10
                else WagerAction.MATCH_OR_PASS
            )
            return ActionDistribution({action: 1.0})

    selected = StrategyPortfolio.default()
    wagers = dict(selected.wagers_by_phase)
    wagers["Grande"] = ScoreDrivenWagerStrategy()
    bot = BotPlayer(
        "Bot 1", Team("A"), personality=genome(),
        strategies=StrategyPortfolio(selected.mus, selected.discard, wagers),
    )

    assert bot.wager_action(global_context("Grande", scores={"A": 5, "B": 0}), player_context("Grande")) is WagerAction.RAISE_2
    assert bot.wager_action(global_context("Grande", scores={"A": 10, "B": 0}), player_context("Grande")) is WagerAction.MATCH_OR_PASS


def test_discard_action_must_be_one_of_the_estimated_legal_options():
    bot = BotPlayer("Bot 1", Team("A"), genome(), portfolio(discard=DiscardAction((0, 2))))
    with pytest.raises(ValueError, match="illegal"):
        bot.choose_discards(global_context(), player_context())


def test_default_portfolio_uses_distinct_phase_policies_and_phase_statistics():
    selected = StrategyPortfolio.default()
    assert len({id(policy) for policy in selected.wagers_by_phase.values()}) == 5
    baseline = player_context("Pares")
    changed = player_context("Pares", probabilities={name: (0.95 if name == "Pares" else 0.5) for name in PHASES})
    public = global_context("Pares", WagerState(1, 1, None))
    before = selected.wagers_by_phase["Pares"].decide(public, baseline, genome()).probabilities
    after = selected.wagers_by_phase["Pares"].decide(public, changed, genome()).probabilities
    assert after[WagerAction.RAISE_2] > before[WagerAction.RAISE_2]
    grande_public = global_context("Grande", WagerState(1, 1, None))
    grande_baseline = player_context("Grande")
    grande_changed = player_context(
        "Grande", probabilities={name: (0.95 if name == "Pares" else 0.5) for name in PHASES},
    )
    assert (
        selected.wagers_by_phase["Grande"].decide(grande_public, grande_baseline, genome()).probabilities
        == selected.wagers_by_phase["Grande"].decide(grande_public, grande_changed, genome()).probabilities
    )


def test_default_mus_policy_changes_with_private_estimates_and_personality():
    selected = StrategyPortfolio.default()
    weak = player_context(probabilities={name: 0.1 for name in PHASES})
    strong = player_context(probabilities={name: 0.9 for name in PHASES})
    public = global_context()
    weak_mus = selected.mus.decide(public, weak, genome()).probabilities[MusAction.MUS]
    strong_mus = selected.mus.decide(public, strong, genome()).probabilities[MusAction.MUS]
    eager_mus = selected.mus.decide(public, strong, genome(mus_eagerness=1.0)).probabilities[MusAction.MUS]
    assert weak_mus > strong_mus
    assert eager_mus > strong_mus


def test_default_mus_policy_responds_to_public_score_mus_count_and_position():
    selected = StrategyPortfolio.default()
    private = player_context()
    first = selected.mus.decide(global_context(mus_exchanges=0), private, genome()).probabilities[MusAction.MUS]
    later = selected.mus.decide(global_context(mus_exchanges=3), private, genome()).probabilities[MusAction.MUS]
    trailing = selected.mus.decide(global_context(scores={"A": 10, "B": 30}), private, genome()).probabilities[MusAction.MUS]
    no_mano = selected.mus.decide(global_context(mano_seat=1), private, genome()).probabilities[MusAction.MUS]
    assert later < first
    assert trailing > first
    assert no_mano > first


def test_default_discard_policy_uses_aggressiveness_only_to_break_value_ties():
    selected = StrategyPortfolio.default()
    ordinary = player_context(probabilities={name: 0.5 for name in PHASES}).statistics
    improved = player_context(probabilities={name: 0.53 for name in PHASES}).statistics
    better_discard = player_context(options=(
        DiscardOption(DiscardAction(()), ordinary),
        DiscardOption(DiscardAction((0,)), improved),
    ))
    public = global_context()
    conservative = selected.discard.decide(
        public, better_discard, genome(discard_aggressiveness=0)
    ).probabilities
    aggressive = selected.discard.decide(
        public, better_discard, genome(discard_aggressiveness=1)
    ).probabilities
    assert conservative == {DiscardAction((0,)): 1.0}
    assert aggressive == {DiscardAction((0,)): 1.0}

    tied_discards = player_context(options=(
        DiscardOption(DiscardAction(()), ordinary),
        DiscardOption(DiscardAction((0,)), ordinary),
    ))
    conservative_tie = selected.discard.decide(
        public, tied_discards, genome(discard_aggressiveness=0)
    ).probabilities
    aggressive_tie = selected.discard.decide(
        public, tied_discards, genome(discard_aggressiveness=1)
    ).probabilities
    assert conservative_tie == {DiscardAction(()): 1.0}
    assert aggressive_tie == {DiscardAction((0,)): 1.0}


def test_default_wager_policy_changes_with_thresholds_and_public_context():
    selected = StrategyPortfolio.default()
    policy = selected.wagers_by_phase["Grande"]
    private = player_context("Grande", probabilities={name: 0.7 for name in PHASES})
    opening = global_context("Grande", WagerState(1, 1, None))
    cautious = policy.decide(opening, private, genome(raise_threshold=0.9)).probabilities
    bold = policy.decide(opening, private, genome(raise_threshold=0.1)).probabilities
    trailing = policy.decide(global_context("Grande", WagerState(1, 1, None), scores={"A": 5, "B": 30}), private, genome(raise_threshold=0.1)).probabilities
    later = policy.decide(global_context("Grande", WagerState(1, 1, None), mus_exchanges=3), private, genome(raise_threshold=0.1)).probabilities
    other_position = policy.decide(global_context("Grande", WagerState(1, 1, None), mano_seat=2), private, genome(raise_threshold=0.1)).probabilities
    assert WagerAction.FOLD not in cautious
    assert bold[WagerAction.RAISE_2] > cautious[WagerAction.RAISE_2]
    assert trailing[WagerAction.RAISE_2] > bold[WagerAction.RAISE_2]
    assert later[WagerAction.RAISE_2] > bold[WagerAction.RAISE_2]
    assert other_position[WagerAction.RAISE_2] != bold[WagerAction.RAISE_2]


def test_default_wager_response_contains_fold_and_ordago_response_is_restricted():
    selected = StrategyPortfolio.default()
    private = player_context("Juego", probabilities={name: 0.1 for name in PHASES})
    policy = selected.wagers_by_phase["Juego"]
    offered = policy.decide(global_context("Juego", WagerState(2, 1, "B")), private, genome()).probabilities
    ordago = policy.decide(global_context("Juego", WagerState(2, 1, "B", True)), private, genome()).probabilities
    assert offered[WagerAction.FOLD] > 0
    assert set(ordago) == {WagerAction.MATCH_OR_PASS, WagerAction.FOLD}


def test_injected_weighted_mus_strategy_uses_context_and_a_fixed_draw():
    class ToyMusStrategy:
        def decide(self, global_context, player_context, personality):
            win_chance = player_context.statistics.outcomes_by_phase["Grande"].p_win
            mus_chance = 0.46 if win_chance < 0.5 else 0.06
            return ActionDistribution({
                MusAction.MUS: mus_chance,
                MusAction.CORTA: 1.0 - mus_chance,
            })

    public = global_context()
    weak = player_context(probabilities={name: 0.1 for name in PHASES})
    strong = player_context(probabilities={name: 0.9 for name in PHASES})
    draw = 0.3
    defaults = StrategyPortfolio.default()
    strategies = StrategyPortfolio(ToyMusStrategy(), defaults.discard, defaults.wagers_by_phase)
    bot = BotPlayer("Bot 1", Team("A"), genome(), strategies, FixedDrawRandom(draw))

    assert bot.vote_mus(public, weak) is MusAction.MUS
    assert bot.vote_mus(public, strong) is MusAction.CORTA


def test_default_bot_wager_uses_contextual_weights_when_sampling():
    public = global_context("Grande", WagerState(2, 1, "B"))
    weak = player_context("Grande", probabilities={name: 0.05 for name in PHASES})
    strong = player_context("Grande", probabilities={name: 0.95 for name in PHASES})
    personality = genome()
    bot = BotPlayer("Bot 1", Team("A"), personality, random_generator=FixedDrawRandom(0.85))

    weak_weights = bot.strategies.wagers_by_phase["Grande"].decide(
        public, weak, personality,
    ).probabilities
    strong_weights = bot.strategies.wagers_by_phase["Grande"].decide(
        public, strong, personality,
    ).probabilities
    assert 0 < weak_weights[WagerAction.FOLD] < 1
    assert strong_weights[WagerAction.FOLD] == 0
    assert strong_weights[WagerAction.RAISE_4] > weak_weights[WagerAction.RAISE_4]
    assert bot.wager_action(public, weak) is WagerAction.FOLD
    assert bot.wager_action(public, strong) is WagerAction.RAISE_4


def test_default_bot_discard_choice_is_certain_but_changes_with_estimated_value():
    public = global_context()
    low = player_context(probabilities={name: 0.2 for name in PHASES}).statistics
    high = player_context(probabilities={name: 0.8 for name in PHASES}).statistics
    keep_is_better = player_context(options=(
        DiscardOption(DiscardAction(()), high),
        DiscardOption(DiscardAction((0,)), low),
    ))
    exchange_is_better = player_context(options=(
        DiscardOption(DiscardAction(()), low),
        DiscardOption(DiscardAction((0,)), high),
    ))
    personality = genome()
    bot = BotPlayer("Bot 1", Team("A"), personality)

    assert bot.strategies.discard.decide(public, keep_is_better, personality).probabilities == {
        DiscardAction(()): 1.0,
    }
    assert bot.strategies.discard.decide(public, exchange_is_better, personality).probabilities == {
        DiscardAction((0,)): 1.0,
    }
    assert bot.choose_discards(public, keep_is_better) == ()
    assert bot.choose_discards(public, exchange_is_better) == (0,)
