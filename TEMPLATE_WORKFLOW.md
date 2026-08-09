# Static project page template workflow

This repo is the public/static dashboard and output site. It should contain safe generated summaries and public output only.

## Add a new project

1. Copy the template folder:

```bash
cp -R templates/project-template projects/<project-id>
```

2. Edit `projects/<project-id>/index.html`:
- current status
- latest research
- latest experiments
- actual output link

3. Add/update project output page or generated artifact:

```text
projects/<project-id>/output.html
projects/<project-id>/*.json
```

4. Add an entry to `projects.json` so homepage cards/generators can discover it.

5. Rebuild the homepage from the registry:

```bash
python scripts/render_home_from_projects.py
```

6. Keep root `index.html` as the homepage, not a single project's output.

## Add a new page to an existing project

Use the scaffold so the page is registered and linked from the homepage/project card:

```bash
python scripts/scaffold_site_page.py pl-model team-strength-comparison \
  "Team strength comparison" \
  "Comparison-only external team ratings and xG strengths" \
  --kind comparison_only --status "COMPARISON ONLY"
python scripts/render_home_from_projects.py
```

Then edit the generated HTML/JSON and add any generator script needed under `scripts/`.

## Add a new external comparison source

1. Start from `templates/comparison-source-template/README.md`.
2. Cache raw payloads outside git under `/root/football-data-cache/...`.
3. Publish only normalized summary artifacts in the site repo.
4. Add the source to the relevant JSON `source_registry`.
5. Run the homepage renderer if adding a new public page link.

## Guardrails

- Do not commit `.env`, tokens, raw scraped data, account data, private betting logs, or model training datasets.
- Public project pages should summarize research/experiments and link to safe generated outputs only.
- If a project has no validated output yet, publish a placeholder explaining what is missing.

## Suggested page sections

- Current status
- Latest research / queue
- Latest experiments / evaluator recommendation
- Actual output
- Guardrails / caveats
