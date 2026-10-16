"""Limits shared by training configuration and runners."""

MAX_CONCURRENT_GAMES = 16

# Built-in bot policies currently ignore personality; enable genes as each
# decision effect is reintroduced and verified on a fixed game state.
USED_GENES = []
