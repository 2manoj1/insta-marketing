"""
Command Line Interface for Instagram Influencer Marketing Manager.
A professional, interactive CLI wizard powered by Google ADK multi-agent architecture.
"""
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Optional
import typer
import uvicorn
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.prompt import Confirm, Prompt
from rich.table import Table

from src.agents.adk_system import adk_orchestrator
from src.agents.draft_manager import draft_manager
from src.agents.workflow_graph import marketing_graph
from src.browser.scraper import creator_scraper
from src.browser.session import session_manager
from src.config import settings

app = typer.Typer(
    name="insta-marketing",
    help="Professional Instagram Influencer Marketing Manager CLI (Google ADK & Playwright)",
    add_completion=False,
)
console = Console()


def print_pro_banner():
    banner = """
[bold cyan]╔══════════════════════════════════════════════════════════════════════════════╗[/bold cyan]
[bold cyan]║[/bold cyan]       [bold magenta]INSTAGRAM INFLUENCER MARKETING MANAGER (PRO MULTI-AGENT)[/bold magenta]        [bold cyan]║[/bold cyan]
[bold cyan]║[/bold cyan]    [dim]Powered by Google ADK Architecture, Playwright & Ollama LLM Gateway[/dim]       [bold cyan]║[/bold cyan]
[bold cyan]╚══════════════════════════════════════════════════════════════════════════════╝[/bold cyan]
"""
    console.print(banner)


@app.command()
def login(
    delay: int = typer.Option(5, "--delay", "-d", help="Initial buffer delay in seconds before checking login"),
    timeout: int = typer.Option(180, "--timeout", "-t", help="Timeout in seconds for human login completion"),
):
    """
    Launch human browser for marketing team to log into Instagram and save persistent session.
    """
    print_pro_banner()
    console.print(Panel(
        "[bold cyan]Instagram Human Authentication Mode[/bold cyan]\n"
        "1. A visible browser window will open at Instagram login.\n"
        f"2. A {delay}-second buffer allows initial page load.\n"
        "3. Complete your login manually (including 2FA/captchas).\n"
        "4. Storage state will be saved to reuse for all future agent tasks.",
        border_style="cyan"
    ))

    success = asyncio.run(session_manager.human_login_flow(delay_seconds=delay, timeout_seconds=timeout))
    if success:
        console.print("[bold green]✓ Session successfully authenticated and saved![/bold green]")
    else:
        console.print("[bold red]✗ Login was not completed or timed out.[/bold red]")
        sys.exit(1)


