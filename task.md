Fix the chat response rendering in ra_omega_app.html.

The API returns structured JSON but the UI shows plain text.
The JSON has these fields: tldr, trader_memo, execution_rules, 
failure_modes, scenarios, final_report (contains executive_brief, 
bull_thesis, bear_thesis, trade_plan, price_levels, 
catalysts_timeline, key_risks, hidden_angles).

TASK 1 — Replace plain text with structured cards:
- TLDR card: large text, green border for buy, red for sell, amber for hold
- Executive Summary card
- Trade Plan card: entry/target/stop as a mini table
- Scenarios card: bull/base/bear with probability bars
- Execution Rules card: each rule as a trigger row  
- Failure Modes card: severity badges
- Trader Memo card: styled differently from other cards

TASK 2 — Add export bar below each response:
- "HTML Report" button: opens styled standalone HTML in new tab
- "Copy JSON" button: copies raw JSON to clipboard

Do NOT change: query logic, API calls, right panel telemetry.
Only change how responses render in the chat area.
