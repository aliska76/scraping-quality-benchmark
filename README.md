# Tavily Scraping Assignment

Web scraping system for the Tavily Scraping Quality Benchmark assignment. Extracts clean content from 500 training URLs and 500 test URLs, balancing latency, accuracy, and cost.

## Features

- Async HTTP requests with proxy support and smart retry logic
- Browser-based fallback (Playwright) for JavaScript-heavy pages
- Optional Selenium fallback for compatibility
- Multi-format extraction: HTML, PDF, JSON
- Automatic content validation and quality scoring
- Configurable via JSON files
- Cross-platform (Windows / macOS)

## Requirements

- Python 3.12.6 or higher
- pip 24.2 or higher
- Internet connection (for downloading dependencies)

## Installation

```bash
python setup.py

or

pip install -r requirements.txt
python -m playwright install chromium
```

The installer will:
- Install Python dependencies from `requirements.txt`
- Download Playwright Chromium browser
- Create required directories (`results/`, `logs/`)

## Configuration

Edit files in the `config/` directory:

| File | Purpose |
|------|---------|
| `config/config.json` | Main settings (timeout, retries, browser options) |
| `config/user_agents.json` | User-Agent strings for rotation |

Key configuration parameters:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `timeout` | 10 | Request timeout in seconds |
| `max_concurrent` | 10 | Concurrent request limit |
| `min_content_length` | 500 | Minimum content length to consider good |
| `use_playwright` | false | Enable Playwright fallback |
| `use_selenium` | false | Enable Selenium fallback |
| `allow_direct_fallback` | false | Allow requests without proxy (dangerous) |

### Configuration Files

**config/config.json**:
```json
{
    "scraper": {
        "timeout": 10,
        "max_retries": 2,
        "max_concurrent": 10,
        "use_playwright": false,
        "use_selenium": true,
        "retry_without_compression": true,
        "allow_direct_fallback": false,
        "min_content_length": 500
    },
    "playwright": {
        "headless": true,
        "timeout": 30000
    },
    "selenium": {
        "headless": true,
        "timeout": 30,
        "incognito": true
    },
    "proxy": {
        "enabled": true
    }
}
```

**config/user_agents.json**:
User-Agent strings grouped by operating system for rotation on 403 errors.

### Proxy Configuration

Proxy credentials are stored in `proxy.json` (provided with the assignment). The system extracts:
- Username and password for authentication
- Hostname and port (HTTP port 65534 is used for requests)
- Falls back to direct connection only if `allow_direct_fallback=true`

## Documentation

Detailed system architecture, component design, and design decisions are documented in:

- **System Design Document.pdf** – complete design overview

## Usage

### Basic Usage

```bash
# Test run (first 10 URLs)
python main.py --input train.csv --output results/train_results.jsonl --limit 10

# Full run (all URLs)
python main.py --input train.csv --output results/train_results.jsonl

# Run on test set
python main.py --input test.csv --output results/test_results.jsonl
```

### With Browser Fallback

```bash
# Enable Playwright
python main.py --input train.csv --output results/train_results.jsonl --use-playwright

# Or enable via config.json (set "use_playwright": true)
```

### Evaluate Results

```bash
python score.py --results results/train_results.jsonl --ground-truth train.csv
```

## Command Line Arguments

| Argument | Description |
|----------|-------------|
| `--input` | Input CSV file path (train.csv or test.csv) |
| `--output` | Output JSONL file path |
| `--limit` | Limit number of URLs to process (for testing) |
| `--use-playwright` | Enable Playwright for JavaScript rendering |
| `--max-concurrent` | Maximum concurrent requests (default: from config) |

## Project Structure

```
project/
├── config/                     # Configuration files
│   ├── config.json
│   └── user_agents.json
├── scraper/                   # Low-level fetching modules
│   ├── base.py                # Abstract fetcher interface
│   ├── fetcher.py             # HTTP fetcher (httpx)
│   ├── browser.py             # Playwright fetcher
│   └── selenium_browser.py    # Selenium fetcher (optional)
├── extractor.py               # Content extraction
├── validator.py               # Content quality validation
├── writer.py                  # JSONL output writer
├── pipeline.py                # Orchestration logic
├── models.py                  # Data models
├── logger.py                  # Metrics and statistics
├── config.py                  # Configuration loader
├── main.py                    # Entry point
├── setup.py                   # Cross-platform installer
└── requirements.txt           # Python dependencies
```

## Results

After running the scraper on all 500 training URLs, the following results were achieved:
```text
============================================================
SCRAPING QUALITY BENCHMARK RESULTS
============================================================
URLs evaluated: 500
Successful scrapes: 398 / 500
Success Rate: 79.6%

Overall Metrics (including failures as 0):
Avg F1: 0.4687
Avg Precision: 0.5110
Avg Recall: 0.4515

Quality Metrics (successful scrapes only):
Avg F1: 0.5798
Avg Precision: 0.6259
Avg Recall: 0.5601

Latency (seconds):
P50: 3.74s
P90: 14.89s
P95: 20.30s
Avg: 7.32s
============================================================
```

### Interpretation

- **Success Rate (79.6%)**: 398 out of 500 URLs were successfully scraped with valid content. The remaining 102 URLs returned HTTP errors (404, 403, 502) or empty content.
- **Average F1 (0.47)**: When counting failed URLs as zero, the overall F1 is 0.47. This is expected because failed URLs contribute nothing to the score.
- **Quality F1 (0.58)**: On successful scrapes only, the F1 reaches 0.58, indicating good content extraction quality.
- **Latency (7.32s average)**: Within the realistic budget of 5-10 seconds per URL. The P95 of 20.30s reflects the slower browser-based fallbacks for problematic sites.

### Key Observations

| Observation | Explanation |
|-------------|-------------|
| 79.6% success rate | Some URLs are expected to fail (404s, paywalls, blocked pages) |
| Precision (0.63) > Recall (0.56) | The extractor is conservative – it avoids pulling in noise at the cost of missing some relevant content |
| Browser fallback helped | Sites like inc.com, dogecoin.com, and localsearch.com.au were only accessible via Playwright/Selenium |
| Latency variation | HTTP-only requests average 3-4 seconds; browser-based requests add 10-20 seconds overhead |

## Testing

```bash
# Run all tests
python -m pytest

# Run with coverage
python -m pytest --cov=. --cov-report=term

# Run specific test file
python -m pytest tests/test_fetcher.py -v
```

| Category | Purpose | Tools |
|----------|---------|-------|
| Unit tests | Test individual functions in isolation | pytest, AsyncMock |
| Integration tests | Test component interactions | pytest, real HTTP requests |
| End-to-end tests | Test full pipeline on sample URLs | pytest with real train.csv |

### 10.2 Mock Configuration

All tests use mocked configuration to ensure isolation and reproducibility:

```python
@pytest.fixture
def mock_config():
    config = Mock()
    config.min_content_length = 500
    config.timeout = 10
    config.max_concurrent = 10
    return config
```

## Output Format

Results are saved in JSONL format (one JSON object per line):

```json
{"id": 1, "url": "https://...", "content": "extracted text...", "status_code": 200, "latency": 1.23}
```

## Troubleshooting

### Playwright browser not installed

```bash
python -m playwright install chromium
```

### Proxy connection issues

Check that `proxy.json` exists and has the correct format. The system uses port 65534 for HTTP requests.

### Selenium not working

Make sure Chrome is installed. The `webdriver-manager` will download the appropriate ChromeDriver automatically.

## License

MIT (for assignment purposes)

## Author
Alisa Rakhlina
aliska76@gmail.com
