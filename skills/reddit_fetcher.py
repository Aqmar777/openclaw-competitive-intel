#!/usr/bin/env python3
"""
Skill: Reddit Fetcher (with RSS fallback)
Three auth methods (auto-fallback):
  1. OAuth API (best, needs REDDIT_CLIENT_ID + REDDIT_CLIENT_SECRET)
  2. RSS feeds (good, no auth needed, works on most servers)
  3. .json scraping (basic, may be blocked on servers)

Two modes:
  1. Search mode: Search all of Reddit for a keyword (discovery)
  2. Subreddit mode: Fetch posts from a specific subreddit (deep dive)

Usage:
  python3 reddit_fetcher.py --search "larrybrain" --no-comments -o data.json
  python3 reddit_fetcher.py "https://www.reddit.com/r/SaaS/" -o data.json

Dependencies:
  pip3 install requests feedparser --break-system-packages
"""

import requests
import json
import sys
import time
import re
import os
import argparse
from datetime import datetime, timezone
from collections import Counter

try:
    import feedparser
    HAS_FEEDPARSER = True
except ImportError:
    HAS_FEEDPARSER = False


# ─── Authentication ───

def get_oauth_token():
    """Get Reddit OAuth token using client credentials."""
    client_id = os.environ.get("REDDIT_CLIENT_ID", "")
    client_secret = os.environ.get("REDDIT_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        return None
    username = os.environ.get("REDDIT_USERNAME", "competitive-intel-bot")
    try:
        auth = requests.auth.HTTPBasicAuth(client_id, client_secret)
        headers = {"User-Agent": f"script:competitive-intel:v2.0 (by /u/{username})"}
        data = {"grant_type": "client_credentials"}
        r = requests.post("https://www.reddit.com/api/v1/access_token",
                          auth=auth, headers=headers, data=data, timeout=15)
        r.raise_for_status()
        token = r.json().get("access_token")
        if token:
            sys.stderr.write("[reddit-fetcher] ✅ OAuth authenticated\n")
            return token
    except Exception as e:
        sys.stderr.write(f"[reddit-fetcher] OAuth failed: {e}\n")
    return None


def get_headers(token=None):
    username = os.environ.get("REDDIT_USERNAME", "competitive-intel-bot")
    ua = f"script:competitive-intel:v2.0 (by /u/{username})"
    if token:
        return {"Authorization": f"Bearer {token}", "User-Agent": ua}
    return {"User-Agent": ua}


# ─── RSS mode (无需认证，服务器友好) ───

def fetch_rss_search(query, limit=100):
    """Search Reddit via RSS. No auth needed."""
    url = f"https://www.reddit.com/search.rss?q={requests.utils.quote(query)}&limit={limit}&sort=relevance"
    headers = {"User-Agent": "script:competitive-intel:v2.0 (research-bot)"}
    
    try:
        r = requests.get(url, headers=headers, timeout=30)
        if r.status_code == 429:
            wait = int(r.headers.get("Retry-After", 60))
            sys.stderr.write(f"  RSS rate limited, waiting {wait}s...\n")
            time.sleep(wait)
            r = requests.get(url, headers=headers, timeout=30)
        if r.status_code != 200:
            sys.stderr.write(f"  RSS search failed: HTTP {r.status_code}\n")
            return None
        
        feed = feedparser.parse(r.text)
        posts = []
        for entry in feed.entries:
            # Extract subreddit from link
            sub_match = re.search(r'/r/([^/]+)/', entry.get("link", ""))
            subreddit = sub_match.group(1) if sub_match else "unknown"
            
            # Extract post ID from link
            id_match = re.search(r'/comments/([^/]+)/', entry.get("link", ""))
            post_id = id_match.group(1) if id_match else ""
            
            posts.append({
                "id": post_id,
                "title": entry.get("title", ""),
                "body": "",  # RSS doesn't include selftext
                "author": entry.get("author", entry.get("author_detail", {}).get("name", "")),
                "score": 0,  # RSS doesn't include score
                "url": entry.get("link", ""),
                "created_at": entry.get("published", ""),
                "subreddit": subreddit,
                "num_comments": 0,
                "permalink": "",
                "comments": []
            })
            
            # Extract permalink from url
            link = entry.get("link", "")
            perm_match = re.search(r'(\/r\/[^?]+)', link)
            if perm_match:
                posts[-1]["permalink"] = perm_match.group(1).rstrip("/")
        
        sys.stderr.write(f"  RSS search: got {len(posts)} results\n")
        return posts
    except Exception as e:
        sys.stderr.write(f"  RSS search failed: {e}\n")
        return None


def fetch_rss_subreddit(subreddit_name, sort="hot", limit=100):
    """Fetch subreddit posts via RSS. No auth needed."""
    url = f"https://www.reddit.com/r/{subreddit_name}/{sort}.rss?limit={limit}"
    headers = {"User-Agent": "script:competitive-intel:v2.0 (research-bot)"}
    
    try:
        r = requests.get(url, headers=headers, timeout=30)
        if r.status_code == 429:
            wait = int(r.headers.get("Retry-After", 60))
            sys.stderr.write(f"  RSS rate limited, waiting {wait}s...\n")
            time.sleep(wait)
            r = requests.get(url, headers=headers, timeout=30)
        if r.status_code != 200:
            sys.stderr.write(f"  RSS subreddit failed: HTTP {r.status_code}\n")
            return None
        
        feed = feedparser.parse(r.text)
        posts = []
        for entry in feed.entries:
            id_match = re.search(r'/comments/([^/]+)/', entry.get("link", ""))
            post_id = id_match.group(1) if id_match else ""
            
            link = entry.get("link", "")
            perm_match = re.search(r'(\/r\/[^?]+)', link)
            permalink = perm_match.group(1).rstrip("/") if perm_match else ""
            
            posts.append({
                "id": post_id,
                "title": entry.get("title", ""),
                "body": "",
                "author": entry.get("author", entry.get("author_detail", {}).get("name", "")),
                "score": 0,
                "url": link,
                "created_at": entry.get("published", ""),
                "num_comments": 0,
                "permalink": permalink,
                "comments": []
            })
        
        sys.stderr.write(f"  RSS subreddit: got {len(posts)} results\n")
        return posts
    except Exception as e:
        sys.stderr.write(f"  RSS subreddit failed: {e}\n")
        return None


def enrich_post_via_json(post, delay=2.0):
    """Fetch score, body, num_comments for a single post via .json endpoint."""
    permalink = post.get("permalink", "")
    if not permalink:
        return post
    
    headers = {"User-Agent": "script:competitive-intel:v2.0 (research-bot)"}
    try:
        url = f"https://www.reddit.com{permalink}.json"
        r = requests.get(url, headers=headers, params={"raw_json": 1}, timeout=20)
        if r.status_code == 200:
            data = r.json()
            if data and len(data) > 0:
                d = data[0]["data"]["children"][0]["data"]
                post["score"] = d.get("score", 0)
                post["body"] = d.get("selftext", "")
                post["num_comments"] = d.get("num_comments", 0)
                post["author"] = d.get("author", post.get("author", ""))
                created = d.get("created_utc", 0)
                if created:
                    post["created_at"] = datetime.fromtimestamp(created, tz=timezone.utc).isoformat()
        time.sleep(delay)
    except:
        pass
    return post


# ─── OAuth/JSON mode ───

def search_api(query, sort="relevance", time_filter="all", pages=2, delay=2.0, token=None):
    """Search via OAuth API or .json fallback."""
    headers = get_headers(token)
    base = "https://oauth.reddit.com" if token else "https://www.reddit.com"
    all_posts = []
    after = None

    for page in range(pages):
        url = f"{base}/search" if token else f"{base}/search.json"
        params = {"q": query, "sort": sort, "t": time_filter, "limit": 100, "raw_json": 1, "type": "link"}
        if after:
            params["after"] = after

        try:
            r = requests.get(url, headers=headers, params=params, timeout=30)
            if r.status_code == 429:
                wait = int(r.headers.get("Retry-After", 60))
                sys.stderr.write(f"  Rate limited, waiting {wait}s...\n")
                time.sleep(wait)
                r = requests.get(url, headers=headers, params=params, timeout=30)
            if r.status_code in (403, 429):
                sys.stderr.write(f"  HTTP {r.status_code} — blocked\n")
                return None  # Signal to try RSS fallback
            r.raise_for_status()
        except Exception as e:
            sys.stderr.write(f"  API search page {page+1} failed: {e}\n")
            return None

        children = r.json().get("data", {}).get("children", [])
        if not children:
            break

        for item in children:
            d = item["data"]
            created = datetime.fromtimestamp(d.get("created_utc", 0), tz=timezone.utc).isoformat()
            all_posts.append({
                "id": d.get("id", ""),
                "title": d.get("title", ""),
                "body": d.get("selftext", ""),
                "author": d.get("author", ""),
                "score": d.get("score", 0),
                "url": f"https://www.reddit.com{d.get('permalink', '')}",
                "created_at": created,
                "subreddit": d.get("subreddit", ""),
                "num_comments": d.get("num_comments", 0),
                "permalink": d.get("permalink", ""),
                "comments": []
            })

        after = r.json().get("data", {}).get("after")
        sys.stderr.write(f"  API search page {page+1}: +{len(children)} results (total: {len(all_posts)})\n")
        if not after:
            break
        if page < pages - 1:
            time.sleep(delay)

    return all_posts


def fetch_posts_api(subreddit_name, sort="hot", time_filter="all", pages=2, delay=2.0, token=None):
    """Fetch subreddit via OAuth API or .json fallback."""
    headers = get_headers(token)
    base = "https://oauth.reddit.com" if token else "https://www.reddit.com"
    all_posts = []
    after = None

    for page in range(pages):
        if token:
            url = f"{base}/r/{subreddit_name}/{sort}"
        else:
            url = f"{base}/r/{subreddit_name}/{sort}.json"
        
        params = {"limit": 100, "raw_json": 1}
        if after:
            params["after"] = after
        if sort == "top":
            params["t"] = time_filter

        try:
            r = requests.get(url, headers=headers, params=params, timeout=30)
            if r.status_code == 429:
                wait = int(r.headers.get("Retry-After", 60))
                sys.stderr.write(f"  Rate limited, waiting {wait}s...\n")
                time.sleep(wait)
                r = requests.get(url, headers=headers, params=params, timeout=30)
            if r.status_code in (403, 429):
                sys.stderr.write(f"  HTTP {r.status_code} — blocked\n")
                return None
            r.raise_for_status()
        except Exception as e:
            sys.stderr.write(f"  API page {page+1} failed: {e}\n")
            return None

        children = r.json().get("data", {}).get("children", [])
        if not children:
            break

        for item in children:
            d = item["data"]
            created = datetime.fromtimestamp(d.get("created_utc", 0), tz=timezone.utc).isoformat()
            all_posts.append({
                "id": d.get("id", ""),
                "title": d.get("title", ""),
                "body": d.get("selftext", ""),
                "author": d.get("author", ""),
                "score": d.get("score", 0),
                "url": f"https://www.reddit.com{d.get('permalink', '')}",
                "created_at": created,
                "num_comments": d.get("num_comments", 0),
                "permalink": d.get("permalink", ""),
                "comments": []
            })

        after = r.json().get("data", {}).get("after")
        sys.stderr.write(f"  API page {page+1}: +{len(children)} posts (total: {len(all_posts)})\n")
        if not after:
            break
        if page < pages - 1:
            time.sleep(delay)

    return all_posts


# ─── Comments ───

def fetch_comments(permalink, limit=15, delay=2.0, token=None):
    headers = get_headers(token)
    try:
        if token:
            url = f"https://oauth.reddit.com{permalink}"
        else:
            url = f"https://www.reddit.com{permalink}.json"
        
        r = requests.get(url, headers=headers, params={"limit": limit, "depth": 1, "raw_json": 1}, timeout=30)
        if r.status_code == 429:
            time.sleep(60)
            r = requests.get(url, headers=headers, params={"limit": limit, "depth": 1, "raw_json": 1}, timeout=30)
        r.raise_for_status()
        data = r.json()
        comments = []
        if len(data) > 1 and "data" in data[1]:
            for item in data[1]["data"]["children"]:
                if item.get("kind") == "t1":
                    c = item["data"]
                    comments.append({
                        "author": c.get("author", ""),
                        "body": c.get("body", ""),
                        "score": c.get("score", 0)
                    })
        return comments
    except:
        return []


# ─── Subreddit ranking ───

def build_subreddit_ranking(posts):
    counter = Counter()
    score_counter = Counter()
    for post in posts:
        sub = post.get("subreddit", "unknown")
        counter[sub] += 1
        score_counter[sub] += post.get("score", 0)

    ranking = []
    for sub, count in counter.most_common():
        ranking.append({
            "subreddit": f"r/{sub}",
            "post_count": count,
            "total_score": score_counter[sub],
            "avg_score": round(score_counter[sub] / count, 1) if count > 0 else 0,
            "url": f"https://www.reddit.com/r/{sub}/"
        })
    return ranking


# ─── Main logic with fallback ───

def run_search(query, sort="relevance", time_filter="all", pages=2,
               comments_per_post=15, delay=2.0, fetch_comments_flag=True, token=None):
    """Search mode with auto-fallback: OAuth → RSS → .json"""
    
    sys.stderr.write(f"[reddit-fetcher] Searching Reddit for \"{query}\"...\n")
    
    # Try 1: OAuth API (if token available)
    posts = None
    auth_method = "anonymous"
    
    if token:
        sys.stderr.write("[reddit-fetcher] Trying OAuth API...\n")
        posts = search_api(query, sort, time_filter, pages, delay, token)
        if posts is not None:
            auth_method = "oauth"
    
    # Try 2: RSS (no auth needed, good for servers)
    if posts is None and HAS_FEEDPARSER:
        sys.stderr.write("[reddit-fetcher] Trying RSS feed...\n")
        posts = fetch_rss_search(query)
        if posts is not None:
            auth_method = "rss"
            # RSS doesn't give scores, enrich top posts
            sys.stderr.write(f"[reddit-fetcher] Enriching top posts with scores...\n")
            for i, post in enumerate(posts[:20]):  # Only enrich top 20 to save time
                posts[i] = enrich_post_via_json(post, delay=delay)
                if (i + 1) % 5 == 0:
                    sys.stderr.write(f"  Enriched {i+1}/{min(20, len(posts))} posts\n")
    
    # Try 3: .json scraping (last resort)
    if posts is None:
        sys.stderr.write("[reddit-fetcher] Trying .json scraping...\n")
        posts = search_api(query, sort, time_filter, pages, delay, token=None)
        if posts is not None:
            auth_method = "json"
    
    # All methods failed
    if posts is None:
        sys.stderr.write("[reddit-fetcher] ❌ All methods failed. Reddit may be blocking this server.\n")
        posts = []
        auth_method = "failed"

    # Build subreddit ranking
    ranking = build_subreddit_ranking(posts)

    if ranking:
        sys.stderr.write(f"\n[reddit-fetcher] === Subreddit Ranking ({len(posts)} posts found) ===\n")
        for i, r in enumerate(ranking[:15]):
            bar = "█" * min(r["post_count"], 30)
            sys.stderr.write(f"  #{i+1:<3} {r['subreddit']:<25} {r['post_count']:>3} posts  score:{r['total_score']:>6}  {bar}\n")
        sys.stderr.write(f"\n  Found in {len(ranking)} subreddits total\n\n")

    # Fetch comments if requested
    if fetch_comments_flag and posts:
        sys.stderr.write(f"[reddit-fetcher] Fetching comments for {len(posts)} posts...\n")
        for i, post in enumerate(posts):
            if post.get("permalink"):
                post["comments"] = fetch_comments(post["permalink"], comments_per_post, delay, token)
            post.pop("permalink", None)
            post.pop("num_comments", None)
            if (i + 1) % 10 == 0:
                sys.stderr.write(f"  {i+1}/{len(posts)} done\n")
            time.sleep(delay)
    else:
        for post in posts:
            post.pop("permalink", None)

    return {
        "source": "reddit_search",
        "source_id": query,
        "posts": posts,
        "subreddit_ranking": ranking,
        "metadata": {
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "total_posts": len(posts),
            "query": query,
            "subreddits_found": len(ranking),
            "auth_method": auth_method
        }
    }


def run_subreddit(subreddit_url, sort="hot", time_filter="all", pages=2,
                  comments_per_post=15, delay=2.0, token=None):
    """Subreddit mode with auto-fallback: OAuth → RSS → .json"""
    
    match = re.search(r'/r/([^/]+)', subreddit_url)
    sub_name = match.group(1) if match else subreddit_url.rstrip("/").split("/")[-1]
    
    sys.stderr.write(f"[reddit-fetcher] Fetching r/{sub_name}...\n")
    
    posts = None
    auth_method = "anonymous"
    
    # Try 1: OAuth
    if token:
        sys.stderr.write("[reddit-fetcher] Trying OAuth API...\n")
        posts = fetch_posts_api(sub_name, sort, time_filter, pages, delay, token)
        if posts is not None:
            auth_method = "oauth"
    
    # Try 2: RSS
    if posts is None and HAS_FEEDPARSER:
        sys.stderr.write("[reddit-fetcher] Trying RSS feed...\n")
        posts = fetch_rss_subreddit(sub_name, sort)
        if posts is not None:
            auth_method = "rss"
            sys.stderr.write(f"[reddit-fetcher] Enriching posts with scores...\n")
            for i, post in enumerate(posts[:30]):
                posts[i] = enrich_post_via_json(post, delay=delay)
                if (i + 1) % 10 == 0:
                    sys.stderr.write(f"  Enriched {i+1}/{min(30, len(posts))} posts\n")
    
    # Try 3: .json
    if posts is None:
        sys.stderr.write("[reddit-fetcher] Trying .json scraping...\n")
        posts = fetch_posts_api(sub_name, sort, time_filter, pages, delay, token=None)
        if posts is not None:
            auth_method = "json"
    
    if posts is None:
        sys.stderr.write("[reddit-fetcher] ❌ All methods failed.\n")
        posts = []
        auth_method = "failed"

    # Fetch comments
    sys.stderr.write(f"[reddit-fetcher] Fetching comments for {len(posts)} posts...\n")
    for i, post in enumerate(posts):
        if post.get("permalink"):
            post["comments"] = fetch_comments(post["permalink"], comments_per_post, delay, token)
        post.pop("permalink", None)
        post.pop("num_comments", None)
        if (i + 1) % 10 == 0:
            sys.stderr.write(f"  {i+1}/{len(posts)} done\n")
        time.sleep(delay)

    return {
        "source": "reddit",
        "source_id": sub_name,
        "posts": posts,
        "metadata": {
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "total_posts": len(posts),
            "auth_method": auth_method
        }
    }


# ─── CLI ───

def main():
    parser = argparse.ArgumentParser(
        description="Reddit Fetcher with auto-fallback (OAuth → RSS → .json)",
        epilog="""
Auth methods (auto-detected, highest priority first):
  1. OAuth: set REDDIT_CLIENT_ID + REDDIT_CLIENT_SECRET
  2. RSS:   no auth needed, works on most servers (needs: pip install feedparser)
  3. .json: no auth, but often blocked on servers

Examples:
  python3 reddit_fetcher.py --search "larrybrain" --no-comments
  python3 reddit_fetcher.py "https://www.reddit.com/r/OpenClaw/" --pages 1
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("subreddit_url", nargs="?", help="Subreddit URL")
    parser.add_argument("--search", help="Search keyword (global search)")
    parser.add_argument("--pages", type=int, default=2)
    parser.add_argument("--comments", type=int, default=15)
    parser.add_argument("--no-comments", action="store_true")
    parser.add_argument("--delay", type=float, default=2.0)
    parser.add_argument("--sort", default="hot", choices=["hot", "new", "top", "rising", "relevance"])
    parser.add_argument("--time", default="all", choices=["day", "week", "month", "year", "all"])
    parser.add_argument("-o", "--output", help="Output file")
    args = parser.parse_args()

    # Check feedparser
    if not HAS_FEEDPARSER:
        sys.stderr.write("[reddit-fetcher] ⚠️  feedparser not installed. RSS fallback disabled.\n")
        sys.stderr.write("[reddit-fetcher] Install: pip3 install feedparser --break-system-packages\n\n")

    # Try OAuth
    token = get_oauth_token()
    if not token:
        if HAS_FEEDPARSER:
            sys.stderr.write("[reddit-fetcher] No OAuth. Will use RSS fallback.\n\n")
        else:
            sys.stderr.write("[reddit-fetcher] No OAuth, no feedparser. Using .json (may fail on servers).\n\n")

    # Run
    if args.search:
        search_sort = args.sort if args.sort in ["relevance", "hot", "top", "new"] else "relevance"
        result = run_search(
            args.search, search_sort, args.time, args.pages,
            args.comments, args.delay,
            fetch_comments_flag=not args.no_comments,
            token=token
        )
    elif args.subreddit_url:
        result = run_subreddit(
            args.subreddit_url, args.sort, args.time, args.pages,
            args.comments, args.delay, token=token
        )
    else:
        parser.error("Either provide a subreddit URL or use --search 'keyword'")
        return

    output = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        sys.stderr.write(f"[reddit-fetcher] Saved to {args.output}\n")
    else:
        print(output)


if __name__ == "__main__":
    main()
