#!/usr/bin/env python3
"""
Skill: Keyword Filter (Universal)
Filters posts + comments by keywords. Platform-agnostic.

Input:  Standard data contract JSON (stdin or file)
Output: Filtered data contract JSON (stdout or file)

Usage:
  cat data.json | python3 keyword_filter.py "AI, automation, pain point"
  python3 keyword_filter.py "AI, automation" -i data.json -o filtered.json

Pipe-friendly:
  python3 reddit_fetcher.py "https://..." | python3 keyword_filter.py "keyword1, keyword2"
"""

import json
import sys
import argparse


def filter_posts(data, keywords):
    """Filter posts and comments by keyword match. Returns new data contract."""
    kw_lower = [k.lower().strip() for k in keywords]
    filtered_posts = []
    keyword_hits = {k: 0 for k in kw_lower}

    for post in data.get("posts", []):
        title_l = post.get("title", "").lower()
        body_l = post.get("body", "").lower()

        # Check which keywords hit in post
        post_keywords = [k for k in kw_lower if k in title_l or k in body_l]
        post_hit = len(post_keywords) > 0

        # Check comments
        matched_comments = []
        for c in post.get("comments", []):
            c_body = c.get("body", "").lower()
            c_keywords = [k for k in kw_lower if k in c_body]
            if c_keywords:
                matched_comments.append(c)
                for k in c_keywords:
                    keyword_hits[k] += 1

        if post_hit or matched_comments:
            filtered_post = dict(post)
            if matched_comments:
                # Keep only matched comments
                filtered_post["comments"] = matched_comments
            for k in post_keywords:
                keyword_hits[k] += 1
            filtered_posts.append(filtered_post)

    # Return new data contract with filter metadata
    result = dict(data)
    result["posts"] = filtered_posts
    result["metadata"] = dict(data.get("metadata", {}))
    result["metadata"]["filtered"] = True
    result["metadata"]["keywords"] = keywords
    result["metadata"]["matched_posts"] = len(filtered_posts)
    result["metadata"]["keyword_hits"] = keyword_hits

    return result


def run(data, keywords_str):
    """Main entry point."""
    keywords = [k.strip() for k in keywords_str.split(",") if k.strip()]
    if not keywords:
        sys.stderr.write("[keyword-filter] Error: provide at least one keyword\n")
        return data

    total = len(data.get("posts", []))
    result = filter_posts(data, keywords)
    matched = len(result["posts"])

    sys.stderr.write(f"[keyword-filter] {matched}/{total} posts matched keywords: {keywords}\n")
    return result


def main():
    parser = argparse.ArgumentParser(description="Filter posts + comments by keywords.")
    parser.add_argument("keywords", help="Comma-separated keywords")
    parser.add_argument("-i", "--input", help="Input JSON file (default: stdin)")
    parser.add_argument("-o", "--output", help="Output JSON file (default: stdout)")
    args = parser.parse_args()

    # Read input
    if args.input:
        with open(args.input, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = json.load(sys.stdin)

    result = run(data, args.keywords)

    # Write output
    output = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
    else:
        print(output)


if __name__ == "__main__":
    main()
