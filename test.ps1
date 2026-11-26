# Agent KitKat - run the test suites.
#
#   .\test.ps1            pytest (all stages) + legacy phase scripts + frontend build
#   .\test.ps1 -Live      also the live checks: real Ollama and real job sites (pytest -m live)
#   .\test.ps1 -Quick     pytest only
#
# Every test uses a temporary database and storage folder: your data is never touched.

param([switch]$Live, [switch]$Quick)

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
$py = Join-Path $root "venv\Scripts\python.exe"
if (-not (Test-Path $py)) { Write-Host "Run install.bat first." -ForegroundColor Red; exit 1 }

$results = New-Object System.Collections.Generic.List[object]
function Run($name, [scriptblock]$block) {
    Write-Host ""
    Write-Host ">>> $name" -ForegroundColor Cyan
    & $block
    $ok = ($LASTEXITCODE -eq 0)
    $results.Add([pscustomobject]@{ Suite = $name; Result = $(if ($ok) { "PASS" } else { "FAIL" }) })
}

Run "pytest (stages 2-10)" { & $py -m pytest -q -p no:warnings }

if (-not $Quick) {
    # Legacy phase scripts. phase1 needs Ollama and phase7 / master_e2e need internet: they run with -Live.
    $legacy = @("test_phase2", "test_phase3", "test_phase4", "test_phase5", "test_phase6", "test_phase8", "test_phase9")
    if ($Live) { $legacy += @("test_phase1", "test_phase7", "test_master_e2e") }
    foreach ($t in $legacy) { Run "legacy $t" { & $py "tests\$t.py" | Out-Null } }
    Run "frontend build" { Push-Location frontend; npm run build | Out-Null; $code = $LASTEXITCODE; Pop-Location; $global:LASTEXITCODE = $code }
}

if ($Live) {
    Run "live checks (Ollama + job sites)" { & $py -m pytest -m live -v -p no:warnings }
}

Write-Host ""
Write-Host "==================================================" -ForegroundColor Yellow
$results | Format-Table -AutoSize | Out-String | Write-Host
$failed = @($results | Where-Object { $_.Result -eq "FAIL" }).Count
if ($failed -eq 0) { Write-Host "All $($results.Count) suites passed." -ForegroundColor Green; exit 0 }
Write-Host "$failed of $($results.Count) suites failed." -ForegroundColor Red
exit 1
