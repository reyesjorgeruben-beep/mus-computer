from dataclasses import fields
import pytest

from mus_computer.bots.bot_genome import BotGenome
from mus_computer.training.genome_generator import CustomGeneticGenomeGenerator


def genome(value):
    return BotGenome(*([value] * len(fields(BotGenome))))


def test_alpha_pairs_are_averaged_and_alpha_beta_copies_are_perturbed(monkeypatch):
    population = [genome(i / 20) for i in range(20)]
    fitness = [1.0] * 10 + [0.0] * 10
    monkeypatch.setattr("random.shuffle", lambda values: None)
    monkeypatch.setattr("random.sample", lambda values, count: list(values)[:count])
    monkeypatch.setattr("random.uniform", lambda low, high: 0.0)

    children = CustomGeneticGenomeGenerator().next_generation(population, fitness)

    assert len(children) == 20
    assert [child.mus_eagerness for child in children[:5]] == pytest.approx(
        [(4 * i + 1) / 40 for i in range(5)]
    )
    assert children[5:15] == population[:10]
    assert children[15:] == population[10:15]
    assert all(child is not parent for child, parent in zip(children[5:15], population[:10]))


def test_perturbation_clamps_each_gene_to_unit_interval(monkeypatch):
    population = [genome(0.98)] * 10 + [genome(0.02)] * 10
    fitness = [1.0] * 10 + [0.0] * 10
    monkeypatch.setattr("random.uniform", lambda low, high: high if high == 0.10 else low)

    children = CustomGeneticGenomeGenerator().next_generation(population, fitness)

    assert all(0 <= value <= 1 for child in children for value in vars(child).values())
    assert children[5:15] == [genome(1.0)] * 10
    assert children[15:] == [genome(0.0)] * 5
