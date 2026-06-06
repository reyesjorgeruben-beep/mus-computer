"""
export_tables.py — Export probability_tables.pkl to CSV and HTML.

Usage:
    python export_tables.py
    python export_tables.py --input my_tables.pkl --out-dir exports/

Outputs:
    tables_summary.csv   — one row per hand, all key statistics flat
    tables_discard.csv   — one row per (hand, kept) discard option
    tables_report.html   — sortable, colour-coded browser report
"""
import argparse
import csv
import json
import pickle
import sys
from pathlib import Path

from build_tables import TABLE_PATH
from constants import cards_space
from build_tables import all_canonical_hands

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def hand_str(hand: tuple) -> str:
    return "".join(c.value for c in hand)


def hand_juego_sum(hand: tuple) -> int:
    return sum(c.juego_value for c in hand)


def hand_has_pares(hand: tuple) -> bool:
    from collections import Counter
    return max(Counter(hand).values()) >= 2


def hand_has_juego(hand: tuple) -> bool:
    return hand_juego_sum(hand) >= 31


def discard_pattern(full_hand: tuple, kept: tuple) -> str:
    """Return e.g. 'K - - -' showing which positions of full_hand are kept."""
    remaining = list(kept)
    parts = []
    for card in full_hand:
        if card in remaining:
            parts.append(card.value)
            remaining.remove(card)
        else:
            parts.append("-")
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Build flat rows
# ---------------------------------------------------------------------------

EP_PHASES    = ["Grande", "Chica", "Pares", "Juego", "Punto"]
WIN1V1_PHASES = ["Grande", "Chica", "Pares", "Juego"]

def build_summary_rows(tables: dict, multiplicities: dict) -> list[dict]:
    rows = []
    for hand, entry in tables.items():
        if not isinstance(hand, tuple):
            continue  # skip "_avg_opp_phase_improvements" sentinel key

        row = {
            "hand":         hand_str(hand),
            "multiplicity": multiplicities.get(hand, ""),
            "has_pares":    int(hand_has_pares(hand)),
            "has_juego":    int(hand_has_juego(hand)),
            "juego_sum":    hand_juego_sum(hand),
        }

        # 1v1 win probabilities
        for phase in WIN1V1_PHASES:
            d = entry.get(phase, {})
            row[f"{phase.lower()}_p_win"]  = round(d.get("p_win",  0.0), 6)
            row[f"{phase.lower()}_p_tie"]  = round(d.get("p_tie",  0.0), 6)
            row[f"{phase.lower()}_p_loss"] = round(d.get("p_loss", 0.0), 6)

        # 4-player mano expected points
        ep = entry.get("ep_mano", {})
        for phase in EP_PHASES:
            pd = ep.get(phase, {})
            row[f"ep_{phase.lower()}_prob_A_wins"]   = round(pd.get("prob_A_wins",   0.0), 6)
            row[f"ep_{phase.lower()}_exp_A_pts"]     = round(pd.get("expected_A_points", 0.0), 6)
            row[f"ep_{phase.lower()}_exp_B_pts"]     = round(pd.get("expected_B_points", 0.0), 6)
            row[f"ep_{phase.lower()}_net_A"]         = round(pd.get("expected_net_A", 0.0), 6)
            row[f"ep_{phase.lower()}_total_pts"]     = round(pd.get("expected_total_winner_points", 0.0), 6)
            if phase in ("Pares", "Juego"):
                row[f"ep_{phase.lower()}_both_A"] = round(pd.get("prob_both_given_A_wins", 0.0), 6)
                row[f"ep_{phase.lower()}_both_B"] = round(pd.get("prob_both_given_B_wins", 0.0), 6)
        row["total_net_A"] = round(
            sum(ep.get(ph, {}).get("expected_net_A", 0.0) for ph in EP_PHASES), 6
        )

        # Best discard improvement per phase (old p_win metric)
        opts = entry.get("discard_options", {})
        if opts:
            kept_all_key = hand
            for phase in WIN1V1_PHASES:
                current = opts.get(kept_all_key, {}).get(phase, 0.0)
                best    = max((v.get(phase, 0.0) for v in opts.values()), default=current)
                row[f"discard_gain_{phase.lower()}"] = round(best - current, 6)

        # Best discard gain in total net_A terms (from best_discards table)
        nd = entry.get("no_discard_stats", {})
        row["discard_net_gain"] = round(nd.get("delta_total_net_vs_best", 0.0), 6)
        row["nd_rank"]          = nd.get("rank", "")
        imp = nd.get("improvement_by_phase", {})
        for ph in WIN1V1_PHASES:
            row[f"nd_imp_{ph.lower()}"] = round(imp.get(ph, 0.0), 6)

        rows.append(row)

    rows.sort(key=lambda r: r["hand"])
    return rows


