# skill: general_chat

## name
general_chat

## description
Answer general questions conversationally. No trade cards. No report structure. Plain helpful text.

## when_to_use
- User asks a general or casual question
- Question is not tied to a specific company or trade request
- output_mode is "chat", "general_chat", or "finance_answer"
- Intent route is GENERAL_FINANCE or no strong finance intent

## when_not_to_use
- User asks about a specific company or ticker (use company_report)
- User wants trade execution levels (use trade_plan)
- User wants a formal report or document export

## inputs_required
- User question (any topic)
- Optional: session context for continuity

## steps
1. Confirm output_mode is chat/general_chat/finance_answer — not company_report or trade_plan
2. Identify what the user is actually asking
3. Answer directly in conversational plain text
4. Do not pad with unrequested financial analysis

## outputs
- renderer_type: chat_bubble
- Format: conversational prose
- Tone: casual, direct, helpful
- Forbidden: THE SETUP, YOUR RULES, WHAT BREAKS THIS, HOW THIS PLAYS OUT, Action rows, Trade Rating

## safety_rules
- NEVER produce trade card format for general chat
- NEVER include Action/Stop/Target/Risk-Reward rows
- NEVER produce THE SETUP or WHAT BREAKS THIS sections
- Answer the question the user actually asked
- Do not pad with unrequested financial analysis

## quality_checks
- chat_bubble renderer assigned
- No trade card rows in output
- No structured report sections in output
- Response answers the user's actual question

## examples
Input: "How do I make apple pie?"
Output: Plain text recipe — no financial analysis, no trade cards

Input: "What is a P/E ratio?"
Output: Conversational explanation in plain text

## repair_strategy
If output contains trade card rows or report sections, strip all structured finance content and regenerate as plain conversational text.

## related_files
- omega_os/skills/company_report/skill.md
- omega_os/skills/trade_plan/skill.md
