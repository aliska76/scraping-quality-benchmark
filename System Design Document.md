# Tavily Scraping Assignment: System Design Document

## 1. Executive Summary

This document describes the architecture and design decisions for a production-grade web scraping system developed for the Tavily Scraping Quality Benchmark assignment. The system extracts meaningful content from 500 training URLs and 500 test URLs, balancing latency, accuracy, and cost while handling diverse content types including news articles, e-commerce pages, PDFs, JSON APIs, and JavaScript-heavy single-page applications.

### Design Goals

- Maximize F1 score (primary objective)
- Balance latency vs quality (fast HTTP vs browser fallback)
- Ensure high success rate under blocking conditions
- Support heterogeneous content types (HTML, PDF, JSON, JS)
- Maintain modular and extensible architecture

### F1 Optimization Strategy

- Precision: reduce boilerplate using trafilatura and readability
- Recall: fallback to browser for missing dynamic content
- Content length threshold tuning to avoid noise vs truncation
- Sliding window awareness: avoid excessive text extraction

### Sliding Window Impact on System Design

The scoring function (`score.py`) does not compare the entire extracted content with the ground truth. Instead, it:

- Tokenizes both extracted content and `truth_text`
- Uses a sliding window over the extracted content
- The window size equals the number of tokens in `truth_text`
- Finds the window with the highest overlap with `truth_text`
- Computes precision, recall, and F1 for that best-matching window

### Design Implications

This evaluation method directly influenced several architectural decisions:

| Decision | Impact on Sliding Window |
|----------|--------------------------|
| Avoid extracting full HTML or excessive content | Large noisy content reduces precision, as the correct segment becomes harder to isolate |
| Preserve natural text order | The sliding window relies on contiguous sequences of tokens; reordering paragraphs breaks matching |
| Use structured extractors (Trafilatura, Readability) | These tools preserve sentence structure and produce coherent text blocks, improving recall |
| Avoid aggressive normalization | Over-cleaning may break word boundaries or remove meaningful tokens, reducing overlap |
| Apply content length limits | Reduces noise while keeping the relevant segment likely within the extracted window |

Overall, the system is optimized to produce a clean, contiguous block of meaningful text where the relevant segment appears intact and discoverable by the sliding window.

## 2. Problem Analysis

### 2.1 Core Challenge

The assignment requires extracting content that matches the `truth_text` field while excluding noise (`lie_text`). The F1 metric is computed using a sliding window over the extracted text, meaning:

- Token order matters: the window searches for a continuous block of text most similar to `truth_text`
- Excessive content (raw HTML) dilutes the window and reduces precision
- Overly aggressive cleaning may remove needed sentences and reduce recall

### 2.2 Data Diversity

We analyzed the URLs from train.csv and test.csv to understand the content types. The goal was to determine whether a single extraction method would work or if we needed multiple strategies.

The table below shows what we found. The key observation: PDFs, JSON APIs, social media pages, and search engines all require different handling. A single HTTP request with trafilatura would fail on most of these cases.

This analysis directly shaped the architecture. We built a pipeline that can switch between multiple fetchers (HTTP, Playwright, Selenium) and multiple extractors (trafilatura, readability, pypdf, JSON formatter) depending on the detected page type.

| Category | Characteristics | Strategy |
|----------|-----------------|----------|
| PDF | `.pdf` in URL or Content-Type | pypdf text extraction |
| JSON API | `/api/`, `.json`, `application/json` | JSON formatting to text |
| Documentation | `/docs/`, `/api/`, `/reference/` | Trafilatura extraction |
| Article / Blog | `/news/`, `/blog/`, `/story/` | Trafilatura (optimized for text) |
| Corporate | `/company/`, `/about/`, `/team/` | Trafilatura + block extraction |
| E-commerce | `/products/`, `/shop/`, `/collections/` | Title, price, description extraction |
| Social Media | `threads.net`, `instagram.com` | Browser rendering required |
| Search Engine | `duckduckgo.com`, `google.com` | `nojs=1` parameter or Playwright |
| Redirect | Status 301/302, meta refresh | `follow_redirects=True` |
| Block Page | 403, CAPTCHA, Cloudflare | User-Agent rotation, proxy rotation |
| 404 / Broken | Status 404 | Return status immediately |

The diversity of content types is the reason the system has fallbacks, browser automation, and specialized extractors — not because of over-engineering, but because the data demands it.

### 2.3 Performance Requirements

