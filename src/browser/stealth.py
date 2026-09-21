"""
Advanced Anti-Detection & Human Emulation Engine.
Protects the marketing team's Instagram account, login session, and IP address
by emulating natural human browsing behavior with randomized delays, smooth scrolling,
and browser fingerprint masking.
"""
import asyncio
import logging
import random
import time
from typing import Optional
from playwright.async_api import Page

logger = logging.getLogger(__name__)


class HumanEmulator:
    """
    Simulates human interactions and applies anti-detection stealth scripts
    to ensure Instagram treats the browser as an authentic human session.
    """

    STEALTH_JS = """
    // 1. Hide webdriver flag
    Object.defineProperty(navigator, 'webdriver', {
        get: () => undefined
    });

    // 2. Mock Chrome runtime
    window.chrome = {
        runtime: {},
        loadTimes: function() {},
        csi: function() {},
        app: {}
    };

    // 3. Mock plugins & mimeTypes
    Object.defineProperty(navigator, 'plugins', {
        get: () => [1, 2, 3, 4, 5],
    });
    Object.defineProperty(navigator, 'languages', {
        get: () => ['en-US', 'en'],
    });

    // 4. Mock permissions query
    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (parameters) => (
        parameters.name === 'notifications' ?
            Promise.resolve({ state: Notification.permission }) :
            originalQuery(parameters)
    );
    """

    def __init__(self, min_delay: float = 2.5, max_delay: float = 5.5):
        self.min_delay = min_delay
        self.max_delay = max_delay
        self._action_timestamps: list[float] = []
        self.max_actions_per_minute = 10

    async def apply_stealth(self, page: Page):
        """Injects stealth evasion scripts before any scripts on the page load."""
        try:
            await page.add_init_script(self.STEALTH_JS)
            # Set extra realistic headers
            await page.set_extra_http_headers({
                "Accept-Language": "en-US,en;q=0.9",
                "Sec-Ch-Ua": '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": '"macOS"',
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1"
            })
            logger.debug("Applied browser stealth scripts and headers.")
        except Exception as e:
            logger.warning(f"Failed to inject stealth scripts: {e}")

    async def human_delay(self, factor: float = 1.0, reason: str = ""):
        """
        Pauses execution with natural randomized human jitter.
        Applies a normal distribution around the average delay.
        """
        base = random.uniform(self.min_delay, self.max_delay) * factor
        # Add micro jitter
        jitter = random.gauss(0, 0.3)
        actual_delay = max(1.2, base + jitter)

        if reason:
            logger.info(f"Stealth delay ({reason}): sleeping {actual_delay:.2f}s to emulate human behavior...")
        await asyncio.sleep(actual_delay)

    async def human_scroll(self, page: Page, steps: int = 3):
        """
        Smoothly scrolls the page down with variable speed, micro-pauses,
        and slight jitter to simulate natural human mouse wheel behavior.
        """
        for _ in range(steps):
            delta_y = random.randint(250, 600)
            await page.mouse.wheel(0, delta_y)
            # Human micro pause after scrolling
            await asyncio.sleep(random.uniform(0.6, 1.8))

        # Occasionally scroll back up slightly like a human re-reading
        if random.random() < 0.4:
            await page.mouse.wheel(0, -random.randint(80, 180))
            await asyncio.sleep(random.uniform(0.5, 1.2))

    async def human_mouse_wander(self, page: Page):
        """Moves mouse across the viewport in a curved trajectory."""
        try:
            start_x = random.randint(100, 400)
            start_y = random.randint(100, 400)
            end_x = random.randint(500, 900)
            end_y = random.randint(300, 700)

            # Move in small increments simulating hand movement
            steps = random.randint(5, 10)
            for i in range(steps):
                x = start_x + (end_x - start_x) * (i / steps) + random.randint(-15, 15)
                y = start_y + (end_y - start_y) * (i / steps) + random.randint(-15, 15)
                await page.mouse.move(x, y)
                await asyncio.sleep(random.uniform(0.02, 0.08))
        except Exception as e:
            logger.debug(f"Mouse wander bypassed: {e}")

    def check_rate_limit(self) -> bool:
        """
        Guards against spamming Instagram requests.
        Keeps actions within human velocity limits.
        """
        now = time.time()
        # Keep only actions in last 60 seconds
        self._action_timestamps = [t for t in self._action_timestamps if now - t < 60]
        if len(self._action_timestamps) >= self.max_actions_per_minute:
            logger.warning("Rate limit throttle active: too many requests in 60s window.")
            return False

        self._action_timestamps.append(now)
        return True


human_emulator = HumanEmulator()
