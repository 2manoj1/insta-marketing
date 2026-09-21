"""
Instagram session manager handling human login flow, 5s delay, and persistent cookies.
Enforces that the marketing team logs in first before any scraping is allowed.
"""
import asyncio
import json
import logging
from pathlib import Path
from typing import Optional, Tuple
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

from src.config import settings

logger = logging.getLogger(__name__)
console = Console()


class InstagramSessionManager:
    """
    Manages Playwright browser instance, human login flow with delay,
    and storage state persistence.
    """

    def __init__(self, session_path: Optional[str] = None):
        self.session_path = Path(session_path or settings.session_file)

    def has_saved_session(self) -> bool:
        """Checks if a saved storage state file exists and has valid Instagram cookies."""
        if not self.session_path.exists():
            return False
        try:
            with open(self.session_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                cookies = data.get("cookies", [])
                return any(c.get("name") in ["sessionid", "ds_user_id"] for c in cookies)
        except Exception:
            return False

    async def launch_authenticated_browser(
        self,
        playwright: Playwright,
        headless: Optional[bool] = None,
    ) -> Tuple[Browser, BrowserContext]:
        """
        Launches browser reusing saved session state if available.
        """
        is_headless = settings.headless if headless is None else headless

        browser = await playwright.chromium.launch(
            headless=is_headless,
            args=[
                "--single-process",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--no-crashpad",
                "--disable-crash-reporter",
                "--disable-breakpad",
                "--disable-blink-features=AutomationControlled",
            ],
        )

        storage_state = str(self.session_path) if self.has_saved_session() else None

        context = await browser.new_context(
            storage_state=storage_state,
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/128.0.0.0 Safari/537.36"
            ),
        )
        return browser, context

    async def ensure_authenticated(self, force_relogin: bool = False) -> bool:
        """
        Guarantees that the marketing team is logged into Instagram BEFORE any scraping.
        If not logged in, launches browser with 5s delay and waits for human login.
        """
        if not force_relogin and self.has_saved_session():
            console.print("[green]✓ Instagram marketing session is authenticated and active.[/green]")
            return True

        console.print(Panel(
            "[bold yellow]⚠️  Instagram Marketing Authentication Gate  ⚠️[/bold yellow]\n"
            "Instagram strictly blocks automated requests. To protect the scraping pipeline,\n"
            "[bold white]the marketing team must log into Instagram first.[/bold white]\n\n"
            f"1. A visible browser window will open at Instagram Login.\n"
            f"2. A {settings.login_delay_seconds}-second buffer gives the page time to load.\n"
            "3. Enter your marketing credentials (and 2FA if required).\n"
            "4. Your session will be securely saved to reuse for all future searches.",
            border_style="yellow",
        ))

        Prompt.ask("[bold cyan]Press [Enter] to launch the browser and complete Instagram login[/bold cyan]", default="")
        success = await self.human_login_flow(delay_seconds=settings.login_delay_seconds)
        if not success:
            console.print("[bold red]Authentication failed or was cancelled. Cannot proceed with scraping.[/bold red]")
            return False
        return True

    async def human_login_flow(
        self,
        delay_seconds: Optional[int] = None,
        timeout_seconds: int = 180,
    ) -> bool:
        """
        Opens a visible browser for human login:
        1. Navigates to Instagram login page.
        2. Waits initial 5-second buffer as requested.
        3. Allows human to enter credentials / solve 2FA.
        4. Detects when login is complete and saves storage state.
        """
        delay = settings.login_delay_seconds if delay_seconds is None else delay_seconds

        console.print(f"[bold cyan]Launching browser for Human Instagram Login...[/bold cyan]")
        console.print(f"[yellow]Holding {delay}-second initial buffer for network settling...[/yellow]")

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=False,
                args=[
                    "--single-process",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--no-crashpad",
                    "--disable-crash-reporter",
                    "--disable-breakpad",
                    "--disable-blink-features=AutomationControlled",
                ],
            )

            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/128.0.0.0 Safari/537.36"
                ),
            )

            page = await context.new_page()

            console.print("[cyan]Navigating to https://www.instagram.com/accounts/login/ ...[/cyan]")
            try:
                await page.goto("https://www.instagram.com/accounts/login/", timeout=60000)
            except Exception as e:
                console.print(f"[yellow]Navigation notice: {e}[/yellow]")

            # 5-second human buffer
            await asyncio.sleep(delay)

            console.print("[bold green]>>> Please log in to Instagram in the opened browser window. <<<[/bold green]")
            console.print("[dim]Monitoring login status (session cookies or feed redirect)...[/dim]")

            # Polling loop
            logged_in = False
            elapsed = 0
            poll_interval = 2

            while elapsed < timeout_seconds:
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval

                try:
                    cookies = await context.cookies()
                    has_session_cookie = any(c.get("name") in ["sessionid", "ds_user_id"] for c in cookies)

                    current_url = page.url
                    is_on_feed = "accounts/login" not in current_url and ("instagram.com" in current_url)

                    if has_session_cookie and is_on_feed:
                        await asyncio.sleep(2)
                        logged_in = True
                        break
                except Exception as e:
                    # User closed the browser window or navigated away
                    logger.debug(f"Login polling interrupted (browser closed): {e}")
                    break

            if logged_in:
                console.print("[bold green]✓ Login verified successfully![/bold green]")
                await context.storage_state(path=str(self.session_path))
                console.print(f"[green]✓ Session securely saved to [bold]{self.session_path}[/bold]. Future tasks will not need login.[/green]")
            else:
                console.print("[bold red]Login timed out or window was closed.[/bold red]")

            try:
                await browser.close()
            except Exception:
                pass
            return logged_in


session_manager = InstagramSessionManager()
