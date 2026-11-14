# Phase-specific CFR betting models

Run from the project environment:

```powershell
python -m mus_computer.training.cfr --policy glm --iterations 100 --seed 7 --glm-learning-rate 0.1 --run-dir docs/training/cfr_runs/glm_seed7
```

`--policy tabular` remains the default comparison baseline. GLM mode trains
only wagering; mus and discards use the unchanged strategy portfolio, including
the existing sampling exploration. The separate `coefficient_cfr` and genetic
trainers are unchanged. Game rules, physical shuffled decks, four-player shared
self-play, scoring, legal actions and paired evaluation are reused.

## Predictors and public events

### Reusable scoring and fitting

`linear_softmax.py` is independent of Mus phases and action enums. Its caller
supplies block names, action names and input names. It initializes fresh weights,
computes linear scores and legal-action probabilities, and fits explicit weighted
target distributions. For example:

```python
from mus_computer.training.cfr.linear_softmax import (
    BlockSpec, initialize_coefficients, predict_distribution,
)

spec = BlockSpec(("left", "right"), ("bias",))
weights = initialize_coefficients({"route": spec})
# {"route": {"left": {"bias": 0.0}, "right": {"bias": 0.0}}}
probabilities = predict_distribution(weights["route"], {"bias": 1.0}, spec.actions)
# {"left": 0.5, "right": 0.5}
```

Each initialization creates independent dictionaries; parameters are not shared
mutable globals. The old helper read global game catalogues but also created
fresh dictionaries. Its replacement receives the schema explicitly instead of
knowing about betting. `_betting_schema(phases, stages, actions)` is the adapter
that declares the Mus-specific inputs and coefficient blocks.

`ProjectionExample` carries a block, named input values, legal action names,
target probabilities and a positive fitting mass. The generic fitter does not
choose CFR targets or add sampling corrections. `GLMCFRPolicy` owns those choices
and supplies separate examples for current and accumulated-average targets.
Outputs are ordinary probability maps; callers can feed them into another model
as named inputs without changing the scoring engine. No pipeline scheduler or
new training objective is introduced. Checkpoint layout `phase_glm_v1` is unchanged.

For each legal action `a`, in phase `p` and betting stage `s`:

```text
z[p,s,a] = baseline[p,s,a]
         + hand_strength[p,s,a] * (1 - own_phase_p_loss)
         + sum(history[p,s,a,l] * opponent_wager[l])
P(a) = exp(z[a] - max(z)) / sum_legal exp(z[b] - max(z))
```

These are categorical softmax logits, not separately normalized binary
probabilities. Every raise size, ordago, fold, and match/pass has its own
coefficients. Match/pass means pass in the opening block and call in response
blocks. Stages are `opening`, `response` (first offer), `counter_raise`
(two or more numeric/ordago offers in the current phase), and
`ordago_response` (takes precedence when ordago is outstanding).
Existing legality masks still govern every stage; no new action restrictions
are imposed. All coefficients initially equal zero, giving a uniform legal
wager policy; hand strength and history effects are learned independently.

| Model phase | Earlier-lance indicators |
|---|---|
| Grande | None |
| Chica | Grande |
| Pares | Grande, Chica |
| Juego | Grande, Chica, Pares |
| Punto | Grande, Chica, Pares |

An indicator is one when either opposing player emitted an opening bet,
numeric raise or ordago in that earlier lance in the current hand. The parser
recognizes the game's `Lance | Player: envida`, `envida N`,
`envida N (total T)`, and `ordago` events (N from 2 through 5). It maps the
game's display label `Pequeña` to `Chica`. Opposing identity comes from
`GlobalGameContext.seat_order` and the actor's team. Own-team offers, calls
(`quiero`), passes (`paso`), folds (`no quiero`), declarations, unknown
players, and current/future-lance events do not activate history indicators.
Repeated offers still produce one. No opponent cards are read. History resets
with the game's existing per-hand public history.

`features.PREVIOUS_LANCES` and `feature_names` declare the permitted inputs.
Checkpoint names such as
`Chica/response -> WagerAction:fold -> opponent_wager_Grande` identify each
coefficient. No parameters are indexed by complete histories. Additional
features can extend this declaration/extractor in a future checkpoint version;
wager counts/sizes, player identity, score and hand-strength interactions are
not implemented.

## Actual learning update

Each iteration freezes one shared model before sampling and counterfactual
rollouts. In GLM mode, one visited **betting** decision per player is selected
uniformly, and every legal alternative is evaluated using the existing replay
and continuation machinery. For selected history `h`:

```text
delta_R[a] = N_betting_i * pi_other(h) / q_actions(h)
             * (Q[a] - sum_b P[b] Q[b])
strategy_sum[a] += pi_i(h) / q_actions(h) * P[a]
```

Prefix reaches still include mus/discard actions. Chance sampling cancels as
in existing CFR. No final-game policy-gradient or reward-regression objective
replaces these counterfactual differences.

The implementation retains per-information-state cumulative regrets and
strategy sums. Current targets are regret matching of those cumulative
regrets, with the existing portfolio prior as fallback. Each target's fitting
weight is its total positive regret mass, or one for fallback states. Average
targets are the table's normalized strategy sums, weighted by their total
accumulated reach mass. These sums already contain the sampling corrections;
the fit does not multiply them by counterfactual/reach weights again.

Each iteration takes **one full-batch weighted cross-entropy gradient step**
over all retained states, independently for each phase/stage block and for
current and average coefficient sets:

```text
theta[a,f] += learning_rate * sum_h normalized_weight[h]
              * (target[h,a] - predicted[h,a]) * feature[h,f]
```

Weights normalize within a block; they are rescaled before summing for numerical
stability. Frozen predictions precede each block's parameter update. The
average model approximates the exact accumulated average targets; it is not
an arithmetic average of coefficients or an alias of the current model.

## Checkpoints and limits

Snapshots serialize current/average coefficients, retained features, regret
and strategy sums, config, trainer RNG state, evaluation checkpoint and metrics.
Resume in Python with the same custom strategy portfolio if one was used:

```python
from pathlib import Path
from mus_computer.training.cfr import CFRTrainer

trainer = CFRTrainer.from_snapshot(Path("run/snapshots/iteration_000010.json"),
                                   run_dir=Path("run"))
trainer.train()  # completes remaining iterations in the saved config
```

Legacy tabular policy snapshots still load through `CFRPolicy.from_snapshot`;
exact trainer continuation requires the new RNG/config metadata. Evaluation
continues to use the existing current/average interfaces and deterministic
seeds. Generated training output remains ignored and uncommitted.

Linear fitting is approximate: different histories share logits, one gradient
step need not reach the projection optimum, and softmax cannot exactly express
zero probabilities with finite parameters. The training tables and full-batch
replay still grow with visited information states; only the predictive model is
compact. Sampling weights retain the existing estimator's high variance. The
existing four-player/team and per-hand recall limitations remain, with no CFR
convergence or playing-strength guarantee. This implementation has correctness
and reproducibility tests; longer learning-quality comparisons remain future work.
