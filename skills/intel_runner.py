#!/usr/bin/env python3
"""
Competitive Intelligence (竞品情报 - 全维度)
One command to scan all dimensions:
  1. Web: changelog, landing page, pricing changes
  2. Social: Reddit + X discussions about competitor
  3. GitHub: issues, PRs, releases

Usage:
  python3 intel_runner.py scan
  python3 intel_runner.py scan --competitor manus
  python3 intel_runner.py scan --only web
  python3 intel_runner.py scan --only social,github
  python3 intel_runner.py watch --interval 24
"""

import os, sys, json, argparse, time
from datetime import datetime, timezone, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "configs")
DATA_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "data")
INTEL_LOG = os.path.join(DATA_DIR, "intel_log.json")
sys.path.insert(0, SCRIPT_DIR)

def load_config():
    with open(os.path.join(CONFIG_DIR, "competitors.json"), "r", encoding="utf-8") as f:
        return json.load(f)

def load_intel_log():
    if os.path.exists(INTEL_LOG):
        with open(INTEL_LOG, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"scans": []}

def save_intel_log(log):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(INTEL_LOG, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)

# ═══════════════════════════════════════
# Dimension 1: Web Monitoring
# ═══════════════════════════════════════

def scan_web(competitor):
    from page_fetcher import fetch_and_save
    from diff_detector import detect_changes
    results = []
    comp_id = competitor["id"]
    for monitor in competitor.get("web_monitors", []):
        url, label = monitor["url"], monitor["label"]
        page_type = monitor.get("type", "general")
        sys.stdout.write(f"      🌐 {label}... "); sys.stdout.flush()
        try:
            fr = fetch_and_save(url, comp_id, label, page_type)
            if fr["is_first"]:
                print("📸 First snapshot")
                results.append({"source": "web", "label": label, "status": "first_snapshot"})
            elif fr["is_changed"]:
                diff = detect_changes(comp_id, label)
                sev = diff.get("changes", {}).get("severity", "minor")
                added = diff.get("changes", {}).get("lines_added", 0)
                removed = diff.get("changes", {}).get("lines_removed", 0)
                icon = {"major": "🔴", "moderate": "🟡", "minor": "🟢"}.get(sev, "⚪")
                print(f"{icon} CHANGED (+{added}/-{removed})")
                results.append({"source": "web", "label": label, "status": "changed",
                    "severity": sev, "added": added, "removed": removed, "url": url, "diff_data": diff})
            else:
                print("✅ No change")
                results.append({"source": "web", "label": label, "status": "no_change"})
        except Exception as e:
            print(f"❌ {e}")
            results.append({"source": "web", "label": label, "status": "error", "error": str(e)})
    return results

# ═══════════════════════════════════════
# Dimension 2: Social Media
# ═══════════════════════════════════════

def scan_social(competitor, settings):
    results = []
    keywords = competitor.get("social_keywords", [])
    subreddits = competitor.get("social_subreddits", [])
    if not keywords: return results
    keyword_str = ", ".join(keywords)

    for sub in subreddits:
        sub_name = sub.replace("r/", "")
        sys.stdout.write(f"      📱 Reddit r/{sub_name}... "); sys.stdout.flush()
        try:
            from reddit_fetcher import run as reddit_fetch
            from keyword_filter import run as kw_filter
            data = reddit_fetch(f"https://www.reddit.com/r/{sub_name}/", max_posts=25)
            filtered = kw_filter(data, keyword_str)
            matched = filtered["metadata"].get("matched_posts", 0)
            total = filtered["metadata"].get("total_posts", 0)
            if matched > 0:
                print(f"🔍 {matched}/{total} mentions")
                results.append({"source": "reddit", "subreddit": sub_name, "status": "found",
                    "matched": matched, "total": total, "data": filtered})
            else:
                print(f"0/{total}")
                results.append({"source": "reddit", "subreddit": sub_name, "status": "no_mentions", "total": total})
        except Exception as e:
            print(f"❌ {e}")
            results.append({"source": "reddit", "subreddit": sub_name, "status": "error", "error": str(e)})

    sys.stdout.write(f"      📱 X (Twitter)... "); sys.stdout.flush()
    try:
        from x_fetcher import run as x_fetch
        for kw in keywords[:2]:
            data = x_fetch(keyword=kw, max_posts=20)
            if data and data.get("posts"):
                print(f"🔍 {len(data['posts'])} posts for '{kw}'")
                results.append({"source": "x", "keyword": kw, "status": "found", "count": len(data["posts"]), "data": data})
            else:
                print(f"0 for '{kw}'")
    except Exception as e:
        print(f"⚠️  {e}")
        results.append({"source": "x", "status": "error", "error": str(e)})
    return results

