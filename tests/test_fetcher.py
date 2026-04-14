# tests/test_fetcher.py
"""
Tests for HTTP fetcher using mocks from conftest.py.
"""

import pytest
from unittest.mock import AsyncMock, patch
from scraper.fetcher import HTTPFetcher
import httpx


class TestHTTPFetcher:
    """Test suite for HTTPFetcher."""
    
    @pytest.mark.asyncio
    async def test_fetch_success_returns_200_and_content(self, mock_config):
        """Should return status 200 and HTML content on successful request."""
        fetcher = HTTPFetcher(proxy_url=None)
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.text = "<html><body>Test content</body></html>"
            mock_response.content = b"<html><body>Test content</body></html>"
            
            mock_client.return_value.__aenter__.return_value.get.return_value = mock_response
            
            status, content = await fetcher.fetch("https://example.com")
            
            assert status == 200
            assert "Test content" in content
    
    @pytest.mark.asyncio
    async def test_fetch_timeout_returns_408(self, mock_config):
        """Should return status 408 on timeout."""
        fetcher = HTTPFetcher(proxy_url=None)
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get.side_effect = httpx.TimeoutException("Timeout")
            
            status, content = await fetcher.fetch("https://example.com")
            
            assert status == 408
            assert content == ""
    
    @pytest.mark.asyncio
    async def test_fetch_connection_error_returns_503(self, mock_config):
        """Should return status 503 on connection error."""
        fetcher = HTTPFetcher(proxy_url=None)
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get.side_effect = httpx.ConnectError("Connection failed")
            
            status, content = await fetcher.fetch("https://example.com")
            
            assert status == 503
            assert content == ""
    
    @pytest.mark.asyncio
    async def test_fetch_proxy_error_returns_502(self, mock_config_with_proxy):
        """Should return status 502 on proxy error."""
        fetcher = HTTPFetcher(proxy_url=mock_config_with_proxy.proxy_url)
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get.side_effect = httpx.ProxyError("Proxy failed")
            
            status, content = await fetcher.fetch("https://example.com")
            
            assert status == 502
            assert content == ""
    
    @pytest.mark.unit
    def test_is_garbled_text_with_normal_text_returns_false(self):
        """Should return False for normal readable text."""
        fetcher = HTTPFetcher()
        
        result = fetcher._is_garbled_text("Hello world! This is normal text.")
        
        assert result is False
    
    @pytest.mark.unit
    def test_is_garbled_text_with_replacement_char_returns_true(self):
        """Should return True for text with replacement character."""
        fetcher = HTTPFetcher()
        
        result = fetcher._is_garbled_text("Hello � world")
        
        assert result is True
    
    @pytest.mark.unit
    def test_is_garbled_text_with_null_bytes_returns_true(self):
        """Should return True for text with null bytes."""
        fetcher = HTTPFetcher()
        
        result = fetcher._is_garbled_text("Hello\x00world")
        
        assert result is True
    
    @pytest.mark.unit
    def test_is_garbled_text_with_empty_string_returns_false(self):
        """Should return False for empty string."""
        fetcher = HTTPFetcher()
        
        result = fetcher._is_garbled_text("")
        
        assert result is False
    
    @pytest.mark.unit
    def test_build_headers_with_compression_includes_encoding(self):
        """Should include Accept-Encoding header when compression enabled."""
        fetcher = HTTPFetcher()
        
        headers = fetcher._build_headers(None, use_compression=True)
        
        assert 'Accept-Encoding' in headers
        assert headers['Accept-Encoding'] == 'gzip, deflate, br'
    
    @pytest.mark.unit
    def test_build_headers_without_compression_uses_identity(self):
        """Should use identity encoding when compression disabled."""
        fetcher = HTTPFetcher()
        
        headers = fetcher._build_headers(None, use_compression=False)
        
        assert headers['Accept-Encoding'] == 'identity'
    
    @pytest.mark.unit
    def test_build_headers_merges_custom_headers(self):
        """Should merge custom headers with defaults."""
        fetcher = HTTPFetcher()
        custom = {'X-Custom-Header': 'test-value'}
        
        headers = fetcher._build_headers(custom, use_compression=True)
        
        assert headers['X-Custom-Header'] == 'test-value'
        assert headers['User-Agent'] is not None
    
    @pytest.mark.unit
    def test_decode_response_with_utf8_returns_correct_text(self):
        """Should correctly decode UTF-8 encoded content."""
        fetcher = HTTPFetcher()
        
        result = fetcher._decode_response(b"Hello \xd0\xbc\xd0\xb8\xd1\x80")
        
        assert "Hello мир" in result
    
    @pytest.mark.unit
    def test_decode_response_with_empty_bytes_returns_empty_string(self):
        """Should return empty string for empty bytes."""
        fetcher = HTTPFetcher()
        
        result = fetcher._decode_response(b"")
        
        assert result == ""
    
    @pytest.mark.unit
    def test_decode_response_with_garbled_text_fallback_to_replacement(self):
        """Should handle garbled text with replacement strategy."""
        fetcher = HTTPFetcher()
        
        # Invalid UTF-8 sequence
        result = fetcher._decode_response(b"Hello \xff\xfe")
        
        # Should not raise exception
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_fetch_with_retry_success_on_first_attempt(self, mock_config):
        """Should return success on first attempt."""
        fetcher = HTTPFetcher(proxy_url=None)
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.text = "<html>Test</html>"
            mock_response.content = b"<html>Test</html>"
            
            mock_client.return_value.__aenter__.return_value.get.return_value = mock_response
            
            status, content = await fetcher.fetch_with_retry("https://example.com")
            
            assert status == 200
    
    @pytest.mark.asyncio
    async def test_fetch_with_retry_uses_different_user_agents_on_403(self, mock_config):
        """Should try different User-Agents on 403 error."""
        mock_config.user_agents = [
            'UA1', 'UA2', 'UA3'
        ]
        
        fetcher = HTTPFetcher(
            proxy_url=None,
            retry_without_proxy_on_error=True,
            retry_without_compression_on_garbled=True
        )
        fetcher.user_agents = mock_config.user_agents
        
        call_count = 0
        
        async def mock_get(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_response = AsyncMock()
            # First call returns 403, second returns 200
            if call_count == 1:
                mock_response.status_code = 403
            else:
                mock_response.status_code = 200
            mock_response.text = "<html>Test</html>"
            mock_response.content = b"<html>Test</html>"
            return mock_response
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get.side_effect = mock_get
            
            status, content = await fetcher.fetch_with_retry("https://example.com", max_attempts=3)
            
            assert status == 200
            assert call_count == 2