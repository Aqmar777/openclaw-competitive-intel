#!/usr/bin/env python3
"""
Skill: Change Analyzer
Uses AI to interpret what competitive changes mean strategically.

Input: diff_detector output (JSON with changes)
Output: Strategic analysis in Markdown

Usage:
  python3 diff_detector.py --id manus --label "Product Updates" | python3 change_analyzer.py
  python3 change_analyzer.py -i diff_result.json
"""

import os
import sys
import json
import argparse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def build_prompt(diff_data):
    """Build AI analysis prompt from diff data."""
    competitor = diff_data.get("competitor_id", "unknown")
    label = diff_data.get("monitor_label", "unknown")
    url = diff_data.get("url", "")
    changes = diff_data.get("changes", {})
    old_content = diff_data.get("old_content", "")[:2000]
    new_content = diff_data.get("new_content", "")[:2000]
    added = changes.get("added_content", [])
    removed = changes.get("removed_content", [])

    prompt = f"""You are a competitive intelligence analyst. Analyze the following changes detected on a competitor's website.

## Context
Competitor: {competitor}
Page monitored: {label}
URL: {url}
Change severity: {changes.get('severity', 'unknown')}
Change type: {changes.get('change_type', 'unknown')}
Lines added: {changes.get('lines_added', 0)}
Lines removed: {changes.get('lines_removed', 0)}

## Previous Content (excerpt)
{old_content}

## Current Content (excerpt)
{new_content}

## Key Additions
{chr(10).join('+ ' + a for a in added[:15])}

## Key Removals
{chr(10).join('- ' + r for r in removed[:15])}

## Your Analysis
Provide a strategic analysis in the following structure:

### 1. What Changed (factual summary)
Describe the specific changes in 2-3 sentences.

### 2. What It Means (strategic interpretation)
- What does this change suggest about their product direction?
- Are they targeting a new audience, solving a new problem, or shifting strategy?
- Is this a response to market pressure or a proactive move?

### 3. Competitive Impact
- How does this affect our positioning?
- Should we respond? If so, how?

### 4. Action Items
List 1-3 specific things we should do in response.

### 5. Urgency
Rate: 🔴 High (respond this week) / 🟡 Medium (respond this month) / 🟢 Low (monitor only)

Be concise and actionable. Don't speculate beyond what the data supports.
"""
    return prompt


def analyze(diff_data, provider="openai", model=None, base_url=None):
    """Run AI analysis on diff data."""
    if diff_data.get("status") != "changed":
        return f"No analysis needed: {diff_data.get('status', 'unknown')}"

    prompt = build_prompt(diff_data)

    try:
        if provider == "anthropic" and not base_url:
            import anthropic
            m = model or "claude-sonnet-4-5-20250929"
            client = anthropic.Anthropic()
            r = client.messages.create(
                model=m, max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
                system="You are a competitive intelligence analyst. Be concise and strategic."
            )
            return r.content[0].text
        else:
            from openai import OpenAI
            kwargs = {}
            if base_url:
                kwargs["base_url"] = base_url
            m = model or "gpt-4o-mini"
            client = OpenAI(**kwargs)
            r = client.chat.completions.create(
                model=m, max_tokens=2000,
                messages=[
                    {"role": "system", "content": "You are a competitive intelligence analyst. Be concise and strategic."},
                    {"role": "user", "content": prompt}
                ]
            )
            return r.choices[0].message.content
    except Exception as e:
        return f"AI analysis failed: {e}"


def main():
    parser = argparse.ArgumentParser(description="AI analysis of competitive changes")
    parser.add_argument("-i", "--input", help="Diff result JSON file")
    parser.add_argument("--provider", default="openai", choices=["openai", "anthropic"])
    parser.add_argument("--model", help="Model name")
    parser.add_argument("--base-url", help="Custom API base URL")
    args = parser.parse_args()

    if args.input:
        with open(args.input) as f:
            diff_data = json.load(f)
    elif not sys.stdin.isatty():
        diff_data = json.load(sys.stdin)
    else:
        print("Provide input via -i or stdin pipe")
        sys.exit(1)

    result = analyze(diff_data, args.provider, args.model, args.base_url)
    print(result)


if __name__ == "__main__":
    main()
