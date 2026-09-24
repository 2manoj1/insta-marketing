---
name: outreach-review
description: Draft or review creator partnership emails, Instagram DMs, and WhatsApp copy in this MVP, checking factual personalization, proposed terms, and the team's manual handoff.
---

# Draft and review outreach

Read [AGENTS.md](../../../AGENTS.md). Main copy generation is in `src/agents/pitch_drafter_agent.py`; file persistence and terminal review are in `draft_manager.py`. The alternative deep strategist uses `src/skills/pitch_sequencing.py` and `negotiation_pricing.py`. Contracts live in `src/models/outreach.py`.

## Prepare useful copy

Use the creator brief and qualified brand facts. Confirm the recipient against a published business source; generated `partnerships@` or `collab@` addresses are not confirmed recipients. Personalize around actual content and product fit, without fabricating campaign activity, audience metrics, past partnerships, or results.

Separate proposed deliverables and commercial assumptions from agreed terms. For UGC, specify format, number of assets, revisions, and proposed usage period/channel. For a sponsored placement, distinguish creator posting from production-only work. Treat rates as negotiable estimates with a stated currency. Keep email, DM, and WhatsApp copy appropriate to their channel and use a clear, low-pressure next step.

## Review and hand off

Check facts, recipient, subject, body, deliverables, rights, pricing assumptions, and CTA. Explain substantive edits so a teammate can review them. Generated text and fallback templates both need the same fact check.

The current terminal `A` and `S` actions share an approval branch, so a saved `approved` status does not prove explicit review. Edited items can retain `edited`; the web editor is not a versioned approval system. Record the human's actual decision clearly in the handoff rather than inferring it from the file status.

Use existing draft text metadata/layout when editing through the application; DraftManager parses it. Campaign JSON and editable draft files are separate and may not reflect the same later edits. Identify the reviewed artifact and unresolved facts. The team manually copies approved copy to its messaging client; drafting, saving, and review do not authorize sending.
