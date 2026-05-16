# skill: trade_plan

## name
trade_plan

## description
Generate a structured trade plan with entry, stop loss, targets, options play, and execution rules.

## when_to_use
- User explicitly asks for a trade plan, trade setup, or trade execution
- User wants entry/stop/target levels for a specific ticker
- User asks "how do I trade X" or "give me a trade setup for X"
- output_mode resolved to "trade_plan"

## when_not_to_use
- User wants company research without trade specifics (use company_report)
- User is asking a general question (use general_chat)
- No specific ticker or trade intent is present

## inputs_required
- Ticker symbol or asset name
- Optional: direction bias (long/short)
- Optional: options vs equity preference
- Optional: time horizon

## steps
1. Confirm intent is trade_plan — not company_report or general_chat
2. Fetch current price, key levels, recent volatility
3. Calculate entry, stop loss, and targets based on technicals
4. Identify best options play if applicable
5. Synthesize risk/reward and execution rules
6. Return structured trade cards

## outputs
- renderer_type: trade_cards
- Required fields: entry, stop_loss, target_1, risk_reward, options_play
- Format: structured cards with numeric levels
- Tone: precise, actionable, risk-aware

## safety_rules
- Always include a stop loss — never produce a trade plan without one
- Never recommend naked options
- Always state the risk/reward ratio
- Label all levels as suggestions, not guaranteed outcomes
- Do not use leverage recommendations without explicit user request

## quality_checks
- trade_cards renderer assigned
- stop_loss field is numeric and present
- risk_reward ratio is stated
- No naked options recommended
- Entry price is present and numeric

## examples
Input: "Give me a TSLA trade setup"
Output: Trade cards with Entry, Stop Loss, Target 1/2, Options Play, Risk/Reward, Execution Rules

Input: "How do I trade NVDA earnings?"
Output: Trade cards with earnings-specific entry/stop, straddle or directional options setup

## repair_strategy
If output is missing stop_loss or entry, inject repair prompt requiring numeric levels.
If output reads as a company report (prose only), route back through trade_analysis workflow.

## related_files
- omega_os/skills/company_report/skill.md
- omega_os/skills/source_verification/skill.md
