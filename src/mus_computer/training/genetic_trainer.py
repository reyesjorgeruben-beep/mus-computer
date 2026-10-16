"""Orchestrate genome matchups and delegate variation to a generator."""

import json
import random
import time
from dataclasses import asdict
from pathlib import Path

from mus_computer.bots.bot_genome import BotGenome
from mus_computer.training.game_runner import GenomeMatchup, TrainingGameRunner
from mus_computer.training.genome_generator import CustomGeneticGenomeGenerator, GenomeGenerator


class GeneticTrainer:
    def __init__(
        self,
        population_size: int = 20,
        generations: int = 300,
        games_per_eval: int = 1,
        gen_generator: GenomeGenerator | None = None,
        runner: TrainingGameRunner | None = None,
        seed: int = 0,
    ) -> None:
        if population_size < 2 or population_size % 2 or generations < 1 or games_per_eval < 1:
            raise ValueError("Training requires an even population of at least two, one generation, and one game")
        self.population_size = population_size
        self.generations = generations
        self.games_per_eval = games_per_eval
        self.games_per_generation = population_size * games_per_eval // 2
        self.seed = seed
        self.gen_generator = gen_generator or CustomGeneticGenomeGenerator()
        self.runner = runner or TrainingGameRunner()
        self._runner_open = False

    def initial_population(self) -> list[BotGenome]:
        return self.gen_generator.initial_population(self.population_size)

    def evaluate_population(
        self, population: list[BotGenome], generation: int = 0,
    ) -> list[float]:
        """Pair every genome once per round and score both sides of each game."""
        if len(population) != self.population_size:
            raise ValueError("Evaluation population size must match the trainer")
        matchups, seated_indices = self._build_matchups(population, generation)
        if not self._runner_open:
            with self.runner:
                results = self.runner.play_matchups(matchups)
        else:
            results = self.runner.play_matchups(matchups)
        if len(results) != len(matchups):
            raise ValueError("Runner returned the wrong number of results")
        wins = [0] * len(population)
        for result, (a_index, b_index) in zip(results, seated_indices):
            wins[a_index if result.winner == "A" else b_index] += 1
        return [wins / self.games_per_eval for wins in wins]

    def _build_matchups(
        self, population: list[BotGenome], generation: int,
    ) -> tuple[list[GenomeMatchup], list[tuple[int, int]]]:
        """Seat every genome once per pairing round and assign unique game seeds."""
        matchups: list[GenomeMatchup] = []
        seated_indices: list[tuple[int, int]] = []
        seed_start = self.seed + generation * self.games_per_generation
        for round_index in range(self.games_per_eval):
            indices = list(range(len(population)))
            random.shuffle(indices)
            for seat in range(0, len(indices), 2):
                a_index, b_index = indices[seat], indices[seat + 1]
                matchups.append(GenomeMatchup(
                    population[a_index], population[b_index], seed=seed_start + len(matchups),
                ))
                seated_indices.append((a_index, b_index))
        return matchups, seated_indices

    def next_generation(
        self, population: list[BotGenome], fitness: list[float],
    ) -> list[BotGenome]:
        return self.gen_generator.next_generation(population, fitness)

    def evolve(self, snapshot_every: int = 50) -> list[BotGenome]:
        """Run evolution and return the top half of the final generation."""
        if snapshot_every < 1:
            raise ValueError("snapshot_every must be positive")
        previous_state = random.getstate()
        try:
            random.seed(self.seed)
            with self.runner:
                self._runner_open = True
                try:
                    self.runner.warm_up()
                    return self._evolve_with_runner(snapshot_every)
                finally:
                    self._runner_open = False
        finally:
            random.setstate(previous_state)

    def _evolve_with_runner(self, snapshot_every: int) -> list[BotGenome]:
        population = self.initial_population()
        start = time.time()
        log_every = max(1, self.generations // 100)

        for generation in range(self.generations):
            generation_start = time.time()
            fitness = self.evaluate_population(population, generation=generation)
            generation_elapsed = time.time() - generation_start
            if (generation + 1) % log_every == 0 or generation == 0:
                self._log_generation(generation, start, generation_elapsed)
            if (generation + 1) % snapshot_every == 0:
                self.save_population(population, Path(f"population_gen{generation+1}.json"))
            if generation + 1 < self.generations:
                population = self.next_generation(population, fitness)
        winner_indices = sorted(range(len(population)), key=lambda i: fitness[i], reverse=True)
        return [population[i] for i in winner_indices[:len(population) // 2]]

    def _log_generation(self, generation: int, start: float, generation_elapsed: float) -> None:
        completed = generation + 1
        elapsed = time.time() - start
        remaining = elapsed / completed * (self.generations - completed)
        print(
            f"[{completed / self.generations * 100:5.1f}%] gen {completed}/{self.generations} | "
            f"games={self.games_per_generation} | "
            f"gen_time={generation_elapsed:.1f}s elapsed={elapsed:.0f}s eta={remaining:.0f}s"
        )

    def save_population(self, population: list[BotGenome], path) -> None:
        with open(path, "w") as output:
            json.dump([asdict(genome) for genome in population], output, indent=2)

    def load_population(self, path) -> list[BotGenome]:
        with open(path) as source:
            return [BotGenome(**data) for data in json.load(source)]


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Train Mus bot population with genetic algorithm")
    parser.add_argument("--pop", type=int, default=20, help="Even population size (default: 20)")
    parser.add_argument("--gen", type=int, default=300, help="Number of generations (default: 300)")
    parser.add_argument("--games", type=int, default=1, help="Pairing rounds per generation (default: 1)")
    parser.add_argument("--seed", type=int, default=0, help="Starting seed for a repeatable run (default: 0)")
    parser.add_argument("--snapshot", type=int, default=50, help="Save snapshot every N generations (default: 50)")
    parser.add_argument("--out", type=str, default="winning_genomes.json", help="Output file for final-generation winners (default: winning_genomes.json)")
    args = parser.parse_args()
    print(f"Training: pop={args.pop}, gen={args.gen}, games={args.games}")
    trainer = GeneticTrainer(
        population_size=args.pop, generations=args.gen, games_per_eval=args.games, seed=args.seed,
    )
    start = time.time()
    winners = trainer.evolve(snapshot_every=args.snapshot)
    elapsed = time.time() - start
    trainer.save_population(winners, Path(args.out))
    print(f"\nDone in {elapsed:.1f}s. {len(winners)} final-generation winners saved to {args.out}")
