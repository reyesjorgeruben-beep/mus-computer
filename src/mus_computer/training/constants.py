"""Limits shared by training configuration and runners."""

MAX_CONCURRENT_GAMES = 16

# The composed Mus policy in genome matchups consumes exactly these genes.
USED_GENES = ["cut_prone", "cut_prone_with_pares", "cut_prone_with_juego"]
