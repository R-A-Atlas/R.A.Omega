# SKILL: route_map

**Type:** D (Direction) + S (Solution)  
**Priority:** 3 — run whenever new routes or HTML files are added  
**Status:** Active

---

## Purpose

Keep the R.A. Omega route table in sync. Detects orphaned HTML files,
missing file references, and cross-file dead links before they reach users.

---

## When to Use

- After adding any new HTML page or route to `api_server.py`
- After removing or renaming an HTML file
- When a user reports a 404 on a known page
- As part of session start pre-flight (optional, non-blocking)

---

## Commands

```bash
# Full audit (human-readable)
python omega_os/skills/route_map/tools/route_audit.py

# JSON output (for programmatic use)
python omega_os/skills/route_map/tools/route_audit.py --json
```

---

## What It Checks

| Check | Description |
|---|---|
| Page routes | Every GET route that serves HTML — path, file, existence |
| Orphaned HTML | `.html` files in project root with no declared route |
| Dead file refs | Routes that declare a `.html` file that doesn't exist on disk |
| Dead links | `href=` and `fetch(` calls in HTML files pointing to undeclared routes |

---

## Route Map (current)

| Route | Serves | Notes |
|---|---|---|
| `GET /` | `index_1778228972988.html` | Zenith 3D landing |
| `GET /auth` | `auth.html` | Sign in / create account |
| `GET /command-center` | `omega_command_center.html` | **Post-login home** |
| `GET /app` | `ra_omega_app.html` | Main chat UI |
| `GET /option1` | → `/app` | Legacy 301 redirect |
| `GET /login` | → `/auth` | Legacy 301 redirect |
| `GET /dashboard` | `atlas_dashboard_v4.html` | Old dashboard |
| `GET /v2` | `atlas_dashboard_v4.html` | Old dashboard (compat alias) |
| `GET /omega-os/brain-network` | `omega_brain_network.html` | Brain network viz |
| `GET /design_system.css` | `design_system.css` | Design tokens |
| `GET /data-map` | `data_map.html` (generated) | Data map |

---

## Auth Flow

```
User visits /auth → signs in → redirects to /command-center
                              (NOT /option1 or /app)

/command-center → "New Analysis" → /app (chat)
/app header    → "Home" link    → /command-center
```

---

## Intentionally Orphaned (per CLAUDE.md §5 — do not delete)

- `atlas_dashboard_v2.html`, `atlas_dashboard_v3.html`
- `ATLAS_OUTPUT_MAP.html`, `ATLAS_OVERVIEW.html`
- `CANVAS_1_Roadmap.html`, `CANVAS_3_ATLAS_vs_World.html`, `CANVAS_4_Intelligence_Layers.html`
- `dashboard.html`

These are in `route_audit.py`'s `IGNORE_ORPHANS` set.

---

## Guardrails

- Never remove a route without checking `auth.html` and `omega_command_center.html`
  for links pointing to it
- Never rename an HTML file without updating the `FileResponse(...)` call in `api_server.py`
- Auth post-login redirect MUST point to `/command-center` — not `/option1` or `/app`
- `/v2` must remain as alias for `/dashboard` (backwards compatibility)
- Run `python -m py_compile api_server.py` after any route change

---

## Evals

See `evals.json` for binary pass/fail assertions.
