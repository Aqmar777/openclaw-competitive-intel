#!/usr/bin/env python3
"""
Skill: Traffic Fetcher (流量数据)
Fetch website traffic data from SimilarWeb — FREE, no API key needed.

Uses the same undocumented API endpoint that SimilarWeb's Chrome extension uses.
Returns: traffic, global/country rank, bounce rate, geo, traffic sources, category.

This is the SAME data that Manus charges ~4032 credits for. Here it costs $0.

Usage:
  python3 traffic_fetcher.py vidmuse.ai
  python3 traffic_fetcher.py cursor.com manus.im windsurf.com
  python3 traffic_fetcher.py cursor.com --compare manus.im windsurf.com
"""

import os, sys, json, argparse, time, requests
from datetime import datetime, timezone

API_URL = "https://data.similarweb.com/api/v1/data"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json"
}


def fetch_domain(domain):
    """Fetch traffic data for a single domain. FREE, no API key."""
    domain = domain.replace("https://", "").replace("http://", "").rstrip("/")

    sys.stderr.write(f"[traffic] Fetching {domain}...\n")

    try:
        r = requests.get(API_URL, params={"domain": domain}, headers=HEADERS, timeout=20)

        if r.status_code == 429:
            sys.stderr.write(f"[traffic] Rate limited. Waiting 60s...\n")
            time.sleep(60)
            r = requests.get(API_URL, params={"domain": domain}, headers=HEADERS, timeout=20)

        if r.status_code != 200:
            return {"domain": domain, "error": f"HTTP {r.status_code}", "success": False}

        data = r.json()

        # Extract and structure the data
        result = {
            "domain": domain,
            "success": True,
            "fetched_at": datetime.now(timezone.utc).isoformat(),

            # Basic info
            "site_name": data.get("SiteName", ""),
            "description": data.get("Description", ""),
            "category": data.get("Category", ""),
            "category_rank": data.get("CategoryRank", {}).get("Rank"),
            "is_small": data.get("IsSmall", False),

            # Rankings
            "global_rank": data.get("GlobalRank", {}).get("Rank"),
            "country_rank": data.get("CountryRank", {}).get("Rank"),
            "country_code": data.get("CountryRank", {}).get("CountryCode"),

            # Traffic (estimated)
            "estimated_monthly_visits": data.get("EstimatedMonthlyVisits", {}),

            # Engagement
            "engagement": {
                "visits": data.get("Engagments", {}).get("Visits"),
                "time_on_site": data.get("Engagments", {}).get("TimeOnSite"),
                "pages_per_visit": data.get("Engagments", {}).get("PagePerVisit"),
                "bounce_rate": data.get("Engagments", {}).get("BounceRate"),
            },

            # Traffic sources breakdown
            "traffic_sources": data.get("TrafficSources", {}),
            # e.g. {"Social": 0.05, "Paid Referrals": 0.01, "Mail": 0.02,
            #        "Referrals": 0.1, "Search": 0.5, "Direct": 0.32}

            # Geography
            "top_country_shares": data.get("TopCountryShares", []),
            # e.g. [{"CountryCode": 840, "Value": 0.35}, ...]

            # Related sites
            "also_visited": [s.get("Domain") for s in data.get("TopKeywords", [])[:5]] if data.get("TopKeywords") else [],

            # Raw data for advanced use
            "_raw_keys": list(data.keys())
        }

        return result

    except requests.exceptions.ConnectionError:
        return {"domain": domain, "error": "Connection failed (may need VPN for some regions)", "success": False}
    except Exception as e:
        return {"domain": domain, "error": str(e), "success": False}


def fetch_multiple(domains, delay=2):
    """Fetch traffic data for multiple domains with delay between requests."""
    results = []
    for i, domain in enumerate(domains):
        result = fetch_domain(domain)
        results.append(result)
        if i < len(domains) - 1:
            time.sleep(delay)  # Be polite to the API
    return results


