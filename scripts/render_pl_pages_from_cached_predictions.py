#!/usr/bin/env python3
"""Render unified PL model pages from the model repo's cached upcoming_predictions.csv.

This is a safe publication fallback when the live fixture fetch is unavailable.
It uses already-generated no-market model outputs and does not compute new model
probabilities or use external comparison sources as model inputs.
"""
from __future__ import annotations

import csv
import datetime as dt
import html
import json
import shutil
import sys
from pathlib import Path

import pandas as pd

SITE = Path(__file__).resolve().parents[1]
MODEL = Path('/root/football-multi-source-data')
MODEL_SRC = MODEL / 'src'
PRED_CSV = MODEL / 'data' / 'processed' / 'upcoming_predictions.csv'
PL_DIR = SITE / 'projects' / 'pl-model'
TMP = Path('/tmp/pl_site_from_cached_predictions')

sys.path.insert(0, str(MODEL_SRC))
from football_poisson.upcoming_predictions import write_predictions_site  # noqa: E402


def esc(v: object) -> str:
    return html.escape('' if v is None or pd.isna(v) else str(v))


def pct(v: object) -> str:
    return '—' if v is None or pd.isna(v) else f'{100 * float(v):.1f}%'


def num(v: object) -> str:
    return '—' if v is None or pd.isna(v) else f'{float(v):.2f}'


def odds(v: object) -> str:
    if v is None or pd.isna(v) or float(v) <= 0:
        return '—'
    return f'{1 / float(v):.2f}'


def data_label(row: dict) -> str:
    feature_set = str(row.get('model_feature_set') or '')
    missing = int(row.get('missing_no_market_feature_count') or 0)
    if missing:
        return f'Partial ({missing} missing)'
    labels = {
        'pl_oaw_xg_hl5': 'Opponent-adjusted xG model',
        'pl_original_elo_xg_fallback': 'PL Elo+xG fallback',
        'championship_elo_shots': 'Championship shots model',
        'championship_xg_elo_shots': 'Championship xG+shots model',
        'championship_elo_only': 'Championship Elo model',
        'lower_league_goals_only': 'Lower-league goals model',
        'lower_league_shots_sot_conversion': 'Lower-league shots/SOT model',
    }
    return labels.get(feature_set, 'Full')


def topbar(active: str, generated_at: str) -> str:
    links = [
        ('Overview', 'index.html', 'overview'),
        ('Predictions', 'predictions.html', 'predictions'),
        ('Team ratings', 'ratings.html', 'ratings'),
        ('Fixture comparison', 'comparison.html', 'comparison'),
        ('Strength comparison', 'team-strength-comparison.html', 'strength-comparison'),
    ]
    nav = ' · '.join(
        f"<strong>{label}</strong>" if key == active else f"<a href='{href}'>{label}</a>"
        for label, href, key in links
    )
    return f"""<div class='topbar'><a class='brand' href='../../index.html'>Football Project Lab</a><span class='muted'>Generated {esc(generated_at)}</span></div><p><a href='../../index.html'>← Dashboard</a> · {nav}</p>"""


def page(title: str, active: str, generated_at: str, body: str) -> str:
    return f"""<!doctype html>
<html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'>
<title>{esc(title)}</title><link rel='stylesheet' href='../../assets/site.css'>
<style>.table-wrap{{overflow:auto}}table{{width:100%;border-collapse:collapse;background:white;border-radius:.75rem;overflow:hidden;box-shadow:0 1px 4px rgba(15,23,42,.08)}}th,td{{padding:.72rem;border-bottom:1px solid #e2e8f0;text-align:left;vertical-align:top}}th{{background:#e2e8f0;font-size:.9rem}}.odds,.small{{color:#64748b;font-size:.85rem}}.num{{font-variant-numeric:tabular-nums;text-align:right}}.pos{{color:#047857}}.neg{{color:#b91c1c}}.policy{{margin-top:1rem;padding:.75rem;background:#ecfeff;border:1px solid #a5f3fc;border-radius:.5rem;color:#164e63}}.rank{{font-variant-numeric:tabular-nums;text-align:right}}.bar-cell{{min-width:180px;position:relative;font-variant-numeric:tabular-nums}}.bar-cell span{{position:relative;z-index:1;font-weight:700}}.bar{{position:absolute;left:.75rem;top:30%;height:40%;opacity:.65;border-radius:.2rem}}.bar.positive{{background:#7c3aed}}.bar.negative{{background:#94a3b8}}</style>
</head><body><main>{topbar(active, generated_at)}{body}</main></body></html>"""


