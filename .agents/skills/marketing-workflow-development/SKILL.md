---
name: marketing-workflow-development
description: Maintain or debug this project's existing CLI, FastAPI dashboard, marketing pipeline, Python skills, storage, and MCP contracts with scoped changes.
---

# Maintain the current marketing MVP

Read [AGENTS.md](../../../AGENTS.md) for the current architecture, data side effects, and team workflow. Preserve this accepted MVP; implement the requested change without substituting a new product architecture.

## Trace before editing

- For dashboard runs, trace `src/server/static/index.html` → `src/server/app.py` → `marketing_graph.execute` → `adk_orchestrator.execute_adk_pipeline` → profiler/lead finder/drafter.
- For CLI behavior, start in `src/cli/main.py`; terminal review happens after the graph in the run wizard.
- For deep-workflow tasks, inspect `src/agents/deep/` separately. Its presence/import does not mean the default web run invokes it.
- For runtime capabilities, inspect `src/skills/`. MCP exposure requires the manifest and dispatcher in `src/mcp/server.py`; instruction files do not register tools.
- For stale or missing output, identify which store is being read: SQLite, cumulative leads JSON, campaign JSON, draft text, or OKF. Account for module-level instances and in-memory job state.

Check frontend request/response expectations before API changes. Preserve Pydantic contracts and text-file metadata parsed by DraftManager. Trace fallback branches before attributing output to a live source or configured model. The root guide records current implementation caveats; it does not authorize fixing unrelated ones.

## Verify and hand off

Set temporary data and session paths before imports. Select relevant existing tests from the root guide, inspect their external calls, and mock dependencies when checking local behavior. Test a browser interaction when its UI changes. Do not use reset or a real campaign as a routine smoke test.

Report the narrow change, checks performed, and any remaining limitation. Keep docs aligned with actual code. For documentation requests, change only the requested documentation; leave runtime, dependencies, and data intact.
