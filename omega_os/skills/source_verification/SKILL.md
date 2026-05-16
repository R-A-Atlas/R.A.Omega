# skill: source_verification

## name
source_verification

## description
Verify that data sources cited in a report are real, accessible, and match the claimed data.

## when_to_use
- Quality firewall requests source verification
- User asks "where did you get this data?"
- Any report with financial figures that need citation verification

## when_not_to_use
- User is asking a simple question — do not add verification overhead
- output_mode is chat or general_chat (no structured report to verify)

## inputs_required
- Report or data block to verify
- List of cited sources or data fields

## steps
1. Extract all cited data points and their claimed sources from the report
2. Attempt to fetch or match each source
3. Label each data point: CONFIRMED, UNVERIFIED, or SOURCE_UNAVAILABLE
4. Append verification summary to report

## outputs
- renderer_type: (inherits from parent response)
- Format: verification summary appended to or replacing the data section
- Tone: factual, neutral
- Labels: CONFIRMED / UNVERIFIED / SOURCE_UNAVAILABLE

## safety_rules
- Never fabricate source URLs or confirmation
- If a source is unavailable, label it "source unavailable — data unverified"
- Do not modify the original report content during verification

## quality_checks
- Every cited data point has a verification label
- No fabricated source URLs
- Original report content is unchanged

## examples
Input: Company report citing "BlackRock AUM: $10.5T"
Output: Verified against SEC EDGAR filing — CONFIRMED or UNVERIFIED

## repair_strategy
If source cannot be reached, append "(source unavailable)" label to the affected data point.

## related_files
- omega_os/skills/company_report/skill.md
- omega_os/skills/trade_plan/skill.md