def format_number(n):
    """Format large numbers for readability."""
    if n is None: return "N/A"
    if n >= 1_000_000: return f"{n/1_000_000:.1f}M"
    if n >= 1_000: return f"{n/1_000:.1f}K"
    return str(n)


def format_pct(v):
    if v is None: return "N/A"
    try:
        return f"{float(v)*100:.1f}%"
    except (ValueError, TypeError):
        return "N/A"


def format_time(seconds):
    if seconds is None: return "N/A"
    try:
        m, s = divmod(int(float(seconds)), 60)
        return f"{m}m{s}s"
    except (ValueError, TypeError):
        return "N/A"


# Country code mapping (numeric to name, common ones)
COUNTRY_MAP = {
    840: "US", 826: "GB", 156: "CN", 392: "JP", 276: "DE",
    250: "FR", 356: "IN", 76: "BR", 124: "CA", 36: "AU",
    410: "KR", 643: "RU", 380: "IT", 724: "ES", 528: "NL",
    158: "TW", 702: "SG", 344: "HK", 756: "CH", 752: "SE",
    578: "NO", 208: "DK", 246: "FI", 616: "PL", 792: "TR"
}


def print_report(results):
    """Print a formatted comparison report."""
    print(f"\n{'='*70}")
    print(f"  📊 WEBSITE TRAFFIC REPORT — {datetime.now().strftime('%Y-%m-%d')}")
    print(f"  Data source: SimilarWeb (free API)")
    print(f"{'='*70}\n")

    for r in results:
        if not r.get("success"):
            print(f"  ❌ {r['domain']}: {r.get('error', 'Failed')}\n")
            continue

        domain = r["domain"]
        eng = r.get("engagement", {})
        ts = r.get("traffic_sources", {})

        print(f"  ┌{'─'*60}")
        print(f"  │ 🌐 {domain}")
        if r.get("description"):
            print(f"  │ {r['description'][:70]}")
        print(f"  ├{'─'*60}")

        # Rankings
        print(f"  │ 📊 Rankings:")
        print(f"  │    Global: #{r.get('global_rank', 'N/A'):,}" if isinstance(r.get('global_rank'), int) else f"  │    Global: #{r.get('global_rank', 'N/A')}")
        if r.get("country_rank"):
            cc = r.get("country_code", "")
            print(f"  │    Country ({cc}): #{r['country_rank']:,}" if isinstance(r['country_rank'], int) else f"  │    Country ({cc}): #{r['country_rank']}")
        if r.get("category"):
            cat_rank = r.get("category_rank", "N/A")
            print(f"  │    Category ({r['category']}): #{cat_rank}")

        # Monthly visits
        monthly = r.get("estimated_monthly_visits", {})
        if monthly:
            print(f"  │")
            print(f"  │ 📈 Monthly Visits:")
            for month, visits in sorted(monthly.items())[-6:]:
                bar = "█" * min(int(visits / max(monthly.values()) * 20), 20) if max(monthly.values()) > 0 else ""
                print(f"  │    {month}: {format_number(visits):>8} {bar}")

        # Engagement
        print(f"  │")
        print(f"  │ 💡 Engagement:")
        print(f"  │    Bounce Rate: {format_pct(eng.get('bounce_rate'))}")
        print(f"  │    Pages/Visit: {eng.get('pages_per_visit', 'N/A')}")
        print(f"  │    Avg Duration: {format_time(eng.get('time_on_site'))}")

        # Traffic sources
        if ts:
            print(f"  │")
            print(f"  │ 🔗 Traffic Sources:")
            for source, share in sorted(ts.items(), key=lambda x: x[1] or 0, reverse=True):
                if share and share > 0.001:
                    bar = "█" * int(share * 30)
                    print(f"  │    {source:<16} {format_pct(share):>6}  {bar}")

        # Geography
        countries = r.get("top_country_shares", [])
        if countries:
            print(f"  │")
            print(f"  │ 🌍 Top Countries:")
            for c in countries[:5]:
                cc = COUNTRY_MAP.get(c.get("CountryCode", 0), str(c.get("CountryCode", "?")))
                share = c.get("Value", 0)
                print(f"  │    {cc:<5} {format_pct(share)}")

        print(f"  └{'─'*60}\n")

    # Comparison table (if multiple domains)
    if len([r for r in results if r.get("success")]) > 1:
        print(f"  {'─'*70}")
        print(f"  📊 COMPARISON TABLE")
        print(f"  {'─'*70}")
        print(f"  {'Domain':<25} {'Rank':>8} {'Bounce':>8} {'Pages':>8} {'Duration':>10}")
        print(f"  {'─'*25} {'─'*8} {'─'*8} {'─'*8} {'─'*10}")

        for r in results:
            if not r.get("success"): continue
            eng = r.get("engagement", {})
            rank = r.get("global_rank", "N/A")
            rank_str = f"#{rank:,}" if isinstance(rank, int) else "N/A"
            print(f"  {r['domain']:<25} {rank_str:>8} {format_pct(eng.get('bounce_rate')):>8} {str(eng.get('pages_per_visit', 'N/A'))[:5]:>8} {format_time(eng.get('time_on_site')):>10}")

        print(f"  {'─'*70}\n")


