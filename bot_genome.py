import random
from dataclasses import dataclass, fields


@dataclass
class BotGenome:
    mus_eagerness: float
    mus_risk_sensitivity: float
    w_grande: float
    w_chica: float
    w_pares: float
    w_juego: float
    discard_aggressiveness: float
    bluff_rate: float
    risk_factor: float
    fold_threshold: float
    raise_threshold: float
    score_urgency_sensitivity: float
    position_preference: float


def random_genome() -> BotGenome:
    return BotGenome(*[random.random() for _ in range(13)])


def crossover(a: BotGenome, b: BotGenome) -> BotGenome:
    """Uniform crossover: each gene taken independently from parent A or B."""
    genes = [
        getattr(a, f.name) if random.random() < 0.5 else getattr(b, f.name)
        for f in fields(a)
    ]
    return BotGenome(*genes)


def mutate(genome: BotGenome, mutation_rate: float = 0.15, sigma: float = 0.05) -> BotGenome:
    """Gaussian mutation clipped to [0, 1] applied independently per gene."""
    genes = []
    for f in fields(genome):
        val = getattr(genome, f.name)
        if random.random() < mutation_rate:
            val = max(0.0, min(1.0, val + random.gauss(0, sigma)))
        genes.append(val)
    return BotGenome(*genes)
