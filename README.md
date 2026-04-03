# Exposome live webpage

This repository is structured as a static site that keeps a stable textbook-style exposome chapter while adding a machine-managed monthly update layer.

## Main files

- `exposome.md`: canonical textbook content
- `index.html`: generated site entry point for GitHub Pages
- `exposome.html`: generated duplicate of the main page
- `updates/*.md`: monthly digests
- `updates/*.html`: rendered monthly digests
- `data/papers.json`: most recent monthly fetch
- `data/monthly-updates.json`: cumulative accepted updates
- `data/source_queries.json`: literature search queries

## Automation flow

The monthly GitHub Action does this:

1. fetch papers from the previous calendar month
2. rank and classify candidates
3. use an OpenAI-compatible LLM to pick textbook-worthy updates when configured
4. update the monthly section inside `exposome.md`
5. write a monthly archive page under `updates/`
6. render `index.html`, `exposome.html`, and archive HTML pages
7. commit the changes back to the repository

## LLM configuration

The selection step expects an OpenAI-compatible chat endpoint.

Set these repository secrets or variables:

- `LLM_API_KEY` **(required for automatic publication)**
- `LLM_MODEL` **(required for automatic publication)**, for example `gpt-4.1-mini`
- `LLM_BASE_URL` *(optional)*, defaults to `https://api.openai.com/v1`

If the LLM is not configured, the workflow still fetches and ranks papers, but it writes a review queue instead of auto-publishing monthly updates.

## GitHub Pages

Use GitHub Pages to serve from the repository root on the default branch. The rendered entry page is `index.html`.

## Local usage

```bash
python3 -m pip install -r requirements.txt
python3 scripts/fetch_monthly_papers.py
python3 scripts/select_monthly_updates.py
python3 scripts/update_site.py
python3 scripts/render_site.py
```

Optional:

- `TARGET_MONTH=2026-03` to rebuild a specific month
- `LLM_API_KEY`, `LLM_MODEL`, `LLM_BASE_URL` for automatic selection
