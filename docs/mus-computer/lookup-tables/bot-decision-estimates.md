# Bot decision estimates

The bundled `probability_tables.pkl` contains per-hand outcomes for Grande,
Chica, Pares, Juego, and Punto. Punto compares each four-card hand against
physically possible opposing draws after removing that hand from the deck.
The other four phase entries retain their existing table probabilities.

Each hand also has `decision_discard_options`, indexed by the canonical cards
kept after a Mus exchange. Each phase entry contains `p_win`, `p_tie`,
`p_loss`, `expected_points_without_priority`, and
`expected_points_with_priority`. Replacement draws use the deck after removing
all four original cards. Expected points are averaged over each resulting hand,
including its intrinsic phase points. The priority variant counts ties as wins.

`estimate_discard_options` maps the 16 original card-index choices to these
precomputed retained-card entries. Duplicate ranks can lead to multiple index
choices using the same entry. Runtime decisions do not enumerate replacement
draws or combine probabilities from different sources.

To enrich an existing bundled table from PowerShell, run
`$env:PYTHONPATH='src;.'; python -m scripts.tables.enrich_decision_tables`
from the repository root. A full
`build_tables` or `build_and_save` run also generates these entries.
