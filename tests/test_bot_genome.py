import pytest
from bot_genome import BotGenome, random_genome, crossover, mutate

def test_random_genome_genes_in_range():
    g = random_genome()
    for field in g.__dataclass_fields__:
        val = getattr(g, field)
        assert 0.0 <= val <= 1.0, f"{field}={val} out of [0,1]"

def test_random_genome_returns_botgenome():
    assert isinstance(random_genome(), BotGenome)

def test_crossover_genes_from_parents():
    import random
    random.seed(42)
    parent_a = BotGenome(*([0.0] * 13))
    parent_b = BotGenome(*([1.0] * 13))
    child = crossover(parent_a, parent_b)
    for field in child.__dataclass_fields__:
        val = getattr(child, field)
        assert val in (0.0, 1.0), f"{field}={val} should come from a parent"

def test_crossover_returns_botgenome():
    a = random_genome()
    b = random_genome()
    assert isinstance(crossover(a, b), BotGenome)

def test_mutate_stays_in_range():
    import random
    random.seed(0)
    g = BotGenome(*([0.5] * 13))
    for _ in range(100):
        m = mutate(g, mutation_rate=1.0, sigma=0.5)
        for field in m.__dataclass_fields__:
            val = getattr(m, field)
            assert 0.0 <= val <= 1.0, f"{field}={val} out of [0,1]"

def test_mutate_with_rate_zero_returns_unchanged():
    g = BotGenome(*([0.3] * 13))
    m = mutate(g, mutation_rate=0.0, sigma=0.5)
    assert g == m

def test_genome_has_13_fields():
    assert len(BotGenome.__dataclass_fields__) == 13
