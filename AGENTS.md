# Current MVP: guide for agents and the marketing team

## Working agreement

The user accepts the current main-branch application as the MVP. Preserve its dashboard, CLI, workflow, and data formats. Make incremental changes only for the task requested. Do not replace the architecture, introduce a new workspace product, add Laya, or upgrade dependencies as an incidental improvement. Current dependencies are defined in [pyproject.toml](pyproject.toml); Laya is not part of this MVP.

Start with [README.md](README.md), then trace the relevant code below. This guide describes the implementation, including its current shortcuts; it is not a roadmap or a request to fix them. Check `git status` before work and preserve existing changes and operational data.

## Purpose and team workflow

Help a creator marketing team turn an Instagram account into a creator brief, prospective brand partners, contact details, and editable outreach for UGC ads, sponsored reels/stories, and other collaborations.

1. Configure the gateway and local settings in `.env` using `.env.example`. Never paste keys or session cookies into reports or commits.
2. Run `uv sync` and, on first setup, `uv run playwright install chromium`.
3. Use `uv run insta-marketing login` for human Instagram login and saved browser session.
4. Start `uv run insta-marketing serve`; the existing dashboard is at `http://127.0.0.1:8088`. Alternatively run `uv run insta-marketing run --handle HANDLE --location "Bangalore / India" --hitl` for terminal review.
5. Review the creator information, brand relevance, contact sources, suggested rates, and copy. Use saved leads, draft editing, and CSV export in the dashboard as needed.
6. A team member copies reviewed outreach to their messaging client. There is no automatic email, DM, or WhatsApp sender.

The CLI run wizard can ask additional questions; `--sample` selects sample creator data but does not make the whole pipeline offline. Use `uv run insta-marketing --help` or a command's `--help` for current options. Other commands include `leads`, `drafts`, `agents`, `eval`, `mcp`, `okf`, `enrich`, and `verify-brand`. `reset` and the API reset action delete operational data; they are not setup or smoke-test steps.

## Runtime map

| Area | Entry point and responsibility |
| --- | --- |
| CLI | `src/cli/main.py`: Typer commands, login, run wizard, terminal review, dashboard startup |
| Web | `src/server/app.py`: FastAPI APIs; `src/server/static/index.html`: existing dashboard, including its frontend code |
| Main pipeline | `src/agents/workflow_graph.py`: acquire creator, invoke specialists, optional review, save campaign/leads/drafts |
| Specialist orchestration | `src/agents/adk_system.py`: Google ADK agent definitions/manifest and direct Python calls to profiler → lead finder → pitch drafter |
| Creator acquisition | `src/browser/session.py`, `scraper.py`, `brand_scraper.py`, `stealth.py`: session handling, browser scraping, profile parsing |
| Profiling | `src/agents/profiler_agent.py`: niche/media-kit synthesis and estimated commercial positioning |
| Lead discovery | `src/agents/lead_finder_agent.py`, `src/search/brand_finder.py`: exclusions, OKF/search/LLM candidates, enrichment, persistence |
| Drafting/review | `src/agents/pitch_drafter_agent.py`, `draft_manager.py`: generated/fallback copy, terminal review, text-file edits |
| Alternative deep workflow | `src/agents/deep/director.py`, `scout.py`, `strategist.py`: composable scraper/scout/pricing/sequence/OKF implementation; not the handler behind default `/api/run` |
| Runtime skills | `src/skills/`: Python search, extraction, contact checks, pricing, sequencing, scraping, and memory helpers |
| Models | `src/models/creator.py`, `brand.py`, `outreach.py`: Pydantic contracts for profiles, leads, contacts, pitches, and campaign summaries |
| Persistence | `src/storage/db.py` and `okf.py`: SQLite leads and JSON knowledge memory |
| Gateway/config | `src/llm/client.py`, `src/config.py`: OpenAI-compatible requests, JSON parsing, environment settings |
| MCP | `src/mcp/server.py`: tool manifest and JSON-RPC dispatch; CLI stdio and web `/api/mcp` adapters |
| Evaluation | `src/evals/metrics.py`, `benchmark_runner.py`: heuristic checks and stored reports |

The main pipeline constructs ADK agents but invokes domain specialists directly. Do not describe it as an ADK Runner-based durable workflow. `brand_scout_agent.py` is another available specialist; the default ADK orchestrator calls `lead_finder_agent` for discovery.

## Web execution and contracts

`POST /api/run` starts an asyncio task. The dashboard polls `GET /api/job/{job_id}`; `POST /api/stop/{job_id}` requests cancellation. Job state and logs live in the process-local `active_jobs` dictionary and do not survive restart. Blocking work may delay cancellation. `POST /api/run_sync` invokes the same graph without background polling. Both web execution paths disable terminal HITL.

Other endpoint groups cover session/login, saved leads/flagging/export, drafts, live search/enrichment, OKF, skills/MCP, evaluation, and campaign listings. Read request models and handlers in `src/server/app.py` alongside their callers in `index.html` before changing payloads. This is a local shared-state application; creator filters are not tenant authentication or team permissions.

