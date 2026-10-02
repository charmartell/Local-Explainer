# Shared by setup, launcher, and UI build. Environment overrides local configuration.
$localPathsFile = Join-Path $repoPath '.local-paths.json'
$localPaths = if (Test-Path -LiteralPath $localPathsFile) { Get-Content -LiteralPath $localPathsFile -Raw | ConvertFrom-Json } else { $null }
function Resolve-ExplainerPath($Name, $Variable, $Default) {
    $override = [Environment]::GetEnvironmentVariable($Variable)
    $value = if ($override) { $override } elseif ($localPaths -and $localPaths.$Name) { $localPaths.$Name } else { $Default }
    return [IO.Path]::GetFullPath($value)
}
$assetPath = Resolve-ExplainerPath 'assets' 'LOCAL_EXPLAINER_ASSETS' (Join-Path $repoPath 'data\assets')
$scratchPath = Resolve-ExplainerPath 'scratch' 'LOCAL_EXPLAINER_SCRATCH' (Join-Path $repoPath 'data\scratch')
$buildsPath = Resolve-ExplainerPath 'builds' 'LOCAL_EXPLAINER_BUILDS' (Join-Path $repoPath 'data\builds')
$comfyRepoPath = Resolve-ExplainerPath 'comfy_repo' 'LOCAL_EXPLAINER_COMFY_REPO' (Join-Path $assetPath 'Runtime\ComfyUI')
$env:LOCAL_EXPLAINER_ASSETS = $assetPath
$env:LOCAL_EXPLAINER_SCRATCH = $scratchPath
$env:LOCAL_EXPLAINER_BUILDS = $buildsPath
$env:LOCAL_EXPLAINER_COMFY_REPO = $comfyRepoPath
