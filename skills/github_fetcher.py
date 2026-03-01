#!/usr/bin/env python3
"""
Skill: GitHub Issues Fetcher
Fetch issues, discussions, PRs, and releases from competitor GitHub repos.
Standard data contract output.

Usage:
  python3 github_fetcher.py "owner/repo"
  python3 github_fetcher.py "browser-use/browser-use" --days 7
  python3 github_fetcher.py "anthropics/claude-code" --type issues --label bug
"""

import os, sys, json, argparse, requests
from datetime import datetime, timezone, timedelta

GITHUB_API = "https://api.github.com"

def get_headers():
    h = {"Accept": "application/vnd.github.v3+json", "User-Agent": "competitive-intel/1.0"}
    token = os.environ.get("GITHUB_TOKEN", "")
    if token: h["Authorization"] = f"token {token}"
    return h

def fetch_issues(repo, days=7, label=None, state="all", max_items=50):
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    params = {"state": state, "sort": "updated", "direction": "desc", "since": since, "per_page": min(max_items, 100)}
    if label: params["labels"] = label
    try:
        r = requests.get(f"{GITHUB_API}/repos/{repo}/issues", headers=get_headers(), params=params, timeout=15)
        r.raise_for_status()
        items = r.json()
    except Exception as e:
        sys.stderr.write(f"[github] Error: {e}\n"); return []

    results = []
    for item in items[:max_items]:
        is_pr = "pull_request" in item
        comments = []
        if item.get("comments", 0) > 0:
            try:
                cr = requests.get(item["comments_url"], headers=get_headers(), params={"per_page": 10}, timeout=10)
                if cr.status_code == 200:
                    for c in cr.json()[:10]:
                        comments.append({"author": c["user"]["login"], "body": (c.get("body") or "")[:500],
                            "score": 0, "created_at": c.get("created_at", "")})
            except: pass

        results.append({
            "id": str(item["number"]), "title": item.get("title", ""),
            "body": (item.get("body") or "")[:2000],
            "author": item["user"]["login"] if item.get("user") else "",
            "score": item.get("reactions", {}).get("+1", 0) if isinstance(item.get("reactions"), dict) else 0,
            "url": item.get("html_url", ""),
            "created_at": item.get("created_at", ""), "updated_at": item.get("updated_at", ""),
            "state": item.get("state", ""),
            "labels": [l["name"] for l in item.get("labels", [])],
            "is_pr": is_pr, "comment_count": item.get("comments", 0), "comments": comments
        })
    return results

def fetch_releases(repo, max_items=10):
    try:
        r = requests.get(f"{GITHUB_API}/repos/{repo}/releases", headers=get_headers(), params={"per_page": max_items}, timeout=15)
        r.raise_for_status()
        return [{"id": str(rel.get("id","")), "title": rel.get("name","") or rel.get("tag_name",""),
            "body": (rel.get("body") or "")[:2000],
            "author": rel["author"]["login"] if rel.get("author") else "",
            "score": 0, "url": rel.get("html_url",""),
            "created_at": rel.get("published_at", rel.get("created_at","")),
            "tag": rel.get("tag_name",""), "is_prerelease": rel.get("prerelease", False),
            "comments": []} for rel in r.json()[:max_items]]
    except Exception as e:
        sys.stderr.write(f"[github] Releases error: {e}\n"); return []

def fetch_repo_info(repo):
    try:
        r = requests.get(f"{GITHUB_API}/repos/{repo}", headers=get_headers(), timeout=10)
        r.raise_for_status()
        d = r.json()
        return {"stars": d.get("stargazers_count",0), "forks": d.get("forks_count",0),
            "open_issues": d.get("open_issues_count",0), "language": d.get("language",""),
            "description": d.get("description",""), "updated_at": d.get("updated_at",""),
            "topics": d.get("topics",[])}
    except: return {}

def run(repo, days=7, fetch_type="all", label=None, max_items=50):
    sys.stderr.write(f"[github] Fetching {repo} (last {days}d)...\n")
    posts = []
    if fetch_type in ("all", "issues"):
        issues = fetch_issues(repo, days, label, max_items=max_items)
        posts.extend(issues); sys.stderr.write(f"[github] Issues: {len(issues)}\n")
    if fetch_type in ("all", "releases"):
        releases = fetch_releases(repo, max_items=10)
        posts.extend(releases); sys.stderr.write(f"[github] Releases: {len(releases)}\n")
    return {"source": "github", "source_id": repo, "posts": posts,
        "metadata": {"fetched_at": datetime.now(timezone.utc).isoformat(),
            "total_posts": len(posts), "days_range": days, "repo_info": fetch_repo_info(repo)}}

def main():
    parser = argparse.ArgumentParser(description="Fetch GitHub issues and releases")
    parser.add_argument("repo", help="GitHub repo (owner/repo)")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--type", default="all", choices=["all", "issues", "releases"])
    parser.add_argument("--label", help="Filter by label")
    parser.add_argument("--max", type=int, default=50)
    parser.add_argument("-o", "--output", help="Output file")
    args = parser.parse_args()
    result = run(args.repo, args.days, args.type, args.label, args.max)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f: json.dump(result, f, ensure_ascii=False, indent=2)
    else: json.dump(result, sys.stdout, ensure_ascii=False, indent=2)

if __name__ == "__main__": main()