# ═══════════════════════════════════════
# Dimension 3: GitHub
# ═══════════════════════════════════════

def scan_github(competitor, settings):
    results = []
    repos = competitor.get("github_repos", [])
    days = settings.get("github_lookback_days", 7)
    for repo in repos:
        sys.stdout.write(f"      🐙 GitHub {repo}... "); sys.stdout.flush()
        try:
            from github_fetcher import run as gh_fetch
            data = gh_fetch(repo, days=days, fetch_type="all")
            total = data["metadata"]["total_posts"]
            ri = data["metadata"].get("repo_info", {})
            stars = ri.get("stars", "?")
            issues = [p for p in data["posts"] if not p.get("is_pr") and not p.get("tag")]
            prs = [p for p in data["posts"] if p.get("is_pr")]
            releases = [p for p in data["posts"] if p.get("tag")]
            print(f"⭐{stars} | {len(issues)} issues, {len(prs)} PRs, {len(releases)} releases")
            results.append({"source": "github", "repo": repo, "status": "fetched",
                "issues_count": len(issues), "prs_count": len(prs), "releases_count": len(releases),
                "stars": stars, "repo_info": ri, "data": data})
        except Exception as e:
            print(f"❌ {e}")
            results.append({"source": "github", "repo": repo, "status": "error", "error": str(e)})
    return results

# ═══════════════════════════════════════
# AI Synthesis
# ═══════════════════════════════════════

