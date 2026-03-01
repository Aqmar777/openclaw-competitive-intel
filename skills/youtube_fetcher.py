#!/usr/bin/env python3
"""
Skill: YouTube Fetcher (YouTube Data API v3)
Searches YouTube for competitor-related videos and fetches comments.

Usage:
  python3 youtube_fetcher.py --search "manus ai" -o data/youtube_manus.json
  python3 youtube_fetcher.py --search "manus ai review" --max-videos 20 --comments 10 -o data/youtube_manus.json
  python3 youtube_fetcher.py --channel "UCxxxxxx" --max-videos 10 -o data/youtube_channel.json

Requires:
  YOUTUBE_API_KEY environment variable (get from Google Cloud Console)

Dependencies:
  pip3 install requests --break-system-packages
"""

import requests
import json
import sys
import os
import argparse
from datetime import datetime, timezone


API_BASE = "https://www.googleapis.com/youtube/v3"


def get_api_key():
    """Get YouTube API key from environment."""
    key = os.environ.get("YOUTUBE_API_KEY", "")
    if not key:
        sys.stderr.write("[youtube-fetcher] ❌ YOUTUBE_API_KEY not set.\n")
        sys.stderr.write("[youtube-fetcher] Get one at: https://console.cloud.google.com → APIs & Services → Credentials\n")
        return None
    return key


def search_videos(api_key, query, max_results=10, order="relevance", published_after=None):
    """Search YouTube for videos matching a query.
    
    Args:
        order: relevance, date, viewCount, rating
        published_after: ISO 8601 datetime string (e.g. 2025-01-01T00:00:00Z)
    """
    sys.stderr.write(f"[youtube-fetcher] Searching for \"{query}\" (max {max_results} videos, sort: {order})...\n")
    
    all_videos = []
    next_page_token = None
    fetched = 0
    
    while fetched < max_results:
        batch_size = min(50, max_results - fetched)  # API max is 50 per page
        params = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": batch_size,
            "order": order,
            "key": api_key
        }
        if next_page_token:
            params["pageToken"] = next_page_token
        if published_after:
            params["publishedAfter"] = published_after
        
        try:
            r = requests.get(f"{API_BASE}/search", params=params, timeout=30)
            if r.status_code == 403:
                error_reason = r.json().get("error", {}).get("errors", [{}])[0].get("reason", "")
                if error_reason == "quotaExceeded":
                    sys.stderr.write("[youtube-fetcher] ❌ API quota exceeded (10,000 units/day). Try again tomorrow.\n")
                else:
                    sys.stderr.write(f"[youtube-fetcher] ❌ API forbidden: {error_reason}\n")
                break
            r.raise_for_status()
        except requests.exceptions.HTTPError as e:
            sys.stderr.write(f"[youtube-fetcher] ❌ Search failed: {e}\n")
            break
        except Exception as e:
            sys.stderr.write(f"[youtube-fetcher] ❌ Request error: {e}\n")
            break
        
        data = r.json()
        items = data.get("items", [])
        if not items:
            break
        
        for item in items:
            snippet = item.get("snippet", {})
            video_id = item.get("id", {}).get("videoId", "")
            if not video_id:
                continue
            all_videos.append({
                "video_id": video_id,
                "title": snippet.get("title", ""),
                "description": snippet.get("description", ""),
                "channel_title": snippet.get("channelTitle", ""),
                "channel_id": snippet.get("channelId", ""),
                "published_at": snippet.get("publishedAt", ""),
                "url": f"https://www.youtube.com/watch?v={video_id}",
            })
        
        fetched += len(items)
        next_page_token = data.get("nextPageToken")
        sys.stderr.write(f"  Found {fetched} videos so far...\n")
        
        if not next_page_token:
            break
    
    sys.stderr.write(f"[youtube-fetcher] Search complete: {len(all_videos)} videos found\n")
    return all_videos


