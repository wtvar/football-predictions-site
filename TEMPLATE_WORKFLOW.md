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

5. Keep root `index.html` as the homepage, not a single project's output.

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
