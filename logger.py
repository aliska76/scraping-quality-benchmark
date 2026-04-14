"""
Metrics logger for the scraping pipeline.
Collects statistics for analysis and reporting.
"""

import time
import csv
from pathlib import Path
from typing import List, Dict, Any
from dataclasses import dataclass, field

from models import ScrapeResult, ExtractMethod, PageType


@dataclass
class ScrapeStats:
    """Statistics aggregated from scrape results."""
    total: int = 0
    success: int = 0           # status_code < 400 and content > 200 chars
    failed_http: int = 0       # status_code >= 400
    failed_extract: int = 0    # content <= 200 chars but status ok
    blocked: int = 0           # block page detected
    timeout: int = 0           # status_code 408
    
    # By method
    by_method: Dict[str, int] = field(default_factory=dict)
    
    # By page type
    by_page_type: Dict[str, int] = field(default_factory=dict)
    
    # By status code
    by_status: Dict[int, int] = field(default_factory=dict)
    
    # Latency metrics
    latencies: List[float] = field(default_factory=list)
    
    # Errors
    errors: List[Dict] = field(default_factory=list)


class ScraperLogger:
    """
    Collects metrics during scraping for analysis.
    Can save results to CSV and print summaries.
    """
    
    def __init__(self, log_dir: str = "logs"):
        """
        Initialize logger.
        
        Args:
            log_dir: Directory to store log files
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self.stats = ScrapeStats()
        self.results: List[ScrapeResult] = []
    
    def log_result(self, result: ScrapeResult):
        """Log a single scrape result."""
        self.results.append(result)
        
        # Update counters
        self.stats.total += 1
        
        # Update status codes
        self.stats.by_status[result.status_code] = self.stats.by_status.get(result.status_code, 0) + 1
        
        # Track timeouts
        if result.status_code == 408:
            self.stats.timeout += 1
        
        # Track block pages
        if result.page_type == PageType.BLOCKED:
            self.stats.blocked += 1
        
        # Track HTTP errors
        if result.status_code >= 400:
            self.stats.failed_http += 1
            self.stats.success = self.stats.total - self.stats.failed_http - self.stats.failed_extract
        else:
            # Check extraction quality
            if len(result.content) > 200:
                self.stats.success += 1
            else:
                self.stats.failed_extract += 1
        
        # Track by method
        method = result.extract_method.value
        self.stats.by_method[method] = self.stats.by_method.get(method, 0) + 1
        
        # Track by page type
        page_type = result.page_type.value
        self.stats.by_page_type[page_type] = self.stats.by_page_type.get(page_type, 0) + 1
        
        # Track latency
        if result.latency > 0:
            self.stats.latencies.append(result.latency)
    
    def log_error(self, url: str, error_type: str, error_msg: str = ""):
        """Log an error that occurred during scraping."""
        self.stats.errors.append({
            "url": url,
            "error_type": error_type,
            "error_msg": error_msg,
            "timestamp": time.time()
        })
    
    def get_summary(self) -> Dict[str, Any]:
        """Get aggregated statistics as dictionary."""
        stats = self.stats
        
        # Calculate latency percentiles
        latencies = sorted(stats.latencies)
        n = len(latencies)
        
        def percentile(p):
            if not latencies:
                return 0
            k = int((n - 1) * p / 100)
            return round(latencies[k], 2)
        
        # Calculate success rate
        success_rate = (stats.success / stats.total * 100) if stats.total > 0 else 0
        
        return {
            "total": stats.total,
            "success": stats.success,
            "failed_http": stats.failed_http,
            "failed_extract": stats.failed_extract,
            "blocked": stats.blocked,
            "timeout": stats.timeout,
            "success_rate": round(success_rate, 1),
            "by_method": stats.by_method,
            "by_page_type": stats.by_page_type,
            "by_status": stats.by_status,
            "latency": {
                "avg": round(sum(latencies) / n, 2) if latencies else 0,
                "min": percentile(0),
                "p50": percentile(50),
                "p90": percentile(90),
                "p95": percentile(95),
                "p99": percentile(99),
                "max": percentile(100),
            }
        }
    
    def print_summary(self):
        """Print formatted summary to console."""
        s = self.get_summary()
        
        print("\n" + "=" * 60)
        print("  SCRAPING STATISTICS")
        print("=" * 60)
        
        print(f"\nOVERVIEW:")
        print(f"  Total URLs:        {s['total']}")
        print(f"  Successful:        {s['success']} ({s['success_rate']}%)")
        print(f"  Failed (HTTP):     {s['failed_http']}")
        print(f"  Failed (extract):  {s['failed_extract']}")
        print(f"  Blocked pages:     {s['blocked']}")
        print(f"  Timeouts:          {s['timeout']}")
        
        print(f"\nLATENCY (seconds):")
        print(f"  Average:           {s['latency']['avg']}")
        print(f"  P50:               {s['latency']['p50']}")
        print(f"  P90:               {s['latency']['p90']}")
        print(f"  P95:               {s['latency']['p95']}")
        
        print(f"\nBY EXTRACT METHOD:")
        for method, count in sorted(s['by_method'].items(), key=lambda x: -x[1]):
            print(f"  {method:15} : {count}")
        
        print(f"\nBY PAGE TYPE:")
        for ptype, count in sorted(s['by_page_type'].items(), key=lambda x: -x[1]):
            print(f"  {ptype:15} : {count}")
        
        print(f"\nBY STATUS CODE:")
        for status, count in sorted(s['by_status'].items()):
            print(f"  {status:15} : {count}")
        
        print("=" * 60)
    
    def save_to_csv(self, filename: str = None):
        """Save results to CSV file."""
        if filename is None:
            filename = f"scrape_results_{int(time.time())}.csv"
        
        filepath = self.log_dir / filename
        
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['id', 'url', 'status_code', 'latency', 'extract_method', 'page_type', 'content_length'])
            
            for r in self.results:
                writer.writerow([
                    r.id,
                    r.url,
                    r.status_code,
                    r.latency,
                    r.extract_method.value,
                    r.page_type.value,
                    len(r.content)
                ])
        
        print(f"[INFO] Results saved to {filepath}")
    
    def save_summary_to_json(self, filename: str = None):
        """Save summary statistics to JSON file."""
        if filename is None:
            filename = f"summary_{int(time.time())}.json"
        
        filepath = self.log_dir / filename
        
        import json
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.get_summary(), f, indent=2, ensure_ascii=False)
        
        print(f"[INFO] Summary saved to {filepath}")
    
    def reset(self):
        """Reset all statistics."""
        self.stats = ScrapeStats()
        self.results = []


# Singleton instance
_logger_instance = None

def get_logger(log_dir: str = "logs") -> ScraperLogger:
    """Get global logger instance (Singleton)."""
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = ScraperLogger(log_dir)
    return _logger_instance