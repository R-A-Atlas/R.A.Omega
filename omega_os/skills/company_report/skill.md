# skill: company_report

## name
company_report

## description
Generate an institutional-grade company research report with bull/bear thesis, catalyst timeline, and risk analysis.

## when_to_use
- User asks about a specific company, stock, or ticker
- User wants analysis, research, or a report on a public company
- Intent route is COMPANY_RESEARCH or MARKET_DEEP_DIVE
- output_mode resolved to "company_report"

## when_not_to_use
- User asking a general finance question not tied to a specific company
- User explicitly asked for a trade plan only (use trade_plan skill)
- User wants a document export (use document_generator skill)
- output_mode is chat, trade_plan, or document

## inputs_required
- Company name or ticker symbol
- Optional: specific angle (earnings, options, macro impact)
- Optional: research depth (normal or deep)

## steps
1. Classify intent — confirm output_mode is company_report, not trade_plan or chat
2. Fetch data: SEC EDGAR, Yahoo Finance, news sources, analyst consensus
3. Run synthesis with company_report prompt template
4. Quality firewall validates: paper_report renderer, no trade_cards, required sections present
5. Return report with source citations

## outputs
- renderer_type: paper_report
- Required sections: executive_summary, bull_thesis, bear_thesis, key_risks, catalysts_timeline
- Forbidden: trade cards, action/stop/target rows
- Format: structured prose with clear section headers
- Tone: institutional, analytical, evidence-based

## safety_rules
- NEVER render trade_cards for company_report output
- NEVER produce action/stop/target/risk-reward rows as the primary structure
- Always cite data sources
- Do not fabricate earnings numbers or analyst ratings
- Label any missing data as "data unavailable"

## quality_checks
- paper_report renderer assigned (not trade_cards)
- executive_summary present
- bull_thesis and bear_thesis present
- No action/stop/target rows in output
- All data points cite a source

## examples
Input: "Give me everything on BlackRock"
Output: Paper-style report with Executive Summary, Bull Thesis, Bear Thesis, Catalyst Timeline, Key Risks, Price Levels, Analyst Consensus

Input: "Deep dive on NVDA earnings"
Output: Same structure with deep_research workflow (more data sources, longer synthesis)

## repair_strategy
If output contains trade card rows (Action/Stop/Target), strip them and rerun synthesis with company_report prompt.
If required sections are missing, call quality_firewall repair prompt targeting missing sections.

## related_files
- omega_os/skills/trade_plan/skill.md
- omega_os/skills/source_verification/skill.md
- omega_os/skills/report_export/skill.md
