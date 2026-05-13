# Critical Path: Portfolio Analysis Query

TRIGGER: `classify_intent_route()` returns portfolio, allocation, risk, exposure, rebalancing, drawdown, position sizing, or user holdings intent.

STEP 1: Read authenticated user context if available:
        - positions
        - watchlist
        - saved sessions
        Skip this step for unauthenticated users.
STEP 2: Read companion summary files based on portfolio composition:
        - equities for stock-heavy portfolios
        - sector rotation for concentration risk
        - bond yields and CPI for rate/inflation sensitivity
        - crypto summary for digital asset exposure
STEP 3: Calculate or infer:
        - largest concentration
        - sector/theme overlap
        - obvious hedge gaps
        - stale or missing data warnings
STEP 4: Generate response using this structure:
        - Portfolio read
        - Concentration risks
        - Market context
        - Rebalance candidates
        - Questions needed before action
STEP 5: Add standard disclaimer and state that final allocation decisions belong to the user.

DO NOT: fabricate holdings when no portfolio data is available.
DO NOT: create personalized investment advice without user constraints.
DO NOT: hide missing position or price data.
