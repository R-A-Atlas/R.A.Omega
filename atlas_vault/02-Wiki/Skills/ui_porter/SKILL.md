---
name: UI/UX Porter
description: Ports UI patterns from atlas_dashboard_v4.html into index_1778227564596.html using React + Tailwind
type: reference
agent: E4
division: Engineering
---

# Skill: UI/UX Porter (E4)

## [D] Direction
Port vanilla JS UI patterns from atlas_dashboard_v4.html into the React
architecture of index_1778227564596.html. Translate custom CSS → Tailwind.
Translate vanilla JS state → React.useState / React.useCallback hooks.
One component at a time. Smallest diff possible.

## [B] Blueprints
Source:   atlas_dashboard_v4.html
  - inferRiskLevelQuick()        → QuickStatsStrip React component (DONE)
  - inferFinancialImpactQuick()  → QuickStatsStrip React component (DONE)
  - loadSessionsSidebar()        → sessions sidebar React JSX (DONE)
  - buildQuickStatsStrip()       → QuickStatsStrip render (DONE)
  - refreshRegimeNav()           → regime label fetch on mount (PENDING)

Target:   index_1778227564596.html
  - StructuredResponse component  (line ~674)
  - QuickStatsStrip component     (line ~625, DONE)
  - Sessions sidebar JSX          (line ~1263, DONE)
  - generateStandaloneReport()    (line ~250, upgrade PENDING)

API shape: See CLAUDE.md Section 7

## [S] Solutions
Test cycle:
  1. Start server: uvicorn api_server:app --host 127.0.0.1 --port 8000
  2. Hard-refresh /option1 (Ctrl+Shift+R)
  3. Submit: "Analyze NVDA — current setup and trade plan"
  4. Confirm: 7 cards render, RYG meters show, Export button works

## Evals
| # | Assertion | Pass Condition |
|---|-----------|----------------|
| 1 | No JS console errors on load | DevTools console clean |
| 2 | StructuredResponse renders all 7 cards | visual confirm |
| 3 | QuickStatsStrip shows correct risk level | meter bar + label visible |
| 4 | Sessions sidebar loads live chats | GET /sessions returns list |
| 5 | Export HTML report opens standalone page | window.open succeeds |
