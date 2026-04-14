"""
Integration tests for the entire pipeline.
"""

import pytest
from unittest.mock import AsyncMock
from models import ScrapeRequest, ExtractMethod
from pipeline import ScraperPipeline


class TestIntegrationScenarios:
    """Integration tests for real-world scenarios."""
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_fgsglobal_scenario_http_404_selenium_bad_content(self):
        """Test: HTTP 404, Selenium bad content -> status 404, method SELENIUM."""
        http_fetcher = AsyncMock()
        http_fetcher.__class__.__name__ = 'HTTPFetcher'
        http_fetcher.fetch_with_retry = AsyncMock(return_value=(404, ""))
        
        selenium_fetcher = AsyncMock()
        selenium_fetcher.__class__.__name__ = 'SeleniumFetcher'
        selenium_fetcher.fetch_with_retry = AsyncMock(return_value=(200, "A" * 330))
        
        pipeline = ScraperPipeline(
            fetchers=[http_fetcher, selenium_fetcher],
            min_content_length=500
        )
        
        request = ScrapeRequest(id=4, url="https://fgsglobal.com/...")
        result = await pipeline.process(request)
        
        assert result.status_code == 404
        assert result.extract_method == ExtractMethod.SELENIUM
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_inc_scenario_http_403_selenium_good_content(self):
        """Test: HTTP 403, Selenium good content -> status 200, method SELENIUM."""
        http_fetcher = AsyncMock()
        http_fetcher.__class__.__name__ = 'HTTPFetcher'
        http_fetcher.fetch_with_retry = AsyncMock(return_value=(403, ""))
        
        selenium_fetcher = AsyncMock()
        selenium_fetcher.__class__.__name__ = 'SeleniumFetcher'
        selenium_fetcher.fetch_with_retry = AsyncMock(return_value=(200, "<html>" + "A" * 1000 + "</html>"))
        
        pipeline = ScraperPipeline(
            fetchers=[http_fetcher, selenium_fetcher],
            min_content_length=500
        )
        
        request = ScrapeRequest(id=10, url="https://www.inc.com/...")
        result = await pipeline.process(request)
        
        assert result.status_code == 200
        assert result.extract_method == ExtractMethod.SELENIUM
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_dogecoin_scenario_http_502_selenium_good_content(self):
        """Test: HTTP 502, Selenium good content -> status 200, method SELENIUM."""
        http_fetcher = AsyncMock()
        http_fetcher.__class__.__name__ = 'HTTPFetcher'
        http_fetcher.fetch_with_retry = AsyncMock(return_value=(502, ""))
        
        selenium_fetcher = AsyncMock()
        selenium_fetcher.__class__.__name__ = 'SeleniumFetcher'  # ← важно!
        selenium_fetcher.fetch_with_retry = AsyncMock(return_value=(200, "<html>" + "A" * 1500 + "</html>"))
        
        pipeline = ScraperPipeline(
            fetchers=[http_fetcher, selenium_fetcher],
            min_content_length=500
        )
        
        request = ScrapeRequest(id=19, url="https://dogecoin.com/...")
        result = await pipeline.process(request)
        
        assert result.status_code == 200
        assert result.extract_method == ExtractMethod.SELENIUM
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_localsearch_scenario_http_202_selenium_bad_content(self):
        """Test: HTTP 202, Selenium bad content -> status 202, method SELENIUM."""
        http_fetcher = AsyncMock()
        http_fetcher.__class__.__name__ = 'HTTPFetcher'
        http_fetcher.fetch_with_retry = AsyncMock(return_value=(202, "A" * 157))
        
        selenium_fetcher = AsyncMock()
        selenium_fetcher.__class__.__name__ = 'SeleniumFetcher'
        selenium_fetcher.fetch_with_retry = AsyncMock(return_value=(200, "A" * 361))
        
        pipeline = ScraperPipeline(
            fetchers=[http_fetcher, selenium_fetcher],
            min_content_length=500
        )
        
        request = ScrapeRequest(id=9, url="https://www.localsearch.com.au/...")
        result = await pipeline.process(request)
        
        assert result.status_code == 202
        assert result.extract_method == ExtractMethod.SELENIUM
    
    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_beltecno_scenario_http_404_selenium_bad_content(self):
        """Test: HTTP 404, Selenium bad content -> status 404, method SELENIUM."""
        http_fetcher = AsyncMock()
        http_fetcher.__class__.__name__ = 'HTTPFetcher'
        http_fetcher.fetch_with_retry = AsyncMock(return_value=(404, ""))
        
        selenium_fetcher = AsyncMock()
        selenium_fetcher.__class__.__name__ = 'SeleniumFetcher'
        selenium_fetcher.fetch_with_retry = AsyncMock(return_value=(200, "A" * 229))
        
        pipeline = ScraperPipeline(
            fetchers=[http_fetcher, selenium_fetcher],
            min_content_length=500
        )
        
        request = ScrapeRequest(id=13, url="https://www.beltecno.co.jp/...")
        result = await pipeline.process(request)
        
        assert result.status_code == 404
        assert result.extract_method == ExtractMethod.SELENIUM