"""
ATLAS SWARM BOOTSTRAP SCRIPT
Generates all 115 agent directories and stub files locally.
Zero AI credits. Pure Python file creation.

Run this ONCE from your project root:
  cd "C:\\Users\\crist\\OneDrive\\Desktop\\trading platform overview"
  python bootstrap_swarm.py

What it creates:
  - atlas_agents/<division>/<agent>/__init__.py
  - atlas_agents/<division>/<agent>/AGENT_PROMPT.md (stub)
  - atlas_vault/02-Wiki/Skills/<agent-name>/SKILL.md (stub)
  - tests/test_<agent_name>.py (2 basic existence tests)
  - atlas_agents/AGENT_REGISTRY.md (full 115-agent table)

Already-built agents (D1, D2, E2, E7, E8) are SKIPPED.
After running this, only the actual LOGIC needs AI credits.
"""

import os
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent
AGENTS_DIR = ROOT / "atlas_agents"
VAULT_SKILLS = ROOT / "atlas_vault" / "02-Wiki" / "Skills"
TESTS_DIR = ROOT / "tests"

# Already built — skip these entirely
ALREADY_BUILT = {"D1", "D2", "E2", "E7", "E8"}

# ─────────────────────────────────────────────────────────────────
# FULL 115-AGENT ROSTER
# (subdir, agent_id, display_name, division_label, output_file, source)
# ─────────────────────────────────────────────────────────────────
AGENTS = [
    # ── Division 0 — Engineering ──────────────────────────────────
    ("engineering/skill_scripter",    "E1",   "Skill Scripter",
     "0-Engineering", "atlas_vault/02-Wiki/Skills/", "Internal"),
    ("engineering/refactorer",        "E2",   "Refactorer DRY Agent",
     "0-Engineering", "atlas_core/utils/agent_utils.py", "Internal"),
    ("engineering/api_integrator",    "E3",   "API Integrator",
     "0-Engineering", "atlas_core/connectors/", "External APIs"),
    ("engineering/ui_porter",         "E4",   "UI UX Porter",
     "0-Engineering", "ra_omega_app.html", "Internal"),
    ("engineering/db_architect",      "E5",   "DB Architect",
     "0-Engineering", "schema.sql", "Supabase"),
    ("engineering/red_teamer",        "E6",   "Red Teamer",
     "0-Engineering", "tests/security/", "Internal"),
    ("engineering/unit_tester",       "E7",   "Unit Tester",
     "0-Engineering", "tests/", "Internal"),
    ("engineering/data_validator",    "E8",   "Data Validator",
     "0-Engineering", "data_cache/ (read)", "Internal"),
    ("engineering/dep_watcher",       "E9",   "Dependency Watcher",
     "0-Engineering", "requirements.txt", "pip"),
    ("engineering/eval_scorer",       "E10",  "Eval Scorer",
     "0-Engineering", "tests/evals/", "Internal"),

    # ── Division 1 — Trading Desk ─────────────────────────────────
    ("crypto",                        "D1",   "Crypto Hound",
     "1-Trading", "data_cache/crypto_top50_latest.json", "CoinGecko public"),
    ("equities",                      "D2",   "Equities Scanner",
     "1-Trading", "data_cache/equities_latest.json", "Yahoo Finance / yfinance"),
    ("trading/options_flow",          "D3",   "Options Flow Monitor",
     "1-Trading", "data_cache/options_flow_latest.json", "CBOE public"),
    ("trading/insider_tracker",       "D4",   "Insider Tracker",
     "1-Trading", "data_cache/insider_trades_latest.json", "SEC EDGAR RSS"),
    ("trading/earnings_parser",       "D5",   "Earnings Parser",
     "1-Trading", "data_cache/earnings_latest.json", "yfinance + EarningsWhispers"),
    ("trading/forex_radar",           "D6",   "Forex Radar",
     "1-Trading", "data_cache/forex_latest.json", "frankfurter.app (free)"),
    ("trading/commodities",           "D7",   "Commodities Watch",
     "1-Trading", "data_cache/commodities_latest.json", "EIA public + metals-api"),
    ("trading/dark_pool",             "D8",   "Dark Pool Monitor",
     "1-Trading", "data_cache/dark_pool_latest.json", "FINRA ATS public"),
    ("trading/penny_screener",        "D9",   "Penny Stock Screener",
     "1-Trading", "data_cache/penny_stocks_latest.json", "yfinance screener"),
    ("trading/bond_yields",           "D10",  "Bond Yield Curve",
     "1-Trading", "data_cache/bond_yields_latest.json", "api.fiscaldata.treasury.gov"),

    # ── Division 2 — Real Estate ──────────────────────────────────
    ("realestate/residential",        "R1",   "Residential Scout",
     "2-RealEstate", "data_cache/residential_latest.json", "Redfin/Zillow public"),
    ("realestate/rental_yield",       "R2",   "Rental Yield Calculator",
     "2-RealEstate", "data_cache/rental_yield_latest.json", "HUD FMR API"),
    ("realestate/str_analyzer",       "R3",   "Airbnb STR Analyzer",
     "2-RealEstate", "data_cache/str_latest.json", "AirDNA / Inside Airbnb"),
    ("realestate/commercial",         "R4",   "Commercial Property Bot",
     "2-RealEstate", "data_cache/commercial_latest.json", "CoStar public"),
    ("realestate/zoning",             "R5",   "Zoning Permit Watcher",
     "2-RealEstate", "data_cache/zoning_latest.json", "City open data portals"),
    ("realestate/reit_screener",      "R6",   "REIT Screener",
     "2-RealEstate", "data_cache/reits_latest.json", "yfinance + SEC EDGAR"),
    ("realestate/mortgage_rates",     "R7",   "Mortgage Rate Tracker",
     "2-RealEstate", "data_cache/mortgage_rates_latest.json", "Freddie Mac PMMS"),

    # ── Division 3 — Personal Wealth ──────────────────────────────
    ("wealth/credit_cards",           "W1",   "Credit Card Optimizer",
     "3-Wealth", "data_cache/credit_cards_latest.json", "CFPB public"),
    ("wealth/auto_loans",             "W2",   "Auto Loan Scanner",
     "3-Wealth", "data_cache/auto_loans_latest.json", "Federal Reserve G.19"),
    ("wealth/student_debt",           "W3",   "Student Debt Monitor",
     "3-Wealth", "data_cache/student_debt_latest.json", "StudentAid.gov public"),
    ("wealth/hysa",                   "W4",   "HYSA Tracker",
     "3-Wealth", "data_cache/hysa_latest.json", "FDIC BankFind API"),
    ("wealth/retirement_limits",      "W5",   "IRA 401k Limit Bot",
     "3-Wealth", "data_cache/retirement_limits_latest.json", "IRS.gov"),
    ("wealth/personal_loans",         "W6",   "Personal Loan Screener",
     "3-Wealth", "data_cache/personal_loans_latest.json", "CFPB + Bankrate"),
    ("wealth/col_indexer",            "W7",   "Cost of Living Indexer",
     "3-Wealth", "data_cache/col_latest.json", "BLS CPI regional API"),
    ("wealth/insurance",              "W8",   "Insurance Premium Tracker",
     "3-Wealth", "data_cache/insurance_latest.json", "NAIC public data"),

    # ── Division 4 — Tax & Legal ──────────────────────────────────
    ("legal/federal_tax",             "L1",   "Federal Tax Code Bot",
     "4-Legal", "data_cache/federal_tax_latest.json", "IRS.gov"),
    ("legal/state_tax",               "L2",   "State Tax Monitor",
     "4-Legal", "data_cache/state_tax_latest.json", "Tax Foundation public"),
    ("legal/bankruptcy",              "L3",   "Bankruptcy Parser",
     "4-Legal", "data_cache/bankruptcy_latest.json", "US Courts public stats"),
    ("legal/sec_edgar",               "L4",   "SEC EDGAR Bot",
     "4-Legal", "data_cache/sec_filings_latest.json", "efts.sec.gov (public)"),
    ("legal/consumer_protection",     "L5",   "Consumer Protection Watch",
     "4-Legal", "data_cache/consumer_alerts_latest.json", "FTC RSS + CPSC API"),
    ("legal/labor_law",               "L6",   "Labor Law Monitor",
     "4-Legal", "data_cache/labor_law_latest.json", "DOL public data"),

    # ── Division 5 — Business ─────────────────────────────────────
    ("business/sba",                  "B1",   "SBA Grant Loan Finder",
     "5-Business", "data_cache/sba_latest.json", "SBA.gov API + grants.gov"),
    ("business/saas_metrics",         "B2",   "B2B SaaS Metrics Bot",
     "5-Business", "data_cache/saas_metrics_latest.json", "OpenView + ChartMogul public"),
    ("business/ecommerce",            "B3",   "Ecommerce Trends Bot",
     "5-Business", "data_cache/ecommerce_latest.json", "pytrends (Google Trends)"),
    ("business/freelance_rates",      "B4",   "Freelance Rate Indexer",
     "5-Business", "data_cache/freelance_rates_latest.json", "Upwork public + BLS"),
    ("business/franchise",            "B5",   "Franchise Evaluator",
     "5-Business", "data_cache/franchise_latest.json", "FTC FDD database"),
    ("business/vc_deals",             "B6",   "VC Deal Flow Monitor",
     "5-Business", "data_cache/vc_deals_latest.json", "Crunchbase public"),

    # ── Division 6 — Alternative Assets ──────────────────────────
    ("alternative/watches",           "A1",   "Watch Market Bot",
     "6-Alternative", "data_cache/watches_latest.json", "Chrono24 public"),
    ("alternative/art",               "A2",   "Art Auction Tracker",
     "6-Alternative", "data_cache/art_latest.json", "Sotheby's/Christie's public"),
    ("alternative/collectibles",      "A3",   "Collectibles Cards Scraper",
     "6-Alternative", "data_cache/collectibles_latest.json", "eBay Browse API"),
    ("alternative/p2p_lending",       "A4",   "P2P Lending Bot",
     "6-Alternative", "data_cache/p2p_latest.json", "LendingClub public stats"),
    ("alternative/metals",            "A5",   "Physical Metals Bot",
     "6-Alternative", "data_cache/metals_latest.json", "APMEX/JM Bullion public"),

    # ── Division 7 — Macro Risk ───────────────────────────────────
    ("macro/fed_watch",               "M1",   "Fed Rate Probability",
     "7-Macro", "data_cache/fed_watch_latest.json", "CME FedWatch public"),
    ("macro/supply_chain",            "M2",   "Supply Chain Indexer",
     "7-Macro", "data_cache/supply_chain_latest.json", "Freightos public"),
    ("macro/energy",                  "M3",   "Energy Grid Monitor",
     "7-Macro", "data_cache/energy_latest.json", "EIA public API"),
    ("macro/climate_risk",            "M4",   "Climate Risk FEMA Bot",
     "7-Macro", "data_cache/climate_risk_latest.json", "FEMA API + NOAA"),
    ("macro/tariffs",                 "M5",   "Geopolitical Tariff Tracker",
     "7-Macro", "data_cache/tariffs_latest.json", "USTR public database"),
    ("macro/jobs",                    "M6",   "Job Market BLS Bot",
     "7-Macro", "data_cache/jobs_latest.json", "data.bls.gov API"),
    ("macro/inflation",               "M7",   "Inflation CPI Bot",
     "7-Macro", "data_cache/cpi_latest.json", "data.bls.gov timeseries"),
    ("macro/congress_trades",         "M8",   "Congressional Trade Watcher",
     "7-Macro", "data_cache/congress_trades_latest.json", "HouseStockWatcher API"),

    # ── Division 8 — Growth & Marketing ──────────────────────────
    ("growth/lead_gen",               "G1",   "Lead Generation Scraper",
     "8-Growth", "data_cache/leads_latest.json", "Google Maps public"),
    ("growth/crm_sync",               "G2",   "CRM Sync Agent",
     "8-Growth", "Supabase direct", "n8n/ManyChat webhooks"),
    ("growth/ad_spy",                 "G3",   "Competitor Ad Spy",
     "8-Growth", "data_cache/competitor_ads_latest.json", "Meta Ad Library API"),
    ("growth/seo",                    "G4",   "SEO Keyword Tracker",
     "8-Growth", "data_cache/seo_keywords_latest.json", "pytrends"),
    ("growth/sentiment",              "G5",   "Social Sentiment Analyzer",
     "8-Growth", "data_cache/sentiment_latest.json", "Reddit PRAW + Twitter"),
    ("growth/content",                "G6",   "Content Repurposer Bot",
     "8-Growth", "atlas_vault/03-Outputs/Content/", "youtube-transcript-api"),
    ("growth/email_health",           "G7",   "Email Deliverability Monitor",
     "8-Growth", "data_cache/email_health_latest.json", "MXToolbox public API"),
    ("growth/engagement",             "G8",   "Engagement Rater",
     "8-Growth", "data_cache/engagement_latest.json", "Instagram Graph API"),
    ("growth/reviews",                "G9",   "Review Aggregator",
     "8-Growth", "data_cache/reviews_latest.json", "Google My Business public"),
    ("growth/roas",                   "G10",  "ROAS Optimizer",
     "8-Growth", "data_cache/roas_latest.json", "Meta Ads API + Google Ads API"),

    # ── Division 9 — Voice & Interaction ──────────────────────────
    ("voice/input",                   "V1",   "Voice Input Whisper",
     "9-Voice", "POST /voice/query endpoint", "OpenAI Whisper API"),
    ("voice/output",                  "V2",   "Voice Output TTS",
     "9-Voice", "Audio stream in browser", "ElevenLabs or OpenAI TTS"),
    ("voice/memory",                  "V3",   "Conversational Memory Agent",
     "9-Voice", "Loop 5 preference profile", "atlas_memory.db"),
    ("voice/notifier",                "V4",   "Alert Voice Notifier",
     "9-Voice", "Twilio voice call", "Twilio API"),
    ("voice/meeting_prep",            "V5",   "Meeting Prep Agent",
     "9-Voice", "atlas_vault/03-Outputs/Reports/meeting_prep_*.html", "Internal"),
    ("voice/report_editor",           "V6",   "NL Report Editor",
     "9-Voice", "Updated HTML report", "POST /report/edit endpoint"),

    # ── Division 10 — Document Generation ─────────────────────────
    ("documents/infographic",         "DOC1", "Infographic Agent",
     "10-Documents", "atlas_vault/03-Outputs/Charts/*.png", "matplotlib"),
    ("documents/pdf",                 "DOC2", "PDF Report Agent",
     "10-Documents", "atlas_vault/03-Outputs/Reports/*.pdf", "WeasyPrint"),
    ("documents/powerpoint",          "DOC3", "PowerPoint Agent",
     "10-Documents", "atlas_vault/03-Outputs/Decks/*.pptx", "python-pptx"),
    ("documents/excel",               "DOC4", "Excel Model Agent",
     "10-Documents", "atlas_vault/03-Outputs/Models/*.xlsx", "openpyxl"),
    ("documents/email_digest",        "DOC5", "Email Digest Agent",
     "10-Documents", "Daily email to user", "SendGrid or SMTP"),
    ("documents/comparison",          "DOC6", "Comparison Report Agent",
     "10-Documents", "Multi-ticker HTML report", "POST /compare endpoint"),
    ("documents/portfolio_report",    "DOC7", "Portfolio Report Agent",
     "10-Documents", "atlas_vault/03-Outputs/Reports/portfolio_*.pdf", "WeasyPrint"),
    ("documents/watchlist_alert",     "DOC8", "Watchlist Alert Report",
     "10-Documents", "HTML card + Supabase log", "alerts.py hook"),

    # ── Division 11 — Intelligence Synthesis ──────────────────────
    ("intelligence/correlation",      "IQ1",  "Cross Asset Correlation",
     "11-Intelligence", "data_cache/correlation_latest.json", "All data_cache files"),
    ("intelligence/regime_detector",  "IQ2",  "Regime Change Detector",
     "11-Intelligence", "Supabase alert + push", "GET /regime + bond yields"),
    ("intelligence/earnings_coord",   "IQ3",  "Earnings Season Coordinator",
     "11-Intelligence", "data_cache/earnings_season_brief_latest.json", "earnings + options"),
    ("intelligence/sector_rotation",  "IQ4",  "Sector Rotation Agent",
     "11-Intelligence", "data_cache/sector_rotation_latest.json", "equities + dark pool"),
    ("intelligence/news_catalyst",    "IQ5",  "News Catalyst Agent",
     "11-Intelligence", "data_cache/news_catalysts_latest.json", "Reuters/Bloomberg RSS"),
    ("intelligence/sentiment_div",    "IQ6",  "Sentiment Divergence Agent",
     "11-Intelligence", "data_cache/sentiment_divergence_latest.json", "sentiment + dark pool"),
    ("intelligence/backtesting",      "IQ7",  "Backtesting Agent",
     "11-Intelligence", "atlas_vault/03-Outputs/Backtests/*.json", "yfinance historical"),
    ("intelligence/risk_budget",      "IQ8",  "Risk Budget Agent",
     "11-Intelligence", "data_cache/risk_budget_latest.json", "Loop 5 positions"),

    # ── Division 12 — Platform & Integration ──────────────────────
    ("platform/broker",               "P1",   "Broker Integration Agent",
     "12-Platform", "positions_cache.json (live)", "Robinhood/IBKR read-only API"),
    ("platform/discord",              "P2",   "Discord Bot Agent",
     "12-Platform", "Discord channel posts", "discord.py"),
    ("platform/telegram",             "P3",   "Telegram Alert Agent",
     "12-Platform", "Telegram messages", "python-telegram-bot"),
    ("platform/webhooks",             "P4",   "Webhook Publisher Agent",
     "12-Platform", "User-defined webhook URL", "httpx async"),
    ("platform/white_label",          "P5",   "White Label Agent",
     "12-Platform", "Rebranded HTML/PDF", "B2B RIA feature"),
    ("platform/api_gateway",          "P6",   "API Gateway Agent",
     "12-Platform", "POST /api/v1/query", "Billable $0.10/call"),
    ("platform/compliance",           "P7",   "Compliance Archive Agent",
     "12-Platform", "Supabase compliance_archive table", "Read-only after write"),
    ("platform/self_improvement",     "P8",   "Self Improvement Agent",
     "12-Platform", "atlas_vault/04-Projects/ATLAS/Notes/improvement_*.md", "eval reports"),

    # ── Division 13 — Cognitive Scaffolding ───────────────────────
    ("cognitive/codebase_mapper",     "C1",   "Codebase Mapper",
     "13-Cognitive", "atlas_agents/cognitive/codebase_mapper/repo_map.json", "ast stdlib"),
    ("cognitive/arch_planner",        "C2",   "Architecture Planner",
     "13-Cognitive", "atlas_vault/04-Projects/ATLAS/Notes/plan_*.md", "repo_map.json"),
    ("cognitive/sandbox",             "C3",   "Execution Sandbox",
     "13-Cognitive", "APPROVED or REJECTED with traceback", "Docker + pytest"),
    ("cognitive/reflection",          "C4",   "Reflection Correction Engine",
     "13-Cognitive", "atlas_vault/04-Projects/ATLAS/Notes/corrections_*.md", "traceback analysis"),
    ("cognitive/linter",              "C5",   "Static Linter Security Scanner",
     "13-Cognitive", "CLEAN or violations list", "pyflakes + bandit"),
    ("cognitive/diff_synthesizer",    "C6",   "Diff Synthesizer",
     "13-Cognitive", "Unified diff output", "difflib stdlib"),
    ("cognitive/tot_arbiter",         "C7",   "Tree of Thoughts Arbiter",
     "13-Cognitive", "bull/bear/arbiter conclusion JSON", "Multi-model debate"),
    ("cognitive/eval_supervisor",     "C8",   "Evals Benchmarking Supervisor",
     "13-Cognitive", "atlas_vault/04-Projects/ATLAS/Notes/nightly_eval_*.md", "Nightly 2am"),

    # ── Division 14 — Compute Routing ─────────────────────────────
    ("compute/context_cacher",        "CR1",  "Context Cacher",
     "14-Compute", "90% API cost reduction", "Anthropic prompt caching"),
    ("compute/router",                "CR2",  "Compute Router",
     "14-Compute", "Model routing logic", "Haiku/Sonnet/Opus selection"),
    ("compute/local_scaffold",        "CR3",  "Local Scaffolding Ollama",
     "14-Compute", "Empty files and folders", "Ollama local LLM"),
    ("compute/local_file_creator",    "CR4",  "Local File Creator",
     "14-Compute", "Written files on disk", "Pure Python file I/O"),
    ("compute/local_syntax",          "CR5",  "Local Syntax Checker",
     "14-Compute", "CLEAN or error list", "py_compile + pyflakes"),
    ("compute/local_docs",            "CR6",  "Local Documentation Writer",
     "14-Compute", "Docstrings and README files", "Ollama small model"),
    ("compute/local_test_runner",     "CR7",  "Local Test Runner",
     "14-Compute", "test_results_*.json", "pytest local execution"),
]


