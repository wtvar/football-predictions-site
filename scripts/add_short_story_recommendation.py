#!/usr/bin/env python3
"""Add a weekly short-story recommendation to the static reading page.

This updates areas/reading/stories.json and can optionally commit/push the
site repo. It never stores secrets; push uses token values already present in
.env or the environment.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

SITE = Path(__file__).resolve().parents[1]
STORIES_JSON = SITE / "areas" / "reading" / "stories.json"
EXCLUDED_TITLES = {"the ones who walk away from omelas"}


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "story"


def load_env_file(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(SITE), text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=check)


def upsert_story(args: argparse.Namespace) -> dict:
    if args.title.strip().lower() in EXCLUDED_TITLES and not args.allow_excluded:
        raise SystemExit("Refusing to add excluded/disliked story: The Ones Who Walk Away from Omelas")
    data = json.loads(STORIES_JSON.read_text())
    stories = data.setdefault("stories", [])
    story_id = args.story_id or f"{slugify(args.author)}-{slugify(args.title)}"
    existing = next((s for s in stories if s.get("id") == story_id or (s.get("title", "").lower() == args.title.lower() and s.get("author", "").lower() == args.author.lower())), None)
    tags = [t.strip() for t in (args.tags or "").split(",") if t.strip()]
    if "previously recommended" not in tags:
        tags.insert(0, "previously recommended")
    rec_date = args.recommended_date or datetime.now(timezone.utc).date().isoformat()
    payload = {
        "id": story_id,
        "title": args.title,
        "author": args.author,
        "year": args.year,
        "fit": args.fit,
        "length": args.length,
        "tags": tags,
        "source_label": args.source_label,
        "source_url": args.source_url,
        "recommendation_status": "previously_recommended",
        "recommended_dates": [rec_date],
        "recommendation_note": args.recommendation_note or "Added by weekly short-story recommendation workflow.",
    }
    if existing:
        dates = list(dict.fromkeys((existing.get("recommended_dates") or []) + [rec_date]))
        existing.update({k: v for k, v in payload.items() if v is not None})
        existing["recommended_dates"] = dates
        updated = existing
    else:
        stories.append(payload)
        updated = payload
    order = {"previously_recommended": 0, "excluded_disliked_history": 1}
    stories.sort(key=lambda s: (order.get(s.get("recommendation_status"), 9), (s.get("recommended_dates") or ["9999"])[0], s.get("author", ""), s.get("title", "")))
    data["generated_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    data["notes"] = [
        "This page shows recovered/actual Hermes weekly short-story recommendations, plus explicit excluded history.",
        "Future recommendations are added by scripts/add_short_story_recommendation.py from the weekly cron.",
        "Omelas is retained only as excluded history so it is not recommended again.",
    ]
    STORIES_JSON.write_text(json.dumps(data, indent=2))
    return updated


def commit_and_push(title: str) -> None:
    changed = run(["git", "status", "--short"]).stdout.strip()
    if not changed:
        print("no site changes to commit")
        return
    run(["git", "add", "areas/reading/stories.json"])
    quiet = run(["git", "diff", "--cached", "--quiet"], check=False)
    if quiet.returncode == 0:
        print("no staged changes")
        return
    run(["git", "commit", "-m", f"Add short story recommendation: {title}"])
    env = load_env_file(SITE / ".env")
    token = env.get("FOOTBALL_PREDICTIONS_SITE_TOKEN") or env.get("GITHUB_TOKEN") or os.environ.get("FOOTBALL_PREDICTIONS_SITE_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        print("site updated locally but not pushed: missing site token")
        return
    helper = f"!f() {{ echo username=x-access-token; echo password={token}; }}; f"
    push = run(["git", "-c", "credential.helper=", "-c", f"credential.helper={helper}", "push", "origin", "main"], check=False)
    if push.returncode != 0:
        raise SystemExit("push failed:\n" + push.stdout)
    print("site updated and pushed")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--title", required=True)
    parser.add_argument("--author", required=True)
    parser.add_argument("--year", type=int, default=None)
    parser.add_argument("--fit", required=True)
    parser.add_argument("--length", default="Short story")
    parser.add_argument("--tags", default="")
    parser.add_argument("--source-label", default="Source")
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--recommended-date", default=None)
    parser.add_argument("--recommendation-note", default=None)
    parser.add_argument("--story-id", default=None)
    parser.add_argument("--allow-excluded", action="store_true")
    parser.add_argument("--commit-push", action="store_true")
    args = parser.parse_args()
    updated = upsert_story(args)
    print(json.dumps({"updated": updated["title"], "author": updated["author"], "id": updated["id"]}, indent=2))
    if args.commit_push:
        commit_and_push(updated["title"])


if __name__ == "__main__":
    main()
