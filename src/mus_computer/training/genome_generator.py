"""Replaceable population creation and winner driven genome variation."""

import random
from dataclasses import fields
from typing import Protocol

from mus_computer.bots.bot_genome import BotGenome, crossover, mutate, random_genome


class GenomeGenerator(Protocol):
    def initial_population(self, size: int) -> list[BotGenome]: ...

    def next_generation(
        self, population: list[BotGenome], fitness: list[float],
    ) -> list[BotGenome]: ...


class GeneticGenomeGenerator:
    """Keep the strongest genomes and vary children selected by win rate."""

    def __init__(
        self,
        elite_fraction: float = 0.05,
        mutation_rate: float = 0.15,
        mutation_sigma: float = 0.05,
        tournament_k: int = 5,
    ) -> None:
        self.elite_fraction = elite_fraction
        self.mutation_rate = mutation_rate
        self.mutation_sigma = mutation_sigma
        self.tournament_k = tournament_k

    def initial_population(self, size: int) -> list[BotGenome]:
        return [random_genome() for _ in range(size)]

    def _select(self, population: list[BotGenome], fitness: list[float]) -> BotGenome:
        candidates = random.sample(range(len(population)), min(self.tournament_k, len(population)))
        return population[max(candidates, key=lambda i: fitness[i])]

    def next_generation(
        self, population: list[BotGenome], fitness: list[float],
    ) -> list[BotGenome]:
        if len(population) != len(fitness) or not population:
            raise ValueError("Population and fitness must have the same nonzero length")
        count = len(population)
        elite_count = max(1, round(count * self.elite_fraction))
        ranked = sorted(range(count), key=lambda i: fitness[i], reverse=True)
        next_population = [population[i] for i in ranked[:elite_count]]
        while len(next_population) < count:
            first = self._select(population, fitness)
            second = self._select(population, fitness)
            next_population.append(mutate(crossover(first, second), self.mutation_rate, self.mutation_sigma))
        return next_population


class CustomGeneticGenomeGenerator:
    """Build averaged alpha pairs, varied alpha copies, and varied beta copies.

    Each gene receives an independent additive change within the stated range.
    Alpha is the highest scoring half by default; ties retain population order.
    """

    def __init__(self, alpha_fraction: float = 0.5) -> None:
        if not 0 < alpha_fraction <= 2 / 3:
            raise ValueError("alpha_fraction must be above zero and at most two thirds")
        self.alpha_fraction = alpha_fraction

    def initial_population(self, size: int) -> list[BotGenome]:
        return [random_genome() for _ in range(size)]

    @staticmethod
    def _vary(genome: BotGenome, amount: float) -> BotGenome:
        return BotGenome(*(
            max(0.0, min(1.0, getattr(genome, field.name) + random.uniform(-amount, amount)))
            for field in fields(BotGenome)
        ))

    @staticmethod
    def _average(first: BotGenome, second: BotGenome) -> BotGenome:
        return BotGenome(*(
            (getattr(first, field.name) + getattr(second, field.name)) / 2
            for field in fields(BotGenome)
        ))

    def next_generation(
        self, population: list[BotGenome], fitness: list[float],
    ) -> list[BotGenome]:
        if len(population) != len(fitness) or len(population) < 2:
            raise ValueError("Population and fitness must have the same length of at least two")
        count = len(population)
        alpha_count = max(1, int(count * self.alpha_fraction))
        ranked = sorted(range(count), key=lambda index: fitness[index], reverse=True)
        alpha = [population[index] for index in ranked[:alpha_count]]
        beta = [population[index] for index in ranked[alpha_count:]]

        paired_alpha = alpha.copy()
        random.shuffle(paired_alpha)
        averaged = [
            self._average(paired_alpha[i], paired_alpha[i + 1])
            for i in range(0, len(paired_alpha) - 1, 2)
        ]
        varied_alpha = [self._vary(genome, 0.10) for genome in alpha]
        beta_count = count - len(averaged) - len(varied_alpha)
        varied_beta = [self._vary(genome, 0.15) for genome in random.sample(beta, beta_count)]
        return averaged + varied_alpha + varied_beta
