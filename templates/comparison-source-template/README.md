# Comparison-only source template

Use this when adding a source such as OddAlerts, Elevenify, bookmaker-derived fixture tickers, public forecast sites, or team-strength pages.

## Required files

```text
projects/<project-id>/<source-or-page>.html
projects/<project-id>/<source-or-page>.json
projects/<project-id>/<source-or-page>.csv   # optional
```

## Required JSON shape

```json
{
  "generated_at_utc": "...",
  "policy": "Comparison-only external market/model-derived probabilities. Not used in model features or training.",
  "source_registry": [
    {
      "id": "source_id",
      "label": "Human label",
      "url": "https://source-page.example/",
      "endpoint": "https://api-or-data-route.example/optional",
      "fields": ["win", "xg", "rating"],
      "status": "active_comparison_only"
    }
  ],
  "rows": []
}
```

## Mandatory guardrail copy

External market/model-derived probabilities are diagnostics only and are not no-market features, training targets, priors, calibrators, router selectors, or approval evidence for model changes.

## Public-source rules

- Cache raw payloads outside git under `/root/football-data-cache/...`.
- Commit only normalized public summaries/artifacts.
- Include source URL, retrieval timestamp, parser version, and source fields.
- Do not bypass login/paywalls/anti-bot controls.
- If data is visible but terms/access are ambiguous, queue a source-review item before production refresh.
