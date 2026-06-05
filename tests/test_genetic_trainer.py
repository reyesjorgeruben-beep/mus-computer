import pytest
from bot_genome import BotGenome, random_genome
from genetic_trainer import GeneticTrainer, evaluate_game, build_bot_game


def test_trainer_init_creates_population():
    trainer = GeneticTrainer(population_size=10, generations=1, games_per_eval=2)
    population = trainer.initial_population()
    assert len(population) == 10
    assert all(isinstance(g, BotGenome) for g in population)


def test_evaluate_game_returns_winning_team():
    import random
    random.seed(0)
    genomes = [random_genome() for _ in range(4)]
    winner = evaluate_game(genomes)
    assert winner in ("A", "B")


def test_fitness_evaluation_returns_rates_in_range():
    import random
    random.seed(1)
    trainer = GeneticTrainer(population_size=4, generations=1, games_per_eval=2)
    population = trainer.initial_population()
    fitness = trainer.evaluate_population(population)
    assert len(fitness) == 4
    assert all(0.0 <= f <= 1.0 for f in fitness)


def test_next_generation_same_size():
    import random
    random.seed(2)
    trainer = GeneticTrainer(population_size=10, generations=1, games_per_eval=1)
    population = trainer.initial_population()
    fitness = trainer.evaluate_population(population)
    next_gen = trainer.next_generation(population, fitness)
    assert len(next_gen) == 10


def test_next_generation_all_botgenome():
    import random
    random.seed(3)
    trainer = GeneticTrainer(population_size=6, generations=1, games_per_eval=1)
    population = trainer.initial_population()
    fitness = trainer.evaluate_population(population)
    next_gen = trainer.next_generation(population, fitness)
    assert all(isinstance(g, BotGenome) for g in next_gen)


def test_save_and_load_population(tmp_path):
    import random
    random.seed(4)
    trainer = GeneticTrainer(population_size=4, generations=1, games_per_eval=1)
    population = trainer.initial_population()
    path = tmp_path / "pop.json"
    trainer.save_population(population, path)
    loaded = trainer.load_population(path)
    assert len(loaded) == 4
    for orig, load in zip(population, loaded):
        assert orig == load
