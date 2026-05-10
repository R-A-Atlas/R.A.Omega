---
name: Content Repurposer Bot
description: Extracts YouTube transcripts via youtube-transcript-api and reformats into 10-tweet thread + 5-section blog outline saved as markdown in atlas_vault/03-Outputs/Content/
type: reference
agent: G6
division: Business Growth & Ops
---

# Skill: Content Repurposer Bot (G6)

## [D] Direction
Take YouTube URL as input. Extract video_id. Fetch transcript via YouTubeTranscriptApi.
Build 10-tweet thread (each <=280 chars) and 5-section blog outline.
Write markdown to atlas_vault/03-Outputs/Content/{title}_{date}.md.

## [B] Blueprints
Library: youtube-transcript-api (pip install youtube-transcript-api)
Output:  atlas_vault/03-Outputs/Content/

## [S] Solutions
Run repurposer:
  python -m atlas_agents.growth.content.content_repurposer "https://youtube.com/watch?v=..."

Run tests:
  python -m pytest tests/test_content.py -v

## Evals
| # | Assertion | Pass Condition |
|---|-----------|----------------|
| 1 | py_compile exits 0 | exit code 0 |
| 2 | len(twitter_thread) >= 8 | at least 8 tweets |
| 3 | all tweets <= 280 chars | character limit respected |
| 4 | len(blog_outline) == 5 | exactly 5 sections |
| 5 | output file exists after run | markdown file written |
