import pytest
from dataclasses import fields
from mus_computer.bots.bot_genome import BotGenome, random_genome, crossover, mutate

def test_random_genome_genes_in_range():
    genome = random_genome()
    for field in genome.__dataclass_fields__:
        gene_value = getattr(genome, field)
        assert 0.0 <= gene_value <= 1.0, f"{field}={gene_value} out of [0,1]"

def test_random_genome_returns_botgenome():
    assert isinstance(random_genome(), BotGenome)

def test_crossover_genes_from_parents():
    import random
    random.seed(42)
    parent_a = BotGenome(*([0.0] * len(fields(BotGenome))))
    parent_b = BotGenome(*([1.0] * len(fields(BotGenome))))
    child = crossover(parent_a, parent_b)
    for field in child.__dataclass_fields__:
        gene_value = getattr(child, field)
        assert gene_value in (0.0, 1.0), f"{field}={gene_value} should come from a parent"

def test_crossover_returns_botgenome():
    first_parent = random_genome()
    second_parent = random_genome()
    assert isinstance(crossover(first_parent, second_parent), BotGenome)

def test_mutate_stays_in_range():
    import random
    random.seed(0)
    genome = BotGenome(*([0.5] * 13))
    for _ in range(100):
        mutated_genome = mutate(genome, mutation_rate=1.0, sigma=0.5)
        for field in mutated_genome.__dataclass_fields__:
            gene_value = getattr(mutated_genome, field)
            assert 0.0 <= gene_value <= 1.0, f"{field}={gene_value} out of [0,1]"

def test_mutate_with_rate_zero_returns_unchanged():
    genome = BotGenome(*([0.3] * 13))
    mutated_genome = mutate(genome, mutation_rate=0.0, sigma=0.5)
    assert genome == mutated_genome

def test_genome_exposes_three_cut_genes():
    assert {field.name for field in fields(BotGenome)} >= {
        "cut_prone", "cut_prone_with_pares", "cut_prone_with_juego",
    }
