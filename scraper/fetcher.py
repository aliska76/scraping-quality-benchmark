"""
HTTP fetcher with proxy support, smart decompression, and retry logic.
"""

import httpx
from typing import Optional, Dict, Tuple
from scraper.base import BaseFetcher


class HTTPFetcher(BaseFetcher):
    """
    HTTP fetcher with:
    - Proxy support
    - Automatic retry without compression if decoding fails
    - Configurable via constructor parameters
    """
    
    def __init__(
        self, 
        proxy_url: Optional[str] = None,
        enable_compression: bool = True,
        retry_without_compression_on_garbled: bool = True,
        retry_without_proxy_on_error: bool = False
    ):
        self.proxy_url = proxy_url
        self.enable_compression = enable_compression
        self.retry_without_compression_on_garbled = retry_without_compression_on_garbled
        self.retry_without_proxy_on_error = retry_without_proxy_on_error
    
    def _is_garbled_text(self, text: str) -> bool:
        """Check if decoded text looks garbled."""
        if not text:
            return False
        
        sample = text[:200]
        if '�' in sample or '\x00' in sample:
            return True
        
        non_printable = sum(1 for c in sample if ord(c) < 32 and c not in '\n\r\t')
        if non_printable > len(sample) * 0.1:
            return True
        
        return False
    
    def _build_headers(self, custom_headers: Optional[Dict[str, str]] = None, use_compression: bool = True) -> Dict[str, str]:
        """Build request headers."""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        if use_compression:
            headers['Accept-Encoding'] = 'gzip, deflate, br'
        else:
            headers['Accept-Encoding'] = 'identity'
        
        if custom_headers:
            headers.update(custom_headers)
        
        return headers
    
    def _decode_response(self, raw_content: bytes) -> str:
        """Decode raw bytes to string with multiple encoding attempts."""
        if not raw_content:
            return ""
        
        for encoding in ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']:
            try:
                text = raw_content.decode(encoding)
                if not self._is_garbled_text(text):
                    return text
            except UnicodeDecodeError:
                continue
        
        return raw_content.decode('utf-8', errors='replace')
    
    async def _fetch_raw(
        self, 
        url: str, 
        headers: Dict[str, str], 
        timeout: int,
        use_proxy: bool
    ) -> Tuple[int, bytes]:
        """Fetch raw response with or without proxy."""
        client_kwargs = {
            'timeout': timeout,
            'follow_redirects': True,
            'verify': False,
            'limits': httpx.Limits(max_keepalive_connections=5, max_connections=10)
        }
        
        if use_proxy and self.proxy_url:
            client_kwargs['proxy'] = self.proxy_url
        
        try:
            async with httpx.AsyncClient(**client_kwargs) as client:
                response = await client.get(url, headers=headers)
                return response.status_code, response.content
        except httpx.ProxyError as e:
            print(f"[HTTP] Proxy failed: {e}")
            return 502, b""
        except httpx.TimeoutException:
            print(f"[HTTP] Timeout for {url}")
            return 408, b""
        except httpx.ConnectError as e:
            print(f"[HTTP] ConnectError for {url}: {e}")
            return 503, b""
        except Exception as e:
            print(f"[HTTP] {type(e).__name__}: {e}")
            return 500, b""
    
    async def fetch(self, url: str, timeout: int = None) -> Tuple[int, str]:
        """Fetch with smart retry strategy."""
        timeout_sec = timeout or 10
        
        # Attempt 1: Proxy + Compression
        use_proxy = True
        headers_compressed = self._build_headers(None, use_compression=True)
        
        print(f"[HTTP] Attempt 1: Proxy={use_proxy}, Compression=True")
        status, raw = await self._fetch_raw(url, headers_compressed, timeout_sec, use_proxy=use_proxy)
        
        # Attempt 2: If HTTP error, retry without proxy (if allowed)
        if use_proxy and status in [502, 452, 403] and self.retry_without_proxy_on_error:
            print(f"[HTTP] HTTP error {status}, retrying without proxy...")
            use_proxy = False
            status, raw = await self._fetch_raw(url, headers_compressed, timeout_sec, use_proxy=use_proxy)
        elif use_proxy and status in [502, 452, 403]:
            print(f"[HTTP] HTTP error {status}, direct fallback is DISABLED.")
        
        # Decode and check for garbled text
        if status < 400 and raw:
            decoded = self._decode_response(raw)
            
            if not self._is_garbled_text(decoded):
                print(f"[HTTP] Success! {len(decoded)} chars")
                return status, decoded
            
            # Attempt 3: Same proxy setting, but NO compression
            if self.retry_without_compression_on_garbled:
                print(f"[HTTP] Garbled text, retrying with same proxy but NO compression...")
                
                headers_plain = self._build_headers(None, use_compression=False)
                status2, raw2 = await self._fetch_raw(url, headers_plain, timeout_sec, use_proxy=use_proxy)
                
                if status2 < 400 and raw2:
                    decoded2 = self._decode_response(raw2)
                    if not self._is_garbled_text(decoded2):
                        print(f"[HTTP] Success! {len(decoded2)} chars")
                        return status2, decoded2
                    
                    return status2, decoded2
        
        if status >= 400:
            return status, ""
        
        return status, self._decode_response(raw)
    
    async def fetch_with_retry(self, url: str, max_attempts: int = 3, timeout: int = None) -> Tuple[int, str]:
        """Fetch with retry (HTTP already has internal retry logic)."""
        return await self.fetch(url, timeout=timeout)