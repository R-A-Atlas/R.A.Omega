# R.A. Omega Roadmap

This roadmap keeps the next build steps concrete. Each item should end with code, tests, and a pushed branch or pull request.

## Phase 1: Product Foundation

- Stable local startup: `start_ra_omega.ps1` starts the FastAPI app and points users to `/app`.
- Stable app routes: `/app`, `/chat`, and `/ra-omega` serve the primary chat UI; `/option1` remains as a legacy alias.
- Setup docs: `README.md` and `.env.example` describe local install, required keys, and test commands.
- Safe source export: `create_safe_zip.ps1` excludes `.env`, Git internals, caches, reports, databases, and generated files.
- Sprint 10 scraper resilience: equities, options flow, and insider-trade scrapers return non-empty, clearly marked fallback payloads when public sources are blocked or empty.

## Phase 2: UI Consolidation

- Rename or replace `index_1778227564596.html` with a stable product filename, such as `ra_omega_app.html`.
- Keep legacy routes during transition so old bookmarks and tests do not break.
- Move obsolete dashboard prototypes into an archive folder or document which ones are still supported.
- Add browser-level regression checks for desktop and mobile layout.

## Phase 3: ChatGPT-Style Finance UX

- Keep the main composer at the bottom of the chat surface.
- Keep voice input next to the send button, with clear recording, cancel, and error states.
- Make the center chat the default focus; use right-side panels only for context, sources, portfolio, watchlist, or active analysis.
- Add graceful UI messages for missing provider keys, auth state, and API rate limits.

## Phase 4: Finance Intelligence Core

- Centralize provider/model configuration so Gemini, OpenAI, ElevenLabs, Supabase, Tradier, and Alpaca settings are not scattered across scripts.
- Add a single health/config endpoint that reports enabled capabilities without exposing secrets.
- Normalize local cache behavior and document which data is generated versus tracked.
- Add dedicated tests for high-risk finance responses: investment disclaimers, debt/tax/legal boundaries, and data-source freshness.

## Phase 5: Hosted App Readiness

- Lock down `ATLAS_DISABLE_AUTH=true` as local-only behavior.
- Complete Supabase auth/session flows for hosted use.
- Add deployment docs once the target is selected.
- Add CI to run the focused tests first, then the full suite.

## Immediate Next Branch

Recommended next branch after `codex/product-setup-docs`:

```text
codex/ui-consolidation
```

Target outcome:

- Stable UI filename.
- Stable `/app` route.
- Old `/option1` alias preserved.
- Browser screenshots verified.
- Endpoint and UI tests passing.
