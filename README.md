# 🦞 openclaw-competitive-intel

**Competitive intelligence skill for [OpenClaw](https://openclaw.ai) — turn your personal AI assistant into a competitive analyst that collects real data, not hallucinations.**

Your competitors are shipping features, changing pricing, getting roasted on Reddit, and going viral on YouTube — all while you're not looking. This skill gives your OpenClaw agent the ability to monitor it all from a single WhatsApp/Telegram/Discord message.

Unlike generic AI analysis that relies on training data (which is months old at best), this skill runs **real Python scripts** that fetch live data from Reddit, YouTube, GitHub, and traffic APIs. Every claim in the report comes with a URL you can click to verify.

## What It Does

| Capability | How | Output |
| --- | --- | --- |
| 🌐 **Traffic Analysis** | SimilarWeb data via `traffic_fetcher.py` | Monthly visits, bounce rate, traffic sources, geo distribution, competitor comparison |
| 💬 **Reddit Sentiment** | Full-site search + subreddit deep-dive via `reddit_fetcher.py` | Subreddit ranking, top posts with scores, comment analysis, topic clustering |
| 🎬 **YouTube Sentiment** | YouTube Data API v3 via `youtube_fetcher.py` | Video stats (views, likes, comments), top comments verbatim, channel ranking |
| 🐙 **GitHub Activity** | GitHub API via `github_fetcher.py` | Issues, PRs, releases, bug trends, feature requests |
| 📄 **Website Monitoring** | Page snapshots + diff via `page_fetcher.py` / `diff_detector.py` | Changelog detection, pricing page changes, landing page updates |
| 🐦 **X/Twitter Monitoring** | X API v2 via `x_fetcher.py` | Tweet search, engagement metrics, sentiment |
| 🔍 **Keyword Filtering** | Cross-source filtering via `keyword_filter.py` | Topic slicing across any data source (bugs, pricing, feature requests, competitor mentions) |

### How It Works

```
User: "Full competitor scan on Manus AI"
                    │
                    ▼
        ┌───────────────────────┐
        │   SKILL.md (Agent)    │
        │   Reads competitors   │
        │   config, plans the   │
        │   scan, runs scripts  │
        └───────────┬───────────┘
                    │
    ┌───────┬───────┼───────┬───────┬───────┐
    ▼       ▼       ▼       ▼       ▼       ▼
 traffic  reddit  youtube  github  page   x_fetcher
 _fetcher _fetcher _fetcher _fetcher _fetcher  .py
   .py     .py     .py     .py     .py
    │       │       │       │       │       │
    ▼       ▼       ▼       ▼       ▼       ▼
 Similar  Reddit  YouTube  GitHub  Website  X/Twitter
  Web     RSS/API  API v3   API    Snapshot  API v2
    │       │       │       │       │       │
    └───────┴───────┼───────┴───────┴───────┘
                    ▼
            keyword_filter.py
            (topic slicing)
                    │
                    ▼
        ┌───────────────────────┐
        │   AI Analysis Layer   │
        │   Cross-references    │
        │   all data sources    │
        │   into actionable     │
        │   intelligence brief  │
        └───────────────────────┘
```

---

## Quick Start

### Installation

```bash
# Clone the repo
git clone https://github.com/jrr996shujin-png/openclaw-competitive-intel.git

# Copy to OpenClaw workspace
cp -r openclaw-competitive-intel ~/.openclaw/workspace/skills/competitive-intel

# Install Python dependencies
pip3 install requests beautifulsoup4 feedparser --break-system-packages
```

Restart OpenClaw or start a new session to pick it up.

### API Keys (Optional)

Most tools work out of the box with zero configuration. API keys unlock additional capabilities:

| Key | Tool | Required? | How to Get |
| --- | --- | --- | --- |
| `YOUTUBE_API_KEY` | `youtube_fetcher.py` | Optional | [Google Cloud Console](https://console.cloud.google.com) → Enable YouTube Data API v3 → Create API Key |
| `GITHUB_TOKEN` | `github_fetcher.py` | Optional | [GitHub Settings](https://github.com/settings/tokens) → Personal access token (raises rate limit from 60 to 5,000 req/hr) |
| `TWITTER_BEARER_TOKEN` | `x_fetcher.py` | Optional | [X Developer Portal](https://developer.x.com) → Create App → Bearer Token |
| `REDDIT_CLIENT_ID` + `REDDIT_CLIENT_SECRET` | `reddit_fetcher.py` | Optional | [Reddit Apps](https://www.reddit.com/prefs/apps) — but note: Reddit ended self-service API key creation in Nov 2025. RSS mode (no key needed) works for most use cases. |

Add keys to your shell profile:

```bash
echo 'export YOUTUBE_API_KEY="your_key_here"' >> ~/.zshrc
echo 'export GITHUB_TOKEN="your_token_here"' >> ~/.zshrc
source ~/.zshrc
```

Then restart the OpenClaw gateway so the new environment variables take effect.

### Configure Competitors

Edit `configs/competitors.json` to define your competitive landscape:

```json
[
  {
    "name": "Manus AI",
    "id": "manus",
    "website": "https://manus.im",
    "web_monitors": [
      {"type": "changelog", "url": "https://manus.im/blog", "label": "Blog"},
      {"type": "pricing", "url": "https://manus.im/pricing", "label": "Pricing"},
      {"type": "landing_page", "url": "https://manus.im", "label": "Homepage"}
    ],
    "social_keywords": ["manus ai", "manus agent"],
    "social_subreddits": ["r/ManusOfficial"],
    "github_repos": []
  }
]
```

### Try It

Message your OpenClaw on WhatsApp, Telegram, Discord, or any connected channel:

```
"Run a full competitor scan on Manus AI"
"Compare traffic between cursor.com, manus.im, and windsurf.com"
"What are people saying about Cursor on Reddit?"
"Check YouTube sentiment for OpenAI Codex in the last month"
"Has Manus updated their pricing page?"
```

---

## Tools in Detail

### Tool 1: Traffic Analysis (`traffic_fetcher.py`)

Fetches website analytics data including global rank, monthly visits, bounce rate, pages per visit, average visit duration, traffic sources, and geographic distribution.

**Cost:** 🆓 Free — no API key required.

```bash
# Single website
python3 skills/traffic_fetcher.py cursor.com -f json

# Multi-site comparison
python3 skills/traffic_fetcher.py cursor.com manus.im windsurf.com -f json

# Markdown report
python3 skills/traffic_fetcher.py cursor.com manus.im -f markdown -o data/traffic_report.md
```

---

### Tool 2: Reddit Sentiment (`reddit_fetcher.py`)

Two-phase workflow: **discover** where your competitor is discussed across all of Reddit, then **deep-dive** into the most active communities.

**Cost:** 🆓 Free — uses RSS feeds by default (no API key needed). Install `feedparser` for best results.

**Authentication cascade:** OAuth API → RSS Feed → .json scraping (automatic fallback).

> ⚠️ **Note:** Reddit ended self-service API key creation in November 2025. New accounts cannot create OAuth apps without manual approval. The RSS fallback mode works well for most use cases and requires no authentication.

**Phase 1: Full-site search (discover)**
```bash
# Find which subreddits discuss your competitor
python3 skills/reddit_fetcher.py --search "manus ai" --no-comments -o data/search_manus.json

# Filter by time
python3 skills/reddit_fetcher.py --search "manus ai" --time week --no-comments -o data/search_manus.json
```

Output includes `subreddit_ranking` — a ranked list of communities where the keyword appears most.

**Phase 2: Subreddit deep-dive (investigate)**
```bash
# Scrape a specific subreddit based on discovery results
python3 skills/reddit_fetcher.py "https://www.reddit.com/r/ManusOfficial/" --pages 1 --sort hot -o data/reddit_manus.json
```

**Phase 3: Topic slicing**
```bash
cat data/reddit_manus.json | python3 skills/keyword_filter.py "bug, broken, crash"       # Quality issues
cat data/reddit_manus.json | python3 skills/keyword_filter.py "pricing, expensive, free"  # Pricing feedback
cat data/reddit_manus.json | python3 skills/keyword_filter.py "feature request, wish"     # User demands
cat data/reddit_manus.json | python3 skills/keyword_filter.py "better than, vs, switch"   # Competitor comparisons
```

---

### Tool 3: Keyword Filter (`keyword_filter.py`)

Cross-source keyword filtering. Works with output from any fetcher — Reddit, YouTube, GitHub, or X.

**Cost:** 🆓 Free — runs locally with no external calls.

```bash
# Pipe from any fetcher
cat data/reddit.json | python3 skills/keyword_filter.py "manus, cursor, pricing, bug"

# File-to-file
python3 skills/keyword_filter.py "keyword1, keyword2" -i data/reddit.json -o data/filtered.json
```

Output preserves the original data format and adds hit statistics per keyword.

---

### Tool 4: GitHub Activity (`github_fetcher.py`)

Monitors public repositories for issues, pull requests, and releases. Useful for tracking open-source competitors or understanding product development velocity.

**Cost:** 🆓 Free — 60 requests/hour without token, 5,000/hour with `GITHUB_TOKEN`.

```bash
# Last 7 days of activity
python3 skills/github_fetcher.py "owner/repo" --days 7 -o data/github.json

# Issues only
python3 skills/github_fetcher.py "owner/repo" --type issues --days 30 -o data/github.json

# Filter by label
python3 skills/github_fetcher.py "owner/repo" --type issues --label bug -o data/github.json
```

**Analysis output includes:** Categorized issues (Features / Bug Fixes / Performance), priority tags (🔴 High / 🟡 Normal), assignees, status, and a subjective "Top 2 issues worth watching" assessment.

---

### Tool 5: Website Monitoring (`page_fetcher.py` + `diff_detector.py`)

Takes snapshots of competitor web pages and detects changes between snapshots. Tracks changelogs, pricing pages, landing pages, and any other URL.

**Cost:** 🆓 Free — no API key required.

```bash
# Take a snapshot
python3 skills/page_fetcher.py "https://manus.im/pricing" --type pricing --id manus --label "Pricing"

# Detect changes (requires at least 2 snapshots)
python3 skills/diff_detector.py --id manus --label "Pricing"
```

Output includes: severity (`major` / `moderate` / `minor` / `none`), lines added/removed, and the actual content changes.

---

### Tool 6: X/Twitter Monitoring (`x_fetcher.py`)

Searches X/Twitter for competitor mentions and engagement metrics.

**Cost:** 💰 Pay-per-use (purchase credits upfront). Legacy plans Basic $200/mo and Pro $5,000/mo still available. Monthly cap: 2M post reads.

**Requires:** `TWITTER_BEARER_TOKEN` environment variable.

```bash
python3 skills/x_fetcher.py "search keywords" --count 50 -o data/x.json
```

---

### Tool 7: YouTube Sentiment (`youtube_fetcher.py`)

Searches YouTube for competitor-related videos and analyzes comment sections. Returns video statistics (views, likes, comment count), top comments by relevance, and channel rankings.

**Cost:** 🆓 Free with daily quota — 10,000 units/day. A typical search (10 videos + comments) costs ~111 units.

**Requires:** `YOUTUBE_API_KEY` environment variable.

```bash
# Search for competitor videos (default: last 180 days, 10 videos, sorted by relevance)
python3 skills/youtube_fetcher.py --search "manus ai" -o data/youtube_manus.json

# Sort by view count, fetch 20 videos
python3 skills/youtube_fetcher.py --search "manus ai review" --max-videos 20 --sort viewCount -o data/youtube_manus.json

# Last 30 days only (overrides 180-day default)
python3 skills/youtube_fetcher.py --search "manus ai" --days 30 -o data/youtube_manus.json

# Skip comments to save quota
python3 skills/youtube_fetcher.py --search "manus ai" --no-comments -o data/youtube_manus.json

# Specific channel
python3 skills/youtube_fetcher.py --channel "UCxxxxxxx" --max-videos 10 -o data/youtube_channel.json

# Topic slicing with keyword filter
cat data/youtube_manus.json | python3 skills/keyword_filter.py "bug, pricing, alternative"
```

**Analysis output includes:** Video list with stats, channel ranking, 2-3 top comments per video verbatim, comment sentiment summary (what users praise, complain about, request, and which competitors they compare to), and video type distribution (positive review / negative review / tutorial / comparison).

---

## Workflows

### Workflow A: Full Competitor Scan

Triggered by: *"Scan competitors"*, *"Competitor report"*, *"Full scan on X"*

1. **Read config** — loads `configs/competitors.json`
2. **Execute all scripts** per competitor (traffic → Reddit search → Reddit deep-dive → keyword filter → GitHub → website snapshots → YouTube)
3. **Display raw evidence** — every claim includes title, URL, score, author, date
4. **Cross-reference analysis** — summary, key signals per dimension, urgency rating (🔴 / 🟡 / 🟢), recommended actions
5. **Execution verification checklist** + cost summary

### Workflow B: Quick Single-Competitor Check

Triggered by: *"What's going on with X?"*, *"Check on Manus"*

Runs traffic + Reddit search + YouTube. Produces a concise briefing.

### Workflow C: Multi-Competitor Traffic Comparison

Triggered by: *"Compare X, Y, and Z traffic"*

Single command, side-by-side comparison with insights.

### Workflow D: Reddit Sentiment Deep-Dive

Triggered by: *"What does Reddit say about X?"*

Mandatory 3-step flow: full-site search → subreddit deep-dive → evidence presentation with full URLs.

### Workflow E: Website Change Detection

Triggered by: *"Has X changed their pricing?"*

Takes new snapshot, compares with previous, analyzes strategic implications.

### Workflow F: YouTube Sentiment Analysis

Triggered by: *"What does YouTube say about X?"*

Searches recent videos, displays comment highlights, summarizes sentiment by topic.

---

## Cost Estimation

### API Costs Per Tool

| Tool | API Cost | Rate Limit | Typical Usage |
| --- | --- | --- | --- |
| `traffic_fetcher.py` | 🆓 Free | Unlimited | 0 |
| `reddit_fetcher.py` | 🆓 Free (RSS mode) | 2 sec/request | 0 |
| `youtube_fetcher.py` | 🆓 Free (quota-based) | 10,000 units/day | ~111 units (10 videos + comments) |
| `github_fetcher.py` | 🆓 Free | 60 req/hr (no token) · 5,000/hr (with token) | 0 |
| `page_fetcher.py` | 🆓 Free | Unlimited | 0 |
| `x_fetcher.py` | 💰 Pay-per-use (credit-based) | 2M post reads/month | Varies |

### Scenario Estimates

| Scenario | Script Calls | YouTube Quota | Est. Time |
| --- | --- | --- | --- |
| Full scan (1 competitor) | 5–7 | ~111 units | 3–5 min |
| Full scan (3 competitors) | 15–21 | ~333 units | 8–15 min |
| Quick single check | 3–4 | ~111 units | 2–3 min |
| Reddit sentiment only | 2–3 | 0 | 1–2 min |
| YouTube sentiment only | 1–2 | ~111 units | 1–2 min |
| X/Twitter sentiment only | 1–2 | 0 | 1–2 min |
| Traffic comparison (3 sites) | 1 | 0 | 30 sec |

### LLM Token Consumption

Script output (JSON) is fed to the AI model as context. Larger outputs consume more tokens and cost more.

| Tool Output | Typical Size | Est. Input Tokens |
| --- | --- | --- |
| `traffic_fetcher` (1 site) | ~2 KB | ~500 |
| `reddit_fetcher` full search (100 posts, no comments) | ~30–80 KB | ~8,000–20,000 |
| `reddit_fetcher` deep-dive + comments (30 posts) | ~50–100 KB | ~12,000–25,000 |
| `youtube_fetcher` (10 videos + comments) | ~20–40 KB | ~5,000–10,000 |
| `github_fetcher` (7-day issues) | ~10–30 KB | ~3,000–8,000 |
| `page_fetcher` (1 snapshot) | ~5–15 KB | ~1,500–4,000 |
| `keyword_filter` output | ~5–20 KB | ~1,500–5,000 |
| `x_fetcher` (search results) | ~10–30 KB | ~3,000–8,000 |

**Full scan (1 competitor), all dimensions: ~40,000–70,000 input tokens + ~3,000–5,000 output tokens.**

### LLM Cost by Model

> ⚠️ Prices as of March 2026. Verify with each provider's official pricing page.

| Model | Input $/1M tokens | Output $/1M tokens | 1 Competitor Scan | 3 Competitor Scan |
| --- | --- | --- | --- | --- |
| **Claude Opus 4.5/4.6** | $15.00 | $75.00 | $0.98–$2.00 | $2.90–$6.00 |
| **Claude Sonnet 4/4.5** | $3.00 | $15.00 | $0.17–$0.40 | $0.50–$1.20 |
| **Claude Haiku 4.5** | $0.80 | $4.00 | $0.04–$0.09 | $0.13–$0.27 |
| **GPT-4o** | $2.50 | $10.00 | $0.13–$0.30 | $0.40–$0.90 |
| **GPT-4o-mini** | $0.15 | $0.60 | $0.01–$0.02 | $0.02–$0.05 |
| **Kimi K2/K2.5** | $0.60 | $2.50 | $0.03–$0.05 | $0.09–$0.16 |
| **DeepSeek V3** | $0.27 | $1.10 | $0.01–$0.03 | $0.04–$0.08 |
| **Grok 4.1 mini** | $0.20 | $0.50 | $0.01–$0.02 | $0.03–$0.05 |
| **Local (Ollama)** | Free | Free | $0 (electricity only) | $0 (electricity only) |

💡 **The cost difference is massive.** A 3-competitor scan costs ~$6 on Claude Opus but only ~$0.05 on DeepSeek or Kimi. Choose your model based on budget vs. analysis quality needs.

**Tips to reduce token usage:**
- Use `--no-comments` to skip comment fetching on Reddit and YouTube
- Reduce `--max-videos` and `--pages` parameters
- Use `keyword_filter.py` to narrow data before analysis

---

## Directory Structure

```
competitive-intel/
├── configs/
│   └── competitors.json          # Competitor definitions
├── skills/
│   ├── traffic_fetcher.py        # Website traffic (free, no key)
│   ├── reddit_fetcher.py         # Reddit data (free, RSS mode)
│   ├── keyword_filter.py         # Cross-source keyword filter
│   ├── github_fetcher.py         # GitHub issues/PRs/releases
│   ├── page_fetcher.py           # Website snapshots
│   ├── diff_detector.py          # Snapshot diff detection
│   ├── youtube_fetcher.py        # YouTube videos + comments (needs API key)
│   └── x_fetcher.py              # X/Twitter (needs bearer token)
├── data/                         # Output directory (auto-created)
│   └── snapshots/                # Website snapshot storage
└── SKILL.md                      # Agent instructions
```

## Requirements

| Requirement | Required For | Notes |
| --- | --- | --- |
| [OpenClaw](https://openclaw.ai) | Everything | Any model supported |
| Python 3.8+ | All scripts | Pre-installed on most systems |
| `requests` | All fetcher scripts | `pip3 install requests` |
| `beautifulsoup4` | `page_fetcher.py` | `pip3 install beautifulsoup4` |
| `feedparser` | `reddit_fetcher.py` (RSS mode) | `pip3 install feedparser` — **strongly recommended** |

Install all at once:

```bash
pip3 install requests beautifulsoup4 feedparser --break-system-packages
```

## Reddit Access in 2026

Reddit ended self-service API key creation in November 2025. This skill handles it gracefully:

| Auth Method | Status | What You Need |
| --- | --- | --- |
| **OAuth API** | ⚠️ Requires manual approval | Apply at [Reddit Developer Support](https://support.reddithelp.com/hc/en-us/requests/new?ticket_form_id=14868593862164). ~7 day review. |
| **RSS Feed** (default) | ✅ Works out of the box | Just install `feedparser`. No account needed. |
| **.json scraping** | ⚠️ Frequently blocked | Fallback only. Server IPs often rate-limited. |

The script automatically cascades through all three methods. For most users, RSS mode provides sufficient data (100 posts per search, subreddit rankings, post metadata).

## Contributing

Contributions welcome! Some areas that could use help:

- **Additional fetchers** — TikTok, Product Hunt, Hacker News, LinkedIn
- **Visualization** — React dashboard for scan results
- **Scheduling** — Cron-based automated weekly scans
- **Alerting** — Push notifications when significant changes detected
- **Localization** — SKILL.md translations for non-English markets
- **Additional data sources** — Ahrefs/SEMrush integration for backlink analysis

Please open an issue first to discuss what you'd like to change.

## License

[MIT](LICENSE)
