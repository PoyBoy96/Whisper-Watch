param(
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $root

if (-not (Test-Path ".venv")) {
    python -m venv .venv
}

. ".\.venv\Scripts\Activate.ps1"

if (-not $SkipInstall) {
    python -m pip install --upgrade pip
    pip install -r requirements.txt
}

python -m app.main