## Data and side effects

Paths default to the project `data/` directory; `DATA_DIR` can override it through settings.

| Artifact | Meaning |
| --- | --- |
| `data/leads.db` | SQLite `brand_leads`, unique by creator username and company name |
| `data/leads_<creator>.json` | Cumulative export of saved leads for a creator |
| `data/drafts/<creator>/*_pitch.txt` | Editable copy and metadata parsed by the CLI/dashboard |
| `data/campaign_<creator>.json` | Serialized campaign summary from a run |
| `data/okf/brands_intelligence.json` | Shared accumulated brand knowledge |
| `data/okf/creator_memory.json` | Creator memory |
| `data/okf/market_benchmarks.json` | Seeded commercial benchmarks used as estimates |
| `data/eval_benchmark_report.json` | Default evaluation report |
| `instagram_session.json` | Default private Playwright session, configurable with `SESSION_FILE` |

Several modules create storage/singletons during import. Set temporary `DATA_DIR` and `SESSION_FILE` before importing the app in verification scripts. Draft files, campaign JSON, SQLite, and OKF are separate stores, not one transactional record. Do not assume an edit in one automatically updates all others. `get_contacted_brand_names` actually returns saved/scouted brand names; it does not prove a message was sent. Live search may save OKF internally even when API `auto_save` is false.

## Interpretation notes for humans and agents

These are current behaviors to account for, not tasks authorized by this guide:

- The main graph uses sample profiles for sample handles/flags and falls back to a sample profile after live scraping errors. Check logs before presenting metrics as observed facts.
- Discovery/storage can synthesize addresses such as `partnerships@domain` or `collab@domain`. Source labels and the UI word “verified” alone do not establish a published or deliverable mailbox. Check the actual brand source before outreach.
- Contact verification is primarily syntax/role/format checking. Fit/confidence/ad probability and evaluation/ROI figures are heuristics or estimates, not measured conversion outcomes. A Meta Ad Library search link is not an observed active ad.
- The gateway client can fall back from a failed remote call to local Ollama with `llama3.2:latest`. Profile and pitch helpers also have fallback output. Check logs when diagnosing results.
- Terminal review currently handles `A` and `S` together and marks `draft` items approved; edited items can remain `edited`. Saved status therefore is not a reliable audit of explicit human approval. Web draft editing has no version-bound approval mechanism. The team must review the actual recipient, text, and terms before manually sending.
- `POST /api/leads/batch_save` currently refers to `BrandContact` and `BrandOpportunity` without importing them in that module. If that action fails, this is a known code-level starting point for a separately requested fix.

## Working on the code

Preserve the default `src.server.app:app` entry point and existing UI unless the task calls for changing them. Follow the path actually invoked instead of assuming every agent/helper is active. Keep changes to Python runtime skills distinct from instruction skills under `.agents/skills/`; adding a `SKILL.md` does not register a Python or MCP tool.

Use existing models and injected dependencies where available. When changing an API, check its frontend and MCP callers. When changing persisted fields, account for existing SQLite databases, JSON records, and draft text parsing. Keep secrets and collected data out of patches. No automated sending is implied by a request to draft or review outreach.

## Verification

Choose checks for the changed behavior. Inspect tests first: the existing suite includes real network/model/browser paths and writes through module-level stores. A full `uv run pytest` is not guaranteed to be an offline, non-mutating check. Use a temporary environment/data directory before imports and mock live boundaries for unit tests; do not run against the team's saved leads or session.

| Change | Relevant existing tests |
| --- | --- |
| Main pipeline/API/drafts | `tests/test_pipeline.py` |
| Parsing, contacts, pricing, search helpers | `tests/test_skills.py`, `tests/test_omnichannel_discovery.py` |
| Session import/confidence | `tests/test_confidence_and_session.py` |
| Deep workflow | `tests/test_deep_agents.py` |
| Knowledge store | `tests/test_okf.py` |
| MCP | `tests/test_mcp.py` |
| Heuristic evaluation | `tests/test_evals.py` |

For startup, check `/healthz` and load the dashboard. For UI changes, verify the affected interaction in the browser. Do not run campaigns, reset data, or import a session merely to verify documentation. Report mocked/local checks separately from live integrations. Documentation-only work needs link and skill validation, not a campaign run.

## Project instruction skills

- [Project maintenance](.agents/skills/marketing-workflow-development/SKILL.md): trace and make scoped changes to this MVP.
- [Creator research](.agents/skills/creator-research/SKILL.md): build a useful brief from account data with explicit unknowns.
- [Brand lead qualification](.agents/skills/brand-lead-qualification/SKILL.md): verify relevance, provenance, contacts, and duplicate exclusions.
- [Outreach review](.agents/skills/outreach-review/SKILL.md): prepare and review copy and commercial terms for manual handoff.
