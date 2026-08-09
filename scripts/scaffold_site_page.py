#!/usr/bin/env python3
"""Scaffold a public site page and register it in projects.json.

Example:
  python scripts/scaffold_site_page.py pl-model team-strength-comparison \
    "Team strength comparison" "Comparison-only external team ratings"

Then edit the generated HTML/JSON and run:
  python scripts/render_home_from_projects.py
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('project_id')
    parser.add_argument('page_slug')
    parser.add_argument('title')
    parser.add_argument('summary')
    parser.add_argument('--kind', default='public_page')
    parser.add_argument('--status', default='INFO')
    args = parser.parse_args()

    project_dir = SITE / 'projects' / args.project_id
    if not project_dir.exists():
        raise SystemExit(f'unknown project folder: {project_dir}')
    html_path = project_dir / f'{args.page_slug}.html'
    json_path = project_dir / f'{args.page_slug}.json'
    if html_path.exists() or json_path.exists():
        raise SystemExit('target page already exists')

    generated = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    template = (SITE / 'templates' / 'page-template' / 'page.html').read_text()
    html = (template
        .replace('{{PAGE_TITLE}}', args.title)
        .replace('{{PAGE_SUMMARY}}', args.summary)
        .replace('{{STATUS}}', args.status)
        .replace('{{GENERATED_AT}}', generated))
    html_path.write_text(html)
    json_path.write_text(json.dumps({
        'generated_at_utc': generated,
        'policy': 'Public page scaffold. Fill with safe publishable content only.',
        'rows': [],
    }, indent=2))

    registry_path = SITE / 'projects.json'
    registry = json.loads(registry_path.read_text())
    for project in registry.get('projects', []):
        if project.get('id') == args.project_id:
            pages = project.setdefault('pages', [])
            rel = f'projects/{args.project_id}/{args.page_slug}.html'
            if not any(p.get('url') == rel for p in pages):
                pages.append({'label': args.title, 'url': rel, 'kind': args.kind})
            break
    else:
        raise SystemExit(f'project not in projects.json: {args.project_id}')
    registry['generated_at'] = generated
    registry_path.write_text(json.dumps(registry, indent=2))
    print(json.dumps({'html': str(html_path), 'json': str(json_path), 'registered': True}, indent=2))


if __name__ == '__main__':
    main()