def build_discard_rows(tables: dict) -> list[dict]:
    rows = []
    for hand, entry in tables.items():
        if not isinstance(hand, tuple):
            continue
        opts = entry.get("discard_options", {})
        for kept, phase_wins in opts.items():
            discarded = sorted(
                set(hand) - set(kept),
                key=lambda c: c.value
            )
            row = {
                "hand":      hand_str(hand),
                "kept":      hand_str(kept) if kept else "(none)",
                "discarded": hand_str(tuple(discarded)) if discarded else "(none)",
                "n_discarded": len(hand) - len(kept),
            }
            for phase in WIN1V1_PHASES:
                row[f"exp_p_win_{phase.lower()}"] = round(phase_wins.get(phase, 0.0), 6)
            rows.append(row)
    rows.sort(key=lambda r: (r["hand"], r["n_discarded"], r["kept"]))
    return rows


_BEST_PHASES = ["Grande", "Chica", "Pares", "Juego"]

def build_discard_insight_rows(tables: dict) -> list[dict]:
    """One row per hand summarising best_discards + no_discard_stats."""
    rows = []
    for hand, entry in tables.items():
        if not isinstance(hand, tuple):
            continue
        bd = entry.get("best_discards")
        nd = entry.get("no_discard_stats")
        if not bd and not nd:
            continue

        row = {
            "hand":     hand_str(hand),
            "has_pares": int(hand_has_pares(hand)),
            "has_juego": int(hand_has_juego(hand)),
        }

        # No-discard baseline
        if nd:
            row["nd_rank"]       = nd.get("rank", "")
            row["nd_delta_net"]  = round(nd.get("delta_total_net_vs_best", 0.0), 6)
            row["nd_act_vs_max"] = round(nd.get("action_vs_max", 0.0), 6)
            row["nd_act_vs_min"] = round(nd.get("action_vs_min", 0.0), 6)
            imp = nd.get("improvement_by_phase", {})
            for ph in _BEST_PHASES:
                row[f"nd_imp_{ph.lower()}"] = round(imp.get(ph, 0.0), 6)
        else:
            row["nd_rank"] = row["nd_delta_net"] = ""
            row["nd_act_vs_max"] = row["nd_act_vs_min"] = ""
            for ph in _BEST_PHASES:
                row[f"nd_imp_{ph.lower()}"] = ""

        # Best-by-phase kept hands + top-3 overall
        if bd:
            bbp = bd.get("best_by_phase", {})
            for ph in _BEST_PHASES:
                entry_ph = bbp.get(ph, {})
                kept     = entry_ph.get("kept")
                row[f"best_{ph.lower()}_kept"]    = hand_str(kept) if kept else ""
                row[f"best_{ph.lower()}_pattern"] = discard_pattern(hand, kept) if kept else ""
                row[f"best_{ph.lower()}_net"]     = round(entry_ph.get("net_A", 0.0), 6)

            all_opts = bd.get("all_options_net", [])
            for i in range(3):
                if i < len(all_opts):
                    kept_t = all_opts[i]["kept"]
                    row[f"top{i+1}_kept"]    = hand_str(kept_t) if kept_t else "(none)"
                    row[f"top{i+1}_pattern"] = discard_pattern(hand, kept_t) if kept_t else "- - - -"
                    row[f"top{i+1}_net"]     = round(all_opts[i]["total_net_A"], 6)
                else:
                    row[f"top{i+1}_kept"] = row[f"top{i+1}_pattern"] = row[f"top{i+1}_net"] = ""

            max_a = bd.get("max_action_kept", {})
            min_a = bd.get("min_action_kept", {})
            row["max_action_kept"]    = hand_str(max_a["kept"]) if max_a.get("kept") else ""
            row["max_action_pattern"] = discard_pattern(hand, max_a["kept"]) if max_a.get("kept") else ""
            row["max_action_value"]   = round(max_a.get("total_action", 0.0), 6)
            row["min_action_kept"]    = hand_str(min_a["kept"]) if min_a.get("kept") else ""
            row["min_action_pattern"] = discard_pattern(hand, min_a["kept"]) if min_a.get("kept") else ""
            row["min_action_value"]   = round(min_a.get("total_action", 0.0), 6)
        else:
            for ph in _BEST_PHASES:
                row[f"best_{ph.lower()}_kept"] = row[f"best_{ph.lower()}_pattern"] = row[f"best_{ph.lower()}_net"] = ""
            for i in range(3):
                row[f"top{i+1}_kept"] = row[f"top{i+1}_pattern"] = row[f"top{i+1}_net"] = ""
            row["max_action_kept"] = row["max_action_pattern"] = row["max_action_value"] = ""
            row["min_action_kept"] = row["min_action_pattern"] = row["min_action_value"] = ""

        rows.append(row)

    rows.sort(key=lambda r: r["hand"])
    return rows


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------

