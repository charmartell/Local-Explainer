$ErrorActionPreference = 'Stop'
$repoPath = Split-Path -Parent $PSScriptRoot
. (Join-Path $repoPath 'scripts\paths.ps1')
$outputPath = Join-Path $scratchPath 'frontend-build'
New-Item -ItemType Directory -Force -Path $outputPath | Out-Null
& (Join-Path $repoPath 'node_modules\.bin\tsc.cmd') (Join-Path $repoPath 'explainer\static\app.ts') --target ES2022 --module ES2022 --lib ES2022,DOM --strict --skipLibCheck --outDir $outputPath
if ($LASTEXITCODE -ne 0) { throw 'TypeScript compilation failed' }
Copy-Item -LiteralPath (Join-Path $outputPath 'app.js') -Destination (Join-Path $repoPath 'explainer\static\app.js')