def synthesize(comp_name, web_r, social_r, github_r, provider="openai", model=None, base_url=None, traffic_r=None):
    web_s = ""
    for r in web_r:
        if r["status"] == "changed":
            web_s += f"- {r['label']}: CHANGED ({r.get('severity')}, +{r.get('added',0)}/-{r.get('removed',0)})\n"
            added_c = r.get("diff_data",{}).get("changes",{}).get("added_content",[])[:3]
            if added_c: web_s += f"  Additions: {'; '.join(added_c)}\n"

    social_s = ""
    for r in social_r:
        if r["status"] == "found":
            if r["source"] == "reddit":
                social_s += f"- Reddit r/{r.get('subreddit')}: {r['matched']} posts\n"
                for p in r.get("data",{}).get("posts",[])[:3]:
                    social_s += f"  [{p.get('score',0)}pts] {p.get('title','')[:70]}\n"
            elif r["source"] == "x":
                social_s += f"- X '{r.get('keyword')}': {r['count']} posts\n"

    github_s = ""
    for r in github_r:
        if r["status"] == "fetched":
            github_s += f"- {r['repo']}: ⭐{r.get('stars','?')}, {r['issues_count']} issues, {r['prs_count']} PRs, {r['releases_count']} releases\n"
            top = sorted([p for p in r.get("data",{}).get("posts",[]) if not p.get("is_pr") and not p.get("tag")],
                         key=lambda x: x.get("comment_count",0), reverse=True)[:3]
            for i in top:
                github_s += f"  #{i['id']} {i.get('title','')[:60]} ({i.get('comment_count',0)} comments)\n"

    traffic_s = ""
    for r in (traffic_r or []):
        if r.get("status") == "fetched":
            d = r.get("data", {})
            eng = d.get("engagement", {})
            ts = d.get("traffic_sources", {})
            traffic_s += f"- {d.get('domain')}: Global Rank #{d.get('global_rank', 'N/A')}\n"
            traffic_s += f"  Bounce: {eng.get('bounce_rate','N/A')}, Pages/visit: {eng.get('pages_per_visit','N/A')}\n"
            if ts:
                top_sources = sorted(ts.items(), key=lambda x: x[1] or 0, reverse=True)[:3]
                traffic_s += f"  Top sources: {', '.join(f'{k}={v:.0%}' for k,v in top_sources if v)}\n"
            monthly = d.get("estimated_monthly_visits", {})
            if monthly:
                recent = sorted(monthly.items())[-3:]
                traffic_s += f"  Recent visits: {', '.join(f'{m}={v:,}' for m,v in recent)}\n"

    if not web_s and not social_s and not github_s and not traffic_s:
        return "No significant intelligence found."

    prompt = f"""You are a competitive intelligence analyst. Synthesize data about "{comp_name}":

## Web Changes
{web_s or "No changes."}

## Social Media
{social_s or "No mentions."}

## GitHub Activity
{github_s or "No repos tracked."}

## Traffic Data
{traffic_s or "No traffic data."}

Provide in Chinese (简体中文):
### 总结 (2-3句话)
### 产品方向
### 流量分析 (基于traffic data)
### 市场反馈
### 关键信号 (3-5个)
### 建议行动
### 紧急程度: 🔴高 / 🟡中 / 🟢低
"""

    try:
        if provider == "anthropic" and not base_url:
            import anthropic
            m = model or "claude-sonnet-4-5-20250929"
            r = anthropic.Anthropic().messages.create(model=m, max_tokens=3000, messages=[{"role":"user","content":prompt}])
            return r.content[0].text
        else:
            from openai import OpenAI
            kw = {"base_url": base_url} if base_url else {}
            m = model or "gpt-4o-mini"
            r = OpenAI(**kw).chat.completions.create(model=m, max_tokens=3000,
                messages=[{"role":"system","content":"Competitive intelligence analyst. Write in Chinese."},
                          {"role":"user","content":prompt}])
            return r.choices[0].message.content
    except Exception as e:
        return f"AI synthesis failed: {e}"

# ═══════════════════════════════════════
# Dimension 4: Traffic Data (SimilarWeb)
# ═══════════════════════════════════════

def scan_traffic(competitor):
    results = []
    domain = competitor.get("website", "").replace("https://","").replace("http://","").rstrip("/")
    if not domain: return results
    sys.stdout.write(f"      📊 {domain}... "); sys.stdout.flush()
    try:
        from traffic_fetcher import fetch_domain
        data = fetch_domain(domain)
        if data.get("success"):
            rank = data.get("global_rank", "N/A")
            eng = data.get("engagement", {})
            bounce = eng.get("bounce_rate")
            bounce_str = f"{bounce*100:.1f}%" if bounce else "N/A"
            print(f"Rank #{rank} | Bounce {bounce_str}")
            results.append({"source": "traffic", "domain": domain, "status": "fetched", "data": data})
        else:
            print(f"⚠️  {data.get('error', 'Unknown')}")
            results.append({"source": "traffic", "domain": domain, "status": "error", "error": data.get("error")})
    except Exception as e:
        print(f"❌ {e}")
        results.append({"source": "traffic", "domain": domain, "status": "error", "error": str(e)})
    return results

# ═══════════════════════════════════════
# Commands
# ═══════════════════════════════════════

