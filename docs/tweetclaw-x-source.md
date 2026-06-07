# TweetClaw X/Twitter Source

TweetClaw adds an X/Twitter source for competitor intelligence without asking
users to manage a raw X API bearer token. It uses the Xquik API key that the
OpenClaw TweetClaw plugin also uses, then writes the same standard JSON contract
as the existing Reddit, YouTube, GitHub, traffic, and X fetchers.

## Install TweetClaw In OpenClaw

```bash
openclaw plugins install npm:@xquik/tweetclaw
openclaw config set plugins.entries.tweetclaw.config.apiKey "$XQUIK_API_KEY"
openclaw config set tools.alsoAllow '["explore", "tweetclaw"]'
openclaw plugins inspect tweetclaw --runtime
openclaw skills info tweetclaw
```

Store `XQUIK_API_KEY` in OpenClaw plugin config or the local shell environment.
Do not paste API keys into chat, reports, issues, screenshots, or generated
Markdown.

## Fetch X/Twitter Signals

```bash
python3 skills/tweetclaw_fetcher.py "cursor ai" --count 50 -o data/x_cursor.json
cat data/x_cursor.json | python3 skills/keyword_filter.py "pricing, outage, alternative"
cat data/x_cursor.json | python3 skills/ai_analyzer.py -o data/x_cursor_analysis.json
```

Use `--since-time`, `--until-time`, and `--cursor` for time windows and
pagination. The output includes:

- `source: "x_tweetclaw"`
- `posts[]` with `id`, `body`, `author`, `score`, `url`, `created_at`, and
  `comments`
- `metadata.has_more` and `metadata.next_cursor` when the API returns another
  page

## When To Use This Source

Use TweetClaw when a competitor is active on X/Twitter, when launch feedback is
moving faster than Reddit or GitHub, or when you need public tweet search in the
same report as website changes and repository activity.

Keep `skills/x_fetcher.py` for teams that already operate a direct X developer
token. Prefer `skills/tweetclaw_fetcher.py` when the team has a Xquik API key or
already uses the TweetClaw OpenClaw plugin.
