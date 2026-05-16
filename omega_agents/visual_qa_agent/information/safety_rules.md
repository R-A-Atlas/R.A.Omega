# visual_qa_agent — Safety Rules

1. Read screenshots and UI notes only. Do not modify any HTML or JS files.
2. Do not call external APIs or image APIs.
3. Do not store PII or user data found in screenshots.
4. Do not write to the main application files.
5. Output QA reports go to atlas_vault/03-Outputs/ only.
6. If a screenshot cannot be parsed, note it and skip — do not fail silently.
7. Do not send QA reports externally (no email, no Slack yet).