def cmd_scan(comp_filter=None, dimensions=None, provider="openai", model=None, base_url=None):
    config = load_config()
    settings = config.get("settings", {})
    log = load_intel_log()
    comps = config["competitors"]
    if comp_filter:
        comps = [c for c in comps if c["id"] == comp_filter]
        if not comps: print(f"'{comp_filter}' not found."); return
    dims = dimensions or ["web", "social", "github", "traffic"]

    print(f"\n{'='*60}")
    print(f"  🔍 COMPETITIVE INTELLIGENCE SCAN — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  Dimensions: {', '.join(dims)}")
    print(f"{'='*60}\n")

    for comp in comps:
        print(f"  ┌{'─'*50}")
        print(f"  │ 🏢 {comp['name']} ({comp['website']})")
        print(f"  ├{'─'*50}")
        wr, sr, gr = [], [], []
        wr, sr, gr, tr = [], [], [], []
        if "web" in dims:     print(f"  │ 📡 Web:"); wr = scan_web(comp)
        if "social" in dims:  print(f"  │ 💬 Social:"); sr = scan_social(comp, settings)
        if "github" in dims:  print(f"  │ 🐙 GitHub:"); gr = scan_github(comp, settings)
        if "traffic" in dims: print(f"  │ 📊 Traffic:"); tr = scan_traffic(comp)

        has_data = (any(r.get("status")=="changed" for r in wr) or
                    any(r.get("status")=="found" for r in sr) or
                    any(r.get("status")=="fetched" and r.get("issues_count",0)>0 for r in gr) or
                    any(r.get("status")=="fetched" for r in tr))

        analysis = ""
        if has_data:
            sys.stdout.write(f"  │ 🤖 Synthesizing... "); sys.stdout.flush()
            analysis = synthesize(comp["name"], wr, sr, gr, provider, model, base_url, tr)
            print("done")

        log["scans"].append({
            "competitor": comp["name"], "competitor_id": comp["id"],
            "scanned_at": datetime.now(timezone.utc).isoformat(), "dimensions": dims,
            "web_changes": sum(1 for r in wr if r.get("status")=="changed"),
            "social_mentions": sum(r.get("matched", r.get("count",0)) for r in sr if r.get("status")=="found"),
            "github_items": sum(r.get("issues_count",0)+r.get("prs_count",0) for r in gr if r.get("status")=="fetched"),
            "traffic_rank": next((r["data"].get("global_rank") for r in tr if r.get("status")=="fetched"), None),
            "analysis": analysis
        })
        print(f"  └{'─'*50}\n")
        if analysis:
            print(f"{'─'*60}")
            print(f"  📊 {comp['name']} — Intelligence Brief")
            print(f"{'─'*60}\n{analysis}\n")

    save_intel_log(log)

def cmd_watch(interval=24, **kw):
    print(f"\n🔄 Auto-scan every {interval}h. Ctrl+C to stop.\n")
    try:
        while True:
            cmd_scan(**kw)
            print(f"\n⏰ Next: {(datetime.now()+timedelta(hours=interval)).strftime('%Y-%m-%d %H:%M')}\n")
            time.sleep(interval * 3600)
    except KeyboardInterrupt:
        print("\n⏹️  Stopped.")

def main():
    parser = argparse.ArgumentParser(description="竞品情报 — 全维度扫描")
    sub = parser.add_subparsers(dest="command")
    p = sub.add_parser("scan")
    p.add_argument("--competitor"); p.add_argument("--only")
    p.add_argument("--provider", default="openai"); p.add_argument("--model"); p.add_argument("--base-url")
    w = sub.add_parser("watch")
    w.add_argument("--interval", type=int, default=24)
    w.add_argument("--provider", default="openai"); w.add_argument("--model"); w.add_argument("--base-url")
    args = parser.parse_args()
    if args.command == "scan":
        dims = args.only.split(",") if args.only else None
        cmd_scan(args.competitor, dims, args.provider, args.model, args.base_url)
    elif args.command == "watch":
        cmd_watch(args.interval, provider=args.provider, model=args.model, base_url=args.base_url)
    else: parser.print_help()

if __name__ == "__main__":
    main()
