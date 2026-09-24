---
name: brand-lead-qualification
description: Discover or assess prospective brand partners for a creator in this MVP, checking fit, public contact evidence, advertiser claims, and saved-lead exclusions.
---

# Qualify brand leads

Read [AGENTS.md](../../../AGENTS.md), then use the creator brief and requested market/deal scope. The implementation is in `src/search/brand_finder.py`, `src/agents/lead_finder_agent.py`, `src/skills/web_search.py`, `deep_bio_link.py`, `contact_verifier.py`, and `src/search/confidence.py`.

## Research and assess

1. Inspect saved/scouted exclusions for the creator before proposing repeats. `get_contacted_brand_names` indicates stored leads, not confirmed outreach. Respect flagged/excluded leads and explain a deliberate repeat if requested.
2. Prefer an official brand website or public business profile. Check product/category fit, geography, and a specific creator-content connection. Exclude directories, listicles, and unrelated entities rather than treating a search hit as a qualified brand.
3. Locate published business contacts or a collaboration form. Preserve the source URL and distinguish extracted, supplied, inferred, and unknown values in the handoff. The finder/storage can synthesize email addresses; inspect the underlying page before calling one verified.
4. Treat contact checks as syntax/format/role signals. They do not prove mailbox deliverability. Treat fit and confidence scores as implementation heuristics, and ad probability as an estimate. Only describe an active campaign when there is direct dated evidence; an Ad Library search URL alone does not qualify.
5. Review the candidate and uncertainties before an intended save. Discovery itself can update OKF, including when API `auto_save` is false; do not promise a no-write preview from that switch.

## Handoff

For each candidate, include brand/website, fit rationale, market, published contact and source (or unknown), advertising evidence (or unknown), duplicate/exclusion status, and recommended next research or outreach action. Use existing BrandOpportunity/BrandContact fields when working in the app; do not invent unsupported provenance fields in an API payload.

Saved leads and OKF knowledge can be stale. A save timestamp or `last_verified` field does not substitute for inspecting a source. Do not send outreach as part of qualification.
