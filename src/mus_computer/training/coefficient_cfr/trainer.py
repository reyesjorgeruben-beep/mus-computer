"""Frozen parallel batches and one averaged coefficient update per batch."""

from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path
import random
from statistics import mean, stdev

from .policy import Coefficients, PARAMETER_COUNT
from .round import sample_round


@dataclass(frozen=True)
class TrainingConfig:
    rounds: int = 1000
    batch_size: int = 16
    workers: int = 16
    learning_rate: float = 0.1
    seed: int = 7

    def __post_init__(self):
        if any(type(x) is not int or x < 1 for x in (self.rounds, self.batch_size, self.workers)):
            raise ValueError('Rounds, batch size, and workers must be positive integers')
        if not math.isfinite(self.learning_rate) or self.learning_rate <= 0:
            raise ValueError('Learning rate must be finite and positive')


def _evaluate(payload):
    seed, coefficients = payload
    return sample_round(seed, coefficients)


class CoefficientTrainer:
    """All four seats share one immutable policy until the batch completes."""

    def __init__(self, config: TrainingConfig | None = None):
        self.config = config or TrainingConfig()
        self.coefficients = Coefficients()
        self.metrics = []
        self.coefficient_history = [{'iteration': 0, **self.coefficients.as_dict()}]

    def train(self, run_dir: Path, *, evaluator=None) -> Coefficients:
        if evaluator is not None and self.config.workers != 1:
            raise ValueError('A custom evaluator requires serial execution')
        run_dir = Path(run_dir)
        run_dir.mkdir(parents=True, exist_ok=True)
        rng = random.Random(self.config.seed)
        executor = (ProcessPoolExecutor(max_workers=min(self.config.workers, self.config.batch_size))
                    if self.config.workers > 1 else None)
        try:
            for iteration in range(1, self.config.rounds + 1):
                seeds = [rng.randrange(2**63) for _ in range(self.config.batch_size)]
                frozen = self.coefficients
                results = (list(executor.map(_evaluate, ((seed, frozen) for seed in seeds)))
                           if executor else [(evaluator or sample_round)(seed, frozen) for seed in seeds])
                # Average both actors' improvements in units of a 40-piedra
                # match. No opponent derivative and no worker-side learning.
                gradient = tuple(sum(r.team_gradients[t][i] for r in results for t in (0, 1))
                                 / (len(results) * 2 * 40) for i in range(PARAMETER_COUNT))
                self.coefficients = frozen.updated(gradient, self.config.learning_rate)
                self.coefficient_history.append({'iteration': iteration, **self.coefficients.as_dict()})
                metric = {
                    'iteration': iteration,
                    'hands': iteration * len(results),
                    'expected_points': [mean(r.expected_points[t] for r in results) for t in (0, 1)],
                    'expected_local_penalty': [mean(r.penalties[t] for r in results) for t in (0, 1)],
                    'ordago_probability': mean(sum(o.probability for o in r.outcomes if o.reason == 'ordago')
                                               for r in results),
                    'max_probability_error': max(abs(sum(o.probability for o in r.outcomes) - 1)
                                                 for r in results),
                }
                self.metrics.append(metric)
                if iteration % 100 == 0 or iteration == self.config.rounds:
                    self.save(run_dir)
                    print(f"batch {iteration}/{self.config.rounds} | hands={metric['hands']} | "
                          f"penalties={metric['expected_local_penalty']} | "
                          f"ordago={metric['ordago_probability']:.3f}", flush=True)
        finally:
            if executor:
                executor.shutdown(wait=True, cancel_futures=True)
        # An inspectable hand evaluated under the FINAL coefficients, with
        # per-action probabilities, values, best-action gaps, and reach.
        example = sample_round(seeds[0], self.coefficients, details=True)
        payload = asdict(example)
        for decision in payload['decisions']:
            for key in ('probabilities', 'action_values', 'penalties'):
                decision[key] = {action.name.lower(): value for action, value in decision[key].items()}
        (run_dir / 'example_hand.json').write_text(
            json.dumps({'seed': seeds[0], **payload}, indent=2, allow_nan=False), encoding='utf-8')
        return self.coefficients

    def save(self, run_dir: Path, *, evaluation: dict | None = None):
        payload = {
            'method': 'exact-hand actor-local coefficient policy gradient (CFR-inspired)',
            'policy_version': 2,
            'config': asdict(self.config),
            'coefficients': self.coefficients.as_dict(),
            'metrics': self.metrics,
            'coefficient_history': self.coefficient_history,
        }
        if evaluation is not None:
            payload['evaluation_against_initial'] = evaluation
        (run_dir / 'training.json').write_text(json.dumps(payload, indent=2, allow_nan=False), encoding='utf-8')

    def evaluate_against_initial(self, pairs: int = 32) -> dict:
        """Unilateral held-out comparison, swapping policies across team sides."""
        if pairs < 2:
            raise ValueError('Evaluation requires at least two paired seeds')
        margins = []
        for offset in range(pairs):
            seed = self.config.seed + 10_000_000 + offset
            a = sample_round(seed, self.coefficients, Coefficients())
            b = sample_round(seed, Coefficients(), self.coefficients)
            margins.append((a.expected_points[0] - a.expected_points[1]
                            + b.expected_points[1] - b.expected_points[0]) / 2)
        return {'paired_deals': pairs, 'mean_piedra_margin': mean(margins),
                'approx_95pct_half_width': 1.96 * stdev(margins) / math.sqrt(pairs)}

