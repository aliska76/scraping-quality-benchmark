# tests/test_pipeline.py
"""
Tests for scraping pipeline using mocks from conftest.py.
"""

import pytest
from models import ScrapeRequest, PageType
from pipeline import ScraperPipeline


class TestScraperPipeline:
    """Test suite for ScraperPipeline using mocks."""
    
    @pytest.mark.asyncio
    async def test_process_success(self, mock_http_fetcher, mock_config):
        """Should return success when HTTP returns good content."""
        mock_config.min_content_length = 50
        mock_http_fetcher.fetch_with_retry.return_value = (200, "<html>Long content for testing</html>")
        
        pipeline = ScraperPipeline(
            fetchers=[mock_http_fetcher],
            min_content_length=mock_config.min_content_length
        )
        
        request = ScrapeRequest(id=1, url="https://example.com")
        result = await pipeline.process(request)
        
        assert result.status_code == 200
        assert mock_http_fetcher.fetch_with_retry.called
    
    @pytest.mark.asyncio
    async def test_process_http_404_returns_error(self, mock_failing_http_fetcher):
        """Should return error for HTTP 404."""
        pipeline = ScraperPipeline(fetchers=[mock_failing_http_fetcher])
        
        request = ScrapeRequest(id=1, url="https://example.com/404")
        result = await pipeline.process(request)
        
        assert result.status_code == 404
        assert result.content == ""
    
    @pytest.mark.asyncio
    async def test_process_browser_fallback_on_poor_content(
        self, mock_http_fetcher, mock_selenium_fetcher, mock_config
    ):
        """Should use browser fallback when HTTP content is poor."""
        mock_config.min_content_length = 50
        
        # HTTP returns short content
        mock_http_fetcher.fetch_with_retry.return_value = (200, "short")
        # Selenium returns good content
        mock_selenium_fetcher.fetch_with_retry.return_value = (200, "<html>Long good content for testing</html>")
        
        pipeline = ScraperPipeline(
            fetchers=[mock_http_fetcher, mock_selenium_fetcher],
            min_content_length=mock_config.min_content_length
        )
        
        request = ScrapeRequest(id=1, url="https://example.com")
        result = await pipeline.process(request)
        
        assert mock_selenium_fetcher.fetch_with_retry.called
        assert result.status_code == 200
    
    @pytest.mark.asyncio
    async def test_process_browser_fallback_on_http_error(
        self, mock_failing_http_fetcher, mock_selenium_fetcher
    ):
        """Should use browser fallback when HTTP returns error."""
        mock_failing_http_fetcher.fetch_with_retry.return_value = (403, "")
        mock_selenium_fetcher.fetch_with_retry.return_value = (200, "<html>Content from browser</html>")
        
        pipeline = ScraperPipeline(fetchers=[mock_failing_http_fetcher, mock_selenium_fetcher])
        
        request = ScrapeRequest(id=1, url="https://example.com/blocked")
        result = await pipeline.process(request)
        
        assert mock_selenium_fetcher.fetch_with_retry.called
    
    @pytest.mark.unit
    def test_classify_by_url_with_pdf_returns_pdf(self):
        """Should classify PDF URLs correctly."""
        pipeline = ScraperPipeline(fetchers=[])
        
        result = pipeline._classify_by_url("https://example.com/document.pdf")
        
        assert result == PageType.PDF
    
    @pytest.mark.unit
    def test_classify_by_url_with_json_returns_json(self):
        """Should classify JSON URLs correctly."""
        pipeline = ScraperPipeline(fetchers=[])
        
        assert pipeline._classify_by_url("https://example.com/data.json") == PageType.JSON
    
    @pytest.mark.unit
    def test_classify_by_url_with_blog_returns_article(self):
        """Should classify blog URLs as article."""
        pipeline = ScraperPipeline(fetchers=[])
        
        assert pipeline._classify_by_url("https://example.com/blog/post-1") == PageType.ARTICLE
    
    @pytest.mark.unit
    def test_classify_by_url_with_unknown_returns_none(self):
        """Should return None for unknown URL patterns."""
        pipeline = ScraperPipeline(fetchers=[])
        
        result = pipeline._classify_by_url("https://example.com/about")
        
        assert result is None
    
    @pytest.mark.unit
    def test_is_bad_content_with_short_content_returns_true(self, mock_config):
        """Should return True for content shorter than min_length."""
        mock_config.min_content_length = 500
        pipeline = ScraperPipeline(fetchers=[], min_content_length=mock_config.min_content_length)
        
        assert pipeline._is_bad_content("short") is True
    
    @pytest.mark.unit
    def test_is_bad_content_with_long_content_returns_false(self, mock_config):
        """Should return False for content longer than min_length."""
        mock_config.min_content_length = 500
        pipeline = ScraperPipeline(fetchers=[], min_content_length=mock_config.min_content_length)
        
        assert pipeline._is_bad_content("A" * 500) is False
    
    @pytest.mark.asyncio
    async def test_process_batch_returns_results_for_multiple_urls(
        self, mock_http_fetcher, sample_requests
    ):
        """Should process multiple URLs concurrently."""
        mock_http_fetcher.fetch_with_retry.return_value = (200, "<html>Test</html>")
        
        pipeline = ScraperPipeline(fetchers=[mock_http_fetcher], max_concurrent=2)
        
        results = await pipeline.process_batch(sample_requests, max_concurrent=2)
        
        assert len(results) == 3
        for result in results:
            assert result.status_code == 200