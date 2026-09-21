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
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.agents.workflow_graph import marketing_graph
from src.agents.draft_manager import draft_manager
from src.agents.deep.director import deep_director
from src.browser.session import session_manager
from src.browser.brand_scraper import instagram_brand_scraper
from src.config import settings
from src.evals.benchmark_runner import benchmark_runner
from src.mcp.server import mcp_server, MCP_TOOLS_MANIFEST
from src.models.outreach import CampaignSummary
from src.search.confidence import calculate_lead_confidence
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
    deal_preference: str = "All"
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


class FlagLeadRequest(BaseModel):
    is_test: bool = True
    reason: str = "Test / Mock Company"


@app.get("/api/leads")
async def get_saved_leads(
    creator: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 100,
    verified_only: bool = False,
    exclude_flagged: bool = False,
):
    """
    Directly queries SQLite database for saved brand leads, verified emails,
    and phone numbers without running any agents.
    """
    leads = db_manager.get_all_leads(
        creator_username=creator,
        search=search,
        limit=limit,
        verified_only=verified_only,
        exclude_flagged=exclude_flagged,
    )
    return {
        "count": len(leads),
        "leads": leads,
    }


@app.delete("/api/leads/{lead_id}")
async def delete_lead_endpoint(lead_id: int):
    """
    1-click delete endpoint: Permanently removes a lead from SQLite and clears it from OKF memory.
    """
    company_name = db_manager.delete_lead(lead_id)
    if not company_name:
        raise HTTPException(status_code=404, detail=f"Lead with id {lead_id} not found")
    
    # Also remove from OKF memory store if present
    okf_manager.remove_brand(company_name)

    return {
        "status": "deleted",
        "message": f"Lead '{company_name}' removed permanently.",
        "id": lead_id,
        "company_name": company_name,
    }


@app.post("/api/leads/{lead_id}/flag")
async def flag_lead_endpoint(lead_id: int, req: FlagLeadRequest):
    """
    Flags a lead if it is a test company, mock, or has improper details from web/crawlers.
    If flagged as test, automatically purges it from OKF memory.
    """
    success = db_manager.flag_lead(lead_id=lead_id, reason=req.reason, is_test=req.is_test)
    if not success:
        raise HTTPException(status_code=404, detail=f"Lead with id {lead_id} not found")

    if req.is_test:
        # Find company name to purge from OKF memory
        leads = db_manager.get_all_leads(limit=1000)
        for l in leads:
            if l.get("id") == lead_id:
                okf_manager.remove_brand(l.get("company_name", ""))
                break

    return {
        "status": "flagged",
        "message": f"Lead {lead_id} flagged: {req.reason}",
        "id": lead_id,
        "is_test": req.is_test,
        "reason": req.reason,
    }


