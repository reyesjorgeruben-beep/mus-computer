import pytest
from mus_computer.bots.bot_genome import BotGenome, random_genome
from mus_computer.training.genetic_trainer import GeneticTrainer
from mus_computer.training.game_runner import GameResult, GenomeMatchup, play_genome_game
from mus_computer.training.genome_generator import GenomeGenerator


def test_trainer_init_creates_population():
    trainer = GeneticTrainer(population_size=10, generations=1, games_per_eval=2)
    population = trainer.initial_population()
    assert len(population) == 10
    assert all(isinstance(g, BotGenome) for g in population)


def test_evaluate_game_returns_winning_team():
    import random
    random.seed(0)
    genomes = [random_genome() for _ in range(2)]
    winner = play_genome_game(GenomeMatchup(*genomes)).winner
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


def test_trainer_uses_injected_gen_generator_for_population_and_variation():
    class RecordingGenerator(GenomeGenerator):
        def __init__(self):
            self.next_fitness = None

        def initial_population(self, size):
            return [random_genome() for _ in range(size)]

        def next_generation(self, population, fitness):
            self.next_fitness = fitness
            return list(reversed(population))

    generator = RecordingGenerator()
    trainer = GeneticTrainer(population_size=4, generations=1, games_per_eval=1, gen_generator=generator)
    population = trainer.initial_population()
    assert len(population) == 4
    fitness = [0.0, 1.0, 0.5, 0.25]
    assert trainer.next_generation(population, fitness) == list(reversed(population))
    assert generator.next_fitness is fitness


def test_fitness_uses_winners_from_a_supplied_runner():
    population = [random_genome(), random_genome()]

    class FixedResultRunner:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def play_matchups(self, matchups):
            assert len(matchups) == 1
            winner = "A" if matchups[0].team_a is population[0] else "B"
            return [GameResult(winner, "points", 0.0, 1)]

    trainer = GeneticTrainer(population_size=2, generations=1, games_per_eval=1, runner=FixedResultRunner())
    assert trainer.evaluate_population(population) == [1.0, 0.0]


def test_twenty_genomes_are_paired_into_ten_games_once_each():
    population = [random_genome() for _ in range(20)]

    class RecordingRunner:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def play_matchups(self, matchups):
            assert len(matchups) == 10
            seated = [genome for matchup in matchups for genome in (matchup.team_a, matchup.team_b)]
            assert {id(genome) for genome in seated} == {id(genome) for genome in population}
            return [GameResult("A", "points", 0.0, 1) for _ in matchups]

    trainer = GeneticTrainer(population_size=20, generations=1, games_per_eval=1, runner=RecordingRunner())
    fitness = trainer.evaluate_population(population)
    assert sorted(fitness) == [0.0] * 10 + [1.0] * 10


def test_matchup_seeds_vary_with_game_and_generation():
    population = [random_genome() for _ in range(20)]
    batches = []

    class RecordingRunner:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def play_matchups(self, matchups):
            batches.append(matchups)
            return [GameResult("A", "points", 0.0, 1) for _ in matchups]

    runner = RecordingRunner()
    trainer = GeneticTrainer(population_size=20, games_per_eval=1, seed=42, runner=runner)
    trainer.evaluate_population(population, generation=0)
    trainer.evaluate_population(population, generation=1)
    assert [matchup.seed for matchup in batches[0]] == list(range(42, 52))
    assert [matchup.seed for matchup in batches[1]] == list(range(52, 62))


def test_generations_share_one_warmed_runner(monkeypatch):
    calls = []

    class RecordingRunner:
        def __enter__(self):
            calls.append("open")
            return self

        def __exit__(self, *args):
            calls.append("close")

        def warm_up(self):
            calls.append("warm")

        def play_matchups(self, matchups):
            calls.append(len(matchups))
            return [GameResult("A", "points", 0.0, 1) for _ in matchups]

    monkeypatch.setattr("mus_computer.training.genetic_trainer.TrainingGameRunner", RecordingRunner)
    trainer = GeneticTrainer(population_size=20, generations=2, games_per_eval=1)
    assert len(trainer.evolve()) == 10
    assert calls == ["open", "warm", 10, 10, "close"]


def test_evolve_returns_winners_from_final_generation(monkeypatch):
    first_generation = [random_genome() for _ in range(20)]
    final_generation = [random_genome() for _ in range(20)]
    batches = []

    class FixedGenerator:
        def initial_population(self, size):
            assert size == 20
            return first_generation

        def next_generation(self, population, fitness):
            assert population is first_generation
            return final_generation

    class RecordingRunner:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def warm_up(self):
            pass

        def play_matchups(self, matchups):
            batches.append(matchups)
            return [GameResult("A", "points", 0.0, 1) for _ in matchups]

    monkeypatch.setattr("mus_computer.training.genetic_trainer.TrainingGameRunner", RecordingRunner)
    winners = GeneticTrainer(generations=2, gen_generator=FixedGenerator()).evolve()
    assert len(batches) == 2
    assert len(winners) == 10
    assert {id(genome) for genome in winners} == {id(matchup.team_a) for matchup in batches[-1]}
    assert {id(genome) for genome in winners}.isdisjoint({id(genome) for genome in first_generation})


def test_seeded_training_is_repeatable_without_changing_callers_random_state(monkeypatch):
    import random

    class FixedRunner:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def warm_up(self):
            pass

        def play_matchups(self, matchups):
            return [GameResult("A", "points", 0.0, 1) for _ in matchups]

    monkeypatch.setattr("mus_computer.training.genetic_trainer.TrainingGameRunner", FixedRunner)
    state_before = random.getstate()
    first = GeneticTrainer(generations=2, seed=123).evolve()
    assert random.getstate() == state_before
    second = GeneticTrainer(generations=2, seed=123).evolve()
    assert first == second
