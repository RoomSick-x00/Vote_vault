param(
  [string]$Workspace = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path,
  [string]$BeleniosTool = '/root/.local/share/votevault-belenios-3.3.0/_run/tool-debug/bin/belenios-tool',
  [string]$WslDistro = 'Ubuntu',
  [string]$Rpc = 'http://127.0.0.1:18546'
)
$ErrorActionPreference = 'Stop'

$archiveDir = Join-Path $Workspace 'docs\belenios-real-synthetic'
$archive = Join-Path $archiveDir 'election.bel'
$announced = Join-Path $archiveDir 'announced-result.json'
$anchorManifest = Join-Path $archiveDir 'anchor-manifest.json'
$chainReference = Join-Path $archiveDir ("chain-reference-{0}.json" -f [guid]::NewGuid().ToString('N'))
$runOutput = Join-Path $archiveDir 'standalone-verifier-output.txt'
$env:PYTHONPATH = Join-Path $Workspace 'backend'
$env:VV_LOCAL_RPC = $Rpc

Push-Location $Workspace
try {
  & .\.venv\Scripts\python.exe backend/scripts/prepare_belenios_anchor.py $archive $anchorManifest
  if ($LASTEXITCODE -ne 0) { throw 'Preparing the synthetic anchor manifest failed.' }

  $env:VV_ANCHOR_MANIFEST = $anchorManifest
  $env:VV_ANCHOR_OUTPUT = $chainReference
  Push-Location (Join-Path $Workspace 'blockchain')
  try {
    & .\node_modules\.bin\hardhat.cmd run scripts/anchor_belenios_demo.js --network localhost
    if ($LASTEXITCODE -ne 0) { throw 'Anchoring the synthetic election failed.' }
  } finally { Pop-Location }

  $reference = Get-Content -LiteralPath $chainReference -Raw | ConvertFrom-Json
  $arguments = @(
    'backend/scripts/verify_belenios_election.py', $archive,
    '--belenios-tool', $BeleniosTool, '--wsl-distro', $WslDistro,
    '--expected-result', $announced,
    '--receipt', (Get-Content -LiteralPath (Join-Path $archiveDir 'receipt.txt') -Raw).Trim(),
    '--rpc', $reference.rpc, '--chain-id', [string]$reference.chain_id,
    '--contract', $reference.contract, '--code-hash', $reference.code_hash,
    '--election-id', $reference.election_id, '--hardhat-project', 'blockchain'
  )
  & .\.venv\Scripts\python.exe @arguments *>&1 | Tee-Object -FilePath $runOutput
  if ($LASTEXITCODE -ne 0) { throw "Independent verifier did not PASS; see $runOutput" }
  Write-Host "Chain reference saved to $chainReference"
  Write-Host "Verifier output saved to $runOutput"
} finally {
  Pop-Location
}
