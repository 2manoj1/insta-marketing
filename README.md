# Instagram Influencer Marketing Manager (Multi-Agent System)

An automated, human-in-the-loop influencer marketing system built with **Python**, **uv**, **Playwright**, and **Google ADK & Graph Orchestration**.

Configured specifically to work with:
- **Local / Remote OpenAI-compatible Gateway**: `https://api.manojmukherjee.co.in/v1` (Ollama-backed) or local Ollama `http://localhost:11434/v1`.
- **Human-in-the-Loop Instagram Login**: Opens browser with a 5-second buffer and session persistence to `instagram_session.json` so login is required only once.
- **Creator Opportunity Scouting**: Extracts Instagram bio, follower metrics, recent reels, captions, and niche indicators.
- **Verified Brand Leads**: Finds high-probability Instagram advertisers, collecting verified marketing emails, mobile/phone numbers, and websites saved to `data/leads_<creator>.json`.
- **Human-in-the-Loop (HITL) Email Drafts**: Drafts tailored pitches for UGC video ads (with 30-day paid usage rights) and sponsored reels, saved as individual text files in `data/drafts/<creator>/`.
- **Dual Interfaces**: Native `uv` CLI and responsive Web Dashboard.

---

## Quickstart with UV (Fully Automated)

Everything runs seamlessly with `uv` — no manual virtualenv activation needed!

```bash
# 1. Sync dependencies and lockfile
uv sync

# 2. Install Playwright Chromium browser binary (one-time setup)
uv run playwright install chromium

# 3. Log into Instagram (opens human browser with 5s initial buffer)
uv run insta-marketing login

# 4. Run marketing manager workflow for a creator
uv run insta-marketing run --handle iva_mana5 --location "Bangalore / India"

# 5. View verified company emails & mobile numbers table
uv run insta-marketing leads iva_mana5

# 6. List all ready-to-send draft email files
uv run insta-marketing drafts iva_mana5

# 7. Launch the modern Web Dashboard UI
uv run insta-marketing serve

# 8. Run unit test suite
uv run pytest
```

---

## Configuration (`.env`)

```env
# LLM Gateway Configuration
LLM_API_BASE=https://api.manojmukherjee.co.in/v1
LLM_API_KEY=your_token_here
LLM_MODEL=llama3.2:latest

# Target Creator (Default)
CREATOR_HANDLE=iva_mana5
CREATOR_URL=https://www.instagram.com/iva_mana5

# Browser & Delay Settings
HEADLESS=false
SESSION_FILE=instagram_session.json
LOGIN_DELAY_SECONDS=5
```

---

## Output Files

- **Company Contacts & Leads**: `data/leads_<username>.json` (Company Name, Marketing Email, Mobile/Phone, Instagram, Ad Probability).
- **Editable Email Pitches**: `data/drafts/<username>/<Company_Name>_pitch.txt` (Contains email subject, body, Instagram DM, deliverables, and call to action).
- **Full Campaign Brief**: `data/campaign_<username>.json` (Media kit, creator rate card, and pitch packages).
