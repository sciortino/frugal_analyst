#!/bin/bash
# Generate TTS audio for a blog post using Kokoro TTS.
#
# Usage: ./scripts/tts-post.sh [post-slug]
#   e.g.: ./scripts/tts-post.sh 2026-03-18-abbvie-sga-analysis
#
# If no slug is given, lists available posts without audio.
#
# Requirements:
#   - espeak-ng: brew install espeak-ng
#   - ffmpeg: brew install ffmpeg
#   - kokoro + soundfile in the pipeline env: cd pipeline && uv add "kokoro>=0.9.4" soundfile "torch<2.10"

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SITE_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_DIR="$(dirname "$SITE_DIR")"
BLOG_DIR="$SITE_DIR/src/content/blog"
AUDIO_DIR="$SITE_DIR/public/audio"
SYNC_DIR="$SITE_DIR/public/audio/sync"
PIPELINE_DIR="$PROJECT_DIR/pipeline"

mkdir -p "$AUDIO_DIR" "$SYNC_DIR"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m'

# Check dependencies
for cmd in ffmpeg espeak-ng; do
  if ! command -v "$cmd" &>/dev/null; then
    echo -e "${RED}Error: $cmd is not installed. Run: brew install $cmd${NC}"
    exit 1
  fi
done

# If no argument, list posts without audio
if [ $# -eq 0 ]; then
  echo -e "${CYAN}Posts without audio:${NC}"
  echo ""
  for f in "$BLOG_DIR"/*.md; do
    [ -f "$f" ] || continue
    if ! grep -q "^audio:" "$f"; then
      basename "$f" .md
    fi
  done
  echo ""
  echo -e "Usage: ${GREEN}./scripts/tts-post.sh <post-slug>${NC}"
  exit 0
fi

SLUG="$1"
POST_FILE="$BLOG_DIR/$SLUG.md"
AUDIO_FILE="$AUDIO_DIR/$SLUG.mp3"
WAV_FILE="/tmp/$SLUG-tts.wav"

if [ ! -f "$POST_FILE" ]; then
  echo -e "${RED}Error: Post not found: $POST_FILE${NC}"
  exit 1
fi

if [ -f "$AUDIO_FILE" ]; then
  echo -e "${YELLOW}Audio already exists: $AUDIO_FILE${NC}"
  read -p "Overwrite? (y/N) " -n 1 -r
  echo
  [[ $REPLY =~ ^[Yy]$ ]] || exit 0
fi

# Extract title for display
TITLE=$(grep "^title:" "$POST_FILE" | sed 's/^title: *"*//' | sed 's/"*$//')
echo ""
echo -e "${CYAN}Generating TTS audio for:${NC}"
echo -e "  ${GREEN}$TITLE${NC}"
echo -e "  $POST_FILE"
echo ""

# Run Kokoro TTS via the dedicated TTS venv (arm64)
TTS_PYTHON="$PROJECT_DIR/tts/.venv/bin/python"
if [ ! -f "$TTS_PYTHON" ]; then
  echo -e "${RED}Error: TTS venv not found at $TTS_PYTHON${NC}"
  echo -e "Set up with: ${CYAN}cd tts && arch -arm64 /usr/bin/python3 -m venv .venv && arch -arm64 .venv/bin/pip install kokoro soundfile numpy${NC}"
  exit 1
fi

echo -e "${CYAN}Running Kokoro TTS...${NC}"
PYTORCH_ENABLE_MPS_FALLBACK=1 arch -arm64 "$TTS_PYTHON" "$SCRIPT_DIR/tts-generate.py" "$POST_FILE" "$WAV_FILE"

if [ ! -f "$WAV_FILE" ]; then
  echo -e "${RED}TTS generation failed — no audio produced.${NC}"
  exit 1
fi

# Convert WAV to MP3
echo -e "${CYAN}Converting to MP3...${NC}"
ffmpeg -i "$WAV_FILE" -codec:a libmp3lame -qscale:a 2 -ar 44100 "$AUDIO_FILE" -y 2>/dev/null

# Get duration
DURATION=$(ffprobe -v quiet -show_entries format=duration -of csv=p=0 "$AUDIO_FILE" | cut -d. -f1)
MINS=$((DURATION / 60))
SECS=$((DURATION % 60))

echo -e "${GREEN}Audio saved:${NC} $AUDIO_FILE (${MINS}m ${SECS}s)"

# Clean up WAV
rm -f "$WAV_FILE"

# Update frontmatter
if grep -q "^audio:" "$POST_FILE"; then
  # Replace existing audio line
  sed -i '' "s|^audio:.*|audio: \"/audio/$SLUG.mp3\"|" "$POST_FILE"
else
  # Add audio field before the closing ---
  if ! grep -q "^audio:" "$POST_FILE"; then
    awk '/^---$/ && ++n==2 {print "audio: \"/audio/'"$SLUG"'.mp3\""}1' "$POST_FILE" > "$POST_FILE.tmp" && mv "$POST_FILE.tmp" "$POST_FILE"
  fi
fi

echo -e "${GREEN}Frontmatter updated${NC} with audio path"

# Whisper alignment
echo ""
echo -e "${CYAN}Running alignment for scroll sync...${NC}"
python3 "$SCRIPT_DIR/align-audio.py" "$POST_FILE" "$AUDIO_FILE" "$SYNC_DIR/$SLUG.json"
echo -e "${GREEN}Sync file generated:${NC} $SYNC_DIR/$SLUG.json"

echo ""
echo -e "${GREEN}Done!${NC} Next steps:"
echo "  1. Preview: cd site && npm run dev — check the audio player"
echo "  2. Commit: git add site/public/audio/$SLUG.mp3 site/src/content/blog/$SLUG.md"
echo "  3. Push to deploy"
