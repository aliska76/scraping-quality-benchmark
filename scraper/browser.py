"""
Playwright fetcher for JavaScript-heavy pages.
"""

from typing import Optional, Dict, Tuple, List
from scraper.base import BaseFetcher


class PlaywrightFetcher(BaseFetcher):
    """
    Playwright fetcher with User-Agent rotation.
    Returns whatever HTML it gets. Quality decisions are made by pipeline.
    """
    
    def __init__(
        self, 
        proxy_config: Optional[Dict[str, str]] = None, 
        headless: bool = True,
        timeout: int = 30000,
        user_agents: Optional[List[str]] = None
    ):
        self.proxy_config = proxy_config
        self.headless = headless
        self.timeout = timeout
        self.user_agents = user_agents or [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36'
        ]
        self._ua_index = 0
    
    def _get_next_user_agent(self) -> str:
        ua = self.user_agents[self._ua_index % len(self.user_agents)]
        self._ua_index += 1
        return ua
    
    def _reset_ua_index(self):
        self._ua_index = 0
    
    async def fetch(self, url: str, timeout: int = None) -> Tuple[int, str]:
        """Fetch a URL using Playwright."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return 500, "Playwright not installed"
        
        timeout_ms = timeout or self.timeout
        ua = self._get_next_user_agent()
        
        print(f"[PLAYWRIGHT] Fetching {url[:60]}... with UA: {ua[:40]}...")
        
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=self.headless,
                    proxy=self.proxy_config
                )
                
                context = await browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent=ua,
                    locale='en-US',
                    timezone_id='America/New_York'
                )
                
                page = await context.new_page()
                
                response = await page.goto(url, timeout=timeout_ms, wait_until='networkidle')
                status_code = response.status if response else 200
                content = await page.content()
                
                await browser.close()
                
                print(f"[PLAYWRIGHT] Got status={status_code}, content_len={len(content)}")
                return status_code, content
                
        except Exception as e:
            print(f"[PLAYWRIGHT] Error: {type(e).__name__}: {e}")
            return 500, ""
    
    async def fetch_with_retry(self, url: str, max_attempts: int = 2, timeout: int = None) -> Tuple[int, str]:
        """Fetch with User-Agent rotation retries."""
        self._reset_ua_index()
        
        for attempt in range(max_attempts):
            print(f"[PLAYWRIGHT] Attempt {attempt + 1}/{max_attempts}")
            status, content = await self.fetch(url, timeout=timeout)
            
            # Only retry on network errors (5xx), not on empty content
            if status < 500:
                return status, content
            
            print(f"[PLAYWRIGHT] Attempt {attempt + 1} failed (status {status}), retrying...")
        
        return status, content