- Realistic budget: 5-10 seconds per URL average
- 500 URLs total: approximately 1 hour of execution time
- Must support multilingual content without breaking

## 3. Architecture Overview

The system follows a modular pipeline architecture with clear separation of concerns:

```
CSV Input -> Task Queue -> Pipeline Orchestration -> Content Extraction -> Validation -> JSONL Output
```

Each component is replaceable and adheres to the Single Responsibility Principle (SRP).

## 4. Component Design

### 4.1 Configuration Loader

The configuration system supports JSON files and environment variables with a clear priority order:

1. Environment variables (highest priority)
2. `config/config.json` file
3. Default values (lowest priority)

Key configuration parameters:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `timeout` | 10 | Request timeout in seconds |
| `max_retries` | 2 | Maximum retry attempts |
| `max_concurrent` | 10 | Concurrent request limit |
| `min_content_length` | 500 | Minimum content length to consider good |
| `use_playwright` | false | Enable Playwright fallback |
| `use_selenium` | false | Enable Selenium fallback |
| `retry_without_compression` | true | Retry without gzip/brotli if garbled |
| `allow_direct_fallback` | false | Allow requests without proxy (dangerous) |

### 4.2 HTTP Fetcher

The HTTP fetcher implements a smart retry strategy with three attempts:

**Attempt 1: Proxy + Compression**
- Uses residential proxy from `proxy.json`
- Requests compressed response (gzip, deflate, br)
- Fastest and most economical

**Attempt 2: Direct + Compression** (only if `allow_direct_fallback=true`)
- Bypasses proxy when proxy returns errors (502, 452, 403)
- Keeps compression for speed

**Attempt 3: Same proxy + No Compression** (if `retry_without_compression=true`)
- Uses same proxy setting but requests `Accept-Encoding: identity`
- Solves garbled text issues caused by compression

The fetcher also includes automatic response decoding with multiple encoding fallbacks (UTF-8, latin-1, cp1252, iso-8859-1).

### 4.3 Browser Fetchers (Playwright and Selenium)
Some websites cannot be scraped with simple HTTP requests. They require JavaScript execution, handle user interactions, or actively block scripts that don't look like real browsers. For these cases, the system includes two browser-based fetchers.

Both fetchers are optional. They are disabled by default and only activated when explicitly enabled in the configuration file. This keeps the default behavior fast and lightweight.

**PlaywrightFetcher**

Playwright is the recommended browser automation tool for this system. It is modern, fast, and designed with async programming in mind, which fits well with the rest of the pipeline.

When enabled, Playwright launches a Chromium browser instance (in headless mode by default, meaning no visible window opens). It then:

- Rotates through different User-Agent strings taken from `user_agents.json` to avoid looking like a bot
- Sets a realistic browser context with a standard viewport size, English locale, and US timezone
- Uses the same residential proxy as the HTTP fetcher, with full authentication support
- Injects a stealth script before page load to hide automation fingerprints (like navigator.webdriver)

These steps make the browser appear more like a regular user, which helps bypass simple bot detection systems.

**SeleniumFetcher**

Selenium is an older but well-established browser automation tool. It serves as a fallback when Playwright encounters compatibility issues (for example, with certain proxy configurations or specific websites).

Selenium works similarly to Playwright but has some differences:

- It runs in headless mode by default, meaning no browser window appears. However, this is configurable. You can set `headless: false` in the selenium section of config.json to watch the browser navigate in real time. This can be useful when investigating why a particular page fails to load properly.
- Rotates User-Agent strings from the same configuration file
- Supports proxy authentication, but not natively. To work around this, the system creates a temporary Chrome extension that handles login and password. This extension is packaged into a ZIP file, loaded into the browser, and then deleted after the request finishes
- Selenium itself is synchronous, so the system runs it in a separate thread pool to avoid blocking the async event loop

Because Selenium is slower and requires temporary file handling, it is not the first choice. It exists as a safety net.

### How They Work Together ###

Both fetchers implement the same **BaseFetcher** interface, meaning the pipeline treats them identically. The order in which they are tried depends on the configuration. Typically, Playwright is tried first because it is faster and more modern. If it fails, Selenium is tried next. The pipeline continues to the next fetcher only when the previous one returns bad content or an error.

This design gives the system flexibility. If a website works with Playwright, great. If not, Selenium can still handle it. And if neither works, the system falls back to the original HTTP result.

