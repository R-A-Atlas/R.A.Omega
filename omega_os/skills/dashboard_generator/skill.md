# Skill: dashboard_generator

## name
dashboard_generator

## description
Generate an interactive HTML dashboard or widget for finance data visualization.
Dark theme, Inter font, ATLAS branding, contenteditable annotations, Export PDF via print.

## when_to_use
- User asks "create an HTML dashboard for [topic]"
- User asks "make me a visual report" or "build an interactive chart"
- User asks "HTML report" or "interactive dashboard"
- intent == HTML_ARTIFACT
- output_mode == html_artifact

## inputs_required
- Topic or data to visualize (required)
- Optional: specific charts (price levels, scenarios donut, catalyst timeline)
- Optional: company name or ticker
- Optional: time range

## steps
1. Confirm HTML artifact output from query
2. Route to OmegaAgent or FourLoopEngine for data synthesis
3. Apply OUTPUT_CONTRACTS["html_artifact"]
4. Build standalone HTML with:
   - Dark theme (#0a0a0a background, #00D4AA accent, Inter font)
   - ATLAS branding in header
   - Price levels rail + horizontal bars
   - Scenarios donut chart (bull / base / bear probabilities)
   - Catalyst timeline strip
   - Contenteditable annotations (user can add notes)
   - Export PDF via browser print (window.print())
   - "117 agents active" footer
5. Return as inline HTML string or serve via FastAPI static endpoint

## outputs
- Self-contained HTML file (all CSS/JS inline)
- Can be opened directly in browser or served via /app
- Contenteditable sections for user annotations
- Print-to-PDF ready

## safety_rules
- No external CDN links — all assets must be inline (avoids browser policy blocks)
- Do not include API keys or secrets in HTML output
- Do not auto-execute any scripts that call external APIs without user confirmation
- Do not include user account details or session tokens in HTML
- Note: in-app browser policy blocks direct file:// opening — serve via FastAPI when needed

## related_files
- api_server.py — HTML artifact handling
- ra_omega_app.html — generateStandaloneReport() reference implementation
- output_contracts.py — OUTPUT_CONTRACTS["html_artifact"]
- omega_os/references/ui_design/README.md — color palette, typography
- omega_os/references/report_templates/README.md — dashboard layout

## quality_checks
- [ ] All CSS and JS is inline (no external CDN dependencies)
- [ ] Dark theme applied (background #0a0a0a or similar)
- [ ] ATLAS branding in header
- [ ] At least one interactive element (chart, annotation, expandable section)
- [ ] Print-to-PDF works (window.print() wired to Export button)
- [ ] No API keys in HTML source
- [ ] output_mode == "html_artifact" confirmed