def render_predictions(payload: dict) -> str:
    rows = []
    for f in payload['fixtures']:
        rows.append(
            '<tr>'
            f"<td>{esc(str(f.get('kickoff_utc','')).replace('T',' ').replace('+00:00',' UTC'))}</td>"
            f"<td>{esc(f.get('competition_name') or f.get('league'))}<br><span class='small'>{esc(f.get('model_feature_set'))}</span></td>"
            f"<td><strong>{esc(f.get('home_team'))}</strong> vs <strong>{esc(f.get('away_team'))}</strong></td>"
            f"<td>{pct(f.get('model_home_win_prob'))}<br><span class='odds'>{odds(f.get('model_home_win_prob'))}</span></td>"
            f"<td>{pct(f.get('model_draw_prob'))}<br><span class='odds'>{odds(f.get('model_draw_prob'))}</span></td>"
            f"<td>{pct(f.get('model_away_win_prob'))}<br><span class='odds'>{odds(f.get('model_away_win_prob'))}</span></td>"
            f"<td>{num(f.get('model_expected_home_goals'))} - {num(f.get('model_expected_away_goals'))}</td>"
            f"<td>{esc(data_label(f))}</td>"
            '</tr>'
        )
    leagues = {}
    for f in payload['fixtures']:
        leagues[f.get('competition_name') or f.get('league')] = leagues.get(f.get('competition_name') or f.get('league'), 0) + 1
    chips = ' '.join(f"<span class='pill info'>{esc(k)}: {v}</span>" for k, v in sorted(leagues.items()))
    body = f"""<section class='card hero'><span class='pill ok'>NO-MARKET MODEL</span><h1>Fixture predictions</h1><p>Next {int(payload.get('days', 365))} days · Fixtures: {int(payload.get('fixture_count', len(payload['fixtures'])))} · {chips}</p><p><a class='button' href='predictions.json'>Download JSON</a><a class='button secondary' href='comparison.html'>Compare vs OddAlerts</a></p></section><section class='card'><div class='table-wrap'><table><thead><tr><th>Kickoff</th><th>Competition/model</th><th>Fixture</th><th>Home<br><span class='odds'>fair odds</span></th><th>Draw<br><span class='odds'>fair odds</span></th><th>Away<br><span class='odds'>fair odds</span></th><th>xG</th><th>Data</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div></section><div class='policy'>Model policy: no current or closing odds used. External published probabilities are shown only on the comparison page and are never model inputs.</div>"""
    return page('Fixture predictions', 'predictions', payload['generated_at_utc'], body)


def render_ratings(payload: dict) -> str:
    ratings = payload['ratings']
    max_abs = max([abs(float(r['overall'])) for r in ratings if r.get('overall') is not None] + [0.25])
    rows = []
    for r in ratings:
        overall = r.get('overall')
        width = 0 if overall is None else min(100, abs(float(overall)) / max_abs * 100)
        cls = 'positive' if (overall or 0) >= 0 else 'negative'
        rows.append(
            '<tr>'
            f"<td class='rank'>{int(r['rank'])}</td><td><strong>{esc(r['team'])}</strong></td>"
            f"<td class='num'>{num(r.get('attack'))}</td><td class='num'>{num(r.get('defence'))}</td>"
            f"<td class='bar-cell'><div class='bar {cls}' style='width:{width:.1f}%'></div><span>{'—' if overall is None else f'{float(overall):+.2f}'}</span></td>"
            f"<td>{esc(r.get('rating_source'))}</td><td class='num'>{esc(r.get('sample_fixtures'))}</td>"
            '</tr>'
        )
    body = f"""<section class='card hero'><span class='pill ok'>PL TEAM STRENGTH</span><h1>Premier League team ratings</h1><p>{len(ratings)} teams · PL OAW xG plus promoted-team adjustments where required.</p><p><a class='button' href='team_ratings.json'>Download JSON</a><a class='button secondary' href='predictions.html'>Fixture predictions</a></p></section><section class='card'><div class='table-wrap'><table><thead><tr><th></th><th>Team</th><th>Attack</th><th>Defence</th><th>Overall</th><th>Source</th><th>Matches</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div></section><div class='policy'>{esc(payload.get('metric_policy',''))}</div>"""
    return page('Premier League team ratings', 'ratings', payload['generated_at_utc'], body)


