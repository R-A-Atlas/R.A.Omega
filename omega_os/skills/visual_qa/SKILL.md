# skill: visual_qa

## name
visual_qa

## description
Answer questions about charts, graphs, or images provided by the user.

## when_to_use
- User uploads or pastes a chart, graph, screenshot, or image
- User asks "what does this chart show?" or "analyze this graph"

## when_not_to_use
- No image is provided
- User is asking a text-only finance question

## inputs_required
- Image (chart, graph, or screenshot)
- Optional: specific question about the image

## steps
1. Confirm an image has been provided
2. Identify the chart or graph type
3. Describe the trend, key levels, and notable events visible
4. Answer the user's specific question about the image
5. Label all interpretations as interpretations, not facts

## outputs
- renderer_type: chat_bubble
- Format: plain prose description + analysis
- Tone: analytical, visual
- All interpretations labeled as interpretations

## safety_rules
- Do not fabricate data not visible in the image
- Label all interpretations as interpretations, not facts
- If chart is unclear, state limitations

## quality_checks
- Answer references specific elements visible in the image
- No fabricated data points
- Limitations stated if image is unclear

## examples
Input: Chart of NVDA price over 6 months
Output: "The chart shows NVDA trending up from $400 to $950 between Jan-Jun with a consolidation in March..."

## repair_strategy
If image cannot be parsed, ask user to describe the chart in text.

## related_files
- omega_os/skills/capture_triage/skill.md
- omega_os/skills/company_report/skill.md
