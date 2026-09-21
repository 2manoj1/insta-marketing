"""
FastAPI Server and Web UI Dashboard for Instagram Influencer Marketing Manager.
"""
import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.agents.workflow_graph import marketing_graph
from src.agents.draft_manager import draft_manager
from src.agents.deep.director import deep_director
from src.browser.session import session_manager
from src.config import settings
from src.evals.benchmark_runner import benchmark_runner
from src.mcp.server import mcp_server, MCP_TOOLS_MANIFEST
from src.models.outreach import CampaignSummary
from src.skills.deep_bio_link import deep_bio_link_skill
from src.storage.db import db_manager
from src.storage.okf import okf_manager

app = FastAPI(
    title="Instagram Influencer Marketing Manager API",
    description="Multi-agent automation system for Instagram creator brand outreach and UGC monetization",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)


class RunRequest(BaseModel):
    handle_or_url: str
    location: str = "Global"
    interests: Optional[List[str]] = None
    use_sample: bool = False


# In-memory execution cache for live UI polling
active_jobs: Dict[str, Dict[str, Any]] = {}


@app.get("/healthz")
async def health_check():
    """Production healthcheck probe for Docker/Kubernetes container monitoring."""
    return {
        "status": "healthy",
        "service": "insta-marketing-engine",
        "auth_ready": session_manager.has_saved_session(),
    }


