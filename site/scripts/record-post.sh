#!/bin/bash
# Record audio for a blog post, convert to MP3, update frontmatter, and generate scroll sync.
#
# Usage: ./scripts/record-post.sh [post-filename]
#   e.g.: ./scripts/record-post.sh 2026-03-15-the-great-unbundling
#
# If no filename is given, lists available posts without audio.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SITE_DIR="$(dirname "$SCRIPT_DIR")"
BLOG_DIR="$SITE_DIR/src/content/blog"
AUDIO_DIR="$SITE_DIR/public/audio"
SYNC_DIR="$SITE_DIR/public/audio/sync"

mkdir -p "$AUDIO_DIR" "$SYNC_DIR"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m'

# Check dependencies
for cmd in ffmpeg; do
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
  echo -e "Usage: ${GREEN}./scripts/record-post.sh <post-slug>${NC}"
  exit 0
fi

SLUG="$1"
POST_FILE="$BLOG_DIR/$SLUG.md"
AUDIO_FILE="$AUDIO_DIR/$SLUG.mp3"
RAW_FILE="/tmp/$SLUG-raw.m4a"

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
echo -e "${CYAN}Recording audio for:${NC}"
echo -e "  ${GREEN}$TITLE${NC}"
echo -e "  $POST_FILE"
echo ""
echo -e "${YELLOW}Tips:${NC}"
echo "  - Read at a natural, conversational pace"
echo "  - A few seconds of silence at the start and end is fine"
echo "  - Don't worry about small mistakes — they add authenticity"
echo ""
echo -e "Press ${GREEN}Enter${NC} to start recording. Press ${RED}Ctrl+C${NC} to stop when done."
read -r

# Record using macOS built-in (afrecord for lossless, then convert)
# Using ffmpeg to record from the default mic
echo -e "${GREEN}Recording... Press Ctrl+C when done.${NC}"
echo ""

# Trap Ctrl+C to stop recording gracefully
trap 'echo ""; echo -e "${YELLOW}Stopping recording...${NC}"' INT
ffmpeg -f avfoundation -i ":default" -c:a aac -q:a 2 "$RAW_FILE" -y 2>/dev/null || true
trap - INT

if [ ! -f "$RAW_FILE" ]; then
  echo -e "${RED}Recording failed — no audio captured.${NC}"
  exit 1
fi

# Convert to MP3
echo -e "${CYAN}Converting to MP3...${NC}"
ffmpeg -i "$RAW_FILE" -codec:a libmp3lame -qscale:a 2 -ar 44100 "$AUDIO_FILE" -y 2>/dev/null

# Get duration
DURATION=$(ffprobe -v quiet -show_entries format=duration -of csv=p=0 "$AUDIO_FILE" | cut -d. -f1)
MINS=$((DURATION / 60))
SECS=$((DURATION % 60))

echo -e "${GREEN}Audio saved:${NC} $AUDIO_FILE (${MINS}m ${SECS}s)"

# Update frontmatter
if grep -q "^audio:" "$POST_FILE"; then
  # Replace existing audio line
  sed -i '' "s|^audio:.*|audio: \"/audio/$SLUG.mp3\"|" "$POST_FILE"
else
  # Add audio field before the closing ---
  sed -i '' "/^---$/,/^---$/ { /^---$/ { N; /^---\n/ { s/^---$/audio: \"\/audio\/$SLUG.mp3\"\n---/; }; }; }" "$POST_FILE"
  # Simpler approach: add before the second ---
  if ! grep -q "^audio:" "$POST_FILE"; then
    awk '/^---$/ && ++n==2 {print "audio: \"/audio/'"$SLUG"'.mp3\""}1' "$POST_FILE" > "$POST_FILE.tmp" && mv "$POST_FILE.tmp" "$POST_FILE"
  fi
fi

echo -e "${GREEN}Frontmatter updated${NC} with audio path"

# Clean up raw file
rm -f "$RAW_FILE"

# Whisper alignment (if available)
if command -v whisper &>/dev/null || python3 -c "import whisper" 2>/dev/null; then
  echo ""
  echo -e "${CYAN}Running Whisper alignment for scroll sync...${NC}"
  python3 "$SCRIPT_DIR/align-audio.py" "$POST_FILE" "$AUDIO_FILE" "$SYNC_DIR/$SLUG.json"
  echo -e "${GREEN}Sync file generated:${NC} $SYNC_DIR/$SLUG.json"
else
  echo ""
  echo -e "${YELLOW}Whisper not installed — skipping scroll sync.${NC}"
  echo -e "To enable: ${CYAN}pip3 install openai-whisper${NC}"
fi

echo ""
echo -e "${GREEN}Done!${NC} Next steps:"
echo "  1. Preview: cd site && npm run dev → check the audio player"
echo "  2. Commit: git add site/public/audio/$SLUG.mp3 site/src/content/blog/$SLUG.md"
echo "  3. Push to deploy"
