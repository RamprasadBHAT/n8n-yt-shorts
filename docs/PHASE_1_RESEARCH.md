# Phase 1: Research Engine

Phase 1 implements the Python-first research layer used by the n8n orchestrator. The engine reads `config/settings.json`, collects candidate topics from configured RSS feeds, Reddit, and Hacker News, optionally ranks candidates with Gemini when `GEMINI_API_KEY` is present, removes duplicate/old/banned topics, persists history, and writes `output/topics.json`.

## Run

```bash
python scripts/research_engine.py --limit 10 --output output/topics.json
```

## Configuration

Research behavior is controlled by `research` in `config/settings.json`:

- `rss_feeds`: list of feed objects with `name` and `url`.
- `reddit_subreddits`: subreddits queried through Reddit's official JSON endpoint.
- `max_topic_age_days`: age cutoff for dated topics.
- `use_gemini_ranking`: enables Gemini ranking when the configured API key environment variable exists.
- `fallback_topics_file`: local seed file used only when live sources return no candidates.
- `banned_terms`: safety and brand-exclusion filters.

Topic history is written to `dedupe.state_file` to prevent repeated Shorts across runs.