### 4.4 Content Extractor

The extractor implements multiple extraction strategies:

| Strategy | Use Case | Library |
|----------|----------|---------|
| Trafilatura | General HTML pages (news, blogs, corporate) | `trafilatura` |
| Readability | Complex layouts, fallback for trafilatura | `readability-lxml` |
| JSON | API responses | `json` |
| Raw text | Final fallback, strip all HTML tags | regex |
| PDF | PDF document text extraction | `pypdf` |

The extractor automatically selects the appropriate strategy based on detected page type.

### 4.5 Content Validator

The validator checks extracted content quality using multiple criteria:

- HTTP status code (must be 200-399)
- Content length (minimum threshold configurable)
- Block page detection (Cloudflare, CAPTCHA, access denied)
- Quality scoring based on sentence structure and noise ratio

### 4.6 Pipeline Orchestration

The pipeline implements the core business logic with a chain-of-responsibility pattern:


1. HTTP request -> (status, content)

2. If content is bad (<500 chars) OR status != 200:
   -> Try browser (Playwright or Selenium)

3. If browser returns good content (>500 chars):
   -> Use browser's status and content
   -> ExtractMethod = browser

4. If browser returns bad content:
   -> Fall back to HTTP (status and content)
   -> BUT ExtractMethod = browser (because we tried)

This ensures that:
- HTTP status codes are preserved for 404/403/502 responses
- Browser content is used only when it provides genuine value
- The `extract_method` field accurately reflects which fetcher was attempted

## 5. Data Flow

### 5.1 Complete Processing Pipeline

``` text
main.py
   │
   ├── reads config.json and user_agents.json
   ├── loads proxy.json (residential proxy credentials)
   ├── creates HTTPFetcher with config parameters
   ├── optionally creates PlaywrightFetcher (if enabled)
   ├── optionally creates SeleniumFetcher (if enabled)
   │
   └── creates ScraperPipeline with fetcher chain
              │
              ▼
       pipeline.process(request)
              │
              ├── Step 1: Classify by URL (.pdf, .json, /api/, /blog/)
              │
              ├── Step 2: HTTP fetch with retry logic
              │        │
              │        └── HTTPFetcher.fetch() with smart compression retry
              │
              ├── Step 3: If HTTP fails or content bad -> try enabled browser fetchers
              │        │
              │        ├── PlaywrightFetcher.fetch() (if enabled)
              │        └── SeleniumFetcher.fetch() (if enabled, as fallback)
              │
              ├── Step 4: Detect content type from response
              │
              ├── Step 5: Extract content using appropriate strategy
              │
              ├── Step 6: Validate quality (length, block page detection)
              │
              ├── Step 7: Fallback to Readability or raw text if needed
              │
              └── Step 8: Return ScrapeResult (id, url, content, status, latency, method, type)

       pipeline.process_batch(requests)
              │
              └── asyncio.Semaphore(max_concurrent) limits parallelism
```

### 5.2 Batch Processing

The `process_batch` method uses `asyncio.Semaphore` to limit concurrent requests:

```python
semaphore = asyncio.Semaphore(max_concurrent)

async def process_one(req):
    async with semaphore:
        return await self.process(req)

results = await asyncio.gather(*[process_one(req) for req in requests])
```

This prevents overwhelming the proxy server or target websites.

## 6. Technology Stack
| Library | Version | Purpose | Rationale |
|---------|---------|---------|-----------|
| Python | 3.12.6 | Runtime | Required version for the assignment |
| httpx | >=0.27.0 | Async HTTP client | Fast, supports HTTP/2, proxy auth, follow redirects |
| trafilatura | >=1.0.0 | Content extraction | Optimized for news, blogs, academic papers |
| readability-lxml | >=0.8.0 | Fallback extraction | Extracts main content from complex HTML |
| pypdf | >=3.0.0 | PDF text extraction | Lightweight, pure Python, no external dependencies |
| playwright | >=1.40.0 | Browser automation | Modern, async, supports proxy auth, faster than Selenium |
| selenium | >=4.15.0 | Browser fallback when Playwright fails | Works with proxy via Chrome extension |

### 6.1 Selection Criteria

Each library was evaluated against four criteria:

1. **Popularity**: High download counts and GitHub stars
2. **License**: MIT or Apache (permissive for commercial use)
3. **Stability**: Not a personal "pet project", active maintenance
4. **Fit for purpose**: Specifically designed for the task, not just "exists"