def write_csv(rows: list[dict], path: Path) -> None:
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"  Written: {path}  ({len(rows)} rows)")


# ---------------------------------------------------------------------------
# HTML export
# ---------------------------------------------------------------------------

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>Mus Probability Tables</title>
<style>
  body {{ font-family: system-ui, sans-serif; font-size: 13px; margin: 16px; background: #f8f9fa; }}
  h1   {{ font-size: 1.4em; margin-bottom: 4px; }}
  .meta {{ color: #666; margin-bottom: 16px; font-size: 12px; }}
  .section {{ margin-bottom: 32px; }}
  .stat-grid {{ display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 20px; }}
  .stat-card {{ background: white; border: 1px solid #ddd; border-radius: 6px;
                padding: 10px 16px; min-width: 140px; }}
  .stat-card .label {{ font-size: 11px; color: #888; }}
  .stat-card .value {{ font-size: 1.4em; font-weight: 600; color: #333; }}
  table  {{ border-collapse: collapse; width: 100%; background: white; border-radius: 6px;
            overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,.1); }}
  thead  {{ background: #2c3e50; color: white; position: sticky; top: 0; }}
  th     {{ padding: 8px 10px; cursor: pointer; white-space: nowrap; user-select: none; text-align: center; }}
  th:hover {{ background: #3d5166; }}
  th.sorted-asc::after  {{ content: " ▲"; font-size: 10px; }}
  th.sorted-desc::after {{ content: " ▼"; font-size: 10px; }}
  td     {{ padding: 6px 10px; border-bottom: 1px solid #eee; white-space: nowrap; text-align: center; }}
  tr:hover td {{ background: #f0f4f8; }}
  .hand  {{ font-family: monospace; font-weight: 600; font-size: 14px; }}
  .controls {{ margin-bottom: 10px; display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }}
  input[type=text] {{ padding: 6px 10px; border: 1px solid #ccc; border-radius: 4px; width: 200px; }}
  select {{ padding: 6px 8px; border: 1px solid #ccc; border-radius: 4px; }}
  label  {{ font-size: 12px; color: #555; }}
  .badge {{ display: inline-block; padding: 2px 6px; border-radius: 3px; font-size: 11px; }}
  .badge-yes {{ background: #d4edda; color: #155724; }}
  .badge-no  {{ background: #f8d7da; color: #721c24; }}
  .tabs {{ display: flex; gap: 0; margin-bottom: 20px; border-bottom: 2px solid #2c3e50; }}
  .tab  {{ padding: 8px 24px; cursor: pointer; background: #e9ecef; border: 1px solid #ccc;
           border-bottom: none; font-size: 13px; font-weight: 500; color: #555;
           border-radius: 6px 6px 0 0; margin-right: 4px; }}
  .tab.active {{ background: #2c3e50; color: white; border-color: #2c3e50; }}
  .tab:hover:not(.active) {{ background: #d0d5db; }}
  .page {{ display: none; }}
  .page.active {{ display: block; }}
</style>
</head>
<body>
<h1>Mus Probability Tables</h1>
<div class="meta">Generated from probability_tables.pkl &mdash; {n_hands} canonical hands &mdash; {timestamp}</div>

<div class="tabs">
  <div class="tab active" onclick="switchPage('hands')">Hand Statistics</div>
  <div class="tab"        onclick="switchPage('discards')">Discard Insights</div>
</div>

<div id="page-hands" class="page active">
<div class="section">
<h2>Aggregate statistics</h2>
<div class="stat-grid" id="agg-stats"></div>
</div>

<div class="section">
<h2>Per-hand statistics</h2>
<div class="controls">
  <input type="text" id="search" placeholder="Filter hand (e.g. RRCS)…" oninput="filterTable()"/>
  <label>Pares:
    <select id="f-pares" onchange="filterTable()">
      <option value="">all</option><option value="1">yes</option><option value="0">no</option>
    </select>
  </label>
  <label>Juego:
    <select id="f-juego" onchange="filterTable()">
      <option value="">all</option><option value="1">yes</option><option value="0">no</option>
    </select>
  </label>
  <label>Phase:
    <select id="f-phase" onchange="buildTable()">
      <option value="grande">Grande</option>
      <option value="chica">Chica</option>
      <option value="pares">Pares</option>
      <option value="juego">Juego</option>
      <option value="punto">Punto (ep only)</option>
      <option value="all">All (combined net)</option>
    </select>
  </label>
  <span id="row-count" style="color:#888;font-size:12px"></span>
</div>
<div id="table-container"></div>
</div>
</div><!-- end page-hands -->

<div id="page-discards" class="page">
<script>
const DATA = {data_json};

const AGG = {agg_json};

// Aggregate stats panel
(function() {{
  const el = document.getElementById('agg-stats');
  const items = [
    ['Hands with Pares', DATA.filter(r=>r.has_pares==1).length + ' / ' + DATA.length],
    ['Hands with Juego', DATA.filter(r=>r.has_juego==1).length + ' / ' + DATA.length],
    ['Avg opp Grande improve', (AGG.Grande*100).toFixed(2)+'%'],
    ['Avg opp Chica improve',  (AGG.Chica*100).toFixed(2)+'%'],
    ['Avg opp Pares improve',  (AGG.Pares*100).toFixed(2)+'%'],
    ['Avg opp Juego improve',  (AGG.Juego*100).toFixed(2)+'%'],
  ];
  items.forEach(([label, value]) => {{
    el.innerHTML += `<div class="stat-card"><div class="label">${{label}}</div><div class="value">${{value}}</div></div>`;
  }});
}})();

// Table building
let sortCol = null, sortDir = 1;
let filtered = [...DATA];

function phaseKey() {{ return document.getElementById('f-phase').value; }}

function cols() {{
  const p = phaseKey();
  const base = [
    {{key:'hand',        label:'Hand',   fmt: v=>`<span class="hand">${{v}}</span>`}},
    {{key:'multiplicity',label:'Ways',   fmt:null}},
    {{key:'has_pares',   label:'Pares?', fmt: v=>v?'<span class="badge badge-yes">yes</span>':'<span class="badge badge-no">no</span>'}},
    {{key:'has_juego',   label:'Juego?', fmt: v=>v?'<span class="badge badge-yes">yes</span>':'<span class="badge badge-no">no</span>'}},
    {{key:'juego_sum',   label:'Sum',    fmt:null}},
  ];
  if (p === 'all') {{
    const phases = ['grande','chica','pares','juego','punto'];
    return [
      ...base,
      {{key:'total_net_A',      label:'Total Net A',    fmt: dec3}},
      {{key:'discard_net_gain', label:'Discard gain (net)', fmt: dec3}},
      {{key:'nd_rank',          label:'No-disc rank',      fmt: null}},
      ...phases.map(ph => ({{key:`ep_${{ph}}_net_A`, label:`Net ${{ph[0].toUpperCase()+ph.slice(1)}}`, fmt: dec3}})),
      ...phases.map(ph => ({{key:`ep_${{ph}}_prob_A_wins`, label:`A wins ${{ph[0].toUpperCase()+ph.slice(1)}}`, fmt: pct}})),
    ];
  }}
  const one = [
    {{key:`${{p}}_p_win`, label:'1v1 p_win', fmt: pct}},
    {{key:`${{p}}_p_tie`, label:'1v1 p_tie', fmt: pct}},
  ];
  const ep = [
    {{key:`ep_${{p}}_prob_A_wins`, label:'4p A wins',   fmt: pct}},
    {{key:`ep_${{p}}_net_A`,       label:'Net A (exp)', fmt: dec3}},
    {{key:`ep_${{p}}_exp_A_pts`,   label:'Exp A pts',   fmt: dec3}},
    {{key:`ep_${{p}}_exp_B_pts`,   label:'Exp B pts',   fmt: dec3}},
    {{key:`ep_${{p}}_total_pts`,   label:'Total pts',   fmt: dec3}},
  ];
  const bonus = (p==='pares'||p==='juego') ? [
    {{key:`ep_${{p}}_both_A`, label:'Both (A wins)', fmt: pct}},
    {{key:`ep_${{p}}_both_B`, label:'Both (B wins)', fmt: pct}},
  ] : [];
  const dis = (p!=='punto') ? [
    {{key:`nd_imp_${{p}}`, label:'Discard gain (net)', fmt: dec3}},
  ] : [];
  return [...base, ...one, ...ep, ...bonus, ...dis];
}}

function pct(v)  {{ if(v===''||v===undefined) return '—'; return (v*100).toFixed(1)+'%'; }}
function dec3(v) {{ if(v===''||v===undefined) return '—'; return (+v).toFixed(3); }}

function bg(key, v) {{
  if (v === '' || v === undefined) return '';
  const n = +v;
  if (key.endsWith('_p_win') || key.endsWith('prob_A_wins')) {{
    if (n > 0.5) {{
      const t = Math.min(1, (n - 0.5) / 0.5);
      return `background:rgba(40,${{Math.round(140*t+100)}},40,${{(t*0.45+0.08).toFixed(2)}})`;
    }}
    return '';
  }}
  if (key.endsWith('_net_A') || key === 'total_net_A') {{
    if (n > 0) {{
      const t = Math.min(1, n / 0.5);
      return `background:rgba(40,${{Math.round(140*t+100)}},40,${{(t*0.45+0.08).toFixed(2)}})`;
    }}
  }}
  return '';
}}

function buildTable() {{
  filterTable(true);
}}

function filterTable(rebuild) {{
  const q  = document.getElementById('search').value.toUpperCase();
  const fp = document.getElementById('f-pares').value;
  const fj = document.getElementById('f-juego').value;
  filtered = DATA.filter(r => {{
    if (q  && !r.hand.includes(q)) return false;
    if (fp && String(r.has_pares) !== fp) return false;
    if (fj && String(r.has_juego) !== fj) return false;
    return true;
  }});
  renderTable();
}}

function renderTable() {{
  const c = cols();
  const container = document.getElementById('table-container');
  let html = '<table><thead><tr>';
  html += `<th style="cursor:default;color:#aaa"># / ${{filtered.length}}</th>`;
  c.forEach((col, i) => {{
    const cls = sortCol===i ? (sortDir>0?'sorted-asc':'sorted-desc') : '';
    html += `<th class="${{cls}}" onclick="sortBy(${{i}})">${{col.label}}</th>`;
  }});
  html += '</tr></thead><tbody>';
  filtered.forEach((row, idx) => {{
    html += `<tr>`;
    html += `<td style="color:#aaa;font-size:11px">${{idx+1}}</td>`;
    c.forEach(col => {{
      const v = row[col.key];
      const style = bg(col.key, v);
      const display = col.fmt ? col.fmt(v) : (v === undefined ? '—' : v);
      html += `<td style="${{style}}">${{display}}</td>`;
    }});
    html += '</tr>';
  }});
  html += '</tbody></table>';
  container.innerHTML = html;
  document.getElementById('row-count').textContent = `${{filtered.length}} rows`;
}}

function sortBy(i) {{
  if (sortCol === i) sortDir *= -1; else {{ sortCol = i; sortDir = 1; }}
  const key = cols()[i].key;
  filtered.sort((a, b) => {{
    const va = a[key] ?? '', vb = b[key] ?? '';
    if (typeof va === 'number' && typeof vb === 'number') return (va - vb) * sortDir;
    return String(va).localeCompare(String(vb)) * sortDir;
  }});
  renderTable();
}}

buildTable();

// ---- Discard insights table ----
const DATA2 = {discard_json};

let dFiltered = [...DATA2], dSortCol = null, dSortDir = 1;

function mono(v) {{ return v ? `<span class="hand">${{v}}</span>` : '—'; }}

function dCols() {{
  const v  = document.getElementById('d-view').value;
  const badge = val => val ? '<span class="badge badge-yes">yes</span>' : '<span class="badge badge-no">no</span>';
  const base = [
    {{key:'hand',      label:'Hand',   fmt: v => `<span class="hand">${{v}}</span>`}},
    {{key:'has_pares', label:'Pares?', fmt: badge}},
    {{key:'has_juego', label:'Juego?', fmt: badge}},
  ];
  if (v === 'improve') {{
    return [...base,
      {{key:'nd_rank',       label:'No-disc rank',    fmt: null}},
      {{key:'nd_delta_net',  label:'Gain vs best',    fmt: dec3}},
      {{key:'nd_imp_grande', label:'Imp Grande',      fmt: dec3}},
      {{key:'nd_imp_chica',  label:'Imp Chica',       fmt: dec3}},
      {{key:'nd_imp_pares',  label:'Imp Pares',       fmt: dec3}},
      {{key:'nd_imp_juego',  label:'Imp Juego+Punto', fmt: dec3}},
      {{key:'nd_act_vs_max', label:'Max-act gain',     fmt: dec3}},
      {{key:'nd_act_vs_min', label:'Min-act gain',     fmt: dec3}},
    ];
  }}
  if (v === 'best') {{
    return [...base,
      {{key:'top1_pattern', label:'#1 kept',    fmt: mono}},
      {{key:'top1_net',     label:'#1 net',     fmt: dec3}},
      {{key:'top2_pattern', label:'#2 kept',    fmt: mono}},
      {{key:'top2_net',     label:'#2 net',     fmt: dec3}},
      {{key:'top3_pattern', label:'#3 kept',    fmt: mono}},
      {{key:'top3_net',     label:'#3 net',     fmt: dec3}},
      {{key:'best_grande_pattern', label:'Grande kept',    fmt: mono}},
      {{key:'nd_imp_grande',       label:'Grande gain',    fmt: dec3}},
      {{key:'best_chica_pattern',  label:'Chica kept',     fmt: mono}},
      {{key:'nd_imp_chica',        label:'Chica gain',     fmt: dec3}},
      {{key:'best_pares_pattern',  label:'Pares kept',     fmt: mono}},
      {{key:'nd_imp_pares',        label:'Pares gain',     fmt: dec3}},
      {{key:'best_juego_pattern',  label:'Juego+P kept',   fmt: mono}},
      {{key:'nd_imp_juego',        label:'Juego+P gain',   fmt: dec3}},
    ];
  }}
  return [...base,
    {{key:'max_action_pattern', label:'Max action kept',  fmt: mono}},
    {{key:'max_action_value',   label:'Max action (tot)', fmt: dec3}},
    {{key:'nd_act_vs_max',      label:'Max-act gain',     fmt: dec3}},
    {{key:'min_action_pattern', label:'Min action kept',  fmt: mono}},
    {{key:'min_action_value',   label:'Min action (tot)', fmt: dec3}},
    {{key:'nd_act_vs_min',      label:'Min-act gain',     fmt: dec3}},
  ];
}}

function dBg(key, v) {{
  if (v === '' || v === undefined || v === null) return '';
  const n = +v;
  if (key.startsWith('nd_imp_') || key === 'nd_delta_net') {{
    if (n > 0) {{
      const t = Math.min(1, n / 0.3);
      return `background:rgba(40,${{Math.round(140*t+100)}},40,${{(t*0.45+0.08).toFixed(2)}})`;
    }}
  }}
  if (key === 'nd_act_vs_max') {{
    if (n > 0) {{
      const t = Math.min(1, n / 0.3);
      return `background:rgba(40,${{Math.round(140*t+100)}},40,${{(t*0.45+0.08).toFixed(2)}})`;
    }}
  }}
  return '';
}}

function renderDiscard() {{
  const c = dCols();
  let html = '<table><thead><tr>';
  html += `<th style="cursor:default;color:#aaa"># / ${{dFiltered.length}}</th>`;
  c.forEach((col, i) => {{
    const cls = dSortCol===i ? (dSortDir>0?'sorted-asc':'sorted-desc') : '';
    html += `<th class="${{cls}}" onclick="dSortBy(${{i}})">${{col.label}}</th>`;
  }});
  html += '</tr></thead><tbody>';
  dFiltered.forEach((row, idx) => {{
    html += '<tr>';
    html += `<td style="color:#aaa;font-size:11px">${{idx+1}}</td>`;
    c.forEach(col => {{
      const v = row[col.key];
      const style = dBg(col.key, v);
      const display = col.fmt ? col.fmt(v) : (v === undefined || v === '' ? '—' : v);
      html += `<td style="${{style}}">${{display}}</td>`;
    }});
    html += '</tr>';
  }});
  html += '</tbody></table>';
  document.getElementById('discard-table-container').innerHTML = html;
  document.getElementById('d-row-count').textContent = dFiltered.length + ' rows';
}}

function dFilterTable() {{
  const q  = document.getElementById('d-search').value.toUpperCase();
  const fp = document.getElementById('d-pares').value;
  const fj = document.getElementById('d-juego').value;
  dFiltered = DATA2.filter(r => {{
    if (q  && !r.hand.includes(q)) return false;
    if (fp && String(r.has_pares) !== fp) return false;
    if (fj && String(r.has_juego) !== fj) return false;
    return true;
  }});
  renderDiscard();
}}

function buildDiscard() {{ dFilterTable(); }}

function dSortBy(i) {{
  if (dSortCol === i) dSortDir *= -1; else {{ dSortCol = i; dSortDir = 1; }}
  const key = dCols()[i].key;
  dFiltered.sort((a, b) => {{
    const va = a[key] ?? '', vb = b[key] ?? '';
    if (typeof va === 'number' && typeof vb === 'number') return (va - vb) * dSortDir;
    return String(va).localeCompare(String(vb)) * dSortDir;
  }});
  renderDiscard();
}}

</script>

<div class="section">
<h2>Discard insights</h2>
<div class="controls">
  <input type="text" id="d-search" placeholder="Filter hand…" oninput="dFilterTable()"/>
  <label>Pares:
    <select id="d-pares" onchange="dFilterTable()">
      <option value="">all</option><option value="1">yes</option><option value="0">no</option>
    </select>
  </label>
  <label>Juego:
    <select id="d-juego" onchange="dFilterTable()">
      <option value="">all</option><option value="1">yes</option><option value="0">no</option>
    </select>
  </label>
  <label>View:
    <select id="d-view" onchange="buildDiscard()">
      <option value="improve">Improvements</option>
      <option value="best">Best kept options</option>
      <option value="action">Action extremes</option>
    </select>
  </label>
  <span id="d-row-count" style="color:#888;font-size:12px"></span>
</div>
<div id="discard-table-container"></div>
</div>
</div><!-- end page-discards -->

<script>
function switchPage(name) {{
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.getElementById('page-' + name).classList.add('active');
  document.querySelectorAll('.tab').forEach(t => {{
    if (t.textContent.toLowerCase().includes(name === 'hands' ? 'hand' : 'discard'))
      t.classList.add('active');
  }});
}}
buildDiscard();
</script>
</body>
</html>
"""


def write_html(
    summary_rows: list[dict],
    agg_improvements: dict,
    discard_insight_rows: list[dict],
    path: Path,
    n_hands: int,
) -> None:
    import datetime

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    html = _HTML_TEMPLATE.format(
        n_hands=n_hands,
        timestamp=timestamp,
        data_json=json.dumps(summary_rows, ensure_ascii=False),
        agg_json=json.dumps(agg_improvements, ensure_ascii=False),
        discard_json=json.dumps(discard_insight_rows, ensure_ascii=False),
    )
    path.write_text(html, encoding="utf-8")
    print(f"  Written: {path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Export probability tables to CSV and HTML")
    parser.add_argument("--input",   type=Path, default=TABLE_PATH)
    parser.add_argument("--out-dir", type=Path, default=Path(__file__).parent)
    args = parser.parse_args()

    if not args.input.exists():
        print(f"ERROR: {args.input} not found. Run build_tables.py first.", file=sys.stderr)
        sys.exit(1)

    print(f"Loading {args.input}...")
    with open(args.input, "rb") as f:
        tables = pickle.load(f)

    multiplicities = all_canonical_hands(cards_space)
    n_hands = sum(1 for k in tables if isinstance(k, tuple))
    agg = tables.get("_avg_opp_phase_improvements", {})

    print("Building rows...")
    summary_rows        = build_summary_rows(tables, multiplicities)
    discard_rows        = build_discard_rows(tables)
    discard_insight_rows = build_discard_insight_rows(tables)

    args.out_dir.mkdir(parents=True, exist_ok=True)

    print("Writing CSV files...")
    write_csv(summary_rows,        args.out_dir / "tables_summary.csv")
    write_csv(discard_rows,        args.out_dir / "tables_discard.csv")
    write_csv(discard_insight_rows, args.out_dir / "tables_discard_insights.csv")

    print("Writing HTML report...")
    write_html(summary_rows, agg, discard_insight_rows,
               args.out_dir / "tables_report.html", n_hands)

    print("Done.")


if __name__ == "__main__":
    main()
