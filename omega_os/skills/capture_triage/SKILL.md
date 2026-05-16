# skill: capture_triage

## name
capture_triage

## description
Capture and triage user-provided content (screenshots, pasted text, URLs) and extract actionable intelligence.

## when_to_use
- User pastes a screenshot, image, or large block of text
- User shares a URL and asks for analysis
- User wants content extracted and summarized

## when_not_to_use
- User is asking a direct question (use general_chat or company_report)
- No content to triage

## inputs_required
- Content: image, text block, or URL
- Optional: specific extraction goal

## steps
1. Identify content type: image, pasted text, or URL
2. Extract key data points relevant to finance/business context
3. Label extracted data as "from user-provided content"
4. Summarize in chat_bubble format
5. Optionally route to company_report or trade_plan for deeper analysis

## outputs
- renderer_type: chat_bubble
- Format: structured extraction summary
- Tone: concise, factual
- Labels: all extracted data marked as "from user-provided content"

## safety_rules
- Do not store captured content in permanent logs without user consent
- Label extracted data as "from user-provided content"
- Do not make investment decisions based solely on unverified user-provided data

## quality_checks
- Extracted data is labeled as user-provided
- No permanent storage of content without consent
- Summary is actionable and concise

## examples
Input: Screenshot of earnings release
Output: Extracted EPS, revenue, guidance, notable surprises

## repair_strategy
If content cannot be extracted (image unreadable, URL blocked), tell user and ask for text input.

## related_files
- omega_os/skills/company_report/skill.md
- omega_os/skills/source_verification/skill.md
