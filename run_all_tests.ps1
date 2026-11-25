# 🍫 Agent KitKat - Master Test Suite Runner
# Runs every phase test suite sequentially and reports comprehensive results

Write-Host "==================================================" -ForegroundColor Yellow
Write-Host "🍫 AGENT KITKAT - COMPREHENSIVE TEST SUITE RUNNER" -ForegroundColor Yellow
Write-Host "==================================================" -ForegroundColor Yellow

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir
$python = "$scriptDir\venv\Scripts\python.exe"

# 1. Verify Ollama is running
Write-Host "Verifying local Ollama daemon (http://127.0.0.1:11434)..." -ForegroundColor Cyan
try {
    $res = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -Method Get -TimeoutSec 3 -ErrorAction Stop
    Write-Host "✅ Ollama is online." -ForegroundColor Green
} catch {
    Write-Host "Ollama not running. Starting background Ollama daemon..." -ForegroundColor Yellow
    Start-Process "ollama" -ArgumentList "serve" -WindowStyle Minimized
    Start-Sleep -Seconds 3
}

# 0. Deterministic regression suite (mocked Ollama and job APIs; throwaway database)
Write-Host "`n>>> Running pytest regression suite ..." -ForegroundColor Cyan
& $python -m pytest -q
$pytestExit = $LASTEXITCODE
if ($pytestExit -eq 0) { Write-Host "✅ PASSED: pytest suite" -ForegroundColor Green } else { Write-Host "❌ FAILED: pytest suite" -ForegroundColor Red }

# Legacy phase scripts. They use a throwaway database too (tests/_isolation.py).
# phase1 / live_server need Ollama; phase7 / master_e2e need internet access to the job APIs.
$testFiles = @(
    "tests\test_phase1.py",
    "tests\test_phase2.py",
    "tests\test_phase3.py",
    "tests\test_phase4.py",
    "tests\test_phase5.py",
    "tests\test_phase6.py",
    "tests\test_phase7.py",
    "tests\test_phase8.py",
    "tests\test_phase9.py",
    "tests\test_master_e2e.py"
)

$passed = 0
$failed = 0
if ($pytestExit -ne 0) { $failed++ } else { $passed++ }

foreach ($test in $testFiles) {
    Write-Host "`n>>> Running: $test ..." -ForegroundColor Cyan
    & $python $test
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ PASSED: $test" -ForegroundColor Green
        $passed++
    } else {
        Write-Host "❌ FAILED: $test (Exit code: $LASTEXITCODE)" -ForegroundColor Red
        $failed++
    }
}

Write-Host "`n==================================================" -ForegroundColor Yellow
Write-Host "🏁 TEST SUITE RUN SUMMARY" -ForegroundColor Yellow
Write-Host "Total Suites: $($testFiles.Count + 1)" -ForegroundColor White
Write-Host "Passed:       $passed" -ForegroundColor Green
Write-Host "Failed:       $failed" -ForegroundColor $(if ($failed -eq 0) { "Green" } else { "Red" })
Write-Host "==================================================" -ForegroundColor Yellow

if ($failed -gt 0) {
    exit 1
} else {
    exit 0
}
