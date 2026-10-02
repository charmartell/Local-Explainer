[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidateSet('health','list','status','plan','approve','produce','cancel','resume','revise')][string]$Action,
    [string]$Job, [string]$RequestFile, [string]$OutlineHash, [string]$Instruction, [string]$SceneId
)
$ErrorActionPreference = 'Stop'
$baseUrl = 'http://127.0.0.1:8090/api'
$headers = @{ 'Content-Type' = 'application/json' }
if ($Action -eq 'health') { $result = Invoke-RestMethod -Uri "$baseUrl/health" }
elseif ($Action -eq 'list') { $result = Invoke-RestMethod -Uri "$baseUrl/jobs" }
elseif ($Action -eq 'status') { $result = Invoke-RestMethod -Uri "$baseUrl/jobs/$Job" }
else {
    $route = switch ($Action) { 'plan' { 'jobs' }; 'approve' { "jobs/$Job/approval" }; 'produce' { "jobs/$Job/production" }; 'revise' { "jobs/$Job/revisions" }; default { "jobs/$Job/$Action" } }
    $body = switch ($Action) {
        'plan' { Get-Content -LiteralPath $RequestFile -Raw }
        'approve' { @{outline_hash=$OutlineHash} | ConvertTo-Json -Compress }
        'revise' { @{instruction=$Instruction;scene_id=$(if ($SceneId) { $SceneId } else { $null })} | ConvertTo-Json -Compress }
        default { '{}' }
    }
    $result = Invoke-RestMethod -Uri "$baseUrl/$route" -Method Post -Headers $headers -Body ([System.Text.Encoding]::UTF8.GetBytes($body))
}
$result | ConvertTo-Json -Depth 30
