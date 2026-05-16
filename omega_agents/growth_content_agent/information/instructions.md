# growth_content_agent — Instructions

## What This Worker Does
Turns R.A. Omega engineering progress into content ideas, social posts, launch updates,
and marketing scripts. Reads DONE files and git log to identify shippable milestones,
then drafts content for Twitter/X, Reddit, and Product Hunt launches.

## When to Run
- Weekly, after a meaningful shipping week
- Before any public launch or beta announcement
- When preparing r/algotrading, r/options, or FinTwit posts

## Skills Used
- (Planned) `content_generator` skill — when added to omega_os/skills/
- For now: reads DONE files and formats them manually into content templates

## Content Formats
- Twitter/X thread (5-10 tweets)
- Reddit post for r/algotrading or r/options (narrative format)
- Product Hunt launch copy (tagline, description, first comment)
- Feature demo script (for video or screen recording)

## Output
- Markdown file with drafted content, organized by format
- Saved to `atlas_vault/03-Outputs/content_<date>.md`
- NOT posted automatically — always requires human review and approval

## Error Recording
On any failure, append to `past_errors.md` with date, content type, and issue.

## How to Improve
After each run, append to `memory.md`: what content was drafted, what performed well.
Update `plan.md` with upcoming launch milestones.
