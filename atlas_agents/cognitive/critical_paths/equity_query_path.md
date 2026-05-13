# Critical Path: Equity Query

TRIGGER: `classify_intent_route()` returns an equity, stock research, or market snapshot route.

STEP 1: Read `data_cache/summaries/equities_summary.json`.
        Use `equities_latest.json` only for Deep Research or ticker-level evidence expansion.
STEP 2: Extract `breadth_signal`, `top_gainer`, `top_loser`, and `most_active`.
STEP 3: If the user names a ticker, check whether it appears in the summary fields.
        If not present, say the summary layer does not currently contain that ticker.
STEP 4: Add companion context only when relevant:
        - options flow for unusual derivatives activity
        - insider trades for Form 4 context
        - sector rotation for broader market confirmation
STEP 5: Generate response using this structure:
        - Bottom line
        - What the tape shows
        - Confirmation or conflict from companion data
        - Risk controls and invalidation points
STEP 6: Add standard disclaimer and source freshness.

DO NOT: Treat fallback or mock-backed rows as live market truth without labeling them.
DO NOT: Invent a price target.
DO NOT: Convert research into personalized investment advice.
