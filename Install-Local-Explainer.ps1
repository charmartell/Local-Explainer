[CmdletBinding()]
param([switch]$SkipModels, [switch]$SkipSkill)
$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
$repoPath = $PSScriptRoot
. (Join-Path $repoPath 'scripts\paths.ps1')
New-Item -ItemType Directory -Force -Path $assetPath, $scratchPath | Out-Null
$env:UV_CACHE_DIR = Join-Path $scratchPath 'uv-cache'
$env:TEMP = Join-Path $scratchPath 'setup-temp'
$env:TMP = $env:TEMP
New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null
foreach ($tool in @('uv','git')) { if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) { throw "Install $tool first, then run this setup again." } }
function Invoke-Checked([string]$Program, [string[]]$Arguments) {
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Setup command failed: $Program $($Arguments -join ' ')" }
}
$appEnv = Join-Path $assetPath 'Runtime\app'
$inferenceEnv = Join-Path $assetPath 'Runtime\inference'
if (-not (Test-Path -LiteralPath (Join-Path $appEnv 'Scripts\python.exe'))) { Invoke-Checked 'uv' @('venv','--python','3.12.10',$appEnv) }
if (-not (Test-Path -LiteralPath (Join-Path $inferenceEnv 'Scripts\python.exe'))) { Invoke-Checked 'uv' @('venv','--python','3.12.10',$inferenceEnv) }
$appPython = Join-Path $appEnv 'Scripts\python.exe'
$inferencePython = Join-Path $inferenceEnv 'Scripts\python.exe'
Invoke-Checked 'uv' @('pip','install','--python',$appPython,'-r',(Join-Path $repoPath 'requirements-app.lock'))
Invoke-Checked 'uv' @('pip','install','--python',$appPython,'--no-deps','--editable',$repoPath)
Invoke-Checked 'uv' @('pip','install','--python',$inferencePython,'-r',(Join-Path $repoPath 'requirements-inference.lock'),'--extra-index-url','https://download.pytorch.org/whl/cu130','--index-strategy','unsafe-best-match')
$comfyPath = $comfyRepoPath
if (-not (Test-Path -LiteralPath (Join-Path $comfyPath '.git'))) {
    if (Test-Path -LiteralPath $comfyPath) { throw "An existing non-Git folder occupies $comfyPath. Choose another path before installing." }
    Invoke-Checked 'git' @('clone','https://github.com/Comfy-Org/ComfyUI.git',$comfyPath)
    Invoke-Checked 'git' @('-C',$comfyPath,'checkout','170594057a22673349ddf0a3d88624b7fa5865bb')
}
$comfyCommit = & git -C $comfyPath rev-parse HEAD
if ($comfyCommit -ne '170594057a22673349ddf0a3d88624b7fa5865bb') { throw 'ComfyUI checkout differs from the tested version. Preserve local work before selecting the pinned commit.' }
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path $assetPath 'Runtime\browsers'
Invoke-Checked $appPython @('-m','playwright','install','chromium')
if (-not $SkipModels) { Invoke-Checked $appPython @((Join-Path $repoPath 'scripts\setup_assets.py')) }
if (-not $SkipModels) { Invoke-Checked $appPython @('-m','explainer.voices') }
if (-not $SkipSkill) {
    $skillRoot = if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME 'skills' } else { Join-Path $env:USERPROFILE '.codex\skills' }
    $destination = Join-Path $skillRoot 'local-explainer'
    if (-not (Test-Path -LiteralPath $destination)) { Copy-Item -LiteralPath (Join-Path $repoPath 'skill\local-explainer') -Destination $destination -Recurse }
}
Invoke-Checked $appPython @('-m','explainer.cli','doctor')
Write-Host 'Local Explainer is ready. Run Start-Local-Explainer.ps1.'
