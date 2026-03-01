#!/usr/bin/env python3
"""
Skill: AI Analyzer (Universal)
Analyzes filtered posts to find pain points, trends, solutions.
Platform-agnostic: works on Reddit, X, LinkedIn, or any source.

Input:  Standard data contract JSON (stdin or file)
Output: Data contract JSON with analysis in metadata (stdout or file)

Usage:
  cat filtered.json | python3 ai_analyzer.py
  python3 ai_analyzer.py -i filtered.json -o analyzed.json
  cat filtered.json | python3 ai_analyzer.py --provider anthropic

Pipe-friendly:
  python3 reddit_fetcher.py "..." | python3 keyword_filter.py "..." | python3 ai_analyzer.py
"""

import json
import sys
import argparse
import os


def build_prompt(data):
    """Build analysis prompt from data contract."""
    source = data.get("source", "unknown")
    source_id = data.get("source_id", "")
    keywords = data.get("metadata", {}).get("keywords", [])
    kw_str = ", ".join(keywords) if keywords else "general topics"

    chunks = []
    for p in data.get("posts", []):
        chunk = f"## [{p.get('title', '') or p.get('body', '')[:80]}] "
        chunk += f"(score:{p.get('score', 0)}, by:{p.get('author', '?')})\n"
        if p.get("body"):
            chunk += p["body"][:500] + "\n"
        if p.get("comments"):
            chunk += "Comments:\n"
            for c in p["comments"][:5]:
                chunk += f"- [{c.get('author', '?')}, +{c.get('score', 0)}] {c.get('body', '')[:300]}\n"
        chunks.append(chunk)

    content = "\n---\n".join(chunks)
    if len(content) > 14000:
        content = content[:14000] + "\n...(truncated)"

    return f"""Analyze these {source} posts from "{source_id}" filtered by: "{kw_str}".

Provide a structured analysis:

## 1. Top 10 Pain Points
Most mentioned challenges/frustrations related to "{kw_str}". Note who mentioned each.

## 2. Resolved / Partially Resolved
Discussions with working solutions or workarounds.

## 3. Most Popular Discussions
Highest-engagement posts/comments with key insights.

## 4. Emerging Trends
Patterns, new tools, or shifting opinions.

## 5. Key Takeaways
3-5 bullet summary.

---
Data ({len(data.get('posts', []))} posts from {source}):

{content}"""


def analyze_openai(prompt, model="gpt-4o-mini", base_url=None):
    from openai import OpenAI
    kwargs = {}
    if base_url:
        kwargs["base_url"] = base_url
    client = OpenAI(**kwargs)
    r = client.chat.completions.create(
        model=model, max_tokens=4000,
        messages=[
            {"role": "system", "content": "You are an expert analyst. Extract actionable insights from community discussions. Be specific, cite usernames when possible."},
            {"role": "user", "content": prompt}
        ]
    )
    return r.choices[0].message.content


def analyze_anthropic(prompt, model="claude-sonnet-4-5-20250929"):
    import anthropic
    client = anthropic.Anthropic()
    r = client.messages.create(
        model=model, max_tokens=4000,
        messages=[{"role": "user", "content": f"You are an expert analyst. Extract actionable insights from community discussions. Be specific, cite usernames when possible.\n\n{prompt}"}]
    )
    return r.content[0].text


def run(data, provider="openai", model=None, base_url=None):
    """Main entry point. Returns data contract with analysis added."""
    if not data.get("posts"):
        sys.stderr.write("[ai-analyzer] No posts to analyze\n")
        result = dict(data)
        result["metadata"] = dict(data.get("metadata", {}))
        result["metadata"]["analysis"] = "No posts to analyze."
        return result

    prompt = build_prompt(data)
    sys.stderr.write(f"[ai-analyzer] Analyzing {len(data['posts'])} posts with {provider}...\n")

    try:
        if provider == "anthropic" and not base_url:
            m = model or "claude-sonnet-4-5-20250929"
            analysis = analyze_anthropic(prompt, m)
        else:
            m = model or "gpt-4o-mini"
            analysis = analyze_openai(prompt, m, base_url)
        sys.stderr.write("[ai-analyzer] Done\n")
    except Exception as e:
        sys.stderr.write(f"[ai-analyzer] Failed: {e}\n")
        analysis = f"*AI analysis failed: {e}*"

    result = dict(data)
    result["metadata"] = dict(data.get("metadata", {}))
    result["metadata"]["analysis"] = analysis

    return result


def main():
    parser = argparse.ArgumentParser(description="AI-analyze filtered posts for pain points and trends.")
    parser.add_argument("-i", "--input", help="Input JSON (default: stdin)")
    parser.add_argument("-o", "--output", help="Output JSON (default: stdout)")
    parser.add_argument("--provider", default="openai", choices=["openai", "anthropic"])
    parser.add_argument("--model", help="Model name")
    parser.add_argument("--base-url", help="Custom API base URL")
    args = parser.parse_args()

    if args.input:
        with open(args.input, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = json.load(sys.stdin)

    result = run(data, args.provider, args.model, args.base_url)

    output = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
    else:
        print(output)


if __name__ == "__main__":
    main()
