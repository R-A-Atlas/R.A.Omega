# report_qa_agent — Plan

## Current Plan (v1)
1. Run canonical test queries through quality_firewall.validate_response() locally
2. For company_report queries: use verify_company_report verifier
3. For trade_plan queries: use verify_trade_plan verifier
4. For chat queries: check no trade sections present
5. Output pass/fail report to stdout or atlas_vault/03-Outputs/

## Canonical Query Set
| Query | Expected output_mode | Expected renderer | Key checks |
|---|---|---|---|
| "Give me everything on BlackRock" | company_report | paper_report | no trade cards, executive summary present |
| "Give me a TSLA trade setup" | trade_plan | trade_cards | stop loss present, entry present |
| "How do I make apple pie?" | chat | chat_bubble | no trade sections |
| "Analyze NVDA" | company_report | paper_report | no trade cards |
| "Goldman Sachs research" | company_report | paper_report | no trade cards |

## Future Enhancements
- Live end-to-end tests against running server (POST /query)
- Compare output quality scores over time
