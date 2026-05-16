# visual_qa_agent — Plan

## Current Plan (v1)
1. Scan `atlas_vault/01-Raw/Screenshots/` for new screenshots
2. For each screenshot, run visual_qa skill analysis
3. Check for: structured response cards, trade card gating, export bar, sessions sidebar
4. Output markdown QA report to `atlas_vault/03-Outputs/visual_qa_<date>.md`

## UI Elements to Always Check
- StructuredResponse cards render for company_report and trade_plan
- Chat bubble renders for general_chat (no trade cards)
- Sessions sidebar: new chat, list, rename, delete
- ExportBar: Copy JSON, Listen (TTS) buttons
- Live market regime chip in header

## Future Enhancements
- Automated screenshot capture via Playwright (when local hosting is set up)
- Diff screenshots against baseline to catch regressions automatically