@app.get("/api/evals/latest")
async def get_latest_benchmark(creator: Optional[str] = None):
    """
    Returns the latest accuracy and investor ROI benchmark report.
    Generates report on the fly if not yet cached.
    """
    if benchmark_runner.report_path.exists():
        try:
            with open(benchmark_runner.report_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return benchmark_runner.run_benchmark(creator_handle=creator)


@app.post("/api/evals/run")
async def execute_fresh_benchmark(creator: Optional[str] = None):
    """
    Executes a fresh quantitative benchmark across all leads and drafts.
    """
    return benchmark_runner.run_benchmark(creator_handle=creator)


@app.get("/api/status")
async def get_system_status():
    return {
        "instagram_authenticated": session_manager.has_saved_session(),
        "session_file": str(session_manager.session_path),
        "llm_api_base": settings.llm_api_base,
        "llm_model": settings.llm_model,
        "default_creator_handle": settings.creator_handle or None,
        "default_creator_url": settings.creator_url or None,
    }


@app.get("/api/stats")
async def get_database_stats():
    """
    Returns database lead, brand, and creator counts directly from SQLite
    without needing to run any agent workflow.
    """
    return db_manager.get_stats()


@app.get("/api/creators")
async def get_database_creators():
    """
    Returns all distinct creators recorded in the database and their lead counts.
    """
    return db_manager.get_creators()


@app.get("/api/leads")
async def get_saved_leads(
    creator: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 100,
):
    """
    Directly queries SQLite database for saved brand leads, verified emails,
    and phone numbers without running any agents.
    """
    leads = db_manager.get_all_leads(creator_username=creator, search=search, limit=limit)
    return {
        "count": len(leads),
        "leads": leads,
    }


@app.get("/api/drafts")
async def get_saved_drafts(creator: Optional[str] = None):
    """
    Returns ready-to-send cold email and Instagram DM draft pitch files saved on disk.
    """
    drafts = draft_manager.get_all_drafts(creator_username=creator)
    return {
        "count": len(drafts),
        "drafts": drafts,
    }


@app.get("/api/okf")
async def get_okf_data():
    """
    Returns Open Knowledge Framework (OKF) store data:
    Accumulated brand intelligence, verified contacts, and market benchmarks.
    """
    return {
        "summary": okf_manager.get_summary(),
        "brands": okf_manager.load_brands(),
        "benchmarks": okf_manager.get_benchmarks(),
    }


@app.get("/api/skills")
async def list_modular_skills():
    """
    Returns the registry of active open-source agent skills.
    """
    return {
        "count": 6,
        "skills": [
            {
                "name": "stealth_scraper",
                "title": "Playwright Stealth Scraper",
                "description": "Scrapes public Instagram creator metrics with human Gaussian delay, mouse wandering, and rate limits.",
                "type": "browser_automation",
                "open_source": True,
            },
            {
                "name": "deep_bio_link_scraper",
                "title": "Deep Bio-Link & Website Crawler",
                "description": "Traverses brand websites, Linktree, and contact/collab pages using BeautifulSoup4 & httpx to extract emails and WhatsApp numbers.",
                "type": "web_crawling",
                "open_source": True,
            },
            {
                "name": "contact_verifier",
                "title": "Contact Deliverability Verifier",
                "description": "Validates RFC 5322 email syntax, MX viability, role classification, and E.164 telephone standardization.",
                "type": "verification",
                "open_source": True,
            },
            {
                "name": "negotiation_pricing",
                "title": "Negotiation & Commercial Rate Pricing",
                "description": "Calculates commercial rate cards for UGC video ad usage rights and sponsored reels based on creator tiers.",
                "type": "pricing",
                "open_source": True,
            },
            {
                "name": "pitch_sequencing",
                "title": "3-Channel Pitch Sequencer",
                "description": "Generates synchronized multi-touchpoint pitches: Cold Email, Instagram DM, and professional WhatsApp outreach.",
                "type": "copywriting",
                "open_source": True,
            },
            {
                "name": "okf_memory",
                "title": "Open Knowledge Framework Memory",
                "description": "Persistent memory and learning loop across campaigns for verified advertiser intelligence.",
                "type": "memory_knowledge",
                "open_source": True,
            },
        ],
    }


@app.post("/api/mcp")
async def mcp_jsonrpc_endpoint(request: Dict[str, Any]):
    """
    Model Context Protocol (MCP) JSON-RPC 2.0 endpoint for external AI agents,
    Claude, Cursor, Antigravity, and SaaS client integrations.
    """
    return await mcp_server.handle_jsonrpc_request(request)


class EnrichRequest(BaseModel):
    url: str
    subpages: int = 3


class LiveSearchRequest(BaseModel):
    niche: str
    location: str = "India"
    limit: int = 5


@app.post("/api/enrich")
async def enrich_brand_url(req: EnrichRequest):
    """
    Directly deep-crawls a brand website or Linktree URL to extract emails & phones.
    """
    return await deep_bio_link_skill.crawl_brand_site(req.url, max_subpages=req.subpages)


@app.post("/api/search/live")
async def search_live_brands(req: LiveSearchRequest):
    """
    Live open-source WWW search (DuckDuckGo + DeepBioLink) for active brands & contacts.
    Returns real-time discovered brands with verified marketing emails & phone numbers.
    """
    from src.search.brand_finder import brand_finder
    brands = await brand_finder.search_live_web_brands(
        niche=req.niche,
        location=req.location,
        limit=req.limit,
    )
    return {
        "status": "success",
        "niche": req.niche,
        "location": req.location,
        "count": len(brands),
        "brands": [b.model_dump() for b in brands],
    }


@app.post("/api/login")
async def trigger_human_login(background_tasks: BackgroundTasks):
    """
    Triggers the human browser login flow in the background.
    """
    async def _do_login():
        await session_manager.human_login_flow(delay_seconds=settings.login_delay_seconds)

    background_tasks.add_task(_do_login)
    return {
        "status": "launched",
        "message": f"Browser launched with {settings.login_delay_seconds}s initial delay. Please complete login in the opened browser window."
    }


async def _execute_job(job_id: str, req: RunRequest):
    handle = req.handle_or_url.strip() or settings.creator_handle or "iva_mana5"
    job = active_jobs[job_id]

    def _status_cb(msg: str, pct: int):
        job["progress_pct"] = pct
        job["progress_text"] = msg
        job["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg} ({pct}%)")

    try:
        state = await marketing_graph.execute(
            handle_or_url=handle,
            location=req.location,
            interests=req.interests,
            use_sample_data=req.use_sample,
            enable_hitl=False,
            status_callback=_status_cb,
        )

        job["status"] = "completed"
        job["progress_pct"] = 100
        job["progress_text"] = "Workflow Completed Successfully!"
        job["result"] = {
            "creator": state.profile.model_dump() if state.profile else None,
            "brands": [b.model_dump() for b in state.brands],
            "pitches": [p.model_dump() for p in state.pitches],
            "summary": state.summary.model_dump() if state.summary else None,
            "logs": state.logs,
        }
    except asyncio.CancelledError:
        job["status"] = "stopped"
        job["progress_text"] = "Workflow cancelled by user."
        job["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] 🛑 Workflow stopped by user.")
    except Exception as e:
        job["status"] = "failed"
        job["progress_text"] = f"Workflow failed: {str(e)}"
        job["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] ❌ Error: {str(e)}")


@app.post("/api/run")
async def start_pipeline(req: RunRequest):
    """
    Spawns the multi-agent marketing manager workflow as an interruptible background job.
    """
    job_id = f"job_{uuid.uuid4().hex[:8]}"
    active_jobs[job_id] = {
        "job_id": job_id,
        "status": "running",
        "progress_pct": 5,
        "progress_text": "Initializing agent graph...",
        "logs": [f"[{datetime.now().strftime('%H:%M:%S')}] Initializing multi-agent workflow..."],
        "result": None,
        "task": None,
    }

    task = asyncio.create_task(_execute_job(job_id, req))
    active_jobs[job_id]["task"] = task

    return {
        "status": "running",
        "job_id": job_id,
    }


@app.post("/api/stop/{job_id}")
async def stop_pipeline(job_id: str):
    """
    Stops and cancels a running marketing workflow immediately.
    """
    job = active_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.get("status") == "running":
        task: Optional[asyncio.Task] = job.get("task")
        if task and not task.done():
            task.cancel()
        job["status"] = "stopped"
        job["progress_text"] = "Workflow stopped by user."
        job["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] 🛑 Workflow stopped by user.")

    return {
        "status": "stopped",
        "message": "Workflow execution stopped successfully.",
        "job_id": job_id,
    }


@app.get("/api/job/{job_id}")
async def get_job_status(job_id: str):
    """
    Polls status, progress, logs, and results for a running or completed workflow job.
    """
    job = active_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return {
        "job_id": job_id,
        "status": job.get("status"),
        "progress_pct": job.get("progress_pct", 0),
        "progress_text": job.get("progress_text", ""),
        "logs": job.get("logs", []),
        "result": job.get("result"),
    }


@app.post("/api/run_sync")
async def run_pipeline_sync(req: RunRequest):
    """
    Executes the workflow synchronously (useful for automated integration tests).
    """
    handle = req.handle_or_url.strip() or settings.creator_handle or "alex_tech_creator"
    try:
        state = await marketing_graph.execute(
            handle_or_url=handle,
            location=req.location,
            interests=req.interests,
            use_sample_data=req.use_sample,
            enable_hitl=False,
        )
        return {
            "status": "completed",
            "creator": state.profile.model_dump() if state.profile else None,
            "brands": [b.model_dump() for b in state.brands],
            "pitches": [p.model_dump() for p in state.pitches],
            "summary": state.summary.model_dump() if state.summary else None,
            "logs": state.logs,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/campaigns")
async def list_campaigns():
    """Returns saved campaign JSON summaries from disk."""
    campaigns = []
    for p in settings.data_dir.glob("campaign_*.json"):
        try:
            with open(p, "r", encoding="utf-8") as f:
                campaigns.append(json.load(f))
        except Exception:
            pass
    return campaigns


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return HTMLResponse(content=index_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Instagram Marketing Manager API running. static/index.html not found.</h1>")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