def make_slug(name):
    return name.lower().replace(" ", "-").replace("/", "-")


def write_file(path: Path, content: str, skip_if_exists=True):
    if skip_if_exists and path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def create_agent(subdir, agent_id, name, division, output, source):
    if agent_id in ALREADY_BUILT:
        print(f"  ⏭  {agent_id} {name} — already built, skipping")
        return 0

    agent_dir = AGENTS_DIR / subdir
    slug = make_slug(name)
    created = 0

    # 1. __init__.py
    init = agent_dir / "__init__.py"
    if write_file(init, f"# {name} — ATLAS Swarm\n# Division: {division} | ID: {agent_id}\n"):
        created += 1

    # 2. AGENT_PROMPT.md
    prompt_path = agent_dir / "AGENT_PROMPT.md"
    prompt = f"""# {name}
# ID: {agent_id} | Division: {division}
# Status: STUB — implement logic with AI assistance

## IDENTITY
You are the {name} for the ATLAS financial intelligence platform.

## OUTPUT
File: {output}
Source: {source}

## YOUR JOB
[TODO: Implement specific task logic]
Read CLAUDE.md and ATLAS_115_AGENT_SWARM.md for full specification.

## RULES
- NEVER modify: query_router.py, atlas_omega.py, deep_research.py, gemini_limiter.py
- NEVER delete: atlas_memory.db, atlas_tracker.db
- Always import from atlas_core.utils.agent_utils where applicable
- Always run py_compile before reporting done
- Always run pytest after creating test files

## SELF-VALIDATION
python -m py_compile atlas_agents/{subdir}/__init__.py
python -m pytest tests/test_{slug.replace("-", "_")}.py -v
"""
    if write_file(prompt_path, prompt):
        created += 1

    # 3. SKILL.md in vault
    skill_path = VAULT_SKILLS / slug / "SKILL.md"
    skill = f"""# Skill: {name}
# ID: {agent_id} | Division: {division}
# DBS Framework

## [D] Direction
{name} — part of the ATLAS {division} division.
Output: {output}
Source: {source}
Read ATLAS_115_AGENT_SWARM.md for full specification and JSON schema.

## [B] Blueprints
Reference implementation: atlas_agents/crypto/crypto_scraper.py
Shared utilities: atlas_core/utils/agent_utils.py
  - requests_get_json(url, params) — handles 429, timeout, retry
  - write_cache_json_pair(data, stable_name, prefix) — handles timestamps
  - sleep_backoff(attempt) — exponential backoff

## [S] Solutions
Validate after implementation:
  python -m py_compile atlas_agents/{subdir}/__init__.py
  python atlas_agents/{subdir}/<scraper>.py --dry-run
  python -m pytest tests/test_{slug.replace("-", "_")}.py -v
  python -m atlas_core.validation.data_validator
"""
    if write_file(skill_path, skill):
        created += 1

    # 4. Test stub
    safe_slug = slug.replace("-", "_")
    test_path = TESTS_DIR / f"test_{safe_slug}.py"
    test = f"""# tests/test_{safe_slug}.py
# {name} — existence and structure tests
# Run: python -m pytest tests/test_{safe_slug}.py -v

import os
import pytest

AGENT_DIR = os.path.join(
    os.path.dirname(__file__), "..", "atlas_agents", "{subdir}"
)
SKILL_FILE = os.path.join(
    os.path.dirname(__file__), "..",
    "atlas_vault", "02-Wiki", "Skills", "{slug}", "SKILL.md"
)


def test_agent_directory_exists():
    \"\"\"Agent directory must exist.\"\"\"
    assert os.path.isdir(AGENT_DIR), f"Missing: {{AGENT_DIR}}"


def test_agent_prompt_exists():
    \"\"\"AGENT_PROMPT.md must exist.\"\"\"
    path = os.path.join(AGENT_DIR, "AGENT_PROMPT.md")
    assert os.path.exists(path), f"Missing AGENT_PROMPT.md in {{AGENT_DIR}}"


def test_skill_file_exists():
    \"\"\"SKILL.md must exist in vault.\"\"\"
    assert os.path.exists(SKILL_FILE), f"Missing: {{SKILL_FILE}}"


def test_init_file_exists():
    \"\"\"__init__.py must exist.\"\"\"
    path = os.path.join(AGENT_DIR, "__init__.py")
    assert os.path.exists(path), f"Missing __init__.py in {{AGENT_DIR}}"
"""
    if write_file(test_path, test):
        created += 1

    status = "✅ CREATED" if created > 0 else "⏭  EXISTS"
    print(f"  {status} {agent_id:5} {name} ({created} files)")
    return created


