# Skill: Option 1 sessions sidebar integration

**ID:** SK-14  
**Created:** 2026-05-09  
**Proven:** 2+ (dashboard v4 pattern ported; Option 1 ships with `/sessions`, `session_id` on `/query`, localStorage)

---

## [D] Direction

**What this skill does:** Documents the **end-to-end** chat thread UX on **`/option1`** (`index_1778227564596.html`): list/create/rename/archive/delete sessions, persist active session, attach `session_id` to queries, and scope history.

**When to use it:** Porting the sidebar to another surface, debugging 503 vs auth, or verifying `session_id` flows to the backend.

**Step-by-step workflow**

1. **Read API** — `GET /sessions?include_archived=...` populates the sidebar; handle 503 with user-facing copy pointing to B6 `schema.sql` migration (`supabase-b6-tenant-migration`).
2. **Create** — `POST /sessions` with JSON body (title optional); store returned `id` as active session.
3. **Mutate** — `PATCH /sessions/{id}` for rename, archive, `context_topic`; `DELETE /sessions/{id}` removes thread.
4. **Client state** — Persist active id in `localStorage` key **`atlas_active_session_id`**; clear when deleting active session.
5. **Queries** — Include **`session_id`** in JSON body for `POST /query` (and form `FormData` for voice/file paths if present).
6. **History** — `GET /history/reports?session_id=` loads session-scoped research runs when implementing history UI.
7. **Auth** — Send the same Bearer token Supabase JWT as the rest of the app; `test_user_local` + `ATLAS_DISABLE_AUTH` paths are dev-only per `CLAUDE.md`.

**Rules and guardrails**

- Do not strip `session_id` from the payload on auto-created sessions; backend expects consistency with DB FK after migration.
- Sidebar must tolerate empty list (first visit) and offer “new chat” flow.
- Reference `atlas_dashboard_v4.html` only for **parity**; Option 1 is the canonical integration for the main app shell.

---

## [B] Blueprints

**Read before using**

- Frontend: `index_1778227564596.html` — search `atlas_active_session_id`, `fetch(apiBase() + '/sessions'`, `session_id`
- Backend: `api_server.py` — `@app.post/get/patch/delete("/sessions")` and docstring block near file header
- Data: `atlas_db.py` — `list_chat_sessions`, create/update/delete session helpers + Supabase vs mock
- Migration: `supabase-b6-tenant-migration` for `chat_sessions` table
- Notes: `atlas_vault/04-Projects/ATLAS/Notes/2026-05-08-Intent-Routing-Session-UX.md`

**Good outcome**

- User picks a thread, sends a message, `POST /query` includes `session_id`, response persists to session in Supabase (when configured).

**Bad outcome to avoid**

- Using only `localStorage` without API sync (threads lost across devices).
- Omitting auth headers then blaming “empty sessions” when RLS returns nothing.

---

## [S] Solutions

**Discover hooks**

```powershell
cd "C:\Users\crist\OneDrive\Desktop\trading platform overview"
findstr /C:"/sessions" index_1778227564596.html
findstr /C:"atlas_active_session_id" index_1778227564596.html
findstr /C:"session_id" index_1778227564596.html
findstr /C:"/sessions" api_server.py
```

**Smoke compile**

```powershell
python -m py_compile api_server.py
```

**Validation**

- Run evals in `evals.json`.
