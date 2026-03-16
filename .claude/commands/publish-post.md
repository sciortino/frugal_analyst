# Publish Post

You are helping the owner of frugalanalyst.com review and publish a pipeline-generated blog post. Follow this checklist exactly — do not skip steps.

## Step 1: Find the PR

Check for open PRs on the repo:
```
gh pr list --repo sciortino/frugal_analyst --state open
```

If no open PRs, tell the user and stop.

## Step 2: Review the Post

Read the full post content from the PR diff. Check for:

- **Hallucinated data**: Numbers that seem implausible (margins >100%, revenue that doesn't match the company's scale, wrong year references like "2024" when we're in 2026)
- **Missing data**: Sections that talk about missing data instead of analyzing real numbers — this means the pipeline didn't get enough data
- **Wordiness**: Claude-generated posts tend to be ~20% too long. Identify paragraphs that repeat the same point, filler transitions, and sections that can be merged
- **Source citations**: Every post should cite SEC EDGAR, FRED, and/or BLS in a data sources note at the end
- **Frontmatter**: Verify `date` field matches today, tags are reasonable, description is concise

Report your findings to the user before making any changes.

## Step 3: Edit if Needed

If the post needs tightening or corrections:
1. Check out the PR branch: `gh pr checkout <number>`
2. Edit the post file in `site/src/content/blog/`
3. Commit and push the changes to the PR branch

## Step 4: Audio Recording

Ask the user if they want to record audio for this post. If yes:

### Recording
The user records themselves reading the post aloud. Options:
- **QuickTime Player** > File > New Audio Recording (most reliable on macOS)
- **Voice Memos** on Mac or iPhone
- The recording script at `site/scripts/record-post.sh` (if terminal mic permissions are configured)

The raw recording should be saved somewhere accessible (e.g. `audio_recordings/` in the project root).

### Processing
Process the raw recording with ffmpeg to normalize levels, trim dead air, and optionally speed up:

```bash
ffmpeg -i /path/to/raw-recording.m4a \
  -af "silenceremove=start_periods=1:start_silence=0.3:start_threshold=-35dB:stop_periods=-1:stop_silence=0.8:stop_threshold=-35dB,loudnorm=I=-19:TP=-3:LRA=11,atempo=1.2" \
  -codec:a libmp3lame -qscale:a 2 -ar 44100 \
  site/public/audio/YYYY-MM-DD-slug.mp3 -y
```

This does three things:
- **Trims silence** throughout (>0.8s pauses trimmed, leading silence removed)
- **Normalizes levels** to -19 LUFS (comfortable podcast level)
- **Speeds up to 1.2x** (natural sounding, saves ~17% runtime)

Adjust `atempo` if the user wants a different speed (1.0 = original, 1.1 = slight speedup, 1.2 = recommended).

### Scroll Sync Alignment
Generate paragraph timestamps using local Whisper (pywhispercpp — runs on Apple Silicon with Metal GPU, no API keys needed):

```bash
cd pipeline && uv run python ../site/scripts/align-audio.py \
  ../site/src/content/blog/YYYY-MM-DD-slug.md \
  ../site/public/audio/YYYY-MM-DD-slug.mp3 \
  ../site/public/audio/sync/YYYY-MM-DD-slug.json
```

This transcribes the audio locally using whisper.cpp, then fuzzy-matches the transcript to post paragraphs to generate a sync JSON file. The AudioPlayer component on the site uses this to:
- Highlight the current paragraph as audio plays
- Auto-scroll the page to follow the narration
- Dim past paragraphs
- Provide a SYNC toggle button for the reader

### Update Frontmatter
Add the audio path to the post:
```yaml
audio: "/audio/YYYY-MM-DD-slug.mp3"
```

### Commit
Stage and commit both the MP3 and sync JSON:
```
git add site/public/audio/YYYY-MM-DD-slug.mp3 site/public/audio/sync/YYYY-MM-DD-slug.json site/src/content/blog/YYYY-MM-DD-slug.md
```

## Step 5: Build Verification

Verify the site builds cleanly:
```
cd site && npm run build
```

If the build fails, fix the issue before proceeding.

## Step 6: Merge

Ask the user for confirmation, then merge the PR:
```
gh pr merge <number> --merge --repo sciortino/frugal_analyst
```

The deploy workflow triggers automatically on merge to main.

## Step 7: Verify Deployment

After merge, check that the deploy workflow succeeded:
```
gh run list --workflow=deploy.yml --repo sciortino/frugal_analyst --limit=1
```

Report the result to the user.

---

## Important Rules

- NEVER merge without user confirmation
- NEVER publish a post with hallucinated or implausible data — close the PR instead
- Always tighten prose by ~20% — Claude overwrites
- Always switch to the `sciortino` GitHub account before PR operations
- Trigger pipeline runs via GitHub Actions, not locally (audit trail)
- Always offer audio recording — it adds a personal touch and feeds the podcast
