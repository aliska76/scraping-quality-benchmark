#!/usr/bin/env python3
"""
Scoring script for the Tavily Scraping Assignment.

Evaluates your scraping results against the training set ground truth.
Use this to measure and improve your scraper before submitting test results.

Usage:
    python score.py --results results.jsonl --ground-truth train.csv

Your results file should be a JSONL file (one JSON object per line) with this schema:
    {"id": 1, "url": "https://...", "content": "extracted text or markdown...", "status_code": 200, "latency": 1.23, "format": "markdown"}

Fields:
    - id (required): Task ID matching the CSV
    - url (required): The URL that was scraped
    - content (required): Extracted page content (text or markdown)
    - status_code (required): HTTP status code (e.g., 200, 403, 500)
    - latency (optional): Time in seconds to scrape the URL
    - format (optional): "markdown" or "text" (default: "text"). If "markdown",
      formatting markers will be stripped before scoring.
"""

import argparse
import csv
import json
import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

def smart_tokenize(text: str) -> list[str]:
    """Tokenize text into lowercase words/phrases for comparison."""
    return re.findall(r"\d+/\d+|[\w'-]+", (text or "").lower())


# ---------------------------------------------------------------------------
# Markdown stripping
# ---------------------------------------------------------------------------

def strip_markdown(md: str) -> str:
    """Remove markdown formatting to get plain text for scoring."""
    if not md:
        return ""
    text = md
    text = re.sub(r"```[\s\S]*?```", " ", text)
    text = re.sub(r"`[^`]+`", " ", text)
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"^[#>\-\*\+\s]+", "", text, flags=re.MULTILINE)
    text = re.sub(r"[*_]{1,3}([^*_]+)[*_]{1,3}", r"\1", text)
    text = re.sub(r"\|", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ---------------------------------------------------------------------------
# Block page detection
# ---------------------------------------------------------------------------

BLOCK_MARKERS = [
    "attention required",
    "cloudflare",
    "verify you are a human",
    "access denied",
    "bot detection",
    "datadome",
    "akamai bot manager",
    "imperva",
    "sucuri website firewall",
]


def is_block_page(text: str) -> bool:
    """Detect if the content is a CAPTCHA/block page rather than real content."""
    if not text:
        return False
    t = text.lower()
    return any(marker in t for marker in BLOCK_MARKERS)


# ---------------------------------------------------------------------------
# Quality scoring (sliding window)
# ---------------------------------------------------------------------------

def score_one(content: str, truth_text: str, lie_text: str, status_code: int,
              content_format: str = "text") -> dict:
    """
    Score a single scrape result against ground truth.

    Returns dict with: success, precision, recall, f1
    """
    # Strip markdown if needed
    if content_format == "markdown":
        content = strip_markdown(content)

    content_tokens = smart_tokenize(content)
    truth_tokens = smart_tokenize(truth_text)
    lie_tokens = smart_tokenize(lie_text)

    # Window-based scoring: find the best-matching window in content
    # that is the same length as the truth text
    def window_scores(content_tokens, imp_tokens):
        if not content_tokens or not imp_tokens:
            return 0.0, 0.0, 0.0
        win = max(len(imp_tokens), 1)
        best_recall = 0.0
        best_precision = 0.0
        imp_set = set(imp_tokens)
        for i in range(0, max(len(content_tokens) - win + 1, 1)):
            window = content_tokens[i:i + win]
            wset = set(window)
            recall = len(wset & imp_set) / max(len(imp_set), 1)
            precision = len(wset & imp_set) / max(len(wset), 1)
            if (recall > best_recall) or (
                abs(recall - best_recall) < 1e-9 and precision > best_precision
            ):
                best_recall = recall
                best_precision = precision
        if best_recall + best_precision > 0:
            f1 = 2 * (best_precision * best_recall) / (best_precision + best_recall)
        else:
            f1 = 0.0
        return best_recall, best_precision, f1

    recall, precision, f1 = window_scores(content_tokens, truth_tokens)

    # Determine success
    if not truth_tokens and not lie_tokens:
        success = False
    else:
        success = bool(
            (status_code is not None and 200 <= int(status_code) < 400)
            and bool(content)
            and len(content.strip()) > 0
            and not is_block_page(content)
        )

    return {
        "success": success,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Score scraping results against ground truth."
    )
    parser.add_argument(
        "--results", required=True,
        help="Path to your results JSONL file."
    )
    parser.add_argument(
        "--ground-truth", required=True,
        help="Path to ground truth CSV (train.csv)."
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Print per-URL scores."
    )
    args = parser.parse_args()

    # Load ground truth
    ground_truth = {}
    with open(args.ground_truth, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ground_truth[str(row["id"])] = row

    # Load results
    results = {}
    with open(args.results, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                results[str(obj["id"])] = obj
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Warning: Skipping line {line_num}: {e}")

    print(f"Ground truth entries: {len(ground_truth)}")
    print(f"Result entries: {len(results)}")

    # Score each
    scores = []
    latencies = []
    missing = 0

    for task_id, truth in sorted(ground_truth.items(), key=lambda x: int(x[0])):
        if task_id not in results:
            missing += 1
            scores.append({
                "id": task_id,
                "url": truth["url"],
                "success": False,
                "precision": 0.0,
                "recall": 0.0,
                "f1": 0.0,
            })
            continue

        result = results[task_id]
        content = result.get("content", "") or ""
        status_code = result.get("status_code", 0) or 0
        content_format = result.get("format", "text") or "text"
        latency = result.get("latency")

        s = score_one(
            content=content,
            truth_text=truth.get("truth_text", ""),
            lie_text=truth.get("lie_text", ""),
            status_code=status_code,
            content_format=content_format,
        )
        s["id"] = task_id
        s["url"] = truth["url"]
        scores.append(s)

        if latency is not None:
            latencies.append(float(latency))

    if missing:
        print(f"Missing results for {missing} URLs (counted as failures)\n")

    # Aggregate
    n = len(scores)
    success_count = sum(1 for s in scores if s["success"])
    success_rate = success_count / n if n else 0

    avg_f1 = sum(s["f1"] for s in scores) / n if n else 0
    avg_precision = sum(s["precision"] for s in scores) / n if n else 0
    avg_recall = sum(s["recall"] for s in scores) / n if n else 0

    # Successful-only metrics
    successful = [s for s in scores if s["success"]]
    if successful:
        succ_f1 = sum(s["f1"] for s in successful) / len(successful)
        succ_precision = sum(s["precision"] for s in successful) / len(successful)
        succ_recall = sum(s["recall"] for s in successful) / len(successful)
    else:
        succ_f1 = succ_precision = succ_recall = 0

    print("=" * 60)
    print("  SCRAPING QUALITY BENCHMARK RESULTS")
    print("=" * 60)
    print(f"  URLs evaluated:     {n}")
    print(f"  Successful scrapes: {success_count} / {n}")
    print(f"  Success Rate:       {success_rate:.1%}")
    print()
    print("  Overall Metrics (including failures as 0):")
    print(f"    Avg F1:           {avg_f1:.4f}")
    print(f"    Avg Precision:    {avg_precision:.4f}")
    print(f"    Avg Recall:       {avg_recall:.4f}")
    print()
    print("  Quality Metrics (successful scrapes only):")
    print(f"    Avg F1:           {succ_f1:.4f}")
    print(f"    Avg Precision:    {succ_precision:.4f}")
    print(f"    Avg Recall:       {succ_recall:.4f}")

    if latencies:
        latencies.sort()
        ln = len(latencies)
        def pct(p):
            k = int((ln - 1) * p / 100)
            return latencies[k]
        print()
        print("  Latency (seconds):")
        print(f"    P50:              {pct(50):.2f}s")
        print(f"    P90:              {pct(90):.2f}s")
        print(f"    P95:              {pct(95):.2f}s")
        print(f"    Avg:              {sum(latencies)/ln:.2f}s")

    print("=" * 60)

    # Verbose: per-URL breakdown
    if args.verbose:
        print("\nPer-URL Scores:")
        print(f"{'ID':>5}  {'Success':>7}  {'F1':>6}  {'Prec':>6}  {'Recall':>6}  URL")
        print("-" * 90)
        for s in scores:
            mark = "OK" if s["success"] else "FAIL"
            print(f"{s['id']:>5}  {mark:>7}  {s['f1']:.4f}  {s['precision']:.4f}  {s['recall']:.4f}  {s['url'][:50]}")


if __name__ == "__main__":
    main()
