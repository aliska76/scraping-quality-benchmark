# main.py
"""
Main entry point for the scraping pipeline.
"""

import asyncio
import csv
import argparse
from pathlib import Path
from typing import List, Optional

from models import ScrapeRequest, ScrapeResult
from scraper.fetcher import HTTPFetcher
from scraper.browser import PlaywrightFetcher
from pipeline import ScraperPipeline
from scraper.selenium_browser import SeleniumFetcher
from utils.config_loader import get_config
from logger import get_logger
from writer import JSONLWriter


def load_requests_from_csv(csv_path: str, limit: Optional[int] = None) -> List[ScrapeRequest]:
    """Load scrape requests from CSV file."""
    requests = []
    
    if not Path(csv_path).exists():
        print(f"[ERROR] File not found: {csv_path}")
        return []
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if limit and i >= limit:
                break
            requests.append(ScrapeRequest(
                id=int(row['id']),
                url=row['url']
            ))
    
    return requests


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Tavily Scraping Pipeline')
    
    parser.add_argument(
        '--input', '-i',
        type=str,
        required=True,
        help='Input CSV file path (train.csv or test.csv)'
    )
    
    parser.add_argument(
        '--output', '-o',
        type=str,
        required=True,
        help='Output JSONL file path'
    )
    
    parser.add_argument(
        '--limit', '-l',
        type=int,
        default=None,
        help='Limit number of URLs to process (for testing)'
    )
    
    parser.add_argument(
        '--use-playwright',
        action='store_true',
        help='Enable Playwright for JavaScript rendering'
    )

    parser.add_argument(
        '--use-selenium',
        action='store_true',
        help='Enable Selenium for JavaScript rendering'
    )
    
    parser.add_argument(
        '--max-concurrent',
        type=int,
        default=None,
        help='Maximum concurrent requests (default: from config)'
    )
    
    return parser.parse_args()


async def main():
    """Main entry point."""
    args = parse_args()
    
    # Load configuration
    config = get_config()
    
    # Override config with command line arguments
    use_browser = args.use_playwright or config.use_playwright
    
    # Load proxy from proxy.json (priority)
    proxy_url = config.load_proxy_from_json("proxy.json")
    print(f"[DEBUG] Raw proxy_url: {proxy_url}")
    print(f"[DEBUG] Proxy enabled: {config.get('proxy.enabled', True)}")
    
    if proxy_url:
        # Hide credentials in output
        proxy_display = proxy_url.split('@')[0] + '@...' if '@' in proxy_url else proxy_url
        print(f"[INFO] Using proxy: {proxy_display}")
    else:
        print("[INFO] No proxy configured")
    
    fetchers = []

    # Initialize HTTP fetcher
    http_fetcher = HTTPFetcher(
        proxy_url=proxy_url if config.get('proxy.enabled', True) else None, retry_without_compression_on_garbled=config.retry_without_compression,
        retry_without_proxy_on_error=config.allow_direct_fallback
    )

    fetchers.append(http_fetcher)

    print("[DEBUG] Testing proxy connection...")
    test_status, test_html = await http_fetcher.fetch("https://httpbin.org/ip", timeout=10)
    print(f"[DEBUG] Test result: status={test_status}, response={test_html[:100]}")
    
    # Initialize proxy
    browser_proxy = None
    if proxy_url and '@' in proxy_url:
        parts = proxy_url.split('://')
        protocol = parts[0]
        rest = parts[1]
        
        if '@' in rest:
            user_pass, host_port = rest.split('@', 1)
            if ':' in user_pass:
                username, password = user_pass.split(':', 1)
                browser_proxy = {
                    "server": f"{protocol}://{host_port}",
                    "username": username,
                    "password": password,
                }
    
    # Playwright fetcher
    if config.use_playwright:
        playwright_fetcher = PlaywrightFetcher(
            proxy_config=browser_proxy,
            headless=config.playwright_headless,
            timeout=config.playwright_timeout,
            user_agents=config.get_user_agents_for_os()
        )
        fetchers.append(playwright_fetcher)
        print("[INFO] Playwright fetcher enabled")

    print(f"[DEBUG] config.use_selenium = {config.use_selenium}")

    # Selenium fetcher
    if config.use_selenium:
        print(f"[DEBUG] Fetchers in chain: {[f.__class__.__name__ for f in fetchers]}")
        selenium_fetcher = SeleniumFetcher(
            proxy_config=browser_proxy,
            headless=config.selenium_headless,
            timeout=config.selenium_timeout,
            incognito=config.selenium_incognito,
            user_agents=config.get_user_agents_for_os()
        )
        fetchers.append(selenium_fetcher)
        print("[INFO] Selenium fetcher enabled")
    
    # Initialize pipeline
    pipeline = ScraperPipeline(
        fetchers=fetchers,
        timeout=config.timeout,
        min_content_length=config.min_content_length
    )
    print(f"[DEBUG] Pipeline created:")
    print(f"  - http_fetcher: {http_fetcher}")
    print(f"  - use_browser: {use_browser}")
    print(f"  - timeout: {config.timeout}")
    print(f"  - max_retries: {config.max_retries}")
    
    # Initialize logger
    logger = get_logger()
    
    # Load requests
    requests = load_requests_from_csv(args.input, args.limit)
    print(f"[INFO] Loaded {len(requests)} URLs from {args.input}")
    
    if not requests:
        print("[ERROR] No requests loaded")
        return
    
    # Initialize writer
    writer = JSONLWriter(args.output)
    
    # Process batch
    print(f"[INFO] Starting scraping with max_concurrent={args.max_concurrent or config.max_concurrent}")
    results = await pipeline.process_batch(requests, writer=writer, max_concurrent=args.max_concurrent)
    
    writer.close()
    
    # Log all results
    for result in results:
        logger.log_result(result)
    
    # Save logs
    logger.save_to_csv()
    logger.save_summary_to_json()
    
    # Print summary
    logger.print_summary()


if __name__ == "__main__":
    asyncio.run(main())