@app.command()
def run(
    handle: Optional[str] = typer.Option(None, "--handle", "-u", help="Target Instagram creator username or profile URL"),
    location: Optional[str] = typer.Option(None, "--location", "-l", help="Target geographic region for brand collaboration"),
    sample: bool = typer.Option(False, "--sample", "-s", help="Use realistic sample creator data for instant demonstration"),
    hitl: Optional[bool] = typer.Option(None, "--hitl/--no-hitl", help="Enable or disable interactive Human-in-the-Loop draft review"),
    port: int = typer.Option(8088, "--port", "-p", help="Dashboard port"),
):
    """
    Pro Interactive Wizard:
    1. Authenticates marketing team on Instagram FIRST (no scraping without login).
    2. Asks marketing team targeted questions on behalf of the creator.
    3. Runs the Google ADK Multi-Agent System.
    4. Extracts verified company emails & mobile numbers.
    5. Drafts customizable cold emails & Instagram DMs.
    """
    print_pro_banner()

    # -----------------------------------------------------------------------
    # Step 1: Mandatory Instagram Authentication Gate
    # -----------------------------------------------------------------------
    if not sample:
        console.print("[bold yellow]Step 1: Checking Marketing Team Instagram Authentication...[/bold yellow]")
        auth_ok = asyncio.run(session_manager.ensure_authenticated())
        if not auth_ok:
            console.print("[bold red]Aborting: Instagram login is required before creator scraping can proceed.[/bold red]")
            sys.exit(1)
        console.print("[bold green]✓ Marketing Team Session Confirmed.[/bold green]\n")

    # -----------------------------------------------------------------------
    # Step 2: Pro Interactive Wizard Questions
    # -----------------------------------------------------------------------
    console.print("[bold cyan]Step 2: Campaign & Creator Scope Configuration[/bold cyan]")

    target_handle = handle
    if not target_handle:
        default_handle = settings.creator_handle or "iva_mana5"
        target_handle = Prompt.ask(
            "  [bold white]1. Which creator account do you want to manage?[/bold white]",
            default=default_handle
        )

    clean_name = creator_scraper.clean_handle(target_handle)

    target_loc = location
    if not target_loc:
        target_loc = Prompt.ask(
            "  [bold white]2. Target location / market for brand sponsors?[/bold white]",
            default="Bangalore / India"
        )

    deal_choice = "All"
    if sys.stdin.isatty():
        console.print("  [bold white]3. Primary Brand Collaboration Focus:[/bold white]")
        console.print("     [1] UGC Video Ads (High-converting paid ad assets)")
        console.print("     [2] Sponsored Reels & Stories (Organic influencer feed)")
        console.print("     [3] Luxury Hospitality & Property Collabs (Resorts & stays)")
        console.print("     [4] All Formats (Recommended)")
        choice = Prompt.ask("     Select focus (1-4)", choices=["1", "2", "3", "4"], default="4")
        deal_map = {
            "1": "UGC Video Ads",
            "2": "Sponsored Reels & Stories",
            "3": "Hospitality & Property Collabs",
            "4": "All",
        }
        deal_choice = deal_map[choice]

    enable_hitl = hitl
    if enable_hitl is None:
        enable_hitl = Confirm.ask(
            "  [bold white]4. Enable Human-in-the-Loop (HITL) review to edit email drafts before finalizing?[/bold white]",
            default=False
        )

    console.print("\n" + "─" * 70)
    console.print(f"[bold magenta]Launching Google ADK Multi-Agent System for @{clean_name}...[/bold magenta]")
    console.print(f"• LLM Gateway: [cyan]{settings.llm_api_base}[/cyan] ({settings.llm_model})")
    console.print(f"• Target Region: [cyan]{target_loc}[/cyan] | Deal Focus: [cyan]{deal_choice}[/cyan]")
    console.print("─" * 70 + "\n")

    # -----------------------------------------------------------------------
    # Step 3: Run Google ADK Multi-Agent Workflow
    # -----------------------------------------------------------------------
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Executing multi-agent workflow...", total=100)

        def on_status(msg: str, pct: int):
            progress.update(task, completed=pct, description=f"[cyan]{msg} ({pct}%)...")

        # Execute agent workflow with enable_hitl=False inside the progress bar context
        # so the spinner cleanly closes before any user prompts occur
        state = asyncio.run(
            marketing_graph.execute(
                handle_or_url=target_handle,
                location=target_loc,
                interests=[deal_choice] if deal_choice != "All" else None,
                use_sample_data=sample,
                enable_hitl=False,
                status_callback=on_status,
            )
        )

    # -----------------------------------------------------------------------
    # Step 4: Human-in-the-Loop (HITL) Interactive Review (if requested)
    # -----------------------------------------------------------------------
    if enable_hitl and state.pitches:
        state.pitches = draft_manager.hitl_interactive_review(state.pitches)
        # Persist finalized drafts
        draft_manager.save_individual_drafts(clean_name, state.pitches)
        if state.summary:
            state.summary.pitches = state.pitches

    # -----------------------------------------------------------------------
    # Step 5: Next Steps & Dashboard Offer
    # -----------------------------------------------------------------------
    console.print("\n[bold green]═══ Next Steps for Marketing Team ═══[/bold green]")
    console.print(f"1. [bold]Brand Leads JSON:[/bold] View company names, emails & phone numbers in [cyan]{state.leads_file}[/cyan]")
    console.print(f"2. [bold]Send Pitches:[/bold] Open individual drafts in [cyan]{state.drafts_dir}[/cyan] and copy-paste directly into your email client!")

    if sys.stdin.isatty():
        launch_web = Confirm.ask(f"\nWould you like to open the Web Dashboard UI on port {port} to view and copy pitches visually?", default=False)
        if launch_web:
            uvicorn.run("src.server.app:app", host="127.0.0.1", port=port, reload=False)