def generate_markdown(results):
    """Generate Markdown report."""
    lines = [f"# 📊 Website Traffic Report\n",
             f"**Date:** {datetime.now().strftime('%Y-%m-%d')}",
             f"**Source:** SimilarWeb (free API)\n"]

    for r in results:
        if not r.get("success"):
            lines.append(f"## ❌ {r['domain']}\nError: {r.get('error')}\n")
            continue

        eng = r.get("engagement", {})
        ts = r.get("traffic_sources", {})
        lines.append(f"## {r['domain']}\n")
        lines.append(f"| Metric | Value |")
        lines.append(f"|--------|-------|")
        lines.append(f"| Global Rank | #{r.get('global_rank', 'N/A')} |")
        lines.append(f"| Category | {r.get('category', 'N/A')} |")
        lines.append(f"| Bounce Rate | {format_pct(eng.get('bounce_rate'))} |")
        lines.append(f"| Pages/Visit | {eng.get('pages_per_visit', 'N/A')} |")
        lines.append(f"| Avg Duration | {format_time(eng.get('time_on_site'))} |")
        lines.append("")

        if ts:
            lines.append("### Traffic Sources\n")
            lines.append("| Source | Share |")
            lines.append("|--------|-------|")
            for src, share in sorted(ts.items(), key=lambda x: x[1] or 0, reverse=True):
                if share and share > 0.001:
                    lines.append(f"| {src} | {format_pct(share)} |")
            lines.append("")

    return "\n".join(lines)


def run(domains, output_format="json"):
    """Main entry point for composition integration."""
    results = fetch_multiple(domains)

    if output_format == "report":
        print_report(results)
    elif output_format == "markdown":
        print(generate_markdown(results))

    return results


def main():
    parser = argparse.ArgumentParser(description="Fetch website traffic data (FREE, no API key)")
    parser.add_argument("domains", nargs="+", help="Domain(s) to analyze")
    parser.add_argument("--compare", nargs="*", help="Additional domains to compare")
    parser.add_argument("-f", "--format", default="report", choices=["report", "json", "markdown"])
    parser.add_argument("-o", "--output", help="Save to file")
    parser.add_argument("--delay", type=int, default=2, help="Delay between requests (seconds)")
    args = parser.parse_args()

    all_domains = args.domains + (args.compare or [])
    results = fetch_multiple(all_domains, args.delay)

    if args.format == "report":
        print_report(results)
    elif args.format == "json":
        json.dump(results, sys.stdout, ensure_ascii=False, indent=2)
    elif args.format == "markdown":
        md = generate_markdown(results)
        print(md)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            if args.format == "markdown":
                f.write(generate_markdown(results))
            else:
                json.dump(results, f, ensure_ascii=False, indent=2)
        sys.stderr.write(f"Saved to {args.output}\n")


if __name__ == "__main__":
    main()
