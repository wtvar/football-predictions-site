#!/usr/bin/env python3
"""Refresh comparison-only external source panels for the football prediction site.

Currently supports OddAlerts FPL ticker -> PL comparison page.
External source probabilities are comparison-only. Do not feed these values into
no-market training/features/selectors/calibration.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import html
import json
import math
import re
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd

SITE = Path(__file__).resolve().parents[1]
MODEL = Path('/root/football-multi-source-data')
PL_DIR = SITE / 'projects' / 'pl-model'
RAW_DIR = Path('/root/football-data-cache/oddalerts/fpl-fixture-ticker')
ENDPOINT = 'https://www.oddalerts.com/fpl/api/ticker'
UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1'

ALIASES = {
    'spurs': 'tottenham', 'tottenham hotspur': 'tottenham', 'tottenham': 'tottenham',
    'nottm forest': 'nottingham forest', 'nottingham forest': 'nottingham forest',
    'man city': 'manchester city', 'manchester city': 'manchester city',
    'man utd': 'manchester united', 'man united': 'manchester united', 'manchester united': 'manchester united',
    'coventry city': 'coventry', 'coventry': 'coventry', 'hull city': 'hull', 'hull': 'hull',
    'ipswich town': 'ipswich', 'ipswich': 'ipswich', 'leeds united': 'leeds', 'leeds': 'leeds',
    'wolverhampton wanderers': 'wolves', 'wolverhampton': 'wolves', 'wolves': 'wolves',
    'brighton and hove albion': 'brighton', 'brighton': 'brighton', 'afc bournemouth': 'bournemouth',
    'bournemouth': 'bournemouth', 'newcastle united': 'newcastle', 'newcastle': 'newcastle',
    'west ham united': 'west ham', 'west ham': 'west ham', 'fulham': 'fulham', 'sunderland': 'sunderland',
    'brentford': 'brentford', 'arsenal': 'arsenal', 'aston villa': 'aston villa', 'chelsea': 'chelsea',
    'crystal palace': 'crystal palace', 'everton': 'everton', 'liverpool': 'liverpool',
}


def norm(value: object) -> str:
    s = str(value).lower().strip().replace('&', 'and')
    s = re.sub(r'[^a-z0-9 ]+', '', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return ALIASES.get(s, s)


def fetch_oddalerts(horizon: int = 6) -> tuple[dict, Path]:
    url = ENDPOINT + '?' + urlencode({'horizon': horizon})
    req = Request(url, headers={
        'User-Agent': UA,
        'Accept': 'application/json',
        'Referer': 'https://www.oddalerts.com/fpl/fixture-ticker',
        'X-Requested-With': 'XMLHttpRequest',
    })
    with urlopen(req, timeout=30) as response:
        body = response.read()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    retrieved_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    sha = hashlib.sha256(body).hexdigest()
    raw_path = RAW_DIR / f'{retrieved_at.replace(":", "").replace("-", "")}_{sha[:16]}.json'
    raw_path.write_bytes(body)
    return json.loads(body.decode('utf-8')), raw_path


def fair_odds(prob: float | None) -> float | None:
    if prob is None or pd.isna(prob) or prob <= 0:
        return None
    return round(1.0 / float(prob), 2)


def load_model_predictions() -> dict[tuple[str, str, str], dict]:
    pred_path = MODEL / 'data/processed/upcoming_predictions.csv'
    preds = pd.read_csv(pred_path)
    pl = preds[(preds['league'].astype(str).str.lower().eq('premier_league')) | (preds['competition_name'].astype(str).eq('Premier League'))].copy()
    by_key: dict[tuple[str, str, str], dict] = {}
    for _, r in pl.iterrows():
        ko = pd.to_datetime(r['kickoff_utc'], utc=True, errors='coerce')
        date_key = ko.date().isoformat() if pd.notna(ko) else ''
        home_norm, away_norm = norm(r['home_team']), norm(r['away_team'])
        by_key[tuple(sorted([home_norm, away_norm])) + (date_key,)] = {
            'home_team': r['home_team'], 'away_team': r['away_team'],
            'model_home_win_prob': float(r['model_home_win_prob']),
            'model_draw_prob': float(r['model_draw_prob']),
            'model_away_win_prob': float(r['model_away_win_prob']),
            'model_home_decimal_odds': float(r.get('model_home_decimal_odds', 1 / float(r['model_home_win_prob']))),
            'model_draw_decimal_odds': float(r.get('model_draw_decimal_odds', 1 / float(r['model_draw_prob']))),
            'model_away_decimal_odds': float(r.get('model_away_decimal_odds', 1 / float(r['model_away_win_prob']))),
            'model_expected_home_goals': float(r['model_expected_home_goals']),
            'model_expected_away_goals': float(r['model_expected_away_goals']),
            'model_feature_set': r.get('model_feature_set'),
        }
    return by_key


def collapse_oddalerts(data: dict) -> list[dict]:
    events = {event.get('id'): event for event in data.get('events', [])}
    fixtures: dict[tuple[str, str, str], dict] = {}
    for team in data.get('teams', []):
        for event_key, event_fixtures in (team.get('fixtures') or {}).items():
            for fx in event_fixtures or []:
                ko = pd.to_datetime(fx.get('kickoff'), utc=True, errors='coerce')
                date_key = ko.date().isoformat() if pd.notna(ko) else ''
                team_norm, opp_norm = norm(team.get('name')), norm(fx.get('opponent_name'))
                key = tuple(sorted([team_norm, opp_norm])) + (date_key,)
                event = events.get(fx.get('event')) or events.get(int(event_key)) or {}
                out = fixtures.setdefault(key, {'kickoff_utc': ko.isoformat() if pd.notna(ko) else None, 'gameweek': event.get('short') or event.get('name'), 'event': fx.get('event'), 'oddalerts_source': fx.get('source')})
                side = 'home' if bool(fx.get('is_home')) else 'away'
                other = 'away' if side == 'home' else 'home'
                out[f'{side}_team'] = team.get('name')
                out[f'{other}_team'] = fx.get('opponent_name')
                out[f'oddalerts_{side}_win_prob'] = float(fx['win']) if fx.get('win') is not None else None
                out[f'oddalerts_{side}_decimal_odds'] = fair_odds(out[f'oddalerts_{side}_win_prob'])
                out[f'oddalerts_{side}_xgf'] = fx.get('xgf')
                out[f'oddalerts_{side}_clean_sheet_prob'] = fx.get('cs')
    return [fixtures[k] | {'key': k} for k in sorted(fixtures, key=lambda k: (k[2], k[0], k[1]))]


def build_comparison(horizon: int = 6) -> dict:
    data, raw_path = fetch_oddalerts(horizon=horizon)
    model_by_key = load_model_predictions()
    rows = []
    for fixture in collapse_oddalerts(data):
        key = fixture['key']
        model = model_by_key.get(key)
        row = {k: v for k, v in fixture.items() if k != 'key'}
        row.update({'raw_cache_path': str(raw_path), 'model_match_found': bool(model)})
        if model:
            row.update(model)
            if norm(model['home_team']) != norm(row.get('home_team')):
                row['model_home_win_prob'], row['model_away_win_prob'] = model['model_away_win_prob'], model['model_home_win_prob']
                row['model_home_decimal_odds'], row['model_away_decimal_odds'] = model['model_away_decimal_odds'], model['model_home_decimal_odds']
                row['model_expected_home_goals'], row['model_expected_away_goals'] = model['model_expected_away_goals'], model['model_expected_home_goals']
            row['home_win_prob_delta_oddalerts_minus_model'] = row.get('oddalerts_home_win_prob') - row['model_home_win_prob']
            row['away_win_prob_delta_oddalerts_minus_model'] = row.get('oddalerts_away_win_prob') - row['model_away_win_prob']
        rows.append(row)
    return {'generated_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(), 'policy': 'Comparison-only external market/model-derived probabilities. Not used in PL/no-market model features or training.', 'source_registry': [{'id': 'oddalerts_fpl_ticker', 'label': 'OddAlerts FPL ticker', 'url': 'https://www.oddalerts.com/fpl/fixture-ticker', 'endpoint': ENDPOINT, 'fields': ['win', 'xgf', 'xga', 'cs'], 'status': 'active_comparison_only'}, {'id': 'elevenify', 'label': 'Elevenify', 'url': 'https://elevenify.com/', 'endpoint': None, 'fields': [], 'status': 'queued_research'}], 'match_count': len(rows), 'model_matches': sum(1 for r in rows if r.get('model_match_found')), 'fixtures': rows}


def fmt_prob(v: object) -> str:
    return '—' if v is None or pd.isna(v) else f'{100 * float(v):.1f}%'


def fmt_odds(v: object) -> str:
    return '—' if v is None or pd.isna(v) else f'{float(v):.2f}'


def fmt_delta(v: object) -> str:
    if v is None or pd.isna(v):
        return '—'
    cls = 'pos' if float(v) > 0 else ('neg' if float(v) < 0 else '')
    return f"<span class='{cls}'>{100 * float(v):+.1f}pp</span>"


def render(comparison: dict) -> None:
    PL_DIR.mkdir(parents=True, exist_ok=True)
    (PL_DIR / 'comparison.json').write_text(json.dumps(comparison, indent=2))
    rows = comparison['fixtures']
    fieldnames = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with (PL_DIR / 'comparison.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    row_html = []
    for r in rows:
        row_html.append('<tr>'
            f"<td>{html.escape(str(r.get('kickoff_utc') or '')[:16].replace('T', ' '))}<br><span class='muted'>{html.escape(str(r.get('gameweek') or ''))}</span></td>"
            f"<td><strong>{html.escape(str(r.get('home_team') or ''))}</strong> vs <strong>{html.escape(str(r.get('away_team') or ''))}</strong><br><span class='muted'>OddAlerts source: {html.escape(str(r.get('oddalerts_source') or ''))}</span></td>"
            f"<td>{fmt_prob(r.get('model_home_win_prob'))}<br><span class='odds'>{fmt_odds(r.get('model_home_decimal_odds'))}</span></td>"
            f"<td>{fmt_prob(r.get('model_draw_prob'))}<br><span class='odds'>{fmt_odds(r.get('model_draw_decimal_odds'))}</span></td>"
            f"<td>{fmt_prob(r.get('model_away_win_prob'))}<br><span class='odds'>{fmt_odds(r.get('model_away_decimal_odds'))}</span></td>"
            f"<td>{fmt_prob(r.get('oddalerts_home_win_prob'))}<br><span class='odds'>{fmt_odds(r.get('oddalerts_home_decimal_odds'))}</span></td>"
            f"<td>{fmt_prob(r.get('oddalerts_away_win_prob'))}<br><span class='odds'>{fmt_odds(r.get('oddalerts_away_decimal_odds'))}</span></td>"
            f"<td>{fmt_delta(r.get('home_win_prob_delta_oddalerts_minus_model'))}</td>"
            f"<td>{fmt_delta(r.get('away_win_prob_delta_oddalerts_minus_model'))}</td>"
            f"<td>{html.escape(str(r.get('model_feature_set') or ('pending model fixture match' if not r.get('model_match_found') else '')))}</td>"
            '</tr>')
    generated_at = html.escape(str(comparison['generated_at_utc']))
    page = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>PL Comparison Odds</title><link rel="stylesheet" href="../../assets/site.css">
<style>.odds{{color:#64748b;font-size:.85rem}} .pos{{color:#047857}} .neg{{color:#b91c1c}} table{{font-size:.92rem}} th,td{{vertical-align:top}} .source-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:1rem}}</style>
</head><body><main><div class="topbar"><a class="brand" href="../../index.html">Project Lab</a><span class="muted">Generated {generated_at}</span></div>
<p><a href="index.html">← PL model</a> · <a href="predictions.html">Predictions</a> · <a href="ratings.html">Team ratings</a></p>
<section class="card hero"><span class="pill warn">COMPARISON ONLY</span><h1>PL comparison odds</h1>
<p>Upcoming Premier League fixtures with our no-market model probabilities beside external comparison sources. External probabilities are market/model-derived and are never used as model inputs.</p>
<p><a class="button" href="comparison.json">Download JSON</a><a class="button secondary" href="comparison.csv">Download CSV</a></p></section>
<section class="card"><h2>Source registry</h2><div class="source-grid"><div><strong>OddAlerts FPL ticker</strong><br><a href="https://www.oddalerts.com/fpl/fixture-ticker">source page</a><br><span class="muted">Fields: win%, xGF, xGA, clean sheet%; active comparison-only.</span></div><div><strong>Elevenify</strong><br><span class="muted">Queued: check upcoming-season data and build comparison-only scraper if available.</span></div><div><strong>Future sources</strong><br><span class="muted">Add by appending to <code>comparison.json.source_registry</code> and emitting per-fixture source fields.</span></div></div></section>
<section class="card"><h2>Fixtures</h2><div class="table-wrap"><table><thead><tr><th>Kickoff</th><th>Fixture</th><th>Our home<br><span class="odds">fair odds</span></th><th>Our draw<br><span class="odds">fair odds</span></th><th>Our away<br><span class="odds">fair odds</span></th><th>OddAlerts home<br><span class="odds">fair odds</span></th><th>OddAlerts away<br><span class="odds">fair odds</span></th><th>Home Δ</th><th>Away Δ</th><th>Model/source note</th></tr></thead><tbody>
{''.join(row_html)}
</tbody></table></div></section>
<div class="policy">Guardrail: OddAlerts, Elevenify, bookmaker, exchange, or other published forecast probabilities are comparison-only diagnostics. They are not no-market features, training targets, priors, calibrators, or selectors.</div>
</main></body></html>'''
    (PL_DIR / 'comparison.html').write_text(page)


def main() -> None:
    comparison = build_comparison(horizon=6)
    render(comparison)
    print(json.dumps({'comparison_rows': comparison['match_count'], 'model_matches': comparison['model_matches'], 'html': str(PL_DIR / 'comparison.html')}))


if __name__ == '__main__':
    main()
