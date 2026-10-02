$ErrorActionPreference = 'Stop'
try { $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8090/api/health' -TimeoutSec 2 } catch { Write-Host 'Local Explainer is not running.'; exit 0 }
if ($health.application -ne 'local-explainer') { throw 'Another application occupies port 8090.' }
Invoke-RestMethod -Uri 'http://127.0.0.1:8090/api/shutdown' -Method Post -ContentType 'application/json' -Body '{}' | Out-Null
Write-Host 'Stopping Local Explainer. Completed work is saved; active generation will be resumable.'
