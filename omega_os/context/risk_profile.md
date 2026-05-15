# Risk Profile

## Risk Tolerance
- Overall risk level: LOW — high ambition, low current risk capacity
- Financial situation: Currently in debt and not working; income/debt stabilization is the prerequisite before any live trading
- Max loss per trade: minimal — paper trading only until debt/income situation is resolved
- Max allocation per position: small; no oversized bets

## Trade Rules (Personal)
<!-- Only applies when output_mode == trade_plan -->
- Stop loss style: hard stop — no mental stops
- Preferred R:R minimum: 2:1
- Preferred entry method: defined-risk setups only
- Options preference: defined-risk spreads only — NO naked options, NO naked calls/puts
- NO revenge trading under any circumstances
- NO position sizing that exceeds comfort given current financial state

## Active Trading Mode
- PAPER TRADING ONLY until income is stable and debt plan is in place
- Do not suggest live position sizing or real capital deployment
- When output_mode == trade_plan: flag that user is in paper-trading phase

## Sectors to Avoid
- None explicitly excluded — but defer to financial stability first

## Asset Classes
- [x] US equities (paper only currently)
- [ ] Crypto — deferred until financial stability
- [ ] Bonds — not current focus
- [ ] Real estate — deferred
- [ ] Commodities — deferred

## Emergency Fund Status
- No emergency fund currently — debt repayment and income are the priority
- All analyses should acknowledge this context when relevant (PERSONAL_WEALTH_SCAN, W1-W8)

## Notes
Trading logic (entry, stop loss, take profit, execution rules) only appears in responses
when output_mode == trade_plan. This profile is never injected into classify_intent_route().
