$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
$repoPath = $PSScriptRoot
. (Join-Path $repoPath 'scripts\paths.ps1')
$appPython = Join-Path $assetPath 'Runtime\app\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $appPython)) { throw 'Run Install-Local-Explainer.ps1 first.' }
Set-Location -LiteralPath $PSScriptRoot
New-Item -ItemType Directory -Force -Path $scratchPath | Out-Null
try { $running = Invoke-RestMethod -Uri 'http://127.0.0.1:8090/api/health' -TimeoutSec 2 } catch { $running = $null }
if ($running -and $running.application -ne 'local-explainer') { throw 'Another application occupies port 8090.' }
if (-not $running) {
    Start-Process -FilePath $appPython -ArgumentList @('-m', 'explainer.cli', 'serve') -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $scratchPath 'server.log') -RedirectStandardError (Join-Path $scratchPath 'server-error.log')
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        try { $running = Invoke-RestMethod -Uri 'http://127.0.0.1:8090/api/health' -TimeoutSec 1; break } catch { Start-Sleep -Milliseconds 500 }
    }
    if (-not $running) { throw "The application could not start. Check $scratchPath\server-error.log." }
}
Start-Process 'http://127.0.0.1:8090'
