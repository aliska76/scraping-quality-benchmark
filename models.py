from dataclasses import dataclass
from enum import Enum

"""
Data models and enumerations for the scraping pipeline.
"""


class PageType(Enum):
    """Types of pages we can encounter."""
    HTML = "html"
    JSON = "json"
    PDF = "pdf"
    BLOCKED = "blocked"
    ERROR = "error"
    REDIRECT = "redirect"
    SPA = "spa"
    DOCS = "docs"
    ARTICLE = "article"


class ExtractMethod(Enum):
    """Methods used for content extraction."""
    TRAFILATURA = "trafilatura"
    READABILITY = "readability"
    RAW_TEXT = "raw_text"
    PDF = "pdf"
    JSON = "json"
    PLAYWRIGHT = "playwright"
    SELENIUM = "Selenium"
    NONE = "none"


@dataclass
class ScrapeResult:
    """Result of scraping a single URL."""
    id: int
    url: str
    content: str
    status_code: int
    latency: float
    extract_method: ExtractMethod = ExtractMethod.NONE
    page_type: PageType = PageType.ERROR


@dataclass
class ScrapeRequest:
    """Request to scrape a single URL."""
    id: int
    url: str