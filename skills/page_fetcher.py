#!/usr/bin/env python3
"""
Skill: Page Fetcher
Fetch web pages and store clean text snapshots for diff comparison.

Handles:
- Static HTML pages (requests + BeautifulSoup)
- JS-rendered pages (Playwright, optional)
- Structured changelog extraction
- Landing page text extraction (strips nav/footer noise)

Usage:
  python3 page_fetcher.py "https://manus.im/changelog"
  python3 page_fetcher.py "https://manus.im/changelog" --type changelog
  python3 page_fetcher.py "https://cursor.com/pricing" --type pricing --js
"""

import os
import sys
import json
import hashlib
import re
import argparse
import requests
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "data", "snapshots")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def ensure_dirs(competitor_id):
    path = os.path.join(DATA_DIR, competitor_id)
    os.makedirs(path, exist_ok=True)
    return path


def fetch_html(url, use_js=False):
    """Fetch page HTML. Use Playwright for JS-rendered pages."""
    if use_js:
        try:
            import asyncio
            from playwright.async_api import async_playwright

            async def _fetch():
                async with async_playwright() as p:
                    browser = await p.chromium.launch(headless=True)
                    page = await browser.new_page()
                    await page.goto(url, wait_until="networkidle", timeout=30000)
                    await page.wait_for_timeout(2000)
                    html = await page.content()
                    await browser.close()
                    return html

            return asyncio.run(_fetch())
        except ImportError:
            sys.stderr.write("[page-fetcher] Playwright not installed, falling back to requests\n")

    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    r.encoding = r.apparent_encoding or "utf-8"
    return r.text


