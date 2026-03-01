#!/usr/bin/env python3
"""
Skill: Markdown Reporter (Universal)
Generates a structured Markdown report from analyzed data.
Platform-agnostic: works on Reddit, X, LinkedIn, or any source.

Input:  Standard data contract JSON with analysis (stdin or file)
Output: Markdown report (stdout or file)

Usage:
  cat analyzed.json | python3 markdown_reporter.py
  python3 markdown_reporter.py -i analyzed.json -o report.md

Full pipe:
  python3 reddit_fetcher.py "..." | python3 keyword_filter.py "..." | python3 ai_analyzer.py | python3 markdown_reporter.py -o report.md
"""

import json
import sys
import re
import argparse
from datetime import datetime


SOURCE_LABELS = {
    "reddit": "Reddit",
    "x": "X (Twitter)",
    "linkedin": "LinkedIn",
    "discord": "Discord",
    "github": "GitHub",
    "custom": "Custom Source"
}


def run(data, output_file=None):
    """Main entry point. Returns Markdown string."""
    source = data.get("source", "unknown")
    source_label = SOURCE_LABELS.get(source, source)
    source_id = data.get("source_id", "")
    meta = data.get("metadata", {})
    posts = data.get("posts", [])

    keywords = meta.get("keywords", [])
    analysis = meta.get("analysis", "*No analysis available*")
    total = meta.get("total_posts", len(posts))
    matched = meta.get("matched_posts", len(posts))
    kw_hits = meta.get("keyword_hits", {})
    fetched_at = meta.get("fetched_at", "")

    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Build report
    report = f"""# Research Report: {source_label} — {source_id}

**Generated:** {now}
**Source:** {source_label}
**Target:** {source_id}
**Keywords:** {', '.join(keywords) if keywords else 'N/A'}
**Posts scanned:** {total} | **Matched:** {matched}
"""

    if kw_hits:
        report += "\n**Keyword distribution:**\n"
        for kw, count in sorted(kw_hits.items(), key=lambda x: x[1], reverse=True):
            report += f"- `{kw}`: {count} hits\n"

    report += f"""
---

{analysis}

---

## Appendix: Top Matched Posts (by score)

"""
    sorted_posts = sorted(posts, key=lambda x: x.get("score", 0), reverse=True)[:15]

    for i, p in enumerate(sorted_posts, 1):
        created = p.get("created_at", "")
        if created:
            try:
                dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                date_str = dt.strftime("%Y-%m-%d")
            except:
                date_str = created[:10]
        else:
            date_str = "?"

        title = p.get("title", "") or p.get("body", "")[:80] + "..."
        body = p.get("body", "")
        snippet = (body[:250].replace("\n", " ") + "...") if body else "(no text)"
        url = p.get("url", "")
        author = p.get("author", "?")
        score = p.get("score", 0)
        num_comments = len(p.get("comments", []))

        report += f"""### {i}. {title}
- **Score:** {score} | **Comments:** {num_comments} | **Date:** {date_str} | **By:** {author}
- **URL:** {url}
- {snippet}

"""

    sys.stderr.write(f"[markdown-reporter] Report: {len(posts)} posts, {len(sorted_posts)} in appendix\n")

    # Output
    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(report)
        sys.stderr.write(f"[markdown-reporter] Saved to {output_file}\n")

    return report


def main():
    parser = argparse.ArgumentParser(description="Generate Markdown report from analyzed data.")
    parser.add_argument("-i", "--input", help="Input JSON (default: stdin)")
    parser.add_argument("-o", "--output", help="Output .md file (default: stdout)")
    args = parser.parse_args()

    if args.input:
        with open(args.input, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = json.load(sys.stdin)

    report = run(data, args.output)
    if not args.output:
        print(report)


if __name__ == "__main__":
    main()
