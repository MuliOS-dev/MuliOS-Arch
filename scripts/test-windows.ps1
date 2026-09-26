param(
    [ValidateSet("installer", "taskmanager", "both")]
    [string]$App = "both"
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Venv = Join-Path $RepoRoot ".venv-mulios-test"
$Python = Join-Path $Venv "Scripts\python.exe"

if (-not (Test-Path $Python)) {
    py -3 -m venv $Venv
}

& $Python -m pip install --upgrade pip
& $Python -m pip install PySide6 psutil

if ($App -eq "installer" -or $App -eq "both") {
    Write-Host "Starting MuliOS Installer UI test..."
    & $Python (Join-Path $RepoRoot "profile\airootfs\opt\mulios-installer\main.py") --test
}

if ($App -eq "taskmanager" -or $App -eq "both") {
    Write-Host "Starting MuliOS Task Manager..."
    & $Python (Join-Path $RepoRoot "profile\airootfs\opt\taskmanager\main.py")
}
