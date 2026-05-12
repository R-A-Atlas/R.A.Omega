param(
    [switch]$Full
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $root

Write-Host "R.A. Omega health check" -ForegroundColor Cyan
Write-Host "Workspace: $root"

python -m py_compile api_server.py atlas_db.py orchestration\agent_graph.py orchestration\agent_packets.py

python -m pytest `
    tests/test_api_endpoints.py::test_health_returns_ok `
    tests/test_api_endpoints.py::test_main_chat_routes_return_html `
    tests/test_api_endpoints.py::test_finance_dashboard_routes_return_html `
    tests/test_api_endpoints.py::test_pricing_route_returns_checkout_page `
    tests/test_ui_porter.py `
    tests/test_cursor_launch_kit.py `
    -q

if ($Full) {
    python -m pytest tests/ -q
}

Write-Host "R.A. Omega health check complete." -ForegroundColor Green