def extract_text(html, page_type="general"):
    """Extract meaningful text from HTML, removing boilerplate."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        # Fallback: basic regex extraction
        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', '\n', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    soup = BeautifulSoup(html, "html.parser")

    # Remove noise elements
    for tag in soup.find_all(["script", "style", "noscript", "iframe", "svg"]):
        tag.decompose()

    if page_type == "changelog":
        return _extract_changelog(soup)
    elif page_type == "pricing":
        return _extract_pricing(soup)
    elif page_type == "landing_page":
        return _extract_landing(soup)
    else:
        return _extract_general(soup)


def _extract_changelog(soup):
    """Extract changelog entries — look for dated sections."""
    entries = []

    # Common changelog patterns
    # Pattern 1: sections with date headers
    for header in soup.find_all(["h1", "h2", "h3", "h4"]):
        text = header.get_text(strip=True)
        # Look for date-like headers
        if re.search(r'\d{4}[-/.]\d{1,2}[-/.]\d{1,2}|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)', text, re.IGNORECASE):
            # Get content until next header
            content = []
            for sibling in header.find_next_siblings():
                if sibling.name in ["h1", "h2", "h3", "h4"]:
                    break
                t = sibling.get_text(strip=True)
                if t:
                    content.append(t)
            entries.append(f"## {text}\n" + "\n".join(content))

    if entries:
        return "\n\n---\n\n".join(entries)

    # Pattern 2: article/post containers
    for container in soup.find_all(["article", "section"]):
        cls = " ".join(container.get("class", []))
        if any(kw in cls.lower() for kw in ["changelog", "release", "update", "post", "entry"]):
            entries.append(container.get_text(separator="\n", strip=True))

    if entries:
        return "\n\n---\n\n".join(entries)

    # Fallback: main content area
    main = soup.find("main") or soup.find("article") or soup.find(id=re.compile(r"content|main", re.I))
    if main:
        return main.get_text(separator="\n", strip=True)

    return _extract_general(soup)


def _extract_pricing(soup):
    """Extract pricing information — plans, prices, features."""
    # Remove nav/footer
    for tag in soup.find_all(["nav", "footer", "header"]):
        tag.decompose()

    # Look for pricing containers
    pricing_text = []
    for el in soup.find_all(class_=re.compile(r"pric|plan|tier|package", re.I)):
        pricing_text.append(el.get_text(separator="\n", strip=True))

    if pricing_text:
        return "\n\n---\n\n".join(pricing_text)

    # Fallback
    main = soup.find("main") or soup.body
    if main:
        return main.get_text(separator="\n", strip=True)
    return soup.get_text(separator="\n", strip=True)


def _extract_landing(soup):
    """Extract landing page — hero, features, CTA."""
    # Remove nav/footer
    for tag in soup.find_all(["nav", "footer"]):
        tag.decompose()

    sections = []

    # Hero section
    hero = soup.find(class_=re.compile(r"hero|banner|jumbotron", re.I))
    if hero:
        sections.append("[HERO]\n" + hero.get_text(separator="\n", strip=True))

    # Feature sections
    for el in soup.find_all(class_=re.compile(r"feature|benefit|section", re.I)):
        text = el.get_text(separator="\n", strip=True)
        if len(text) > 50:
            sections.append(text)

    if sections:
        return "\n\n---\n\n".join(sections)

    # Fallback
    main = soup.find("main") or soup.body
    if main:
        return main.get_text(separator="\n", strip=True)
    return soup.get_text(separator="\n", strip=True)


def _extract_general(soup):
    """General text extraction."""
    for tag in soup.find_all(["nav", "footer", "header"]):
        tag.decompose()
    main = soup.find("main") or soup.body or soup
    text = main.get_text(separator="\n", strip=True)
    # Clean up excessive whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text


def save_snapshot(competitor_id, monitor_label, text, url):
    """Save a text snapshot with metadata."""
    snap_dir = ensure_dirs(competitor_id)
    safe_label = re.sub(r'[^\w\-]', '_', monitor_label.lower())
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    content_hash = hashlib.sha256(text.encode()).hexdigest()[:12]

    snapshot = {
        "competitor_id": competitor_id,
        "monitor_label": monitor_label,
        "url": url,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "content_hash": content_hash,
        "content_length": len(text),
        "content": text
    }

    filename = f"{safe_label}_{timestamp}.json"
    filepath = os.path.join(snap_dir, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)

    return filepath, content_hash


def get_latest_snapshot(competitor_id, monitor_label):
    """Get the most recent snapshot for a monitor."""
    snap_dir = os.path.join(DATA_DIR, competitor_id)
    if not os.path.exists(snap_dir):
        return None

    safe_label = re.sub(r'[^\w\-]', '_', monitor_label.lower())
    files = sorted([
        f for f in os.listdir(snap_dir)
        if f.startswith(safe_label) and f.endswith(".json")
    ])

    if not files:
        return None

    latest = os.path.join(snap_dir, files[-1])
    with open(latest, "r", encoding="utf-8") as f:
        return json.load(f)


def fetch_and_save(url, competitor_id, monitor_label, page_type="general", use_js=False):
    """Fetch a page and save snapshot. Returns (filepath, is_new, hash)."""
    sys.stderr.write(f"[page-fetcher] Fetching {url}...\n")

    html = fetch_html(url, use_js)
    text = extract_text(html, page_type)

    # Check if content changed since last snapshot
    previous = get_latest_snapshot(competitor_id, monitor_label)
    prev_hash = previous["content_hash"] if previous else None

    filepath, new_hash = save_snapshot(competitor_id, monitor_label, text, url)

    is_changed = prev_hash is not None and prev_hash != new_hash
    is_first = prev_hash is None

    if is_first:
        sys.stderr.write(f"[page-fetcher] First snapshot saved: {filepath}\n")
    elif is_changed:
        sys.stderr.write(f"[page-fetcher] ⚠️  CHANGE DETECTED! {monitor_label}\n")
    else:
        sys.stderr.write(f"[page-fetcher] No change.\n")

    return {
        "filepath": filepath,
        "is_changed": is_changed,
        "is_first": is_first,
        "content_hash": new_hash,
        "content_length": len(text),
        "competitor_id": competitor_id,
        "monitor_label": monitor_label,
        "url": url
    }


def main():
    parser = argparse.ArgumentParser(description="Fetch and snapshot web pages")
    parser.add_argument("url", help="URL to fetch")
    parser.add_argument("--id", default="unknown", help="Competitor ID")
    parser.add_argument("--label", default="page", help="Monitor label")
    parser.add_argument("--type", default="general", choices=["changelog", "pricing", "landing_page", "general"])
    parser.add_argument("--js", action="store_true", help="Use Playwright for JS-rendered pages")
    args = parser.parse_args()

    result = fetch_and_save(args.url, args.id, args.label, args.type, args.js)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
