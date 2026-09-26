$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$TaskManager = Join-Path $RepoRoot "profile\airootfs\opt\taskmanager\main.py"

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw "Python launcher 'py' was not found. Install Python 3 for Windows first."
}

if (-not (Test-Path $TaskManager)) {
    throw "Task Manager source was not found: $TaskManager"
}

Write-Host "Starting MuliOS Task Manager with Windows Python..."
& py -3 $TaskManager

if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
