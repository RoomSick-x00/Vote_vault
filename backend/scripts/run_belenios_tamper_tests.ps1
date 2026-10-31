param(
  [Parameter(Mandatory = $true)][string]$ChainReference,
  [string]$Workspace = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path,
  [string]$BeleniosTool = '/root/.local/share/votevault-belenios-3.3.0/_run/tool-debug/bin/belenios-tool',
  [string]$WslDistro = 'Ubuntu',
  [string]$OutputDirectory = (Join-Path $Workspace ('.local\belenios-tamper-' + [guid]::NewGuid().ToString('N')))
)
$ErrorActionPreference = 'Stop'
$archiveDir = Join-Path $Workspace 'docs\belenios-real-synthetic'
$source = Join-Path $archiveDir 'election.bel'
$expected = Join-Path $archiveDir 'announced-result.json'
$env:PYTHONPATH = Join-Path $Workspace 'backend'
$env:VV_LOCAL_RPC = (Get-Content -LiteralPath $ChainReference -Raw | ConvertFrom-Json).rpc

Push-Location $Workspace
try {
  & .\.venv\Scripts\python.exe backend/scripts/make_belenios_tamper_copies.py $source $OutputDirectory
  if ($LASTEXITCODE -ne 0) { throw 'Creating altered copies failed.' }
  $reference = Get-Content -LiteralPath $ChainReference -Raw | ConvertFrom-Json
  $reports = @()
  $failures = @()
  Get-ChildItem -LiteralPath $OutputDirectory -Filter '*.bel' | Sort-Object Name | ForEach-Object {
    $path = $_.FullName
    $name = $_.BaseName
    $report = Join-Path $OutputDirectory ($name + '-verification.txt')
    $arguments = @(
      'backend/scripts/verify_belenios_election.py', $path,
      '--belenios-tool', $BeleniosTool, '--wsl-distro', $WslDistro,
      '--expected-result', $expected,
      '--receipt', (Get-Content -LiteralPath (Join-Path $archiveDir 'receipt.txt') -Raw).Trim(),
      '--rpc', $reference.rpc, '--chain-id', [string]$reference.chain_id,
      '--contract', $reference.contract, '--code-hash', $reference.code_hash,
      '--election-id', $reference.election_id, '--hardhat-project', 'blockchain',
      '--timeout', '120'
    )
    $text = & .\.venv\Scripts\python.exe @arguments 2>&1
    $exit = $LASTEXITCODE
    $text | Set-Content -LiteralPath $report -Encoding utf8NoBOM
    $joined = $text -join "`n"
    if ($joined -match 'Tar\.header_of_bytes: not reproducible') {
      throw "Attack $name failed because its tar encoding is invalid, not because of the attack. Inspect $report"
    }
    if ($joined -match 'FAIL: belenios\.proofs:.*(Tar\.header|not reproducible)') {
      throw "Attack $name reports a tar-format error as a proof failure. Inspect $report"
    }
    $expectedCheck = switch ($name) {
      'unauthorized-insertion' { 'FAIL: (chain\.archive|belenios\.proofs):' }
      'ballot-deletion' { 'FAIL: receipt\.inclusion:' }
      'ballot-modification' { 'FAIL: (receipt\.inclusion|chain\.archive|belenios\.proofs):' }
      'manipulated-result-rehashed' { 'FAIL: result\.announced:' }
      'duplicate-credential' { 'FAIL: archive\.structure:' }
      default { throw "No expected check configured for attack $name" }
    }
    if ($exit -eq 2 -and $name -eq 'unauthorized-insertion' -and $joined -match 'INCOMPLETE: belenios\.proofs:' -and $joined -match 'INCOMPLETE: chain\.reference:') {
      $failures += "Attack $name remains UNPROVEN: both independent proof verification and the chain seal are unavailable. Inspect $report"
      Write-Host "BLOCKED: $name — proof verifier and chain unavailable"
    } elseif ($exit -ne 1 -or $joined -notmatch $expectedCheck) {
      $failures += "Attack $name did not fail expected check $expectedCheck (exit=$exit). Inspect $report"
      Write-Host "UNEXPECTED: $name — expected $expectedCheck"
    } else {
      Write-Host "EXPECTED FAIL: $name — $expectedCheck"
    }
    $reports += $report
  }
  Write-Host "Attack verifier reports saved under $OutputDirectory"
  $reports | ForEach-Object { Write-Host "  $_" }
  if ($failures.Count -gt 0) { throw ($failures -join [Environment]::NewLine) }
} finally {
  Pop-Location
}
