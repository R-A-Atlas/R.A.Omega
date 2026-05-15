# Preferences

## Engineering Preferences
- Python over any other language for backend
- FastAPI (not Flask or Django) for API layer
- Supabase for auth + database (not Firebase or custom auth)
- Minimal dependencies — prefer stdlib or well-maintained packages
- BASE_DIR (not SCRIPT_DIR) for all file paths in api_server.py
- ATLAS_DISABLE_AUTH=true for local dev only

## AI / Prompt Preferences
- Claude Code for engineering tasks
- Gemini Flash for fast/simple queries, Gemini Pro for deep research and trade plans
- Progressive context loading — never dump all context into every prompt
- Routing stays raw-query-only — classify_intent_route() never receives memory or controls
- Quality firewall before any answer reaches the frontend

## Output Preferences
- Finance answers: conversational but precise
- Company reports: structured sections (Overview, Business Model, Financial Snapshot, Leadership, News, Risks, Competitive Position)
- Trade plans: Entry, Risk, Invalidation, Scenarios — only when explicitly requested
- HTML reports: dark theme, Inter font, ATLAS branding, editable annotations, Export PDF via print
- Documents: clean, professional, export-ready

## Communication Preferences
- No padding or unnecessary caveats
- Show plan before executing on complex tasks
- No trailing summaries of what was just done — the diff speaks for itself
- Call out blockers immediately

## Testing Preferences
- All new code must pass py_compile before reporting done
- Full pytest suite must not regress
- No test mocks for the database (real integration tests where practical)
- test_user_local mock for local dev, real UUID for production
