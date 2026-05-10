# G6 — Content Repurposer Bot | Division: Business Growth & Ops

## IDENTITY
You extract YouTube video transcripts and reformat them into Twitter/X thread
drafts and blog post outlines. Input: YouTube URL. Output: markdown file saved
to atlas_vault/03-Outputs/Content/. No LLM calls. Transcript extract + reformat.

## DEFINITION
  Input: YouTube video URL (e.g., https://www.youtube.com/watch?v=dQw4w9WgXcQ)
  Output: Markdown file with Twitter thread + blog outline
  twitter_thread: 8–12 numbered tweet drafts (each <= 280 chars)
  blog_outline: 5-section outline with H2 headers + 3 bullet points each

## DATA SOURCES
  youtube-transcript-api (pip install youtube-transcript-api):
    from youtube_transcript_api import YouTubeTranscriptApi
    transcript = YouTubeTranscriptApi.get_transcript(video_id)
  Note: works for videos with auto-generated or manual captions

## OUTPUT FILE
  atlas_vault/03-Outputs/Content/{video_title}_{date}.md

## OUTPUT SCHEMA (markdown file)
```markdown
---
title: {video_title}
date: {YYYY-MM-DD}
source: {youtube_url}
video_id: {video_id}
duration_seconds: {total_duration}
generated_at: {ISO UTC timestamp}
---

# Twitter Thread: {video_title}

1/ {Opening hook — most surprising stat or claim from the video}
2/ {Key point 1}
...
10/ {CTA — follow for more}

# Blog Outline: {video_title}

## Introduction
- {bullet 1}
- {bullet 2}
- {bullet 3}

## {Section 2 title}
- ...
```

## SCRAPER STRUCTURE
```python
from youtube_transcript_api import YouTubeTranscriptApi
from pathlib import Path
import re

REPO_ROOT = Path(__file__).resolve().parents[3]
CONTENT_OUTPUT_DIR = REPO_ROOT / "atlas_vault" / "03-Outputs" / "Content"

def extract_video_id(url: str) -> str: ...        # parse video_id from URL
def fetch_transcript(video_id: str) -> str: ...   # join transcript segments
def build_thread_draft(transcript: str, title: str) -> list[str]: ...  # 10 tweets
def build_blog_outline(transcript: str, title: str) -> list[dict]: ... # 5 sections
def repurpose(youtube_url: str) -> dict: ...
def write_output(payload: dict) -> Path: ...
def main(argv=None) -> int: ...
```

## RULES
- No LLM calls — transcript extraction + text chunking only
- Each tweet must be <= 280 characters
- blog_outline must have exactly 5 sections, each with 3 bullet points
- Output file named: {sanitized_title}_{YYYY-MM-DD}.md
- generated_at must be ISO UTC string
- If transcript unavailable: raise ValueError with reason
- Content output directory: atlas_vault/03-Outputs/Content/

## VALIDATION CHECKLIST
  [ ] python -m py_compile content_repurposer.py exits 0
  [ ] repurpose(url) returns dict with title, date, source, twitter_thread, blog_outline
  [ ] len(twitter_thread) >= 8
  [ ] all(len(t) <= 280 for t in twitter_thread)
  [ ] len(blog_outline) == 5
  [ ] python -m pytest tests/test_content.py -v passes
