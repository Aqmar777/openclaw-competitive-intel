#!/usr/bin/env python3
"""
Skill: X (Twitter) Fetcher
Fetches posts + replies from X/Twitter search or user timeline.
Output: Standard data contract JSON.

Usage:
  python3 x_fetcher.py "AI automation" [options]
  python3 x_fetcher.py --user "elonmusk" --count 50

Requires: X API Bearer Token (TWITTER_BEARER_TOKEN env var)
  Get one at: https://developer.x.com/en/portal/dashboard

Note: X API v2 free tier allows 1,500 tweets/month read.
      Basic tier ($200/month) allows 10,000 tweets/month.
"""

import json
import sys
import argparse
import os
import time
import requests
from datetime import datetime, timezone

BEARER_TOKEN = os.environ.get("TWITTER_BEARER_TOKEN", "")
BASE_URL = "https://api.twitter.com/2"


def search_tweets(query, max_results=50, delay=1.0):
    """Search recent tweets (last 7 days) via X API v2."""
    if not BEARER_TOKEN:
        sys.stderr.write("[x-fetcher] Error: Set TWITTER_BEARER_TOKEN env var\n")
        sys.stderr.write("[x-fetcher] Get one at: https://developer.x.com/en/portal/dashboard\n")
        sys.exit(1)

    headers = {"Authorization": f"Bearer {BEARER_TOKEN}"}
    posts = []
    next_token = None
    fetched = 0

    while fetched < max_results:
        batch = min(max_results - fetched, 100)
        params = {
            "query": query,
            "max_results": max(10, batch),
            "tweet.fields": "created_at,public_metrics,author_id,conversation_id",
            "expansions": "author_id",
            "user.fields": "username"
        }
        if next_token:
            params["next_token"] = next_token

        try:
            r = requests.get(f"{BASE_URL}/tweets/search/recent", headers=headers, params=params, timeout=15)
            if r.status_code == 429:
                reset = int(r.headers.get("x-rate-limit-reset", time.time() + 60))
                wait = max(reset - int(time.time()), 10)
                sys.stderr.write(f"  Rate limited, waiting {wait}s...\n")
                time.sleep(wait)
                continue
            r.raise_for_status()
        except Exception as e:
            sys.stderr.write(f"  Fetch error: {e}\n")
            break

        data = r.json()
        tweets = data.get("data", [])
        if not tweets:
            break

        # Build author lookup
        users = {u["id"]: u["username"] for u in data.get("includes", {}).get("users", [])}

        for t in tweets:
            metrics = t.get("public_metrics", {})
            posts.append({
                "id": t["id"],
                "title": "",  # tweets don't have titles
                "body": t.get("text", ""),
                "author": users.get(t.get("author_id", ""), "unknown"),
                "score": metrics.get("like_count", 0) + metrics.get("retweet_count", 0),
                "url": f"https://x.com/i/status/{t['id']}",
                "created_at": t.get("created_at", ""),
                "comments": []  # replies require separate fetch
            })

        fetched += len(tweets)
        next_token = data.get("meta", {}).get("next_token")
        sys.stderr.write(f"  Fetched {fetched} tweets\n")

        if not next_token:
            break
        time.sleep(delay)

    return posts


def fetch_replies(conversation_id, delay=1.0):
    """Fetch replies to a tweet via conversation_id."""
    if not BEARER_TOKEN:
        return []

    headers = {"Authorization": f"Bearer {BEARER_TOKEN}"}
    params = {
        "query": f"conversation_id:{conversation_id}",
        "max_results": 20,
        "tweet.fields": "created_at,public_metrics,author_id",
        "expansions": "author_id",
        "user.fields": "username"
    }

    try:
        r = requests.get(f"{BASE_URL}/tweets/search/recent", headers=headers, params=params, timeout=15)
        if r.status_code == 429:
            time.sleep(30)
            return []
        r.raise_for_status()
        data = r.json()
        tweets = data.get("data", [])
        users = {u["id"]: u["username"] for u in data.get("includes", {}).get("users", [])}

        return [
            {
                "author": users.get(t.get("author_id", ""), "unknown"),
                "body": t.get("text", ""),
                "score": t.get("public_metrics", {}).get("like_count", 0)
            }
            for t in tweets
        ]
    except:
        return []


def run(query, max_results=50, fetch_replies_flag=True, delay=1.0):
    """Main entry point. Returns standard data contract dict."""
    sys.stderr.write(f"[x-fetcher] Searching: {query}\n")
    posts = search_tweets(query, max_results, delay)

    if fetch_replies_flag:
        sys.stderr.write(f"[x-fetcher] Fetching replies...\n")
        for i, post in enumerate(posts[:20]):  # limit reply fetching
            post["comments"] = fetch_replies(post["id"], delay)
            time.sleep(delay)

    return {
        "source": "x",
        "source_id": query,
        "posts": posts,
        "metadata": {
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "total_posts": len(posts)
        }
    }


def main():
    parser = argparse.ArgumentParser(description="Fetch tweets + replies from X/Twitter.")
    parser.add_argument("query", help="Search query or hashtag")
    parser.add_argument("--count", type=int, default=50, help="Max tweets to fetch")
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--no-replies", action="store_true", help="Skip fetching replies")
    parser.add_argument("-o", "--output", help="Output file (default: stdout)")
    args = parser.parse_args()

    result = run(args.query, args.count, not args.no_replies, args.delay)

    output = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        sys.stderr.write(f"[x-fetcher] Saved to {args.output}\n")
    else:
        print(output)


if __name__ == "__main__":
    main()