def get_video_stats(api_key, video_ids):
    """Fetch view count, like count, comment count for videos.
    Up to 50 video IDs per request (1 unit per call — very cheap).
    """
    if not video_ids:
        return {}
    
    stats = {}
    # Process in batches of 50
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i+50]
        params = {
            "part": "statistics",
            "id": ",".join(batch),
            "key": api_key
        }
        try:
            r = requests.get(f"{API_BASE}/videos", params=params, timeout=30)
            r.raise_for_status()
            for item in r.json().get("items", []):
                s = item.get("statistics", {})
                stats[item["id"]] = {
                    "view_count": int(s.get("viewCount", 0)),
                    "like_count": int(s.get("likeCount", 0)),
                    "comment_count": int(s.get("commentCount", 0)),
                }
        except Exception as e:
            sys.stderr.write(f"[youtube-fetcher] ⚠️  Stats fetch failed: {e}\n")
    
    sys.stderr.write(f"[youtube-fetcher] Fetched stats for {len(stats)} videos\n")
    return stats


def get_video_comments(api_key, video_id, max_comments=10):
    """Fetch top comments for a video, sorted by relevance (highest liked first).
    Costs 1 unit per call.
    """
    params = {
        "part": "snippet",
        "videoId": video_id,
        "maxResults": min(max_comments, 100),
        "order": "relevance",
        "textFormat": "plainText",
        "key": api_key
    }
    
    comments = []
    try:
        r = requests.get(f"{API_BASE}/commentThreads", params=params, timeout=30)
        if r.status_code == 403:
            # Comments might be disabled
            error_reason = r.json().get("error", {}).get("errors", [{}])[0].get("reason", "")
            if error_reason == "commentsDisabled":
                return []
            if error_reason == "quotaExceeded":
                sys.stderr.write("[youtube-fetcher] ⚠️  Quota exceeded, skipping remaining comments\n")
                return []
        if r.status_code != 200:
            return []
        
        for item in r.json().get("items", []):
            snippet = item.get("snippet", {}).get("topLevelComment", {}).get("snippet", {})
            comments.append({
                "author": snippet.get("authorDisplayName", ""),
                "body": snippet.get("textDisplay", ""),
                "score": int(snippet.get("likeCount", 0)),
                "published_at": snippet.get("publishedAt", ""),
            })
    except Exception as e:
        sys.stderr.write(f"[youtube-fetcher] ⚠️  Comments fetch failed for {video_id}: {e}\n")
    
    return comments


def fetch_channel_videos(api_key, channel_id, max_results=10, order="date"):
    """Fetch recent videos from a specific channel."""
    sys.stderr.write(f"[youtube-fetcher] Fetching videos from channel {channel_id}...\n")
    
    params = {
        "part": "snippet",
        "channelId": channel_id,
        "type": "video",
        "maxResults": min(max_results, 50),
        "order": order,
        "key": api_key
    }
    
    videos = []
    try:
        r = requests.get(f"{API_BASE}/search", params=params, timeout=30)
        r.raise_for_status()
        for item in r.json().get("items", []):
            snippet = item.get("snippet", {})
            video_id = item.get("id", {}).get("videoId", "")
            if not video_id:
                continue
            videos.append({
                "video_id": video_id,
                "title": snippet.get("title", ""),
                "description": snippet.get("description", ""),
                "channel_title": snippet.get("channelTitle", ""),
                "channel_id": snippet.get("channelId", ""),
                "published_at": snippet.get("publishedAt", ""),
                "url": f"https://www.youtube.com/watch?v={video_id}",
            })
    except Exception as e:
        sys.stderr.write(f"[youtube-fetcher] ❌ Channel fetch failed: {e}\n")
    
    sys.stderr.write(f"[youtube-fetcher] Got {len(videos)} videos from channel\n")
    return videos


