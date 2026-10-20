import random
from dataclasses import dataclass, fields


@dataclass
class BotGenome:
    """Serializable genetic representation implementing the strategy personality interface."""

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
    cut_prone: float = 0.5
    cut_prone_with_pares: float = 0.5
    cut_prone_with_juego: float = 0.5
    extreme_bluff_rate: float = 0.0


def random_genome() -> BotGenome:
    return BotGenome(*[random.random() for _ in fields(BotGenome)])


def crossover(first_parent: BotGenome, second_parent: BotGenome) -> BotGenome:
    """Uniform crossover: each gene taken independently from parent A or B."""
    genes = [
        getattr(first_parent, gene_field.name)
        if random.random() < 0.5
        else getattr(second_parent, gene_field.name)
        for gene_field in fields(first_parent)
    ]
    return BotGenome(*genes)


def mutate(genome: BotGenome, mutation_rate: float = 0.15, sigma: float = 0.05) -> BotGenome:
    """Gaussian mutation clipped to [0, 1] applied independently per gene."""
    genes = []
    for gene_field in fields(genome):
        gene_value = getattr(genome, gene_field.name)
        if random.random() < mutation_rate:
            gene_value = max(0.0, min(1.0, gene_value + random.gauss(0, sigma)))
        genes.append(gene_value)
    return BotGenome(*genes)