### 6.2 Cross-Platform Compatibility

All dependencies work on Windows and macOS. The `setup.py` installer handles platform-specific differences automatically.

## 7. Quality Metrics

### 7.1 Success Criteria

| Metric | Definition |
|--------|------------|
| Success Rate | Percentage of URLs with status 200-399, non-empty content, no block page |
| Precision | Of tokens in best window, how many match truth_text |
| Recall | Of truth_text tokens, how many appear in best window |
| F1 | Harmonic mean of precision and recall |

### 7.2 Scoring Method

The provided `score.py` script uses a sliding window over the extracted content to find the best-matching region against `truth_text`. This method is sensitive to token order and continuous blocks of text.

## 8. Error Handling and Resilience

### 8.1 Retry Strategy

| Error Type | Action |
|------------|--------|
| Timeout (408) | Retry with same fetcher, up to max_retries |
| Connection error (503) | Retry with same fetcher |
| Proxy error (502) | Switch to direct connection if allowed |
| 403 Forbidden | Rotate User-Agent and retry |
| Garbled text | Retry without compression |
| 404 Not Found | Return immediately, no browser fallback |

### 8.2 Fallback Chain

```
HTTP (fast) -> Playwright (optional, medium) -> Selenium (optional, slow, more reliable) -> Error
```

Each fetcher is tried only if enabled in configuration. The pipeline preserves HTTP status codes even when browser fetchers are used.

Selenium and Playwright are disabled by default and only enabled via use_selenium: true in config.

### 8.3 Safety Considerations

**Direct connection without proxy is disabled by default (`allow_direct_fallback=false`)**

Performing requests without a proxy exposes your real IP address to target websites. This is dangerous for web scraping because sites can block your IP, and in production environments, you risk exposing internal infrastructure. The `allow_direct_fallback` parameter is set to `false` by default, meaning the system will never bypass the proxy unless explicitly enabled for debugging purposes.

**Maximum concurrent requests limited by `max_concurrent` parameter**

Sending too many requests simultaneously can overwhelm the proxy server, trigger rate limiting on target websites, or exhaust local system resources (file handles, memory, network sockets). The `max_concurrent` parameter limits parallel requests using `asyncio.Semaphore`, ensuring that at most N requests run at the same time. This protects both the proxy infrastructure and the target websites from aggressive scraping patterns.

**Temporary files (Selenium proxy extensions) are cleaned up after each request**

Selenium does not natively support proxy servers that require username and password authentication. To work around this limitation, the system creates a temporary Chrome extension that handles proxy authentication. This extension consists of a manifest file and a background script, which are packaged into a ZIP archive. These temporary files are created for each request and deleted immediately after the request completes. While this approach is not elegant, it is the simplest and most reliable way to make authenticated proxy requests with Selenium without introducing complex dependencies like `selenium-wire` (which caused installation issues on some systems).

## 9. Limitations and Future Improvements

### 9.1 Current Limitations

| Limitation | Impact | Mitigation |
|------------|--------|------------|
| Single proxy IP | Some sites may block the proxy | Documented, acceptable for assignment |
| No IP rotation | Rate limiting possible | Keep `max_concurrent` low |
| Selenium requires ChromeDriver | Installation complexity | `webdriver-manager` auto-installs |
| Playwright requires browser download | ~200MB disk space | Documented in setup instructions |

### 9.2 Future Enhancements

| Enhancement | Benefit | Priority |
|-------------|---------|----------|
| IP rotation with proxy pool | Bypass rate limiting and blocks | High |
| Configurable `max_attempts` per fetcher | Fine-grained retry control | Medium |
| Adaptive content length threshold | Better quality detection | Medium |
| Machine learning for page classification | More accurate strategy selection | Low |

## 10. Conclusion

The system successfully implements a modular, configurable scraping pipeline that handles diverse content types including static HTML, JavaScript-heavy SPAs, PDFs, and JSON APIs. The architecture prioritizes:

1. **Reliability**: Multi-stage fallback chain ensures maximum success rate
2. **Quality**: Adaptive extraction strategies optimize F1 score
3. **Engineering**: Clean separation of concerns, replaceable components
4. **Insights**: Comprehensive logging and metrics for analysis
5. **Feasibility**: Realistic trade-offs between speed, accuracy, and cost

The design is production-ready while remaining simple enough for the assignment context. All components are cross-platform and have been tested on both Windows and macOS.