# report_qa_agent — Safety Rules

1. Use local deterministic verifiers only — do not call external AI APIs for QA checks.
2. Do not modify query results or synthesis outputs.
3. Do not write to any source files or database tables.
4. Do not store user query results in permanent logs (use session-scoped temp files only).
5. QA reports go to atlas_vault/03-Outputs/ or stdout only.
6. Do not send QA results externally (no email, no Slack yet).
7. If verifiers are unavailable, degrade gracefully and note in output.