def create_registry(agents):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        "# ATLAS Agent Registry",
        f"# Last Updated: {now}",
        f"# Total Agents: {len(agents)} | "
        f"Built: {len(ALREADY_BUILT)} | "
        f"Pending: {len(agents) - len(ALREADY_BUILT)}",
        "",
    ]

    current_div = None
    for subdir, agent_id, name, division, output, source in agents:
        if division != current_div:
            current_div = division
            lines.append(f"\n## Division {division}")
            lines.append("| ID | Name | Directory | Output | Status |")
            lines.append("|----|------|-----------|--------|--------|")

        status = "BUILT+VERIFIED" if agent_id in ALREADY_BUILT else "PENDING"
        slug = make_slug(name)
        lines.append(
            f"| {agent_id} | {name} | atlas_agents/{subdir}/ "
            f"| {output} | {status} |"
        )

    registry_path = AGENTS_DIR / "AGENT_REGISTRY.md"
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n✅ AGENT_REGISTRY.md written ({len(agents)} agents)")


def main():
    print("=" * 60)
    print("ATLAS SWARM BOOTSTRAP")
    print(f"Root: {ROOT}")
    print(f"Total agents: {len(AGENTS)}")
    print(f"Already built (skipping): {ALREADY_BUILT}")
    print("=" * 60)

    # Ensure base dirs exist
    AGENTS_DIR.mkdir(exist_ok=True)
    VAULT_SKILLS.mkdir(parents=True, exist_ok=True)
    TESTS_DIR.mkdir(exist_ok=True)

    total_created = 0
    current_div = None

    for subdir, agent_id, name, division, output, source in AGENTS:
        if division != current_div:
            current_div = division
            print(f"\n── Division {division} ──")

        total_created += create_agent(subdir, agent_id, name, division, output, source)

    create_registry(AGENTS)

    print("\n" + "=" * 60)
    print(f"BOOTSTRAP COMPLETE")
    print(f"Files created: {total_created}")
    print(f"Next step: python -m pytest tests/ -q --tb=short")
    print("=" * 60)


if __name__ == "__main__":
    main()

