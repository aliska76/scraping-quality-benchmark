"""
Base classes for all fetchers.
Defines common interface for HTTP, Playwright, and Selenium fetchers.
"""

from abc import ABC, abstractmethod
from typing import Tuple


class BaseFetcher(ABC):
    """
    Abstract base class for all fetchers.
    All fetchers must implement the fetch method.
    """
    
    @abstractmethod
    async def fetch(self, url: str, timeout: int = None) -> Tuple[int, str]:
        """
        Fetch a URL and return status code and content.
        
        Args:
            url: Target URL
            timeout: Timeout in seconds (or milliseconds for Playwright)
        
        Returns:
            (status_code, content) - content is HTML text or empty string on error
        """
        pass
    
    @abstractmethod
    async def fetch_with_retry(self, url: str, max_attempts: int = 3, timeout: int = None) -> Tuple[int, str]:
        """
        Fetch with retry logic (User-Agent rotation, etc.).
        
        Args:
            url: Target URL
            max_attempts: Maximum number of attempts
            timeout: Timeout value
        
        Returns:
            (status_code, content)
        """
        pass