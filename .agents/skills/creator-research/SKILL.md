---
name: creator-research
description: Analyze a creator account for this marketing MVP and prepare a brief for brand discovery, distinguishing observed profile data from sample data and inferred commercial estimates.
---

# Creator research

Read [AGENTS.md](../../../AGENTS.md) for the application flow. Relevant code is `src/browser/scraper.py`, `src/browser/session.py`, `src/models/creator.py`, and `src/agents/profiler_agent.py`. The alternative scraper wrapper lives in `src/skills/stealth_scraper.py`.

## Build the brief

Use the supplied handle or URL, target market, content interests, and collaboration preference. Normalize handles using existing scraper helpers. Use the established human login/session workflow when live account access is required; keep session contents private.

Check whether acquisition was live, supplied by the team, cached, or a sample fallback. The graph can substitute a sample after scraping fails. Label that explicitly; a completed workflow is not proof of a successful live scrape.

Summarize observed bio, content themes, recent examples, visible metrics, external links, and available business contact information. Record the source and observation time in the brief when available. Keep inferred niche, audience appeal, and proposed brand categories separate from directly observed facts. Do not infer audience geography or demographics solely from the creator's location.

Use the profiler's UGC/rate information as an estimate for discussion. State currency, format, usage period, and unknowns; do not present benchmark rates as agreed commercial terms.

## Handoff

Provide the normalized account, provenance, target market, a short positioning summary, content examples, suitable partnership categories/formats, and missing facts the team should confirm. Explain which facts support each proposed category. Pass that brief into lead qualification without inventing metrics or claiming sample data is live.
