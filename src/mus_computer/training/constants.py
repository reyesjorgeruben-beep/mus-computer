"""Limits shared by training configuration and runners."""

MAX_CONCURRENT_GAMES = 16
ALPHA_VARIATION = 0.03
BETA_VARIATION = 0.05

# The composed wager policy in genome matchups consumes exactly these genes.
USED_GENES = ["bluff_rate", "extreme_bluff_rate"]