def run_search(api_key, query, max_videos=10, max_comments=10, order="relevance",
               published_after=None, no_comments=False):
    """Full search workflow: search → stats → comments → structured output."""
    
    # Step 1: Search
    videos = search_videos(api_key, query, max_videos, order, published_after)
    if not videos:
        return {
            "source": "youtube_search",
            "source_id": query,
            "posts": [],
            "metadata": {
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "total_posts": 0,
                "query": query,
            }
        }
    
    # Step 2: Get stats
    video_ids = [v["video_id"] for v in videos]
    stats = get_video_stats(api_key, video_ids)
    
    # Step 3: Get comments (unless --no-comments)
    if not no_comments:
        sys.stderr.write(f"[youtube-fetcher] Fetching comments for {len(videos)} videos...\n")
        for i, video in enumerate(videos):
            vid = video["video_id"]
            video["comments"] = get_video_comments(api_key, vid, max_comments)
            if (i + 1) % 5 == 0:
                sys.stderr.write(f"  Comments: {i+1}/{len(videos)} done\n")
    
    # Step 4: Build output (compatible with keyword_filter.py)
    # keyword_filter expects: posts[] with title, body, url, score, author, created_at, comments[]
    posts = []
    channel_ranking = {}
    
    for video in videos:
        vid = video["video_id"]
        s = stats.get(vid, {})
        
        # Track channel ranking
        ch = video["channel_title"]
        if ch not in channel_ranking:
            channel_ranking[ch] = {"video_count": 0, "total_views": 0, "channel_id": video["channel_id"]}
        channel_ranking[ch]["video_count"] += 1
        channel_ranking[ch]["total_views"] += s.get("view_count", 0)
        
        post = {
            "id": vid,
            "title": video["title"],
            "body": video["description"],
            "author": video["channel_title"],
            "score": s.get("view_count", 0),  # Use view_count as "score" for sorting
            "like_count": s.get("like_count", 0),
            "comment_count": s.get("comment_count", 0),
            "view_count": s.get("view_count", 0),
            "url": video["url"],
            "created_at": video["published_at"],
            "channel_id": video["channel_id"],
            "comments": video.get("comments", []),
        }
        posts.append(post)
    
    # Sort by views (highest first)
    posts.sort(key=lambda x: x.get("view_count", 0), reverse=True)
    
    # Build channel ranking (like subreddit_ranking in reddit_fetcher)
    ranking = []
    for ch_name, data in sorted(channel_ranking.items(), key=lambda x: x[1]["total_views"], reverse=True):
        ranking.append({
            "channel": ch_name,
            "channel_id": data["channel_id"],
            "video_count": data["video_count"],
            "total_views": data["total_views"],
            "url": f"https://www.youtube.com/channel/{data['channel_id']}"
        })
    
    if ranking:
        sys.stderr.write(f"\n[youtube-fetcher] === Channel Ranking ({len(posts)} videos found) ===\n")
        for i, r in enumerate(ranking[:15]):
            bar = "█" * min(r["video_count"] * 3, 30)
            sys.stderr.write(f"  #{i+1:<3} {r['channel']:<30} {r['video_count']:>3} videos  views:{r['total_views']:>10,}  {bar}\n")
        sys.stderr.write(f"\n  Found across {len(ranking)} channels\n\n")
    
    # Print top videos summary
    sys.stderr.write(f"[youtube-fetcher] === Top Videos by Views ===\n")
    for i, post in enumerate(posts[:10]):
        sys.stderr.write(f"  #{i+1} [{post['view_count']:>10,} views] {post['title'][:60]}\n")
    sys.stderr.write("\n")
    
    return {
        "source": "youtube_search",
        "source_id": query,
        "posts": posts,
        "channel_ranking": ranking,
        "metadata": {
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "total_posts": len(posts),
            "query": query,
            "channels_found": len(ranking),
            "total_views": sum(p.get("view_count", 0) for p in posts),
            "total_likes": sum(p.get("like_count", 0) for p in posts),
            "total_comments_on_videos": sum(p.get("comment_count", 0) for p in posts),
        }
    }


