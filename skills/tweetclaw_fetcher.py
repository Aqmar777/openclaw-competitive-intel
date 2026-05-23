#!/usr/bin/env python3
"""
Skill: TweetClaw X/Twitter Fetcher
Fetches public X/Twitter search results through the Xquik API used by TweetClaw.
Output: Standard data contract JSON.

Usage:
  python3 tweetclaw_fetcher.py "cursor ai" -o data/x_cursor.json
  XQUIK_BASE_URL=https://xquik.com python3 tweetclaw_fetcher.py "openclaw" --count 25

Requires:
  XQUIK_API_KEY environment variable
"""

import argparse
from datetime import datetime, timezone
import json
import os
import sys

DEFAULT_BASE_URL = "https://xquik.com"
SEARCH_PATH = "/api/v1/x/tweets/search"


def clean_base_url(value):
    return (value or DEFAULT_BASE_URL).rstrip("/")


def read_api_key():
    api_key = os.environ.get("XQUIK_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "Set XQUIK_API_KEY before using tweetclaw_fetcher.py."
        )
    return api_key


def tweet_author(tweet):
    author = tweet.get("author")
    if isinstance(author, dict):
        return (
            author.get("userName")
            or author.get("username")
            or author.get("screen_name")
            or author.get("name")
            or "unknown"
        )
    return tweet.get("author_username") or tweet.get("username") or "unknown"


def tweet_score(tweet):
    return sum(
        int(tweet.get(name) or 0)
        for name in ("likeCount", "retweetCount", "replyCount", "quoteCount")
    )


def normalize_tweet(tweet):
    tweet_id = str(tweet.get("id") or tweet.get("tweet_id") or "")
    text = tweet.get("text") or tweet.get("body") or ""
    url = tweet.get("url") or (
        f"https://x.com/i/status/{tweet_id}" if tweet_id else ""
    )
    return {
        "id": tweet_id,
        "title": "",
        "body": text,
        "author": tweet_author(tweet),
        "score": tweet_score(tweet),
        "url": url,
        "created_at": tweet.get("createdAt") or tweet.get("created_at") or "",
        "comments": [],
    }


def extract_tweets(body):
    if isinstance(body, list):
        return body
    if not isinstance(body, dict):
        return []
    if isinstance(body.get("tweets"), list):
        return body["tweets"]
    data = body.get("data")
    if isinstance(data, dict) and isinstance(data.get("tweets"), list):
        return data["tweets"]
    if isinstance(data, list):
        return data
    if isinstance(body.get("items"), list):
        return body["items"]
    return []


def fetch_tweets(query, count=50, cursor="", since_time="", until_time="", base_url=""):
    api_key = read_api_key()
    import requests
    params = {"q": query, "limit": count}
    if cursor:
        params["cursor"] = cursor
    if since_time:
        params["sinceTime"] = since_time
    if until_time:
        params["untilTime"] = until_time

    response = requests.get(
        clean_base_url(base_url) + SEARCH_PATH,
        headers={
            "Accept": "application/json",
            "X-Api-Key": api_key,
        },
        params=params,
        timeout=60,
    )
    if response.status_code in (401, 403):
        raise RuntimeError(
            "TweetClaw/Xquik API key was rejected. Check XQUIK_API_KEY."
        )
    if response.status_code == 402:
        raise RuntimeError(
            "TweetClaw/Xquik requires credits for this read. Add credits or lower the count."
        )
    response.raise_for_status()
    return response.json()


def build_result(query, response_body):
    posts = [normalize_tweet(tweet) for tweet in extract_tweets(response_body)]
    return {
        "source": "x_tweetclaw",
        "source_id": query,
        "posts": posts,
        "metadata": {
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "total_posts": len(posts),
            "has_more": bool(
                response_body.get("has_more")
                or response_body.get("has_next_page")
            )
            if isinstance(response_body, dict)
            else False,
            "next_cursor": response_body.get("next_cursor", "")
            if isinstance(response_body, dict)
            else "",
        },
    }


def run(query, count=50, cursor="", since_time="", until_time="", base_url=""):
    sys.stderr.write(f"[tweetclaw] Searching X/Twitter: {query}\n")
    body = fetch_tweets(query, count, cursor, since_time, until_time, base_url)
    result = build_result(query, body)
    sys.stderr.write(f"[tweetclaw] Tweets: {len(result['posts'])}\n")
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Fetch X/Twitter search results through TweetClaw/Xquik."
    )
    parser.add_argument("query", help="Search query")
    parser.add_argument("--count", type=int, default=50, help="Max tweets")
    parser.add_argument("--cursor", default="", help="Pagination cursor")
    parser.add_argument("--since-time", default="", help="Unix timestamp seconds")
    parser.add_argument("--until-time", default="", help="Unix timestamp seconds")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("XQUIK_BASE_URL", DEFAULT_BASE_URL),
        help="Xquik-compatible API base URL",
    )
    parser.add_argument("-o", "--output", help="Output file")
    args = parser.parse_args()

    try:
        result = run(
            args.query,
            args.count,
            args.cursor,
            args.since_time,
            args.until_time,
            args.base_url,
        )
    except RuntimeError as exc:
        sys.stderr.write(f"[tweetclaw] Error: {exc}\n")
        sys.exit(1)
    except Exception as exc:
        sys.stderr.write(f"[tweetclaw] Request failed: {exc}\n")
        sys.exit(1)
    output = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        sys.stderr.write(f"[tweetclaw] Saved to {args.output}\n")
    else:
        print(output)


if __name__ == "__main__":
    main()
