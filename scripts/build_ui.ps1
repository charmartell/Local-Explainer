$ErrorActionPreference = 'Stop'
$scratchPath = if ($env:LOCAL_EXPLAINER_SCRATCH) { $env:LOCAL_EXPLAINER_SCRATCH } else { 'C:\Dev\_scratch\Local-Explainer' }
$outputPath = Join-Path $scratchPath 'frontend-build'
$repoPath = Split-Path -Parent $PSScriptRoot
New-Item -ItemType Directory -Force -Path $outputPath | Out-Null
& (Join-Path $repoPath 'node_modules\.bin\tsc.cmd') (Join-Path $repoPath 'explainer\static\app.ts') --target ES2022 --module ES2022 --lib ES2022,DOM --strict --skipLibCheck --outDir $outputPath
if ($LASTEXITCODE -ne 0) { throw 'TypeScript compilation failed' }
Copy-Item -LiteralPath (Join-Path $outputPath 'app.js') -Destination (Join-Path $repoPath 'explainer\static\app.js')
