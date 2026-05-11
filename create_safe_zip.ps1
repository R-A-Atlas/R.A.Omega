param(
    [string]$OutputPath = "R.A.Omega-source-safe.zip"
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$resolvedOutput = if ([System.IO.Path]::IsPathRooted($OutputPath)) {
    $OutputPath
} else {
    Join-Path $root $OutputPath
}

$excludeDirs = @(
    ".git",
    ".venv",
    "node_modules",
    "dist",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "data_cache",
    "congress_cache",
    "delta_snapshots",
    "deep_reports",
    "reports",
    "codex_backups",
    "atlas_memory_data",
    "atlas_rag",
    "atlas_vault/00-Inbox",
    "atlas_vault/01-Raw",
    "atlas_vault/03-Outputs",
    "atlas_vault/04-Projects"
)

$excludeFiles = @(
    ".env",
    ".env.*",
    "*.zip",
    "*.pdf",
    "*.docx",
    "*.db",
    "*.sqlite",
    "*.sqlite3",
    "*.log",
    "paper_trades.json",
    "positions_cache.json",
    "watchlist.json",
    "research_history.json",
    "weekly_insight.json",
    "atlas_alerts.json",
    "atlas_tracking_state.json",
    "atlas_pending_deep.json",
    "dashboard_state.json",
    "full_codebase.txt",
    "test_result_soun.json"
)

function Test-IsExcluded {
    param([string]$Path)

    $rootUri = New-Object System.Uri(($root.TrimEnd("\") + "\"))
    $pathUri = New-Object System.Uri($Path)
    $rel = [System.Uri]::UnescapeDataString($rootUri.MakeRelativeUri($pathUri).ToString())
    foreach ($dir in $excludeDirs) {
        if ($rel -eq $dir -or $rel.StartsWith("$dir/")) {
            return $true
        }
    }
    foreach ($pattern in $excludeFiles) {
        if ($rel -like $pattern -or (Split-Path $rel -Leaf) -like $pattern) {
            return $true
        }
    }
    return $false
}

if (Test-Path $resolvedOutput) {
    Remove-Item -LiteralPath $resolvedOutput -Force
}

$files = Get-ChildItem -LiteralPath $root -Recurse -File -Force |
    Where-Object { -not (Test-IsExcluded $_.FullName) }

if (-not $files) {
    throw "No files selected for ZIP."
}

$tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("ra-omega-safe-zip-" + [guid]::NewGuid())
New-Item -ItemType Directory -Path $tmp | Out-Null

try {
    foreach ($file in $files) {
        $rootUri = New-Object System.Uri(($root.TrimEnd("\") + "\"))
        $fileUri = New-Object System.Uri($file.FullName)
        $rel = [System.Uri]::UnescapeDataString($rootUri.MakeRelativeUri($fileUri).ToString()).Replace("/", "\")
        $dest = Join-Path $tmp $rel
        New-Item -ItemType Directory -Path (Split-Path $dest -Parent) -Force | Out-Null
        Copy-Item -LiteralPath $file.FullName -Destination $dest
    }
    Compress-Archive -Path (Join-Path $tmp "*") -DestinationPath $resolvedOutput -Force
    Write-Host "Created safe ZIP: $resolvedOutput" -ForegroundColor Cyan
    Write-Host "Excluded .env, .git, caches, databases, reports, exports, and existing ZIP files." -ForegroundColor Green
} finally {
    Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue
}
