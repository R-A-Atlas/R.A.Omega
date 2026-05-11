# ATLAS Agent Registry
# Last Updated: 2026-05-09 (Swarm Builder Division 0 pass)
# Total Agents: 115 | Built: 22 | Pending: 93


## Division 0-Engineering
| ID | Name | Directory | Output | Status |
|----|------|-----------|--------|--------|
| E1 | Skill Scripter | atlas_agents/engineering/skill_scripter/ | atlas_vault/02-Wiki/Skills/ | BUILT |
| E2 | Refactorer DRY Agent | atlas_agents/engineering/refactorer/ | atlas_core/utils/agent_utils.py | BUILT+VERIFIED |
| E3 | API Integrator | atlas_agents/engineering/api_integrator/ | atlas_core/connectors/ | BUILT |
| E4 | UI UX Porter | atlas_agents/engineering/ui_porter/ | ra_omega_app.html | BUILT |
| E5 | DB Architect | atlas_agents/engineering/db_architect/ | schema.sql | BUILT |
| E6 | Red Teamer | atlas_agents/engineering/red_teamer/ | tests/security/ | BUILT |
| E7 | Unit Tester | atlas_agents/engineering/unit_tester/ | tests/ | BUILT+VERIFIED |
| E8 | Data Validator | atlas_agents/engineering/data_validator/ | data_cache/ (read) | BUILT |
| E9 | Dependency Watcher | atlas_agents/engineering/dep_watcher/ | requirements.txt | BUILT |
| E10 | Eval Scorer | atlas_agents/engineering/eval_scorer/ | tests/evals/ | BUILT |

## Division 1-Trading
| ID | Name | Directory | Output | Status |
|----|------|-----------|--------|--------|
| D1 | Crypto Hound | atlas_agents/crypto/ | data_cache/crypto_top50_latest.json | BUILT+VERIFIED |
| D2 | Equities Scanner | atlas_agents/equities/ | data_cache/equities_latest.json | BUILT+VERIFIED |
| D3 | Options Flow Monitor | atlas_agents/trading/options_flow/ | data_cache/options_flow_latest.json | BUILT |
| D4 | Insider Tracker | atlas_agents/trading/insider_tracker/ | data_cache/insider_trades_latest.json | BUILT |
| D5 | Earnings Parser | atlas_agents/trading/earnings_parser/ | data_cache/earnings_latest.json | PENDING |
| D6 | Forex Radar | atlas_agents/trading/forex_radar/ | data_cache/forex_latest.json | PENDING |
| D7 | Commodities Watch | atlas_agents/trading/commodities/ | data_cache/commodities_latest.json | PENDING |
| D8 | Dark Pool Monitor | atlas_agents/trading/dark_pool/ | data_cache/dark_pool_latest.json | BUILT+VERIFIED |
| D9 | Penny Stock Screener | atlas_agents/trading/penny_screener/ | data_cache/penny_stocks_latest.json | PENDING |
| D10 | Bond Yield Curve | atlas_agents/trading/bond_yields/ | data_cache/bond_yields_latest.json | BUILT+VERIFIED |

## Division 2-RealEstate
| ID | Name | Directory | Output | Status |
|----|------|-----------|--------|--------|
| R1 | Residential Scout | atlas_agents/realestate/residential/ | data_cache/residential_latest.json | PENDING |
| R2 | Rental Yield Calculator | atlas_agents/realestate/rental_yield/ | data_cache/rental_yield_latest.json | PENDING |
| R3 | Airbnb STR Analyzer | atlas_agents/realestate/str_analyzer/ | data_cache/str_latest.json | PENDING |
| R4 | Commercial Property Bot | atlas_agents/realestate/commercial/ | data_cache/commercial_latest.json | PENDING |
| R5 | Zoning Permit Watcher | atlas_agents/realestate/zoning/ | data_cache/zoning_latest.json | PENDING |
| R6 | REIT Screener | atlas_agents/realestate/reit_screener/ | data_cache/reits_latest.json | PENDING |
| R7 | Mortgage Rate Tracker | atlas_agents/realestate/mortgage_rates/ | data_cache/mortgage_rates_latest.json | PENDING |

