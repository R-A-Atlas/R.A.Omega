# report_qa_agent — Instructions

## What This Worker Does
Tests the R.A. Omega query pipeline with known sample queries to verify output quality.
Checks that company_report, trade_plan, and general_chat outputs are correctly formatted,
contain required sections, and have no trade bleed.

## When to Run
- After any change to output_modes.py, output_contracts.py, quality_firewall.py, or prompt_builder.py
- After any change to the synthesis prompt
- Weekly regression check

## Skills Used
- `company_report` — verify BlackRock / NVDA / Goldman reports
- `trade_plan` — verify TSLA / NVDA trade setup outputs
- `general_chat` — verify "apple pie" and casual queries
- `source_verification` — verify cited data sources in reports
- `improve_system` — analyze failures and produce repair recommendations

## Sample Queries (canonical test set)
1. "Give me everything on BlackRock" → expected: company_report, paper_report renderer, no trade cards
2. "Give me a TSLA trade setup" → expected: trade_plan, trade_cards renderer, stop loss present
3. "How do I make apple pie?" → expected: chat, chat_bubble renderer, no trade sections
4. "Analyze NVDA — current setup" → expected: company_report, paper_report
5. "Goldman Sachs research" → expected: company_report

## Output
- Markdown QA report with PASS/FAIL per query
- Failure details: what was expected vs. what was produced
- Overall PASS/FAIL status

## Error Recording
On any failure, append to `past_errors.md` with query, expected output, actual output, and date.

## How to Improve
After each run, append summary to `memory.md`.
If a query consistently fails, add it to `plan.md` as a tracked regression.
