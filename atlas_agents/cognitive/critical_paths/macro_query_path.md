# Critical Path: Macro Query

TRIGGER: `classify_intent_route()` returns macro, Fed, CPI, liquidity, jobs, forex, commodities, energy, tariff, or supply-chain context.

STEP 1: Read the most specific matching summary file in `data_cache/summaries/`.
STEP 2: Pull the top-level `signal`, `record_count`, `source_generated_at`, and the strongest available datapoint.
STEP 3: Add companion summaries when the query crosses macro domains:
        - CPI and Fed watch for inflation/rate questions
        - global liquidity and sector rotation for risk appetite
        - forex, commodities, and energy for cross-asset stress
STEP 4: Classify the macro answer as:
        - risk-on
        - risk-off
        - neutral/mixed
        - incomplete evidence
STEP 5: Generate response using this structure:
        - Current macro read
        - Evidence behind it
        - What it affects
        - What would change the read
STEP 6: Add standard disclaimer and data freshness.

DO NOT: Overstate stale or fallback data.
DO NOT: use macro context as a standalone trade recommendation.
DO NOT: ignore conflicting evidence between inflation, liquidity, and sector rotation.
