"""Portable, offline HTML views of immutable experiment JSON evidence."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from html import escape
from pathlib import Path

from .contracts import checked_ref, digest, read_json

_STYLE = """
:root{color-scheme:light;--ink:#163047;--muted:#536579;--line:#d7e1e9;--blue:#245b86;--teal:#087b70;--paper:#fff;--back:#edf2f6;--amber:#895b15}
*{box-sizing:border-box}body{margin:0;background:var(--back);color:var(--ink);font:16px/1.6 'Segoe UI',Arial,sans-serif}
main{max-width:1120px;margin:auto;padding:48px 32px 64px}header{border-top:6px solid var(--blue);padding-top:24px;margin-bottom:28px}
h1{font:500 clamp(2rem,5vw,3.4rem)/1.15 Georgia,serif;margin:8px 0 16px;max-width:820px}h2{font-size:1.35rem;margin:0 0 16px}h3{font-size:1rem}
p{max-width:76ch}nav{display:flex;gap:20px;flex-wrap:wrap}a{color:var(--blue);text-underline-offset:4px}a:focus-visible,summary:focus-visible{outline:3px solid var(--teal);outline-offset:4px}
.subtle{color:var(--muted)}.result{display:grid;grid-template-columns:1fr 1fr;gap:24px;background:var(--paper);padding:28px;margin:24px 0;border-left:5px solid var(--amber)}
.score{font-size:2.5rem;line-height:1.1;font-weight:650;display:block;margin-bottom:8px}.result h2{margin-bottom:8px}.result p{margin:4px 0}
section{background:var(--paper);margin:24px 0;padding:28px;border:1px solid var(--line);border-radius:8px}
.legend{display:flex;gap:24px;flex-wrap:wrap;font-size:.9rem;margin-bottom:18px}.legend i{display:inline-block;width:20px;height:8px;margin-right:7px;background:var(--blue)}.legend .challenger{background:var(--teal)}
.table-scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:.92rem}th,td{text-align:left;vertical-align:top;padding:12px;border-bottom:1px solid var(--line)}th{font-weight:600;background:#f3f6f9}caption{text-align:left;color:var(--muted);padding-bottom:12px}
.rate{min-width:170px}.track{height:7px;background:#e6edf3;margin-top:7px;overflow:hidden;border-radius:2px}.bar{height:100%;background:var(--blue)}.bar.challenger{background:var(--teal)}
.pass{color:var(--teal);font-weight:600}.fail{color:var(--amber);font-weight:600}.neutral{color:var(--muted)}.gates li{margin:8px 0}
.config{max-width:440px;white-space:pre-wrap;overflow-wrap:anywhere;font:13px/1.5 Consolas,monospace}.hash{overflow-wrap:anywhere;font:12px/1.5 Consolas,monospace}
details{margin:14px 0}summary{cursor:pointer;font-weight:600}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f3f6f9;padding:16px;font:13px/1.6 Consolas,monospace}
.raw{max-height:440px;overflow:auto;margin-top:18px}.raw th{position:sticky;top:0}.note{font-size:.9rem;color:var(--muted)}footer{font-size:.85rem;color:var(--muted);overflow-wrap:anywhere}
@media(max-width:640px){main{padding:24px 14px}.result{grid-template-columns:1fr;gap:18px}section,.result{padding:20px}th,td{padding:10px}.score{font-size:2rem}}
@media print{body{background:white}main{max-width:none;padding:0}nav{display:none}section,.result{break-inside:avoid;border-radius:0}details:not([open]){display:none}.raw{max-height:none;overflow:visible}}
"""


def _text(value: object) -> str:
    return escape(str(value), quote=True)


def _rate(value: object) -> float:
    result = float(value)  # type: ignore[arg-type]
    if not math.isfinite(result) or not 0 <= result <= 1:
        raise ValueError("Report rates must be finite and in [0, 1]")
    return result


def _score(series: Mapping) -> str:
    return f"{_text(series['wins'])}/{_text(series['matches'])} ({_rate(series['win_rate']):.1%})"


def _config(model: Mapping) -> str:
    return _text(
        json.dumps(
            model.get("spec", {}).get("config", {}), sort_keys=True, ensure_ascii=False
        )
    )


def _comparison_rows(baselines: Mapping, max_regression: float) -> str:
    rows = []
    for name, comparison in baselines.items():
        cells = []
        for role in ("champion", "challenger"):
            series = comparison[role]
            value = _rate(series["win_rate"])
            cells.append(
                f'<td class="rate">{_score(series)}<div class="track"><div class="bar {role}" style="width:{value * 100:.4f}%"></div></div></td>'
            )
        delta = float(comparison["delta"])
        if not math.isfinite(delta):
            raise ValueError("Report differences must be finite")
        status = "pass" if delta >= -max_regression - 1e-12 else "fail"
        rows.append(
            f'<tr><th scope="row">{_text(name)}</th>{"".join(cells)}<td class="{status}">{delta * 100:+.2f} pp</td></tr>'
        )
    return "".join(rows)


def _comparison_table(report: Mapping) -> str:
    rows = _comparison_rows(
        report["comparisons"]["baselines"], float(report["rules"]["max_regression"])
    )
    return f'<div class="table-scroll"><table><thead><tr><th>Opponent</th><th>Champion wins</th><th>Challenger wins</th><th>Challenger difference</th></tr></thead><tbody>{rows}</tbody></table></div>'


def render_report(
    data: Mapping,
    *,
    reasons: Sequence[str] | None = None,
    history: Sequence[Mapping] = (),
    models: Mapping[str, Mapping] | None = None,
    source_name: str = "experiment.json",
    source_sha: str = "",
    related_reports: Sequence[Mapping] = (),
) -> str:
    """Render escaped presentation only; selection policy stays in the pipeline."""
    models = models or {}
    head = data["comparisons"]["head_to_head"]
    rate = _rate(head["win_rate"])
    confirmed = data["stage"] == "confirmation"
    if confirmed and reasons is None:
        raise ValueError("Confirmation reports require evaluated selection gates")
    title = (
        ("Keep champion" if reasons else "Eligible for explicit promotion")
        if confirmed
        else "Development comparison"
    )
    rule = data["rules"]
    gate_items = "".join(f"<li>{_text(reason)}</li>" for reason in reasons or ())
    if confirmed and not reasons:
        gate_items = "<li>All configured gates passed. Promotion remains an explicit command.</li>"
    if not confirmed:
        gate_items = "<li>Development evidence only. Freeze a candidate and run separate confirmation before promotion.</li>"
    baseline_rows = _comparison_rows(
        data["comparisons"]["baselines"], float(rule["max_regression"])
    )
    raw_rows = []
    series_list = [("Challenger vs champion", head)]
    for name, comparison in data["comparisons"]["baselines"].items():
        for role in ("champion", "challenger"):
            series = comparison[role]
            series_list.append((f"{role.title()} vs {name}", series))
    for label, series in series_list:
        for row in series.get("records", ()):
            raw_rows.append(
                "<tr>"
                + "".join(
                    f"<td>{_text(value)}</td>"
                    for value in (
                        label,
                        row["pair"],
                        row["left_team"],
                        row["seed"],
                        row["winner"],
                        f"{row['wins_a']}–{row['wins_b']}",
                    )
                )
                + "</tr>"
            )
    attempt_rows, attempt_details = [], []
    for item in history:
        attempt = item["report"]
        attempt_head = attempt["comparisons"]["head_to_head"]
        screening = item.get("screening_reasons")
        screening_text = (
            "; ".join(screening)
            if screening
            else (
                "Observed rate thresholds passed"
                if screening is not None
                else "Screening unavailable"
            )
        )
        budget = f"{attempt['pairs']} seed pairs; first to {attempt['wins_to_match']} game win(s)"
        attempt_rows.append(
            f'<tr><th scope="row">{_text(attempt["attempt"])}</th><td>{_score(attempt_head)}<p class="note">{_text(budget)}</p></td><td class="config">{_config(item.get("model", {}))}</td><td>{_text(attempt.get("rationale", ""))}<p class="fail">Development screening: {_text(screening_text)}</p></td></tr>'
        )
        attempt_details.append(
            f"<details><summary>Attempt {_text(attempt['attempt'])}: static comparisons and screening</summary><p>{_text(budget)}. Elapsed seconds: {_text(attempt.get('elapsed_seconds', 'Unavailable'))}.</p>{_comparison_table(attempt)}</details>"
        )
    related_sections = []
    for extra in related_reports:
        older = extra["report"]
        failed = "; ".join(extra["reasons"]) or "Configured thresholds passed"
        related_sections.append(
            f'<section><h2>Related saved comparison</h2><p>{_text(older["stage"].title())}: {_score(older["comparisons"]["head_to_head"])} challenger wins. {_text(older["pairs"])} seed pairs; first to {_text(older["wins_to_match"])} game win(s).</p><p>{_text(failed)}</p>{_comparison_table(older)}<p class="note">Separate historical evidence, not pooled with the current comparison. Source JSON SHA-256: <span class="hash">{_text(extra["sha256"])}</span></p></section>'
        )
    identity_rows = []
    for role in ("champion", "challenger"):
        reference = data.get(role, {})
        model = models.get(role, {})
        identity_rows.append(
            f'<tr><th scope="row">{role.title()}</th><td class="config">{_config(model)}</td><td class="hash">{_text(reference.get("sha256", "Unavailable"))}</td></tr>'
        )
    metadata = {
        key: data.get(key)
        for key in (
            "stage",
            "attempt",
            "pairs",
            "wins_to_match",
            "evaluation_seed",
            "namespace",
            "elapsed_seconds",
            "rules",
        )
    }
    model_metadata = {
        role: {
            key: model.get(key)
            for key in (
                "adapter_version",
                "training_seed",
                "checkpoint",
                "files",
                "provenance",
            )
        }
        for role, model in models.items()
    }
    safe_metadata = _text(
        json.dumps(
            {"evaluation": metadata, "models": model_metadata},
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
        )
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light"><title>{_text(title)} · Mus training results</title><style>{_STYLE}</style></head>
<body><main><header><p class="subtle">Mus training results / {_text(data["stage"])} / attempt {_text(data["attempt"])}</p>
<h1>{_text(title)}</h1><p>A trained challenger compared with a frozen champion and the same static opponents.</p>
<nav aria-label="Report sections"><a href="#comparisons">Comparisons</a><a href="#attempts">Attempt history</a><a href="#evidence">Evidence</a></nav></header>
<div class="result"><div><h2>Challenger vs champion</h2><strong class="score">{rate:.1%}</strong><p>{_text(head["wins"])}/{_text(head["matches"])} complete matches won</p>
<p class="subtle">{_text(data["pairs"])} side-swapped seed pairs · first to {_text(data["wins_to_match"])} game win(s)</p></div>
<div><h2>Selection gates</h2><p>Head-to-head ≥ {_rate(rule["win_rate"]):.1%}; at least {_text(rule["min_pairs"])} confirmation pairs.</p>
<p>Maximum observed static regression: {_rate(rule["max_regression"]):.1%}.</p><ul class="gates">{gate_items}</ul></div></div>
<section id="comparisons"><h2>Performance against static opponents</h2><div class="legend"><span><i></i>Champion</span><span><i class="challenger"></i>Challenger</span></div>
<div class="table-scroll"><table><caption>Same opponent artifacts and paired seed schedule for both models. Bars share a 0–100% scale.</caption>
<thead><tr><th scope="col">Opponent</th><th scope="col">Champion wins</th><th scope="col">Challenger wins</th><th scope="col">Challenger difference</th></tr></thead><tbody>{baseline_rows}</tbody></table></div>
<p class="note">pp = percentage points. Differences below the allowed regression are marked in amber.</p></section>
<section id="attempts"><h2>What changed between attempts</h2><p>{_text(data.get("rationale", ""))}</p><div class="table-scroll"><table>
<thead><tr><th scope="col">Attempt</th><th scope="col">Head-to-head and budget</th><th scope="col">Training configuration</th><th scope="col">Rationale and development screening</th></tr></thead><tbody>{"".join(attempt_rows)}</tbody></table></div>
<p class="note">Development screening applies observed rate thresholds only. The minimum confirmation sample is checked separately on held-out evidence.</p>{"".join(attempt_details)}</section>{"".join(related_sections)}
<section id="evidence"><h2>Evidence and reproducibility</h2><p>Pair-level head-to-head standard error: {_text(head.get("pair_standard_error", "Unavailable"))}.</p>
<p class="note">Side swaps are dependent observations. Small samples and observed-rate gates do not establish statistical superiority. Training diagnostics remain in the native checkpoints.</p>
<div class="table-scroll"><table><thead><tr><th scope="col">Model</th><th scope="col">Training configuration</th><th scope="col">Artifact manifest SHA-256</th></tr></thead><tbody>{"".join(identity_rows)}</tbody></table></div>
<details><summary>Run metadata and native checkpoint identities</summary><pre>{safe_metadata}</pre></details>
<details><summary>Raw match results ({len(raw_rows)})</summary><div class="raw"><table><thead><tr><th>Comparison</th><th>Pair</th><th>Left team</th><th>Seed</th><th>Winner</th><th>A–B games</th></tr></thead><tbody>{"".join(raw_rows)}</tbody></table></div></details></section>
<footer>Offline report generated from {_text(source_name)}. JSON remains the authoritative evidence; HTML does not alter training or selection.<br>Source JSON SHA-256: <span class="hash">{_text(source_sha)}</span></footer>
</main></body></html>"""


def write_report(
    source: Path, output: Path | None = None, *, related: Sequence[Path] = ()
) -> Path:
    """Regenerate presentation without loading policies or changing JSON evidence."""
    # Local import avoids a pipeline/reporter import cycle; reuse its selector.
    from .pipeline import SelectionRule, selection_reasons

    data = read_json(source)
    models = {
        role: read_json(checked_ref(data[role]))
        for role in ("champion", "challenger")
        if role in data
    }
    current = (
        read_json(checked_ref(data["development"])) if data.get("development") else data
    )
    history, seen = [], set()
    while current:
        model = (
            read_json(checked_ref(current["challenger"]))
            if current.get("challenger")
            else {}
        )
        screening_rule = SelectionRule(**{**current["rules"], "min_pairs": 1})
        history.append(
            {
                "report": current,
                "model": model,
                "screening_reasons": selection_reasons(
                    current["comparisons"], screening_rule
                ),
            }
        )
        parent = current.get("parent")
        if not parent:
            break
        if parent["sha256"] in seen:
            raise ValueError("Cyclic report history")
        seen.add(parent["sha256"])
        current = read_json(checked_ref(parent))
    reasons = (
        selection_reasons(data["comparisons"], SelectionRule(**data["rules"]))
        if data["stage"] == "confirmation"
        else None
    )
    html = render_report(
        data,
        reasons=reasons,
        history=list(reversed(history)),
        models=models,
        source_name=Path(source).name,
        source_sha=digest(source),
        related_reports=[
            {
                "report": read_json(path),
                "sha256": digest(path),
                "reasons": selection_reasons(
                    read_json(path)["comparisons"],
                    SelectionRule(**read_json(path)["rules"]),
                ),
            }
            for path in related
        ],
    )
    output = Path(output) if output is not None else Path(source).with_suffix(".html")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as target:
        target.write(html)
    return output
