# Critical Path: Crypto Market Query

TRIGGER: `classify_intent_route()` returns `CRYPTO_MARKET_SCAN`.

STEP 1: Read `data_cache/summaries/crypto_top50_summary.json`.
        Use the raw `crypto_top50_latest.json` only when Deep Research is explicitly active.
STEP 2: Check `market_regime`.
        If `RISK_OFF`, lead with the caution signal.
        If `RISK_ON`, lead with the opportunity signal.
STEP 3: Pull `top_gainer`, `top_loser`, and their `change_pct`.
STEP 4: Check whether any ticker matches the user's watchlist.
        Use `GET /watchlist` only when the user is authenticated.
STEP 5: Generate response using this structure:
        - Market regime: [signal]
        - Top mover: [ticker] [change]%
        - Key signal: [from summary]
        - Practical next step: [based on regime and movers]
STEP 6: Append the standard R.A. Omega disclaimer.

DO NOT: Read the full 50-coin raw JSON in normal mode.
DO NOT: Make up tickers not present in the summary or raw cache.
DO NOT: Give specific buy/sell instructions without framing risk and uncertainty.
