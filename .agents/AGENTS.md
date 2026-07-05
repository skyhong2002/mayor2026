# mayor2026 - Workspace Rules

Whenever adding a new entry to `data/sources/candidate-watchlist.csv`:

1. **Stable IDs**: `public_id` decides the candidate page URL (`/city/<candidate_id>/`). Never renumber
   existing rows because of sorting or insertion.
2. **One tag per cell**: `keywords` and any future tag column must be one element per cell; do not
   pack compound values (`交通/住宅`) into a single field.
3. **Build & validation**: run `python3 scripts/run_pipeline.py --skip-watch` for a local dry run, then
   `python3 scripts/validate_public_outputs.py` before publishing.
4. **Deployment**: commit source files (`data/`, `scripts/`, `site/assets`, `site/templates`) to `main`.
   Generated site output is published to `gh-pages` via `scripts/publish_github_pages.py`; never commit
   generated `site/api`, `site/data`, `site/feeds`, or `site/city` output to `main`.
5. **Data preservation**: unlike typical scrapers, `data/feeds/social_feed_inbox.jsonl` and
   `social_candidates.jsonl` are tracked in git on purpose. A candidate deleting a post is itself a
   newsworthy event — never rewrite history in these files, only append.