@app.post("/api/leads/{lead_id}/unflag")
async def unflag_lead_endpoint(lead_id: int):
    """Clears any flag on a lead."""
    success = db_manager.unflag_lead(lead_id=lead_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Lead with id {lead_id} not found")
    return {
        "status": "unflagged",
        "message": f"Flag removed from lead {lead_id}",
        "id": lead_id,
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


class DraftUpdateRequest(BaseModel):
    filename: str
    full_content: str
    creator: Optional[str] = None


@app.post("/api/drafts/update")
async def update_draft(req: DraftUpdateRequest):
    """
    Human-in-the-loop (HITL) endpoint: Updates an existing pitch draft file on disk.
    Allows marketing teams to customize and approve pitch copy directly in the UI.
    """
    success = draft_manager.update_draft_file(
        filename=req.filename,
        full_content=req.full_content,
        creator_username=req.creator,
    )
    if not success:
        raise HTTPException(status_code=404, detail="Draft file not found on disk")
    return {
        "status": "success",
        "message": f"Draft '{req.filename}' updated successfully on disk",
        "filename": req.filename,
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


@app.delete("/api/okf/brand/{brand_name}")
async def delete_okf_brand(brand_name: str):
    """
    1-click remove brand from OKF store (e.g. if flagged as junk or test).
    """
    success = okf_manager.remove_brand(brand_name)
    return {
        "status": "success" if success else "not_found",
        "brand_name": brand_name,
        "removed": success,
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
    exclude_brands: Optional[List[str]] = None
    auto_save: bool = True
    creator_handle: Optional[str] = None


class BatchSaveLeadsRequest(BaseModel):
    creator: Optional[str] = None
    brands: List[Dict[str, Any]]


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
    If auto_save is True, automatically records them to SQLite database and OKF memory.
    """
    from src.search.brand_finder import brand_finder
    exclude_set = set(req.exclude_brands or [])
    creator = req.creator_handle or settings.creator_handle or "pilot_creator"
    existing = db_manager.get_contacted_brand_names(creator)
    exclude_set.update(existing)

    brands = await brand_finder.search_live_web_brands(
        niche=req.niche,
        location=req.location,
        limit=req.limit,
        exclude_brands=exclude_set,
    )
    for b in brands:
        b.contact.confidence_score = calculate_lead_confidence(b)

    saved_count = 0
    if req.auto_save and brands:
        saved_count = db_manager.save_leads(creator, brands)
        for b in brands:
            try:
                okf_manager.save_brand_intelligence(b)
            except Exception:
                pass

    return {
        "status": "success",
        "niche": req.niche,
        "location": req.location,
        "count": len(brands),
        "saved_count": saved_count,
        "brands": [b.model_dump() for b in brands],
    }


@app.post("/api/leads/batch_save")
async def batch_save_leads_endpoint(req: BatchSaveLeadsRequest):
    """
    1-click save one or more discovered brand candidates into SQLite verified leads.
    """
    creator = req.creator or settings.creator_handle or "pilot_creator"
    opps = []
    for b_dict in req.brands:
        contact_dict = b_dict.get("contact", {})
        contact = BrandContact(**contact_dict)
        contact.confidence_score = calculate_lead_confidence(contact)
        opp = BrandOpportunity(
            brand_name=b_dict.get("brand_name", "Unknown"),
            website=b_dict.get("website", ""),
            industry=b_dict.get("industry", "Lifestyle"),
            location=b_dict.get("location", "India"),
            fit_score=b_dict.get("fit_score", 85),
            ad_probability=b_dict.get("ad_probability", "High"),
            collab_type=b_dict.get("collab_type", "UGC Video & Sponsored Reel"),
            suggested_angle=b_dict.get("suggested_angle", ""),
            contact=contact,
        )
        opps.append(opp)
        try:
            okf_manager.save_brand_intelligence(opp)
        except Exception:
            pass

    inserted = db_manager.save_leads(creator, opps)
    return {
        "status": "success",
        "inserted": inserted,
        "message": f"Successfully saved {inserted} leads to verified directory.",
    }


class ImportSessionRequest(BaseModel):
    session_token: Optional[str] = None
    cookies: Optional[Any] = None


class CdpSyncRequest(BaseModel):
    cdp_url: str = "http://127.0.0.1:9222"


class ScrapeBrandInstagramRequest(BaseModel):
    handle: str
    lead_id: Optional[int] = None


@app.post("/api/session/import")
async def import_session_endpoint(req: ImportSessionRequest):
    """
    Imports Instagram session token or cookies from Google Chrome.
    Accepts raw sessionid string, cookie header string, or Cookie-Editor JSON export.
    """
    payload = req.session_token or req.cookies
    if not payload:
        raise HTTPException(status_code=400, detail="Missing session_token or cookies payload.")

    try:
        res = session_manager.import_session_token(payload)
        return {
            "status": "success",
            "message": "Instagram session successfully imported and verified!",
            "details": res,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to import session: {str(e)}")


@app.post("/api/session/sync_cdp")
async def sync_cdp_endpoint(req: CdpSyncRequest):
    """
    Directly connects to a running Google Chrome instance via CDP to sync active Instagram session.
    """
    res = await session_manager.connect_and_sync_cdp(cdp_url=req.cdp_url)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error", "CDP connection failed"))
    return res


@app.post("/api/brand/scrape_instagram")
async def scrape_brand_instagram_endpoint(req: ScrapeBrandInstagramRequest):
    """
    Authenticated Instagram mobile action scraper.
    Extracts direct Business profile buttons ('Contact', 'Email', 'Call', 'WhatsApp').
    """
    res = await instagram_brand_scraper.scrape_brand_profile(req.handle)
    if req.lead_id and res.get("success"):
        # Auto-update SQLite lead record if ID provided
        db_manager.update_lead_contact(
            lead_id=req.lead_id,
            email=res.get("contact_email"),
            phone=res.get("phone_number"),
            confidence_score=res.get("confidence_score"),
            source=res.get("source"),
        )
    return res


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
            deal_preference=req.deal_preference,
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
            deal_preference=req.deal_preference,
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


@app.post("/api/reset")
async def reset_all_data():
    """
    Resets all data stores: SQLite DB, OKF intelligence, leads, drafts, campaigns.
    Use with caution — this is irreversible.
    """
    import shutil
    summary = {"deleted": []}

    # Reset SQLite DB
    db_path = settings.data_dir / "leads.db"
    if db_path.exists():
        db_path.unlink()
        summary["deleted"].append("leads.db")
    db_manager._init_db()

    # Reset OKF
    okf_manager.reset()
    summary["deleted"].append("okf/")

    # Clear leads JSON files
    for f in settings.data_dir.glob("leads_*.json"):
        f.unlink()
        summary["deleted"].append(f.name)

    # Clear campaign files
    for f in settings.data_dir.glob("campaign_*.json"):
        f.unlink()
        summary["deleted"].append(f.name)

    # Clear drafts
    drafts_dir = settings.data_dir / "drafts"
    if drafts_dir.exists():
        shutil.rmtree(drafts_dir)
        drafts_dir.mkdir(parents=True, exist_ok=True)
        summary["deleted"].append("drafts/")

    # Clear eval report
    eval_path = settings.data_dir / "eval_benchmark_report.json"
    if eval_path.exists():
        eval_path.unlink()
        summary["deleted"].append("eval_benchmark_report.json")

    return {
        "status": "reset_complete",
        "items_deleted": len(summary["deleted"]),
        "details": summary["deleted"],
    }


@app.get("/api/leads/export")
async def export_leads_csv(creator: Optional[str] = None):
    """
    Exports all leads as a downloadable CSV file.
    """
    import csv
    import io

    leads = db_manager.get_all_leads(creator_username=creator, limit=10000)
    output = io.StringIO()
    if leads:
        writer = csv.DictWriter(output, fieldnames=leads[0].keys())
        writer.writeheader()
        writer.writerows(leads)
    else:
        output.write("company_name,marketing_email,mobile_number,instagram_handle,website,industry,fit_score,ad_probability,source\n")

    output.seek(0)
    filename = f"leads_{creator or 'all'}_{datetime.now().strftime('%Y%m%d')}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


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
