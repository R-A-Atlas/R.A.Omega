# Critical Path: Options Flow Query

TRIGGER: `classify_intent_route()` returns options flow, unusual activity, derivatives, 0DTE, calls, puts, IV, or gamma-related intent.

STEP 1: Read `data_cache/summaries/options_flow_summary.json`.
        Use `options_flow_latest.json` only for Deep Research or ticker-specific chain expansion.
STEP 2: Pull `put_call_ratio_signal`, `top_conviction_ticker`, `unusual_calls`, and `unusual_puts`.
STEP 3: If the user names a ticker, match it against the summary's unusual calls and puts.
STEP 4: Add equity and insider summaries only when the ticker requires confirmation.
STEP 5: Generate response using this structure:
        - Flow read
        - Bullish flow
        - Bearish flow
        - Confirmation needed
        - Risk and invalidation
STEP 6: Add standard disclaimer and source freshness.

DO NOT: Treat volume/OI as directional certainty.
DO NOT: recommend an options contract without explaining liquidity and loss risk.
DO NOT: infer institutional intent unless the data supports it.
