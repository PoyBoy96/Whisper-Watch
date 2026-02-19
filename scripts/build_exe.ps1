$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $root

if (-not (Test-Path ".venv-build")) {
    python -m venv .venv-build
}

. ".\.venv-build\Scripts\Activate.ps1"

python -m pip install --upgrade pip
pip install -r requirements-build.txt

$svgIconPath = Join-Path $root "assets\whisperwatch-icon.svg"
$icoIconPath = Join-Path $root "assets\whisperwatch-icon.ico"
if (Test-Path $svgIconPath) {
    python .\scripts\generate_icon.py --svg $svgIconPath --ico $icoIconPath --size 256
}

if (Test-Path "build") {
    Remove-Item -Recurse -Force "build"
}

if (Test-Path "dist") {
    Remove-Item -Recurse -Force "dist"
}

$pyInstallerArgs = @(
    "--noconfirm",
    "--clean",
    "--windowed",
    "--name", "WhisperWatch",
    "--add-data", "app/ui/styles.qss;ui",
    "--add-data", "assets/whisperwatch-icon.svg;assets",
    "--collect-all", "faster_whisper",
    "--collect-all", "ctranslate2",
    "--collect-all", "av"
)

$iconPath = Join-Path $root "assets\whisperwatch-icon.ico"
if (Test-Path $iconPath) {
    $pyInstallerArgs += @("--icon", $iconPath)
}

$pyInstallerArgs += "app/main.py"

pyinstaller @pyInstallerArgs

Write-Host ""
Write-Host "Executable build complete."
Write-Host "Folder: dist\WhisperWatch"