def update_indexes(pred_payload: dict, ratings_payload: dict) -> None:
    generated = pred_payload['generated_at_utc']
    fixture_count = pred_payload['fixture_count']
    ratings_count = len(ratings_payload['ratings'])
    pl_index = f"""<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'><title>PL Model</title><link rel='stylesheet' href='../../assets/site.css'></head><body><main>{topbar('overview', generated)}<section class='card hero'><span class='pill ok'>LIVE OUTPUT</span><h1>PL / Football Match Prediction Model</h1><p>One site for predictions, team strength, and comparison-only external odds.</p><p><a class='button' href='predictions.html'>Fixture predictions</a><a class='button secondary' href='ratings.html'>Team ratings</a><a class='button secondary' href='comparison.html'>Fixture comparison</a><a class='button secondary' href='team-strength-comparison.html'>Strength comparison</a></p></section><div class='grid section-title'><section class='card'><h2>Current output</h2><div class='kv'><div>Fixture horizon</div><div>365 days</div><div>Fixtures</div><div>{fixture_count}</div><div>PL ratings</div><div>{ratings_count} teams</div><div>Policy</div><div>No current/closing odds in model. External sources comparison-only.</div></div></section><section class='card'><h2>Why pages exist</h2><p><strong>Predictions</strong> is our model. <strong>Team ratings</strong> explains the PL strength inputs. <strong>Comparison</strong> puts OddAlerts/other published probabilities beside our model without feeding them back into modelling.</p></section></div></main></body></html>"""
    (PL_DIR / 'index.html').write_text(pl_index)
    root = f"""<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'><title>Football Project Lab</title><link rel='stylesheet' href='assets/site.css'></head><body><main><div class='topbar'><a class='brand' href='index.html'>Football Project Lab</a><span class='muted'>Generated {esc(generated)}</span></div><section class='card hero'><h1>Football Project Lab</h1><p>One homepage for the football prediction outputs and project labs.</p></section><h2 class='section-title'>Projects</h2><div class='grid'><section class='card'><span class='pill ok'>LIVE OUTPUT</span><h2>PL / Football Match Prediction Model</h2><p>Fixture predictions, team ratings, and comparison-only external probabilities.</p><p><a class='button' href='projects/pl-model/predictions.html'>Predictions</a><a class='button secondary' href='projects/pl-model/ratings.html'>Team ratings</a><a class='button secondary' href='projects/pl-model/comparison.html'>Comparison</a><a class='button secondary' href='projects/pl-model/index.html'>Overview</a></p></section><section class='card'><span class='pill warn'>DATA NEEDED</span><h2>Premier League SOT Value Model</h2><p>Data-source and schema foundations for player shots/SOT modelling.</p><p><a class='button' href='projects/sot-model/index.html'>Status / research</a><a class='button secondary' href='projects/sot-model/output.html'>Model output</a></p></section></div><section class='card section-title'><h2>Guardrail</h2><p>External forecast/odds sources such as OddAlerts or Elevenify are comparison-only diagnostics and are not used as model inputs.</p></section></main></body></html>"""
    (SITE / 'index.html').write_text(root)


def main() -> None:
    if not PRED_CSV.exists():
        raise SystemExit(f'missing cached predictions: {PRED_CSV}')
    generated_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    TMP.mkdir(parents=True, exist_ok=True)
    predictions = pd.read_csv(PRED_CSV)
    write_predictions_site(predictions, TMP, generated_at_utc=generated_at, days=365)
    PL_DIR.mkdir(parents=True, exist_ok=True)
    for name in ['predictions.json', 'team_ratings.json']:
        shutil.copy2(TMP / name, PL_DIR / name)
        shutil.copy2(TMP / name, SITE / name)
    pred_payload = json.loads((PL_DIR / 'predictions.json').read_text())
    ratings_payload = json.loads((PL_DIR / 'team_ratings.json').read_text())
    (PL_DIR / 'predictions.html').write_text(render_predictions(pred_payload))
    (PL_DIR / 'ratings.html').write_text(render_ratings(ratings_payload))
    (SITE / 'ratings.html').write_text(render_ratings(ratings_payload).replace("href='../../assets/site.css'", "href='assets/site.css'"))
    update_indexes(pred_payload, ratings_payload)
    print(json.dumps({'fixtures': pred_payload['fixture_count'], 'ratings': len(ratings_payload['ratings']), 'generated_at_utc': generated_at}))


if __name__ == '__main__':
    main()
