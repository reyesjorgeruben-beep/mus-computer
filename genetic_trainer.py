import json
import random
from dataclasses import asdict
from pathlib import Path
from typing import List

from bot_genome import BotGenome, random_genome, crossover, mutate
from bot_player import BotPlayer
from game import Game
from team import Team


def build_bot_game(genomes: List[BotGenome]) -> Game:
    """Create a silent game with alternating A/B/A/B genome seats."""
    if len(genomes) != 4:
        raise ValueError("A bot game requires exactly four genomes.")
    team_a = Team("A")
    team_b = Team("B")
    players = [
        BotPlayer("A1", team_a, genomes[0]),
        BotPlayer("B1", team_b, genomes[1]),
        BotPlayer("A2", team_a, genomes[2]),
        BotPlayer("B2", team_b, genomes[3]),
    ]
    return Game.from_players(players)


def evaluate_game(genomes: List[BotGenome]) -> str:
    """Play one full game. Returns winning team name ('A' or 'B')."""
    game = build_bot_game(genomes)
    return game.play().name


class GeneticTrainer:
    def __init__(
        self,
        population_size: int = 100,
        generations: int = 300,
        games_per_eval: int = 10,
        elite_fraction: float = 0.05,
        mutation_rate: float = 0.15,
        mutation_sigma: float = 0.05,
        tournament_k: int = 5,
    ):
        self.population_size = population_size
        self.generations = generations
        self.games_per_eval = games_per_eval
        self.elite_fraction = elite_fraction
        self.mutation_rate = mutation_rate
        self.mutation_sigma = mutation_sigma
        self.tournament_k = tournament_k

    def initial_population(self) -> List[BotGenome]:
        return [random_genome() for _ in range(self.population_size)]

    def evaluate_population(self, population: List[BotGenome]) -> List[float]:
        """Each genome plays games_per_eval games against random opponents. Fitness = win rate."""
        wins = [0] * len(population)
        games = [0] * len(population)

        for genome_idx, genome in enumerate(population):
            for _ in range(self.games_per_eval):
                others = random.sample(
                    [g for i, g in enumerate(population) if i != genome_idx], 3
                )
                order = [(True, genome)] + [(False, other) for other in others]
                random.shuffle(order)
                genomes_game = [entry[1] for entry in order]

                winner = evaluate_game(genomes_game)
                pos = next(i for i, entry in enumerate(order) if entry[0])
                our_team = "A" if pos % 2 == 0 else "B"

                if winner == our_team:
                    wins[genome_idx] += 1
                games[genome_idx] += 1

        return [w / g if g > 0 else 0.0 for w, g in zip(wins, games)]

    def _tournament_select(self, population: List[BotGenome], fitness: List[float]) -> BotGenome:
        candidates = random.sample(list(range(len(population))), min(self.tournament_k, len(population)))
        best = max(candidates, key=lambda i: fitness[i])
        return population[best]

    def next_generation(self, population: List[BotGenome], fitness: List[float]) -> List[BotGenome]:
        n = len(population)
        n_elite = max(1, round(n * self.elite_fraction))
        sorted_idx = sorted(range(n), key=lambda i: fitness[i], reverse=True)
        new_gen = [population[i] for i in sorted_idx[:n_elite]]
        while len(new_gen) < n:
            parent_a = self._tournament_select(population, fitness)
            parent_b = self._tournament_select(population, fitness)
            child = crossover(parent_a, parent_b)
            child = mutate(child, self.mutation_rate, self.mutation_sigma)
            new_gen.append(child)
        return new_gen

    def evolve(self, snapshot_every: int = 50) -> BotGenome:
        """Run full evolution. Returns best genome found."""
        import time
        population = self.initial_population()
        best_genome = population[0]
        best_fitness = 0.0
        start = time.time()
        log_every = max(1, self.generations // 100)  # every 1% of progress

        for gen in range(self.generations):
            gen_start = time.time()
            fitness = self.evaluate_population(population)
            gen_elapsed = time.time() - gen_start

            top_fitness = max(fitness)
            mean_fitness = sum(fitness) / len(fitness)
            top_idx = fitness.index(top_fitness)
            if top_fitness > best_fitness:
                best_fitness = top_fitness
                best_genome = population[top_idx]

            if (gen + 1) % log_every == 0 or gen == 0:
                elapsed = time.time() - start
                pct = (gen + 1) / self.generations * 100
                remaining = (elapsed / (gen + 1)) * (self.generations - gen - 1)
                print(
                    f"[{pct:5.1f}%] gen {gen+1}/{self.generations} | "
                    f"best={top_fitness:.3f} mean={mean_fitness:.3f} | "
                    f"gen_time={gen_elapsed:.1f}s elapsed={elapsed:.0f}s eta={remaining:.0f}s"
                )

            if (gen + 1) % snapshot_every == 0:
                self.save_population(population, Path(f"population_gen{gen+1}.json"))

            population = self.next_generation(population, fitness)

        return best_genome

    def save_population(self, population: List[BotGenome], path) -> None:
        data = [asdict(g) for g in population]
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def load_population(self, path) -> List[BotGenome]:
        with open(path) as f:
            data = json.load(f)
        return [BotGenome(**d) for d in data]


if __name__ == "__main__":
    import argparse
    import time

    parser = argparse.ArgumentParser(description="Train Mus bot population with genetic algorithm")
    parser.add_argument("--pop", type=int, default=100, help="Population size (default: 100)")
    parser.add_argument("--gen", type=int, default=300, help="Number of generations (default: 300)")
    parser.add_argument("--games", type=int, default=10, help="Games per genome per generation (default: 10)")
    parser.add_argument("--snapshot", type=int, default=50, help="Save snapshot every N generations (default: 50)")
    parser.add_argument("--out", type=str, default="best_genome.json", help="Output file for best genome (default: best_genome.json)")
    args = parser.parse_args()

    print(f"Training: pop={args.pop}, gen={args.gen}, games={args.games}")
    trainer = GeneticTrainer(
        population_size=args.pop,
        generations=args.gen,
        games_per_eval=args.games,
    )
    start = time.time()
    best = trainer.evolve(snapshot_every=args.snapshot)
    elapsed = time.time() - start
    trainer.save_population([best], Path(args.out))
    print(f"\nDone in {elapsed:.1f}s. Best genome saved to {args.out}")
