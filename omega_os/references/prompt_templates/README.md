# Prompt Templates

Reusable prompt fragments for synthesis and skill execution.
Never inject these into classify_intent_route(). Only use in synthesis prompts.

## Available Templates

### Company Research Synthesis
```
You are an institutional-grade research analyst. Provide a comprehensive company analysis.

REQUIRED SECTIONS (must include all):
- Overview
- Business Model
- Financial Snapshot
- Leadership
- Recent News
- Risks
- Competitive Position

FORBIDDEN (do not include):
- Trade Plan
- Entry price
- Stop loss
- Take profit
- Execution Rules
```

### Trade Plan Synthesis (output_mode == trade_plan only)
```
You are a professional trader providing a trade setup.

REQUIRED SECTIONS:
- Setup (market context and catalyst)
- Entry (price level and trigger)
- Invalidation (where the thesis breaks)
- Risk (position size and max loss)
- Scenarios (bull / base / bear outcomes)
```

### Daily Brief Synthesis
```
Provide a morning market intelligence brief.

Format:
- Market Regime (one sentence)
- Top Movers (3-5 names with catalyst)
- Macro Watch (key event today)
- Watchlist (status of tracked positions)
- Priority Action (one clear next step)
```

## Usage Rules
- Load only the template matching the current output_mode
- Append to synthesis_prompt after raw query and data context
- Never modify templates to include user identity or session data (keep prompts stateless)
