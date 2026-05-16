# skill: dashboard_generator

## name
dashboard_generator

## description
Generate an interactive HTML dashboard or data visualization artifact.

## when_to_use
- User asks for a dashboard, chart, or interactive visualization
- output_mode is "html_artifact"
- User says "create a dashboard", "show me a chart", "make an interactive report"

## when_not_to_use
- User wants a static document (use document_generator)
- User wants inline analysis in chat (use company_report or general_chat)

## inputs_required
- Data or topic to visualize
- Optional: chart type or layout preference
- Optional: ticker or company list for comparison

## steps
1. Confirm output_mode is html_artifact
2. Gather data: prices, metrics, comparisons as requested
3. Build self-contained HTML with embedded charts (Chart.js or similar)
4. Validate: no external untrusted scripts, no API keys in HTML
5. Return HTML artifact string

## outputs
- renderer_type: html_artifact
- Format: self-contained HTML with embedded CSS/JS
- Tone: visual, data-driven
- Must be self-contained (no server-side dependencies)

## safety_rules
- Generated HTML must not include external script tags from untrusted CDNs
- Do not embed API keys in generated HTML artifacts
- HTML must be self-contained (no server-side dependencies)

## quality_checks
- html_artifact renderer assigned
- HTML is self-contained (no external untrusted dependencies)
- No API keys in generated HTML
- At least one chart or visualization present

## examples
Input: "Create an interactive dashboard comparing NVDA vs AMD"
Output: Self-contained HTML artifact with price chart, comparison metrics, and interactive controls

## repair_strategy
If HTML artifact fails to render, simplify to a static table layout and retry.

## related_files
- omega_os/skills/company_report/skill.md
- omega_os/skills/document_generator/skill.md