## Division 3-Wealth
| ID | Name | Directory | Output | Status |
|----|------|-----------|--------|--------|
| W1 | Credit Card Optimizer | atlas_agents/wealth/credit_cards/ | data_cache/credit_cards_latest.json | PENDING |
| W2 | Auto Loan Scanner | atlas_agents/wealth/auto_loans/ | data_cache/auto_loans_latest.json | PENDING |
| W3 | Student Debt Monitor | atlas_agents/wealth/student_debt/ | data_cache/student_debt_latest.json | PENDING |
| W4 | HYSA Tracker | atlas_agents/wealth/hysa/ | data_cache/hysa_latest.json | PENDING |
| W5 | IRA 401k Limit Bot | atlas_agents/wealth/retirement_limits/ | data_cache/retirement_limits_latest.json | PENDING |
| W6 | Personal Loan Screener | atlas_agents/wealth/personal_loans/ | data_cache/personal_loans_latest.json | PENDING |
| W7 | Cost of Living Indexer | atlas_agents/wealth/col_indexer/ | data_cache/col_latest.json | PENDING |
| W8 | Insurance Premium Tracker | atlas_agents/wealth/insurance/ | data_cache/insurance_latest.json | PENDING |

## Division 4-Legal
| ID | Name | Directory | Output | Status |
|----|------|-----------|--------|--------|
| L1 | Federal Tax Code Bot | atlas_agents/legal/federal_tax/ | data_cache/federal_tax_latest.json | PENDING |
| L2 | State Tax Monitor | atlas_agents/legal/state_tax/ | data_cache/state_tax_latest.json | PENDING |
| L3 | Bankruptcy Parser | atlas_agents/legal/bankruptcy/ | data_cache/bankruptcy_latest.json | PENDING |
| L4 | SEC EDGAR Bot | atlas_agents/legal/sec_edgar/ | data_cache/sec_filings_latest.json | PENDING |
| L5 | Consumer Protection Watch | atlas_agents/legal/consumer_protection/ | data_cache/consumer_alerts_latest.json | PENDING |
| L6 | Labor Law Monitor | atlas_agents/legal/labor_law/ | data_cache/labor_law_latest.json | PENDING |

## Division 5-Business
| ID | Name | Directory | Output | Status |
|----|------|-----------|--------|--------|
| B1 | SBA Grant Loan Finder | atlas_agents/business/sba/ | data_cache/sba_latest.json | PENDING |
| B2 | B2B SaaS Metrics Bot | atlas_agents/business/saas_metrics/ | data_cache/saas_metrics_latest.json | PENDING |
| B3 | Ecommerce Trends Bot | atlas_agents/business/ecommerce/ | data_cache/ecommerce_latest.json | PENDING |
| B4 | Freelance Rate Indexer | atlas_agents/business/freelance_rates/ | data_cache/freelance_rates_latest.json | PENDING |
| B5 | Franchise Evaluator | atlas_agents/business/franchise/ | data_cache/franchise_latest.json | PENDING |
| B6 | VC Deal Flow Monitor | atlas_agents/business/vc_deals/ | data_cache/vc_deals_latest.json | PENDING |

## Division 6-Alternative
| ID | Name | Directory | Output | Status |
|----|------|-----------|--------|--------|
| A1 | Watch Market Bot | atlas_agents/alternative/watches/ | data_cache/watches_latest.json | PENDING |
| A2 | Art Auction Tracker | atlas_agents/alternative/art/ | data_cache/art_latest.json | PENDING |
| A3 | Collectibles Cards Scraper | atlas_agents/alternative/collectibles/ | data_cache/collectibles_latest.json | PENDING |
| A4 | P2P Lending Bot | atlas_agents/alternative/p2p_lending/ | data_cache/p2p_latest.json | PENDING |
| A5 | Physical Metals Bot | atlas_agents/alternative/metals/ | data_cache/metals_latest.json | PENDING |

## Division 7-Macro
| ID | Name | Directory | Output | Status |
|----|------|-----------|--------|--------|
| M1 | Fed Rate Probability | atlas_agents/macro/fed_watch/ | data_cache/fed_watch_latest.json | BUILT+VERIFIED |
| M2 | Supply Chain Indexer | atlas_agents/macro/supply_chain/ | data_cache/supply_chain_latest.json | PENDING |
| M3 | Energy Grid Monitor | atlas_agents/macro/energy/ | data_cache/energy_latest.json | PENDING |
| M4 | Climate Risk FEMA Bot | atlas_agents/macro/climate_risk/ | data_cache/climate_risk_latest.json | PENDING |
| M5 | Geopolitical Tariff Tracker | atlas_agents/macro/tariffs/ | data_cache/tariffs_latest.json | PENDING |
| M6 | Job Market BLS Bot | atlas_agents/macro/jobs/ | data_cache/jobs_latest.json | PENDING |
| M7 | Inflation CPI Bot | atlas_agents/macro/inflation/ | data_cache/cpi_latest.json | BUILT+VERIFIED |
| M8 | Congressional Trade Watcher | atlas_agents/macro/congress_trades/ | data_cache/congress_trades_latest.json | PENDING |
| M9 | Global Liquidity Monitor | atlas_agents/macro/global_liquidity/ | data_cache/global_liquidity_latest.json | BUILT+VERIFIED |

