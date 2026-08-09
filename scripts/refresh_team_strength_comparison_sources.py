#!/usr/bin/env python3
"""Refresh comparison-only external team-strength page.

Currently compares our PL team ratings with OddAlerts Premier League xG table stats.
External values are diagnostics only and must never enter model training/features.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import html
import json
import re
from pathlib import Path
from urllib.request import Request, urlopen

SITE = Path(__file__).resolve().parents[1]
PL_DIR = SITE / 'projects' / 'pl-model'
RAW_DIR = Path('/root/football-data-cache/oddalerts/xg-premier-league')
URL = 'https://www.oddalerts.com/xg/premier-league'
UA = 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1'

ALIASES = {
    'afc bournemouth': 'bournemouth', 'bournemouth': 'bournemouth',
    'brighton and hove albion': 'brighton', 'brighton': 'brighton',
    'manchester city': 'man city', 'man city': 'man city',
    'manchester united': 'man united', 'man united': 'man united', 'man utd': 'man united',
    'newcastle united': 'newcastle', 'newcastle': 'newcastle',
    'nottingham forest': 'nottm forest', "nott'm forest": 'nottm forest', 'nottm forest': 'nottm forest',
    'tottenham hotspur': 'tottenham', 'tottenham': 'tottenham', 'spurs': 'tottenham',
    'west ham united': 'west ham', 'west ham': 'west ham',
    'wolverhampton wanderers': 'wolves', 'wolves': 'wolves',
}


def norm(v: object) -> str:
    s = str(v).lower().strip().replace('&', 'and')
    s = re.sub(r'[^a-z0-9 ]+', '', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return ALIASES.get(s, s)


def fetch_page() -> tuple[str, Path]:
    req = Request(URL, headers={'User-Agent': UA, 'Accept': 'text/html'})
    body = urlopen(req, timeout=40).read()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    sha = hashlib.sha256(body).hexdigest()
    path = RAW_DIR / f'{dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")}_{sha[:16]}.html'
    path.write_bytes(body)
    return body.decode('utf-8', 'replace'), path


def extract_xg_page_data(page: str) -> dict:
    start = page.find('window.xgPageData =')
    if start < 0:
        raise ValueError('window.xgPageData not found')
    brace = page.find('{', start)
    depth = 0
    in_str = False
    esc = False
    quote = ''
    end = None
    for j in range(brace, len(page)):
        c = page[j]
        if in_str:
            if esc:
                esc = False
            elif c == '\\':
                esc = True
            elif c == quote:
                in_str = False
        else:
            if c in '"\'':
                in_str = True
                quote = c
            elif c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    end = j + 1
                    break
    if end is None:
        raise ValueError('xgPageData object did not close')
    src = page[brace:end]
    src = re.sub(r'([\{,]\s*)([A-Za-z_][A-Za-z0-9_]*)\s*:', r'\1"\2":', src)
    return json.loads(src)


def load_our_ratings() -> dict[str, dict]:
    ratings = json.loads((PL_DIR / 'team_ratings.json').read_text())['ratings']
    return {norm(r['team']): r for r in ratings}


def build() -> dict:
    page, raw_path = fetch_page()
    data = extract_xg_page_data(page)
    ours = load_our_ratings()
    rows = []
    for item in data.get('teamStats', {}).values():
        key = norm(item.get('name'))
        our = ours.get(key)
        row = {
            'team': item.get('name'),
            'oddalerts_team_id': item.get('id'),
            'oddalerts_played': item.get('played'),
            'oddalerts_xg': item.get('xg'),
            'oddalerts_xga': item.get('xga'),
            'oddalerts_xgd': item.get('xgd'),
            'oddalerts_xpts': item.get('xpts'),
            'oddalerts_npxg': item.get('npxg'),
            'oddalerts_xgot': item.get('xgot'),
            'oddalerts_home_xg': item.get('home_xg'),
            'oddalerts_away_xg': item.get('away_xg'),
            'oddalerts_home_xga': item.get('home_xga'),
            'oddalerts_away_xga': item.get('away_xga'),
            'our_rating_found': bool(our),
            'raw_cache_path': str(raw_path),
        }
        if our:
            row.update({
                'our_rank': our.get('rank'),
                'our_attack': our.get('attack'),
                'our_defence': our.get('defence'),
                'our_overall': our.get('overall'),
                'our_rating_source': our.get('rating_source'),
                'our_sample_fixtures': our.get('sample_fixtures'),
            })
            row['xgd_minus_our_overall'] = None if item.get('xgd') is None or our.get('overall') is None else round(float(item['xgd']) - float(our['overall']), 3)
        rows.append(row)
    rows.sort(key=lambda r: (r.get('our_rank') is None, r.get('our_rank') or 999, -(r.get('oddalerts_xgd') or -999)))
    return {
        'generated_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
        'policy': 'Comparison-only external team-strength/xG values. Not used in model features or training.',
        'source_registry': [
            {'id': 'oddalerts_xg_premier_league', 'label': 'OddAlerts Premier League xG table', 'url': URL, 'endpoint': 'embedded window.xgPageData.teamStats', 'fields': ['xg','xga','xgd','xpts','npxg','xgot'], 'status': 'active_comparison_only'},
        ],
        'team_count': len(rows),
        'our_rating_matches': sum(1 for r in rows if r.get('our_rating_found')),
        'teams': rows,
    }


def esc(v: object) -> str:
    return html.escape('' if v is None else str(v))


def num(v: object) -> str:
    return '—' if v is None else f'{float(v):.2f}'


def render(payload: dict) -> None:
    PL_DIR.mkdir(parents=True, exist_ok=True)
    (PL_DIR / 'team-strength-comparison.json').write_text(json.dumps(payload, indent=2))
    rows = []
    for r in payload['teams']:
        rows.append('<tr>'
            f"<td>{esc(r.get('our_rank') or '')}</td>"
            f"<td><strong>{esc(r.get('team'))}</strong><br><span class='odds'>{esc(r.get('our_rating_source') or 'no model match')}</span></td>"
            f"<td>{num(r.get('our_attack'))}</td><td>{num(r.get('our_defence'))}</td><td>{num(r.get('our_overall'))}</td>"
            f"<td>{num(r.get('oddalerts_xg'))}</td><td>{num(r.get('oddalerts_xga'))}</td><td>{num(r.get('oddalerts_xgd'))}</td><td>{num(r.get('oddalerts_xpts'))}</td>"
            f"<td>{esc(r.get('oddalerts_played'))}</td>"
            '</tr>')
    generated = esc(payload['generated_at_utc'])
    page = f"""<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'><title>Team strength comparison</title><link rel='stylesheet' href='../../assets/site.css'><style>.table-wrap{{overflow:auto}}table{{width:100%;border-collapse:collapse;background:white;border-radius:.75rem;overflow:hidden}}th,td{{padding:.7rem;border-bottom:1px solid #e2e8f0;text-align:left}}th{{background:#e2e8f0}}.odds{{color:#64748b;font-size:.85rem}}td:nth-child(n+3){{font-variant-numeric:tabular-nums;text-align:right}}</style></head><body><main><div class='topbar'><a class='brand' href='../../index.html'>Football Project Lab</a><span class='muted'>Generated {generated}</span></div><p><a href='../../index.html'>← Dashboard</a> · <a href='index.html'>Overview</a> · <a href='predictions.html'>Predictions</a> · <a href='ratings.html'>Team ratings</a> · <a href='comparison.html'>Fixture comparison</a></p><section class='card hero'><span class='pill warn'>COMPARISON ONLY</span><h1>Team strength comparison</h1><p>Our PL team ratings beside OddAlerts Premier League xG table strength metrics. External values are diagnostics only and are not model inputs.</p><p><a class='button' href='team-strength-comparison.json'>Download JSON</a></p></section><section class='card'><div class='table-wrap'><table><thead><tr><th>Our rank</th><th>Team</th><th>Our attack</th><th>Our defence</th><th>Our overall</th><th>OddAlerts xG</th><th>OddAlerts xGA</th><th>OddAlerts xGD</th><th>OddAlerts xPTS</th><th>OA played</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div></section><div class='policy'>Guardrail: OddAlerts team-strength/xG values are comparison-only diagnostics. They are not no-market features, training targets, priors, calibrators, selectors, or model-approval evidence.</div></main></body></html>"""
    (PL_DIR / 'team-strength-comparison.html').write_text(page)


def main() -> None:
    payload = build()
    render(payload)
    print(json.dumps({'teams': payload['team_count'], 'our_matches': payload['our_rating_matches'], 'html': str(PL_DIR / 'team-strength-comparison.html')}))


if __name__ == '__main__':
    main()