def run_channel(api_key, channel_id, max_videos=10, max_comments=10, order="date", no_comments=False):
    """Fetch videos from a specific channel."""
    
    videos = fetch_channel_videos(api_key, channel_id, max_videos, order)
    if not videos:
        return {
            "source": "youtube_channel",
            "source_id": channel_id,
            "posts": [],
            "metadata": {
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "total_posts": 0,
                "channel_id": channel_id,
            }
        }
    
    # Get stats
    video_ids = [v["video_id"] for v in videos]
    stats = get_video_stats(api_key, video_ids)
    
    # Get comments
    if not no_comments:
        sys.stderr.write(f"[youtube-fetcher] Fetching comments for {len(videos)} videos...\n")
        for i, video in enumerate(videos):
            vid = video["video_id"]
            video["comments"] = get_video_comments(api_key, vid, max_comments)
    
    posts = []
    for video in videos:
        vid = video["video_id"]
        s = stats.get(vid, {})
        posts.append({
            "id": vid,
            "title": video["title"],
            "body": video["description"],
            "author": video["channel_title"],
            "score": s.get("view_count", 0),
            "like_count": s.get("like_count", 0),
            "comment_count": s.get("comment_count", 0),
            "view_count": s.get("view_count", 0),
            "url": video["url"],
            "created_at": video["published_at"],
            "channel_id": video["channel_id"],
            "comments": video.get("comments", []),
        })
    
    posts.sort(key=lambda x: x.get("view_count", 0), reverse=True)
    
    return {
        "source": "youtube_channel",
        "source_id": channel_id,
        "posts": posts,
        "metadata": {
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "total_posts": len(posts),
            "channel_id": channel_id,
        }
    }


# ─── CLI ───

def main():
    parser = argparse.ArgumentParser(
        description="YouTube Fetcher (YouTube Data API v3)",
        epilog="""
Requires YOUTUBE_API_KEY environment variable.
Get one at: https://console.cloud.google.com → APIs & Services → Credentials

Quota: 10,000 units/day (free). Search = 100 units, Video stats = 1 unit, Comments = 1 unit.
A typical run with 10 videos + comments ≈ 111 units.

Examples:
  python3 youtube_fetcher.py --search "manus ai" -o data/youtube_manus.json
  python3 youtube_fetcher.py --search "manus ai review" --max-videos 20 --sort viewCount
  python3 youtube_fetcher.py --search "cursor vs copilot" --days 30 --no-comments
  python3 youtube_fetcher.py --channel "UCxxxxxxx" --max-videos 10
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--search", help="Search query (keyword search)")
    parser.add_argument("--channel", help="Channel ID to fetch videos from")
    parser.add_argument("--max-videos", type=int, default=10, help="Max videos to fetch (default: 10)")
    parser.add_argument("--comments", type=int, default=10, help="Max comments per video (default: 10)")
    parser.add_argument("--no-comments", action="store_true", help="Skip fetching comments")
    parser.add_argument("--sort", default="relevance", choices=["relevance", "date", "viewCount", "rating"],
                        help="Sort order (default: relevance)")
    parser.add_argument("--days", type=int, default=180, help="Only videos from last N days (default: 180)")
    parser.add_argument("-o", "--output", help="Output file (JSON)")
    args = parser.parse_args()

    # Validate
    if not args.search and not args.channel:
        parser.error("Either --search 'query' or --channel 'channel_id' is required")
        return

    api_key = get_api_key()
    if not api_key:
        sys.exit(1)

    # Calculate published_after if --days is set
    published_after = None
    if args.days:
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(days=args.days)
        published_after = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")
        sys.stderr.write(f"[youtube-fetcher] Filtering to last {args.days} days (after {published_after})\n")

    # Run
    if args.search:
        result = run_search(
            api_key, args.search, args.max_videos, args.comments,
            args.sort, published_after, args.no_comments
        )
    elif args.channel:
        result = run_channel(
            api_key, args.channel, args.max_videos, args.comments,
            args.sort, args.no_comments
        )

    output = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        sys.stderr.write(f"[youtube-fetcher] Saved to {args.output}\n")
    else:
        print(output)


if __name__ == "__main__":
    main()
