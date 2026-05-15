# Product Specs

## Core Architecture

### Entry Points
| Route | Handler | Description |
|-------|---------|-------------|
| POST /query | FourLoopEngine | Deep equity/options analysis (10 loops) |
| POST /omega | OmegaAgent | Fast cross-domain (debt, cars, mortgages, macro) |
| POST /voice/query | Whisper → /query | Same envelope as /query |
| POST /tts | OpenAI/ElevenLabs | Text-to-speech |
| POST /export/pdf\|pptx\|xlsx | Export builders | atlas_vault/03-Outputs/ |

### Intent Routing
- `classify_intent_route(raw_query)` — receives ONLY raw query, never memory/controls
- Routes: MARKET_DEEP_DIVE → FourLoopEngine | GENERAL_FINANCE → OmegaAgent | all others → Omega

### Output Modes
| Mode | When Used |
|------|-----------|
| trade_plan | Explicit trade request (entry, stop loss, etc.) |
| company_report | Company research queries |
| document | PDF/report generation requests |
| html_artifact | HTML dashboard/widget requests |
| finance_answer | General finance questions |
| market_snapshot | Market data queries |
| chat | Casual, non-finance queries |

### Quality Control
1. Output mode resolved from raw_query + intent
2. OUTPUT_CONTRACTS enforces required/forbidden sections per mode
3. quality_firewall validates response against contract
4. One repair loop if firewall fails
5. response_judge logs PASS/FAIL verdict

### Data Sources (Free, Parallel)
- yfinance (price, fundamentals, options chain)
- Web scraper (news, analyst notes)
- data_cache/ (64 tracked summaries)
- atlas_memory.db (persistent learned facts)
- atlas_rag/ (Chroma vector DB: SOUN + O + NVDA chunks)

### Cost Target
~$0.017/query using Gemini Flash for simple, Gemini Pro for deep research/trade plans.

## Frontend
- `/` — Zenith 3D landing (index_1778228972988.html)
- `/auth` — Sign In + Create Account (auth.html)
- `/app` — Main chat UI (ra_omega_app.html)
- `/v2` — Legacy dashboard (atlas_dashboard_v4.html)

## API Response Envelope (POST /query)
```json
{
  "query": "...",
  "parsed_query": {"type": "...", "tickers": [], "intent_route": "...", "confidence": 0.9},
  "final_report": {"overall_rating": "...", "trade_plan": {...}, "executive_summary": "..."},
  "tldr": "...",
  "trader_memo": "...",
  "execution_rules": [...],
  "failure_modes": [...],
  "scenarios": [...],
  "timing": {"total": "..."}
}
```
