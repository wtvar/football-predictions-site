#!/usr/bin/env python3
"""Render the public site homepage from projects.json.

New project/output pages should be added to projects.json first, then this script
rebuilds root index.html so the homepage links cannot drift from the registry.
"""
from __future__ import annotations

import datetime as dt
import html
import json
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]
PROJECTS_JSON = SITE / 'projects.json'


def esc(v: object) -> str:
    return html.escape('' if v is None else str(v))


def button(url: str, label: str, secondary: bool = True) -> str:
    cls = 'button secondary' if secondary else 'button'
    return f"<a class='{cls}' href='{esc(url)}'>{esc(label)}</a>"


def render() -> str:
    data = json.loads(PROJECTS_JSON.read_text())
    generated = data.get('generated_at') or dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    area_cards = {}
    for project in data.get('projects', []):
        area = project.get('area') or 'Modelling'
        pages = project.get('pages') or []
        if not pages:
            pages = [
                {'label': 'Overview', 'url': project.get('project_url')},
                {'label': 'Output', 'url': project.get('output_url')},
            ]
        buttons = []
        for i, page in enumerate([p for p in pages if p.get('url')]):
            buttons.append(button(page['url'], page.get('label') or page['url'], secondary=i != 0))
        latest = ''.join(f"<li>{esc(item)}</li>" for item in (project.get('last_research') or [])[:3])
        latest_html = f"<h3>Latest notes</h3><ul class='list'>{latest}</ul>" if latest else ''
        card = f"""<section class='card'><span class='pill {esc(project.get('status_class','info'))}'>{esc(project.get('status',''))}</span><h2>{esc(project.get('title'))}</h2><p>{esc(project.get('summary'))}</p><p>{''.join(buttons)}</p>{latest_html}</section>"""
        area_cards.setdefault(area, []).append(card)
    sections = []
    for area in sorted(area_cards.keys(), key=lambda a: (a != 'Reading', a)):
        sections.append(f"<h2 class='section-title'>{esc(area)}</h2><div class='grid'>{''.join(area_cards[area])}</div>")
    return f"""<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'><title>Home</title><link rel='stylesheet' href='assets/site.css'></head><body><main><div class='topbar'><a class='brand' href='index.html'>Home</a><span class='muted'>Generated {esc(generated)}</span></div><section class='card hero'><h1>Home</h1><p>A small personal dashboard for reading, modelling, and project outputs.</p><p class='muted'>Use the area cards below to jump to reading recommendations or football modelling pages.</p></section>{''.join(sections)}<section class='card section-title'><h2>Guardrail</h2><p>External forecast/odds sources such as OddAlerts, Elevenify, or bookmaker APIs are comparison-only diagnostics unless explicitly approved otherwise.</p></section><section class='card section-title'><h2>Template workflow</h2><p>New pages should use <a href='TEMPLATE_WORKFLOW.md'>the site template workflow</a> and be registered in <code>projects.json</code>.</p></section></main></body></html>"""


def main() -> None:
    (SITE / 'index.html').write_text(render())
    print('rendered index.html from projects.json')


if __name__ == '__main__':
    main()
