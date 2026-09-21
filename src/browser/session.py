"""
Instagram session manager handling human login flow, 5s delay, and persistent cookies.
Enforces that the marketing team logs in first before any scraping is allowed.
Supports:
1. Persistent disk context (preserves cookies, IndexedDB, and tokens across runs).
2. Continuous real-time token sniffing (persists session the instant sessionid arrives).
3. 1-Click Chrome session importer (paste sessionid or cookie JSON).
4. Running Chrome CDP sync (connect_over_cdp).
"""
import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

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
        self.browser_profile_dir = settings.data_dir / "browser_profile"
        self.browser_profile_dir.mkdir(parents=True, exist_ok=True)

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

    def import_session_token(self, token_or_cookies: Union[str, List[Dict[str, Any]], Dict[str, Any]]) -> Dict[str, Any]:
        """
        Imports Instagram session from Chrome:
        - Raw sessionid string (e.g. '68123456789%3A...')
        - Cookie header string (e.g. 'sessionid=xxx; ds_user_id=yyy')
        - Cookie-Editor / DevTools JSON export list
        - Playwright storage_state dict

        Normalizes and writes standard Playwright storage_state to session_path.
        """
        parsed_cookies: List[Dict[str, Any]] = []

        # Case 1: JSON dict with "cookies"
        if isinstance(token_or_cookies, dict) and "cookies" in token_or_cookies:
            raw_list = token_or_cookies.get("cookies", [])
            for c in raw_list:
                if isinstance(c, dict) and c.get("name") and c.get("value"):
                    parsed_cookies.append(self._normalize_cookie(c["name"], c["value"], c.get("domain")))

        # Case 2: List of cookie dicts (Cookie-Editor format)
        elif isinstance(token_or_cookies, list):
            for c in token_or_cookies:
                if isinstance(c, dict) and c.get("name") and c.get("value"):
                    parsed_cookies.append(self._normalize_cookie(c["name"], c["value"], c.get("domain")))

        # Case 3: String input (could be JSON string, cookie header, or raw sessionid)
        elif isinstance(token_or_cookies, str):
            raw_str = token_or_cookies.strip()
            # Try JSON first
            is_json = False
            if (raw_str.startswith("{") and raw_str.endswith("}")) or (raw_str.startswith("[") and raw_str.endswith("]")):
                try:
                    loaded = json.loads(raw_str)
                    return self.import_session_token(loaded)
                except Exception:
                    pass

            # Cookie header format: key=value; key2=val2
            if "=" in raw_str:
                pairs = raw_str.split(";")
                for pair in pairs:
                    if "=" in pair:
                        k, v = pair.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip('"')
                        if k and v:
                            parsed_cookies.append(self._normalize_cookie(k, v))
            else:
                # Raw sessionid string
                session_val = raw_str.strip('"').strip("'")
                parsed_cookies.append(self._normalize_cookie("sessionid", session_val))

        # Check for ds_user_id derivation from sessionid if missing
        has_sessionid = any(c["name"] == "sessionid" for c in parsed_cookies)
        has_user_id = any(c["name"] == "ds_user_id" for c in parsed_cookies)
        if has_sessionid and not has_user_id:
            for c in parsed_cookies:
                if c["name"] == "sessionid":
                    val = c["value"]
                    # Instagram session IDs usually start with <user_id>%3A or <user_id>:
                    m = re.match(r"^(\d+)(?:%3A|:)", val)
                    if m:
                        user_id = m.group(1)
                        parsed_cookies.append(self._normalize_cookie("ds_user_id", user_id))
                    break

        if not parsed_cookies:
            raise ValueError("No valid Instagram cookies found in input.")

        # Ensure csrf token placeholder if missing
        if not any(c["name"] == "csrftoken" for c in parsed_cookies):
            parsed_cookies.append(self._normalize_cookie("csrftoken", "token_placeholder"))

        storage_data = {
            "cookies": parsed_cookies,
            "origins": []
        }

        self.session_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.session_path, "w", encoding="utf-8") as f:
            json.dump(storage_data, f, indent=2)

        return {
            "success": True,
            "cookies_count": len(parsed_cookies),
            "has_sessionid": has_sessionid,
            "session_file": str(self.session_path),
            "cookies_imported": [c["name"] for c in parsed_cookies],
        }

    def _normalize_cookie(self, name: str, value: str, domain: Optional[str] = None) -> Dict[str, Any]:
        """Creates a standardized Playwright cookie object for Instagram."""
        clean_domain = domain if (domain and "instagram.com" in domain) else ".instagram.com"
        return {
            "name": name.strip(),
            "value": value.strip(),
            "domain": clean_domain,
            "path": "/",
            "expires": -1,
            "httpOnly": name in ["sessionid", "rur", "shbid"],
            "secure": True,
            "sameSite": "Lax",
        }

    async def connect_and_sync_cdp(self, cdp_url: str = "http://127.0.0.1:9222") -> Dict[str, Any]:
        """
        Attaches to a running Google Chrome instance via Chrome DevTools Protocol (CDP)
        to extract active Instagram session cookies directly.
        """
        async with async_playwright() as p:
            try:
                browser = await p.chromium.connect_over_cdp(cdp_url, timeout=5000)
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Could not connect to Chrome on {cdp_url}. Ensure Chrome is launched with --remote-debugging-port=9222. ({e})"
                }

            try:
                all_cookies = []
                for context in browser.contexts:
                    cookies = await context.cookies(["https://www.instagram.com"])
                    all_cookies.extend(cookies)

                ig_cookies = [c for c in all_cookies if "instagram.com" in c.get("domain", "")]
                if not ig_cookies:
                    return {
                        "success": False,
                        "error": "Connected to Chrome, but no active Instagram cookies were found. Please log into Instagram in that Chrome window first."
                    }

                res = self.import_session_token(ig_cookies)
                return {
                    "success": True,
                    "message": f"Successfully extracted {len(ig_cookies)} Instagram cookies from running Chrome!",
                    "details": res,
                }
            finally:
                try:
                    await browser.close()
                except Exception:
                    pass

    async def launch_authenticated_browser(
        self,
        playwright: Playwright,
        headless: Optional[bool] = None,
        mobile: bool = False,
    ) -> Tuple[Browser, BrowserContext]:
        """
        Launches browser reusing persistent user profile directory and saved storage state.
        Supports desktop or mobile viewport emulation.
        """
        is_headless = settings.headless if headless is None else headless

        viewport = {"width": 390, "height": 844} if mobile else {"width": 1280, "height": 800}
        user_agent = (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 Instagram 330.0.0.15.110"
            if mobile else
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        )

        context = await playwright.chromium.launch_persistent_context(
            user_data_dir=str(self.browser_profile_dir),
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
            viewport=viewport,
            user_agent=user_agent,
            is_mobile=mobile,
            has_touch=mobile,
        )

        # Pre-seed storage state cookies if available
        if self.has_saved_session():
            try:
                with open(self.session_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if "cookies" in data:
                        await context.add_cookies(data["cookies"])
            except Exception as e:
                logger.debug(f"Could not pre-seed session cookies: {e}")

        return context.browser or context, context

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
        Opens a visible browser with persistent context for human login:
        1. Navigates to Instagram login page.
        2. Waits initial buffer for page rendering.
        3. Real-time sniffing saves sessionid immediately the second it is written.
        4. Detects when login is complete and saves storage state.
        5. Preserves profile permanently on disk.
        """
        delay = settings.login_delay_seconds if delay_seconds is None else delay_seconds

        console.print("[bold cyan]Launching browser for Human Instagram Login (Persistent Profile)...[/bold cyan]")
        console.print(f"[yellow]Holding {delay}-second initial buffer for network settling...[/yellow]")

        async with async_playwright() as p:
            context = await p.chromium.launch_persistent_context(
                user_data_dir=str(self.browser_profile_dir),
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
                viewport={"width": 1280, "height": 800},
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/128.0.0.0 Safari/537.36"
                ),
            )

            # If an existing session file exists, load it
            if self.has_saved_session():
                try:
                    with open(self.session_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if "cookies" in data:
                            await context.add_cookies(data["cookies"])
                except Exception:
                    pass

            page = context.pages[0] if context.pages else await context.new_page()

            console.print("[cyan]Navigating to https://www.instagram.com/accounts/login/ ...[/cyan]")
            try:
                await page.goto("https://www.instagram.com/accounts/login/", timeout=60000)
            except Exception as e:
                console.print(f"[yellow]Navigation notice: {e}[/yellow]")

            # Human delay buffer
            await asyncio.sleep(delay)

            console.print("[bold green]>>> Please log in to Instagram in the opened browser window. <<<[/bold green]")
            console.print("[dim]Monitoring login status (real-time token sniffer active)...[/dim]")

            logged_in = False
            elapsed = 0
            poll_interval = 1

            while elapsed < timeout_seconds:
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval

                try:
                    cookies = await context.cookies()
                    has_session_cookie = any(c.get("name") in ["sessionid", "ds_user_id"] for c in cookies)

                    if has_session_cookie:
                        # CONTINUOUS SNIFFING: Immediately write to storage state file
                        await context.storage_state(path=str(self.session_path))
                        logged_in = True

                    current_url = page.url
                    is_on_feed = "accounts/login" not in current_url and ("instagram.com" in current_url)

                    if has_session_cookie and is_on_feed:
                        await asyncio.sleep(2)
                        await context.storage_state(path=str(self.session_path))
                        logged_in = True
                        break
                except Exception as e:
                    # User closed the browser window or navigated away
                    logger.debug(f"Login polling interrupted (browser closed): {e}")
                    # If we already captured valid session cookies, it's successful!
                    if self.has_saved_session():
                        logged_in = True
                    break

            if logged_in:
                console.print("[bold green]✓ Login verified and session saved permanently![/bold green]")
                console.print(f"[green]✓ Session state saved to [bold]{self.session_path}[/bold] and [bold]{self.browser_profile_dir}[/bold].[/green]")
            else:
                console.print("[bold red]Login timed out or window was closed before authenticating.[/bold red]")

            try:
                await context.close()
            except Exception:
                pass

            return logged_in


session_manager = InstagramSessionManager()
