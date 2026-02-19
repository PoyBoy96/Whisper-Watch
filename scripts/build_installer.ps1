$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $root

& (Join-Path $PSScriptRoot "build_exe.ps1")

$isccCandidates = @(
    (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
    (Join-Path ${env:ProgramFiles} "Inno Setup 6\ISCC.exe")
)

$isccCmd = Get-Command ISCC.exe -ErrorAction SilentlyContinue
if ($isccCmd) {
    $isccCandidates += $isccCmd.Source
}

$isccPath = $isccCandidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
if (-not $isccPath) {
    throw "Inno Setup 6 was not found. Install it from https://jrsoftware.org/isinfo.php and rerun."
}

& $isccPath (Join-Path $root "installer\WhisperWatch.iss")

Write-Host ""
Write-Host "Installer build complete."
Write-Host "Folder: dist-installer"
