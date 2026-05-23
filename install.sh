#!/usr/bin/env bash
set -euo pipefail

SKILL_DIR="$HOME/.openclaw/workspace/skills/competitive-intel"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "🦞 Installing openclaw-competitive-intel..."
echo ""

# Create target directory
mkdir -p "$SKILL_DIR/skills"
mkdir -p "$SKILL_DIR/configs"
mkdir -p "$SKILL_DIR/data/snapshots"

# Copy skill definition
cp "$SCRIPT_DIR/SKILL.md" "$SKILL_DIR/SKILL.md"

# Copy scripts
for script in traffic_fetcher.py reddit_fetcher.py keyword_filter.py github_fetcher.py page_fetcher.py diff_detector.py youtube_fetcher.py x_fetcher.py tweetclaw_fetcher.py; do
  if [ -f "$SCRIPT_DIR/skills/$script" ]; then
    cp "$SCRIPT_DIR/skills/$script" "$SKILL_DIR/skills/$script"
    echo "  ✅ skills/$script"
  else
    echo "  ⚠️  skills/$script not found, skipping"
  fi
done

# Copy competitor config (don't overwrite existing)
if [ ! -f "$SKILL_DIR/configs/competitors.json" ]; then
  cp "$SCRIPT_DIR/configs/competitors.json" "$SKILL_DIR/configs/competitors.json"
  echo "  ✅ configs/competitors.json (sample)"
else
  echo "  ⏭️  configs/competitors.json already exists, not overwriting"
fi

echo ""

# Install Python dependencies
echo "📦 Installing Python dependencies..."
if command -v pip3 &> /dev/null; then
  pip3 install requests beautifulsoup4 feedparser --break-system-packages 2>/dev/null || \
  pip3 install requests beautifulsoup4 feedparser 2>/dev/null || \
  echo "  ⚠️  pip3 install failed. Please run manually:"
  echo "     pip3 install requests beautifulsoup4 feedparser"
else
  echo "  ⚠️  pip3 not found. Please install Python 3 and run:"
  echo "     pip3 install requests beautifulsoup4 feedparser"
fi

echo ""
echo "✅ Installation complete!"
echo ""
echo "📁 Installed to: $SKILL_DIR"
echo ""
echo "Next steps:"
echo "  1. Edit $SKILL_DIR/configs/competitors.json to add your competitors"
echo "  2. (Optional) Set API keys for enhanced data:"
echo "     export YOUTUBE_API_KEY=\"your_key\"    # YouTube video + comment data"
echo "     export GITHUB_TOKEN=\"your_token\"      # Higher GitHub rate limits"
echo "     export TWITTER_BEARER_TOKEN=\"your_token\"  # X/Twitter data"
echo "     export XQUIK_API_KEY=\"your_key\"       # TweetClaw/Xquik X/Twitter data"
echo "  3. Restart OpenClaw: openclaw gateway stop && openclaw gateway"
echo "  4. Message your agent: \"Run a full competitor scan on [competitor name]\""
echo ""
