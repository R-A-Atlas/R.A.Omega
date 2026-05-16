# daily_build_brief — Safety Rules

1. Read-only operations only. Do not write to any source files.
2. Do not commit, push, or modify git state.
3. Do not call external APIs or require credentials.
4. Do not store secrets in output or logs.
5. Do not send emails or messages.
6. Do not deploy or restart servers.
7. If git or pytest is unavailable, degrade gracefully and note in output.
8. Output goes to stdout or a local markdown file — never to a database directly.
