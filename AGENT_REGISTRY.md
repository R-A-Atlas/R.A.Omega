# R.A. OMEGA — AGENT REGISTRY
# Last updated: 2026-05-14
# Total agents with active intents: 82 / 117 built

## WIRED AGENTS (active intents)

### Trading Data Agents
| Agent | Intent | Cache File |
|-------|--------|------------|
| D1 Crypto Hound | CRYPTO_MARKET_SCAN | crypto_top50_latest.json |
| D2 Equities Scanner | EQUITIES_MARKET_SCAN | equities_latest.json |
| D3 Options Flow Monitor | OPTIONS_FLOW_MARKET_SCAN | options_flow_latest.json |
| D4 Insider Tracker | INSIDER_TRADES_MARKET_SCAN | insider_trades_latest.json |
| D5 Earnings Parser | EARNINGS_MARKET_SCAN | earnings_latest.json |
| D6 Forex Radar | FOREX_MARKET_SCAN | forex_latest.json |
| D7 Commodities Watch | COMMODITIES_MARKET_SCAN | commodities_latest.json |
| D8 Dark Pool Monitor ✅ | DARK_POOL_SCAN | dark_pool_latest.json |
| D9 Penny Stock Screener ✅ | PENNY_STOCK_SCAN | penny_stocks_latest.json |
| D10 Bond Yield Curve | TREASURY_YIELD_MARKET_SCAN | treasury_yield_latest.json |

### Macro Agents
| Agent | Intent | Cache File |
|-------|--------|------------|
| M1 Fed Rate Probability | FED_WATCH_MARKET_SCAN | fed_watch_latest.json |
| M2 Supply Chain Indexer | SUPPLY_CHAIN_MARKET_SCAN | supply_chain_latest.json |
| M3 Energy Grid Monitor | ENERGY_MARKET_SCAN | energy_latest.json |
| M4 Climate Risk/FEMA Bot | CLIMATE_RISK_MARKET_SCAN | climate_risk_latest.json |
| M5 Geopolitical Tariff | TARIFFS_MARKET_SCAN | tariffs_latest.json |
| M6 Job Market/BLS Bot | JOBS_MARKET_SCAN | jobs_latest.json |
| M7 Inflation/CPI Bot | CPI_INFLATION_MARKET_SCAN | cpi_inflation_latest.json |
| M8 Congressional Trades | CONGRESS_TRADES_MARKET_SCAN | congress_trades_latest.json |
| M9 Global Liquidity ✅ | GLOBAL_LIQUIDITY_SCAN | global_liquidity_latest.json |

### Real Estate Agents (R1-R7) ✅ → REAL_ESTATE_SCAN
| Agent | Cache File |
|-------|------------|
| R1 Residential | residential_latest.json |
| R2 Rental Yield | rental_yield_latest.json |
| R3 Short-Term Rental | str_latest.json |
| R4 Commercial | commercial_latest.json |
| R5 Zoning | zoning_latest.json |
| R6 REITs | reits_latest.json |
| R7 Mortgage Rates | mortgage_rates_latest.json |

### Wealth/Debt Agents (W1-W8) ✅ → PERSONAL_WEALTH_SCAN
| Agent | Cache File |
|-------|------------|
| W1 Credit Cards | credit_cards_latest.json |
| W2 Auto Loans | auto_loans_latest.json |
| W3 Student Debt | student_debt_latest.json |
| W4 HYSA | hysa_latest.json |
| W5 Retirement Limits | retirement_limits_latest.json |
| W6 Personal Loans | personal_loans_latest.json |
| W7 Cost of Living | col_latest.json |
| W8 Insurance | insurance_latest.json |

### Tax/Legal Agents (L1-L6) ✅ → TAX_LEGAL_SCAN
| Agent | Cache File |
|-------|------------|
| L1 Federal Tax | federal_tax_latest.json |
| L2 State Tax | state_tax_latest.json |
| L3 Bankruptcy | bankruptcy_latest.json |
| L4 SEC Filings | sec_filings_latest.json |
| L5 Consumer Alerts | consumer_alerts_latest.json |
| L6 Labor Law | labor_law_latest.json |

### Business Agents (B1-B6) ✅ → BUSINESS_SCAN
| Agent | Cache File |
|-------|------------|
| B1 SBA | sba_latest.json |
| B2 SaaS Metrics | saas_metrics_latest.json |
| B3 E-Commerce | ecommerce_latest.json |
| B4 Freelance Rates | freelance_rates_latest.json |
| B5 Franchise | franchise_latest.json |
| B6 VC Deals | vc_deals_latest.json |

### Alternative Asset Agents (A1-A5) ✅ → ALTERNATIVE_ASSET_SCAN
| Agent | Cache File |
|-------|------------|
| A1 Watch Market | watches_latest.json |
| A2 Art | art_latest.json |
| A3 Collectibles | collectibles_latest.json |
| A4 P2P Lending | p2p_latest.json |
| A5 Metals | metals_latest.json |

### Growth/Marketing Agents (G1-G10) ✅ → GROWTH_MARKETING_SCAN
| Agent | Cache File |
|-------|------------|
| G1 Leads | leads_latest.json |
| G2 CRM Sync | crm_sync_latest.json |
| G3 Competitor Ads | competitor_ads_latest.json |
| G4 SEO Keywords | seo_keywords_latest.json |
| G5 Sentiment | sentiment_latest.json |
| G6 Content | (in-memory) |
| G7 Email Health | email_health_latest.json |
| G8 Engagement | engagement_latest.json |
| G9 Reviews | reviews_latest.json |
| G10 ROAS | roas_latest.json |

### Intelligence Synthesis Agents (IQ1-IQ8) ✅ → INTELLIGENCE_SYNTHESIS / SECTOR_ROTATION_SCAN / SENTIMENT_DIVERGENCE_SCAN
| Agent | Cache File |
|-------|------------|
| IQ1 Correlation | correlation_latest.json |
| IQ2 Regime Change | regime_change_latest.json |
| IQ3 Earnings Season Brief | earnings_season_brief_latest.json |
| IQ4 Sector Rotation | sector_rotation_latest.json |
| IQ5 News Catalysts | news_catalysts_latest.json |
| IQ6 Sentiment Divergence | sentiment_divergence_latest.json |
| IQ7 Risk Budget | risk_budget_latest.json |
| IQ8 Backtesting | (in-memory) |

### Additional Intents
| Intent | Trigger |
|--------|---------|
| MARKET_DEEP_DIVE | FourLoopEngine (10-loop equity/options/crypto) |
| GENERAL_FINANCE | OmegaAgent (fast cross-domain) |

---

## INTERNAL AGENTS (no wiring needed — act automatically)

| Category | Agents | Count |
|----------|--------|-------|
| Engineering (E1-E10) | build, test, validate, refactor, watch deps | 10 |
| Voice (V1-V6) | /voice/query + /tts endpoints | 6 |
| Documents (DOC1-DOC8) | /export/* endpoints + on-demand from query | 8 |
| Platform (P1-P8) | discord, telegram, webhooks, broker, compliance | 8 |
| Cognitive (C0-C8) | internal code tools | 9 |
| Compute (CR1-CR7) | routing, caching, local tools | 7 |

---

## COVERAGE SUMMARY

| Status | Count |
|--------|-------|
| Data agents with active intents | 47 |
| Macro + market scan agents wired | 19 |
| Internal agents (auto) | 48 |
| **Total active** | **~114** |
| Total built | 117 |
