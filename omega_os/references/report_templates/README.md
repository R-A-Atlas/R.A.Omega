# Report Templates

Structural templates for each report type. Used by document_generator and dashboard_generator skills.

## Available Templates

### Company Report
Sections: Overview | Business Model | Financial Snapshot | Leadership | Recent News | Risks | Competitive Position

### Trade Plan
Sections: Setup | Entry | Invalidation | Risk | Scenarios
Note: Only used when output_mode == trade_plan (user explicitly requests trade analysis)

### Daily Brief
Sections: Market Regime | Top Movers | Macro Watch | My Watchlist | Priority Actions

### Weekly Portfolio Review
Sections: Performance Summary | Position Review | Risk Exposure | Rebalancing Needs | Next Week Watchlist

### Monthly Finance Report
Sections: Market Overview | Sector Performance | Portfolio Changes | Key Events | Outlook

## Format Standards
- Dark theme HTML: Inter font, teal accent, ATLAS branding
- PDF: WeasyPrint/GTK or browser print
- Excel: openpyxl, structured tables
- PowerPoint: python-pptx, branded slides
