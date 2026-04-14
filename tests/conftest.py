"""
Pytest configuration and shared fixtures with mocked config.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock


# Mock configuration fixture

@pytest.fixture
def mock_config():
    """Provide a mocked configuration object."""
    config = Mock()
    
    # Scraper settings
    config.timeout = 10
    config.max_retries = 2
    config.max_concurrent = 10
    config.use_playwright = False
    config.use_selenium = False
    config.retry_without_compression = True
    config.allow_direct_fallback = False
    config.min_content_length = 500
    
    # Playwright settings
    config.playwright_headless = True
    config.playwright_timeout = 30000
    
    # Selenium settings
    config.selenium_headless = True
    config.selenium_timeout = 30
    config.selenium_incognito = True
    
    # Proxy
    config.proxy_enabled = True
    config.proxy_url = None
    
    # User agents
    config.user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36'
    ]
    
    # Methods
    def get_user_agents_for_os(os_name=None):
        return config.user_agents
    
    config.get_user_agents_for_os = get_user_agents_for_os
    
    def get(key, default=None):
        if key == 'proxy.enabled':
            return config.proxy_enabled
        return default
    
    config.get = get
    
    return config


@pytest.fixture
def mock_config_with_proxy(mock_config):
    """Mock config with proxy enabled."""
    mock_config.proxy_enabled = True
    mock_config.proxy_url = "http://user:pass@proxy.example.com:8080"
    return mock_config


@pytest.fixture
def mock_config_with_selenium(mock_config):
    """Mock config with Selenium enabled."""
    mock_config.use_selenium = True
    mock_config.selenium_headless = True
    mock_config.selenium_timeout = 30
    return mock_config


@pytest.fixture
def mock_config_with_playwright(mock_config):
    """Mock config with Playwright enabled."""
    mock_config.use_playwright = True
    mock_config.playwright_headless = True
    mock_config.playwright_timeout = 30000
    return mock_config


# Patch get_config for all tests

@pytest.fixture(autouse=True)
def patch_config(mock_config):
    """Automatically patch get_config for all tests."""
    with patch('utils.config_loader.get_config', return_value=mock_config):
        yield


# Sample data fixtures

@pytest.fixture
def sample_html():
    """Provide sample HTML content for tests."""
    return """
    <!DOCTYPE html>
    <html>
    <head><title>Test Page</title></head>
    <body>
        <h1>Welcome to Test Page</h1>
        <p>This is a paragraph with some content for testing.</p>
        <ul>
            <li>Item 1</li>
            <li>Item 2</li>
        </ul>
    </body>
    </html>
    """


@pytest.fixture
def sample_json():
    """Provide sample JSON content for tests."""
    return '{"id": 1, "name": "test", "items": ["a", "b", "c"]}'


@pytest.fixture
def sample_pdf_marker():
    """Provide PDF marker for tests."""
    return "%PDF-1.4\n%âãÏÓ\n1 0 obj\n<</Type/Catalog/Pages 2 0 R>>\nendobj"


@pytest.fixture
def sample_truth_text():
    """Provide sample truth text for validation tests."""
    return "This is the important content that should be extracted from the page."


@pytest.fixture
def sample_lie_text():
    """Provide sample lie text for validation tests."""
    return "Privacy Policy Terms of Use Cookie Preferences Subscribe to Newsletter"



# Temporary directories

@pytest.fixture
def temp_results_dir(tmp_path):
    """Provide temporary directory for test outputs."""
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    return results_dir


@pytest.fixture
def temp_logs_dir(tmp_path):
    """Provide temporary directory for logs."""
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    return logs_dir


@pytest.fixture
def temp_config_dir(tmp_path):
    """Provide temporary directory for config files."""
    config_dir = tmp_path / "config_files"
    config_dir.mkdir()
    
    # Create dummy config.json
    config_file = config_dir / "config.json"
    config_file.write_text('{"scraper": {"timeout": 10, "min_content_length": 500}}')
    
    return config_dir


# Mock fetchers

@pytest.fixture
def mock_http_fetcher():
    """Create a mock HTTP fetcher."""
    from unittest.mock import AsyncMock, Mock
    fetcher = Mock()
    fetcher.fetch = AsyncMock(return_value=(200, "<html>Test content</html>"))
    fetcher.fetch_with_retry = AsyncMock(return_value=(200, "<html>Test content</html>"))
    return fetcher


@pytest.fixture
def mock_failing_http_fetcher():
    """Create a mock HTTP fetcher that fails."""
    from unittest.mock import AsyncMock, Mock
    fetcher = Mock()
    fetcher.fetch = AsyncMock(return_value=(404, ""))
    fetcher.fetch_with_retry = AsyncMock(return_value=(404, ""))
    return fetcher


@pytest.fixture
def mock_selenium_fetcher():
    """Create a mock Selenium fetcher."""
    from unittest.mock import AsyncMock, Mock
    fetcher = Mock()
    fetcher.fetch = AsyncMock(return_value=(200, "<html>Content from Selenium</html>"))
    fetcher.fetch_with_retry = AsyncMock(return_value=(200, "<html>Content from Selenium</html>"))
    return fetcher


# Mock proxy.json

@pytest.fixture
def mock_proxy_json(tmp_path):
    """Create a mock proxy.json file."""
    proxy_file = tmp_path / "proxy.json"
    proxy_file.write_text('''
    {
        "proxy": {
            "username": "testuser",
            "password": "testpass",
            "hostname": "proxy.example.com:65535",
            "port": {
                "http": 65534,
                "https": 65535,
                "socks5": 65533
            }
        }
    }
    ''')
    return proxy_file


# Mock ScrapeRequest

@pytest.fixture
def sample_request():
    """Provide a sample ScrapeRequest."""
    from models import ScrapeRequest
    return ScrapeRequest(id=1, url="https://example.com/test")


@pytest.fixture
def sample_requests():
    """Provide multiple sample ScrapeRequests."""
    from models import ScrapeRequest
    return [
        ScrapeRequest(id=1, url="https://example.com/page1"),
        ScrapeRequest(id=2, url="https://example.com/page2"),
        ScrapeRequest(id=3, url="https://example.com/page3"),
    ]
