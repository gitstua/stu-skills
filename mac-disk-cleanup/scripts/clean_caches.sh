#!/usr/bin/env bash
# Safe macOS cache cleanup: npm, pip3, Homebrew downloads
set -euo pipefail

freed=0

echo "=== Cache Cleanup ==="

# npm cache
if command -v npm &>/dev/null; then
  size=$(du -sm ~/.npm 2>/dev/null | cut -f1 || echo 0)
  npm cache clean --force 2>/dev/null
  after=$(du -sm ~/.npm 2>/dev/null | cut -f1 || echo 0)
  saved=$((size - after))
  echo "npm: freed ~${saved} MB"
  freed=$((freed + saved))
fi

# pip3 cache
if command -v pip3 &>/dev/null; then
  size=$(du -sm ~/Library/Caches/pip 2>/dev/null | cut -f1 || echo 0)
  pip3 cache purge 2>/dev/null || true
  echo "pip3: freed ~${size} MB"
  freed=$((freed + size))
fi

# Homebrew cache
if command -v brew &>/dev/null; then
  brew cleanup 2>/dev/null | grep "freed\|Removing" | tail -3 || true
  # Also clear the downloads cache which brew cleanup misses
  if [ -d ~/Library/Caches/Homebrew/downloads ]; then
    size=$(du -sm ~/Library/Caches/Homebrew/downloads 2>/dev/null | cut -f1 || echo 0)
    rm -rf ~/Library/Caches/Homebrew/downloads
    echo "Homebrew downloads: freed ~${size} MB"
    freed=$((freed + size))
  fi
fi

echo ""
echo "Total freed: ~${freed} MB"