## Division 8-Growth
| ID | Name | Directory | Output | Status |
|----|------|-----------|--------|--------|
| G1 | Lead Generation Scraper | atlas_agents/growth/lead_gen/ | data_cache/leads_latest.json | PENDING |
| G2 | CRM Sync Agent | atlas_agents/growth/crm_sync/ | Supabase direct | PENDING |
| G3 | Competitor Ad Spy | atlas_agents/growth/ad_spy/ | data_cache/competitor_ads_latest.json | PENDING |
| G4 | SEO Keyword Tracker | atlas_agents/growth/seo/ | data_cache/seo_keywords_latest.json | PENDING |
| G5 | Social Sentiment Analyzer | atlas_agents/growth/sentiment/ | data_cache/sentiment_latest.json | PENDING |
| G6 | Content Repurposer Bot | atlas_agents/growth/content/ | atlas_vault/03-Outputs/Content/ | PENDING |
| G7 | Email Deliverability Monitor | atlas_agents/growth/email_health/ | data_cache/email_health_latest.json | PENDING |
| G8 | Engagement Rater | atlas_agents/growth/engagement/ | data_cache/engagement_latest.json | PENDING |
| G9 | Review Aggregator | atlas_agents/growth/reviews/ | data_cache/reviews_latest.json | PENDING |
| G10 | ROAS Optimizer | atlas_agents/growth/roas/ | data_cache/roas_latest.json | PENDING |

## Division 9-Voice
| ID | Name | Directory | Output | Status |
|----|------|-----------|--------|--------|
| V1 | Voice Input Whisper | atlas_agents/voice/input/ | POST /voice/query endpoint | PENDING |
| V2 | Voice Output TTS | atlas_agents/voice/output/ | Audio stream in browser | PENDING |
| V3 | Conversational Memory Agent | atlas_agents/voice/memory/ | Loop 5 preference profile | PENDING |
| V4 | Alert Voice Notifier | atlas_agents/voice/notifier/ | Twilio voice call | PENDING |
| V5 | Meeting Prep Agent | atlas_agents/voice/meeting_prep/ | atlas_vault/03-Outputs/Reports/meeting_prep_*.html | PENDING |
| V6 | NL Report Editor | atlas_agents/voice/report_editor/ | Updated HTML report | PENDING |

