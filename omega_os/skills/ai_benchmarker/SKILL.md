# Skill: ai_benchmarker

## Purpose
Scores R.A. Omega against ChatGPT, Claude, Gemini, and Perplexity on 9 weighted
dimensions. All competitor scores are based on documented public knowledge — no
external API calls or subscription costs. Our scores are auto-detected from the
actual codebase.

## Trigger
- Weekly (via audit_runner cadence job)
- Before any major feature launch — confirms competitive position
- When a competitor releases a major update

## Steps
```
python omega_os/skills/ai_benchmarker/tools/benchmark.py
python omega_os/skills/ai_benchmarker/tools/benchmark.py --json
```

## Dimensions scored (weight / description)

| Dimension | Weight | What it measures |
|---|---|---|
| Finance Domain Depth | 15% | Specialized finance intents vs general-purpose |
| Output Structure Quality | 15% | Typed envelope: TLDR, scenarios, execution rules, failure modes |
| Memory & Personalization | 10% | atlas_memory.db, Loop 5 portfolio, session context |
| Cost Efficiency | 10% | ~$0.017/query target vs $0.10–$0.30 for GPT-4 API |
| UX Completeness | 12% | Command center, sessions, history, export, mobile |
| Domain Breadth | 10% | Stocks + options + crypto + mortgage + debt + macro + business |
| Data Freshness | 10% | Live web scraping vs training cutoff |
| API Quality | 10% | Routes, structured JSON, streaming |
| Production Readiness | 8% | Deployment, billing, auth guard, tests |

## How competitor scores are set
Competitor scores are static values in `COMPETITORS` dict, based on:
- Public documentation and feature lists
- Pricing pages and API docs
- Community benchmarks and published comparisons
- Updated periodically as competitors ship major changes

## Our moats (structural advantages)
1. **Finance domain depth** — 60+ intents, cross-domain, trade-ready output schema
2. **Output structure** — typed envelopes vs prose; institutional-grade schemas
3. **Cost efficiency** — multi-source free data + single Gemini call = $0.017/query
4. **Memory switching cost** — atlas_memory.db grows smarter every query

## Guardrails
- Do not claim real-time competitor feature data — update COMPETITORS dict manually
- Do not add live API calls to competitor products without explicit user approval
- Do not inflate R.A. Omega scores — they must be auto-detected from actual codebase