@app.command()
def leads(
    handle: Optional[str] = typer.Argument(None, help="Creator handle to view saved leads for"),
):
    """
    Visualize saved brand leads, verified emails, and mobile numbers for a creator.
    """
    username = creator_scraper.clean_handle(handle or settings.creator_handle or "iva_mana5")
    leads_file = settings.data_dir / f"leads_{username}.json"

    if not leads_file.exists():
        console.print(f"[yellow]No leads file found at {leads_file}. Run 'run --handle {username}' first.[/yellow]")
        return

    with open(leads_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    table = Table(
        title=f"Verified Brand Contacts for @{username} (Instagram Advertisers)",
        show_lines=True,
        header_style="bold magenta",
    )
    table.add_column("#", style="dim", width=3)
    table.add_column("Company / Brand", style="bold cyan")
    table.add_column("Marketing Email", style="bold green")
    table.add_column("Mobile / Phone", style="yellow")
    table.add_column("Instagram Handle", style="magenta")
    table.add_column("Ad Probability & Fit", style="white")

    for item in data:
        table.add_row(
            str(item.get("id", "-")),
            f"{item.get('company_name')}\n[dim]{item.get('industry')}[/dim]",
            item.get("marketing_email", "N/A"),
            item.get("mobile_number") or item.get("phone_number") or "N/A",
            item.get("instagram_handle", "N/A"),
            f"{item.get('fit_synergy_score', '')}\n[dim]{item.get('ad_probability', '')}[/dim]",
        )

    console.print(table)
    console.print(f"[dim]Data source: {leads_file}[/dim]")


@app.command()
def drafts(
    handle: Optional[str] = typer.Argument(None, help="Creator handle to list drafts for"),
):
    """
    List and view ready-to-send email drafts for a creator.
    """
    username = creator_scraper.clean_handle(handle or settings.creator_handle or "iva_mana5")
    draft_dir = settings.data_dir / "drafts" / username

    if not draft_dir.exists() or not list(draft_dir.glob("*.txt")):
        console.print(f"[yellow]No drafts found in {draft_dir}. Run 'run --handle {username}' first.[/yellow]")
        return

    console.print(f"\n[bold green]Ready-to-Send Email Drafts for @{username}:[/bold green]")
    for p in draft_dir.glob("*.txt"):
        console.print(f"  • [cyan]{p.name}[/cyan] ([dim]{p}[/dim])")

    console.print(f"\n[dim]To send, simply open any file and copy into your email app.[/dim]")


@app.command()
def agents():
    """
    Inspect the active Google ADK Multi-Agent Manifest.
    """
    print_pro_banner()
    table = Table(title="Google ADK Multi-Agent Manifest", show_lines=True, header_style="bold purple")
    table.add_column("Agent Name", style="bold cyan")
    table.add_column("Role", style="bold green")
    table.add_column("Description", style="white")

    for a in adk_orchestrator.get_agent_manifest():
        table.add_row(a["name"], a["role"], a["description"])

@app.command(name="eval")
def evaluate(
    handle: Optional[str] = typer.Option(None, "--handle", "-u", help="Optional creator handle filter"),
):
    """
    Run the Investor & Enterprise Accuracy & Deliverability Benchmark Suite.
    Calculates email accuracy, phone validity, anti-spam score, and commercial ROI.
    """
    print_pro_banner()
    from src.evals.benchmark_runner import benchmark_runner
    report = benchmark_runner.run_benchmark(creator_handle=handle)
    benchmark_runner.print_scorecard(report)


@app.command()
def mcp():
    """
    Launch Model Context Protocol (MCP) JSON-RPC 2.0 stdio server.
    Enables Claude Desktop, Cursor, Antigravity, and AI agents to call tools.
    """
    from src.mcp.server import mcp_server
    asyncio.run(mcp_server.run_stdio())


@app.command()
def okf():
    """
    Inspect the Open Knowledge Framework (OKF) store:
    Verified advertiser brands, emails, phone numbers, and market benchmarks.
    """
    print_pro_banner()
    from src.storage.okf import okf_manager
    summary = okf_manager.get_summary()

    console.print(Panel(
        f"[bold cyan]Open Knowledge Framework (OKF) Intelligence Store[/bold cyan]\n"
        f"• Total Verified Brands in Knowledge Base: [bold green]{summary['total_brands_in_okf']}[/bold green]\n"
        f"• Total Direct Marketing Emails: [bold green]{summary['total_verified_emails']}[/bold green]\n"
        f"• Total Verified Mobile Numbers: [bold green]{summary['total_verified_phones']}[/bold green]\n"
        f"• Distinct Industries Covered: [bold green]{summary['industries_covered']}[/bold green]\n"
        f"• Storage Location: [dim]{summary['storage_path']}[/dim]",
        border_style="cyan"
    ))

    table = Table(title="Top Advertisers in OKF Knowledge Base", show_lines=True, header_style="bold magenta")
    table.add_column("Brand", style="bold cyan")
    table.add_column("Industry", style="white")
    table.add_column("Verified Email", style="green")
    table.add_column("Mobile / Phone", style="yellow")
    table.add_column("Ad Format & Probability", style="dim")

    for b in okf_manager.load_brands()[:10]:
        email = b.get("marketing_emails", ["N/A"])[0] if b.get("marketing_emails") else "N/A"
        phone = b.get("phone_numbers", ["N/A"])[0] if b.get("phone_numbers") else "N/A"
        table.add_row(
            b.get("brand_name", "Unknown"),
            b.get("industry", "General"),
            email,
            phone,
            f"{b.get('fit_score', 90)}% Fit\n{b.get('ad_probability', 'Active Ad Runner')}",
        )
    console.print(table)


@app.command()
def enrich(
    url: str = typer.Argument(..., help="Brand website or Linktree URL to deep-crawl"),
    subpages: int = typer.Option(3, "--subpages", "-s", help="Max subpages to explore"),
):
    """
    Deep crawl a brand website or Linktree URL for marketing emails and WhatsApp/phones.
    Uses free and open-source Playwright / BeautifulSoup4 with zero paid APIs.
    """
    print_pro_banner()
    console.print(f"[cyan]Deep crawling [bold]{url}[/bold] (exploring up to {subpages} subpages)...[/cyan]")
    from src.skills.deep_bio_link import deep_bio_link_skill

    res = asyncio.run(deep_bio_link_skill.crawl_brand_site(url, max_subpages=subpages))
    console.print(f"[green]✓ Crawl Complete![/green]")
    console.print(f"  • Pages Visited: {len(res['pages_crawled'])}")
    for p in res["pages_crawled"]:
        console.print(f"    - [dim]{p}[/dim]")

    console.print(f"  • Emails Discovered: [bold green]{', '.join(res['emails']) or 'None'}[/bold green]")
    console.print(f"  • Phones Discovered: [bold yellow]{', '.join(res['phones']) or 'None'}[/bold yellow]")


@app.command(name="verify-brand")
def verify_brand(
    handle: str = typer.Argument(..., help="Official brand Instagram handle or URL (e.g. '@snitch.co.in', '@thetamararesorts')"),
):
    """
    Scrape, verify, and extract contacts from an official brand Instagram page or PR profile.
    Extracts PR marketing emails, WhatsApp numbers, bio links, and ad probability.
    """
    print_pro_banner()
    from src.browser.scraper import creator_scraper
    brand_info = asyncio.run(creator_scraper.scrape_brand_page(handle))

    console.print(Panel(
        f"[bold cyan]Official Brand Verification Card: {brand_info['brand_name']}[/bold cyan]\n"
        f"• Instagram Handle: [bold magenta]{brand_info['handle']}[/bold magenta]\n"
        f"• Verified PR / Collab Email: [bold green]{brand_info['pr_email']}[/bold green]\n"
        f"• Direct Mobile / WhatsApp: [bold yellow]{brand_info['mobile_number']}[/bold yellow]\n"
        f"• Industry & Niche: [white]{brand_info['industry']}[/white]\n"
        f"• Official Website: [cyan]{brand_info['website']}[/cyan]\n"
        f"• Bio Link: [dim]{brand_info['bio_link']}[/dim]\n"
        f"• Ad Probability: [bold green]{brand_info['ad_probability']}[/bold green]\n"
        f"• Verification Source: [dim]{brand_info['source']}[/dim]",
        border_style="cyan"
    ))


@app.command()
def reset(
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
):
    """
    Reset all data: SQLite DB, OKF intelligence, leads JSON, campaign files, and drafts.
    Only verified brands discovered by agents will be re-added on next run.
    """
    print_pro_banner()
    from scripts.reset_db import reset_all as do_reset
    do_reset(confirm=not yes)


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Server host"),
    port: int = typer.Option(8088, "--port", "-p", help="Server port"),
):
    """
    Launch the browser-based Web Dashboard UI & Automation Server on port 8088.
    """
    print_pro_banner()
    console.print(Panel(
        f"[bold green]Starting Instagram Marketing Manager Server...[/bold green]\n"
        f"Dashboard available at: [bold cyan]http://{host}:{port}[/bold cyan]\n"
        f"[dim]Features: Visual Login Gate, Live Multi-Agent Execution, 1-Click Pitch Copy[/dim]",
        border_style="green"
    ))
    uvicorn.run("src.server.app:app", host=host, port=port, reload=True)


if __name__ == "__main__":
    app()