## Division 10-Documents
| ID | Name | Directory | Output | Status |
|----|------|-----------|--------|--------|
| DOC1 | Infographic Agent | atlas_agents/documents/infographic/ | atlas_vault/03-Outputs/Charts/*.png | PENDING |
| DOC2 | PDF Report Agent | atlas_agents/documents/pdf/ | atlas_vault/03-Outputs/Reports/*.pdf | BUILT |
| DOC3 | PowerPoint Agent | atlas_agents/documents/powerpoint/ | atlas_vault/03-Outputs/Decks/*.pptx | PENDING |
| DOC4 | Excel Model Agent | atlas_agents/documents/excel/ | atlas_vault/03-Outputs/Reports/*.xlsx | BUILT |
| DOC5 | Email Digest Agent | atlas_agents/documents/email_digest/ | Daily email to user | PENDING |
| DOC6 | Comparison Report Agent | atlas_agents/documents/comparison/ | Multi-ticker HTML report | PENDING |
| DOC7 | Portfolio Report Agent | atlas_agents/documents/portfolio_report/ | atlas_vault/03-Outputs/Reports/portfolio_*.pdf | PENDING |
| DOC8 | Watchlist Alert Report | atlas_agents/documents/watchlist_alert/ | HTML card + Supabase log | PENDING |

## Division 11-Intelligence
| ID | Name | Directory | Output | Status |
|----|------|-----------|--------|--------|
| IQ1 | Cross Asset Correlation | atlas_agents/intelligence/correlation/ | data_cache/correlation_latest.json | PENDING |
| IQ2 | Regime Change Detector | atlas_agents/intelligence/regime_detector/ | Supabase alert + push | PENDING |
| IQ3 | Earnings Season Coordinator | atlas_agents/intelligence/earnings_coord/ | data_cache/earnings_season_brief_latest.json | PENDING |
| IQ4 | Sector Rotation Agent | atlas_agents/intelligence/sector_rotation/ | data_cache/sector_rotation_latest.json | BUILT+VERIFIED |
| IQ5 | News Catalyst Agent | atlas_agents/intelligence/news_catalyst/ | data_cache/news_catalysts_latest.json | PENDING |
| IQ6 | Sentiment Divergence Agent | atlas_agents/intelligence/sentiment_div/ | data_cache/sentiment_divergence_latest.json | PENDING |
| IQ7 | Backtesting Agent | atlas_agents/intelligence/backtesting/ | atlas_vault/03-Outputs/Backtests/*.json | PENDING |
| IQ8 | Risk Budget Agent | atlas_agents/intelligence/risk_budget/ | data_cache/risk_budget_latest.json | PENDING |

## Division 12-Platform
| ID | Name | Directory | Output | Status |
|----|------|-----------|--------|--------|
| P1 | Broker Integration Agent | atlas_agents/platform/broker/ | positions_cache.json (live) | PENDING |
| P2 | Discord Bot Agent | atlas_agents/platform/discord/ | Discord channel posts | PENDING |
| P3 | Telegram Alert Agent | atlas_agents/platform/telegram/ | Telegram messages | PENDING |
| P4 | Webhook Publisher Agent | atlas_agents/platform/webhooks/ | User-defined webhook URL | PENDING |
| P5 | White Label Agent | atlas_agents/platform/white_label/ | Rebranded HTML/PDF | PENDING |
| P6 | API Gateway Agent | atlas_agents/platform/api_gateway/ | POST /api/v1/query | PENDING |
| P7 | Compliance Archive Agent | atlas_agents/platform/compliance/ | Supabase compliance_archive table | PENDING |
| P8 | Self Improvement Agent | atlas_agents/platform/self_improvement/ | atlas_vault/04-Projects/ATLAS/Notes/improvement_*.md | PENDING |

## Division 13-Cognitive
| ID | Name | Directory | Output | Status |
|----|------|-----------|--------|--------|
| C0 | Code Optimizer | atlas_agents/cognitive/code_optimizer/ | data_cache/code_optimizer_latest.json | BUILT |
| C1 | Codebase Mapper | atlas_agents/cognitive/codebase_mapper/ | atlas_agents/cognitive/codebase_mapper/repo_map.json | PENDING |
| C2 | Architecture Planner | atlas_agents/cognitive/arch_planner/ | atlas_vault/04-Projects/ATLAS/Notes/plan_*.md | PENDING |
| C3 | Execution Sandbox | atlas_agents/cognitive/sandbox/ | APPROVED or REJECTED with traceback | PENDING |
| C4 | Reflection Correction Engine | atlas_agents/cognitive/reflection/ | atlas_vault/04-Projects/ATLAS/Notes/corrections_*.md | PENDING |
| C5 | Static Linter Security Scanner | atlas_agents/cognitive/linter/ | CLEAN or violations list | PENDING |
| C6 | Diff Synthesizer | atlas_agents/cognitive/diff_synthesizer/ | Unified diff output | PENDING |
| C7 | Tree of Thoughts Arbiter | atlas_agents/cognitive/tot_arbiter/ | bull/bear/arbiter conclusion JSON | PENDING |
| C8 | Evals Benchmarking Supervisor | atlas_agents/cognitive/eval_supervisor/ | atlas_vault/04-Projects/ATLAS/Notes/nightly_eval_*.md | PENDING |

## Division 14-Compute
| ID | Name | Directory | Output | Status |
|----|------|-----------|--------|--------|
| CR1 | Context Cacher | atlas_agents/compute/context_cacher/ | 90% API cost reduction | PENDING |
| CR2 | Compute Router | atlas_agents/compute/router/ | Model routing logic | PENDING |
| CR3 | Local Scaffolding Ollama | atlas_agents/compute/local_scaffold/ | Empty files and folders | PENDING |
| CR4 | Local File Creator | atlas_agents/compute/local_file_creator/ | Written files on disk | PENDING |
| CR5 | Local Syntax Checker | atlas_agents/compute/local_syntax/ | CLEAN or error list | PENDING |
| CR6 | Local Documentation Writer | atlas_agents/compute/local_docs/ | Docstrings and README files | PENDING |
| CR7 | Local Test Runner | atlas_agents/compute/local_test_runner/ | test_results_*.json | PENDING |

