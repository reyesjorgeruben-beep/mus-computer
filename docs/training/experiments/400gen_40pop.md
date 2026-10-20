# 400-generation genome run

Command: `python -m mus_computer.training.genetic_trainer --pop 40 --gen 400 --games 1 --seed 0 --snapshot 401 --out winning_genomes_400gen_40pop.json`

The 40 genomes were paired into 20 games per generation, for 8,000 games total. The single process pool stayed open across generations. The run completed in 34.3 seconds. The output contains the 20 winning genomes from generation 400, with 13 genes each; all values are within [0, 1], and all 20 genomes are distinct. See `400gen_40pop.log` for timing by generation.

One matchup per genome gives binary fitness (0 or 1). The final winners are therefore the genomes that won their generation-400 matchups, not a ranking of their strength against multiple opponents. Increase `--games` for a less noisy win rate.
