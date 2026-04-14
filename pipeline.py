# pipeline.py
"""
Orchestrates the scraping process with chain of fetchers.
"""

import asyncio
import time
import re
import json
from typing import List, Optional

from models import PageType, ExtractMethod, ScrapeRequest, ScrapeResult
from scraper.base import BaseFetcher
from extractor import ContentExtractor
from validator import ContentValidator
from writer import JSONLWriter


class ScraperPipeline:
    """
    Orchestrates the scraping process.
    All quality decisions are made here, not in fetchers.
    """
    
    def __init__(
        self,
        fetchers: List[BaseFetcher],
        timeout: int = None,
        max_concurrent: int = None,
        min_content_length: int = 500
    ):
        self.fetchers = fetchers
        self.timeout = timeout
        self.max_concurrent = max_concurrent
        
        self.min_content_length = min_content_length
        
        self.extractor = ContentExtractor()
        self.validator = ContentValidator(min_length=200)
    
    def _classify_by_url(self, url: str) -> Optional[PageType]:
        """Classify page type from URL."""
        url_lower = url.lower()
        
        if url_lower.endswith('.pdf'):
            return PageType.PDF
        if url_lower.endswith('.json') or '/api/' in url_lower:
            return PageType.JSON
        if any(x in url_lower for x in ['/docs/', '/api/', '/reference/']):
            return PageType.DOCS
        if '/blog/' in url_lower or '/news/' in url_lower:
            return PageType.ARTICLE
        
        return None
    
    def _detect_from_response(self, html: str, status_code: int) -> PageType:
        """Detect page type from response."""
        if status_code >= 400:
            return PageType.ERROR
        
        if 'application/pdf' in html[:500].lower():
            return PageType.PDF
        
        stripped = html.strip()
        if stripped.startswith('{') or stripped.startswith('['):
            try:
                json.loads(stripped[:1000])
                return PageType.JSON
            except json.JSONDecodeError:
                pass
        
        text_len = len(re.sub(r'<[^>]+>', '', html[:10000]))
        script_count = html.count('<script')
        if text_len < 200 and script_count > 5:
            return PageType.SPA
        
        return PageType.HTML
    
    def _is_bad_content(self, content: str) -> bool:
        """Check if content is bad (too short)."""
        return not content or len(content) < self.min_content_length
    
    async def process(self, request: ScrapeRequest) -> ScrapeResult:
        print(f"[DEBUG] Processing ID {request.id}: {request.url[:50]}...")
        start_time = time.time()
        url = request.url
        
        # Step 1: Classify by URL
        url_type = self._classify_by_url(url)
        print(f"[DEBUG]   URL type: {url_type}")
        
        # Step 2: Try HTTP first (index 0)
        http_status = 500
        http_html = ""
        
        if self.fetchers:
            http_fetcher = self.fetchers[0]
            try:
                http_status, http_html = await http_fetcher.fetch_with_retry(url, max_attempts=2)
                print(f"[DEBUG]   HTTP status: {http_status}, html_len: {len(http_html)}")
            except Exception as e:
                print(f"[DEBUG]   HTTP exception: {e}")
        
        # Step 3: Decide if we need browser
        # Need browser if: status is not 200 OR content is bad
        need_browser = (http_status != 200) or self._is_bad_content(http_html)
        
        final_status = http_status
        final_html = http_html
        used_method = ExtractMethod.TRAFILATURA
        
        if need_browser and len(self.fetchers) > 1:
            print(f"[DEBUG]   Need browser (status={http_status}, content_len={len(http_html)})")
            
            # Try browser fetchers (index 1 and up)
            for fetcher in self.fetchers[1:]:
                fetcher_name = fetcher.__class__.__name__.replace('Fetcher', '').lower()
                print(f"[DEBUG]   Trying {fetcher_name}...")
                
                try:
                    browser_status, browser_html = await fetcher.fetch_with_retry(url, max_attempts=2)

                    # Always update method and content (we tried)
                    used_method = self._get_method_from_fetcher(fetcher)
                    final_html = browser_html

                    # Extract content TEMPORARILY to check quality
                    # Use a temporary page type for quality check
                    temp_page_type = url_type if url_type is not None else PageType.HTML
                    temp_content = self.extractor.extract_for_page_type(browser_html, temp_page_type.value)

                    if not self._is_bad_content(temp_content):
                        # Browser got good content! Use browser's status and content
                        final_status = browser_status
                        print(f"[DEBUG]   {fetcher_name} got good content! status={browser_status}, len={len(temp_content)}")
                        break
                    else:
                        # Browser got bad content, but we tried
                        # Keep HTTP status/content, but mark method as browser
                        print(f"[DEBUG]   {final_status} {fetcher_name} got bad content ((extracted={len(temp_content)} chars)")
                        # DON'T break - continue to next browser if available
                        
                except Exception as e:
                    print(f"[DEBUG]   {fetcher_name} exception: {e}")
        
        # Step 4: If still bad content, return error
        if self._is_bad_content(final_html):
            print(f"[DEBUG]   No good content for {url}")
            return ScrapeResult(
                id=request.id,
                url=url,
                content="",
                status_code=final_status,
                latency=time.time() - start_time,
                extract_method=used_method,
                page_type=PageType.ERROR
            )
        
        # Step 5: Detect content type
        if url_type is not None:
            page_type = url_type
        else:
            page_type = self._detect_from_response(final_html, final_status)
        print(f"[DEBUG]   Page type: {page_type}")
        
        # Step 6: Extract content
        content = self.extractor.extract_for_page_type(final_html, page_type.value)
        print(f"[DEBUG]   Extracted: {len(content)} chars")
        
        # Step 7: Fallback to readability if needed
        if len(content) < 200 and final_html and len(final_html.strip()) > 500:
            readability_content = self.extractor.extract_readability(final_html)
            if readability_content and len(readability_content) > len(content):
                content = readability_content
                used_method = ExtractMethod.READABILITY
        
        # Step 8: Final fallback to raw text
        if len(content) < 100:
            raw_content = self.extractor.extract_raw_text(final_html)
            if raw_content and len(raw_content) > len(content):
                content = raw_content
                used_method = ExtractMethod.RAW_TEXT
        
        # Step 9: Post-process
        if len(content) > 50000:
            content = content[:50000]
        
        latency = time.time() - start_time
        
        return ScrapeResult(
            id=request.id,
            url=url,
            content=content,
            status_code=final_status,
            latency=round(latency, 2),
            extract_method=used_method,
            page_type=page_type
        )
    
    def _get_method_from_fetcher(self, fetcher) -> ExtractMethod:
        """Map fetcher to ExtractMethod enum."""
        name = fetcher.__class__.__name__.lower()
        if 'http' in name:
            return ExtractMethod.TRAFILATURA
        elif 'playwright' in name:
            return ExtractMethod.PLAYWRIGHT
        elif 'selenium' in name:
            return ExtractMethod.SELENIUM
        return ExtractMethod.NONE
    
    async def process_batch(
        self, 
        requests: List[ScrapeRequest], 
        writer: JSONLWriter = None,
        max_concurrent: int = None
    ) -> List[ScrapeResult]:
        """Process multiple URLs concurrently."""
        concurrent = max_concurrent or self.max_concurrent or 10
        
        semaphore = asyncio.Semaphore(concurrent)
        
        async def process_one(req):
            async with semaphore:
                result = await self.process(req)
                if writer:
                    writer.write_result(result)
                return result
        
        tasks = [process_one(req) for req in requests]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        valid_results = []
        for res in results:
            if isinstance(res, Exception):
                print(f"[ERROR] {res}")
                continue
            valid_results.append(res)
        
        return valid_results