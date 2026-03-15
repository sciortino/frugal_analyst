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

## Step 4: Audio (Optional)

Ask the user if they want to record audio for this post. If yes:
1. Remind them of the process:
   - Record themselves reading the post (Voice Memos or GarageBand)
   - Export as MP3
   - Save to `site/public/audio/YYYY-MM-DD-slug.mp3`
2. Once they've provided the file, add `audio: "/audio/YYYY-MM-DD-slug.mp3"` to the post's frontmatter
3. Commit and push

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
- Always tighten prose by ~20% — Claude overwriters
- Always switch to the `sciortino` GitHub account before PR operations
- Trigger pipeline runs via GitHub Actions, not locally (audit trail)
