# Agent KitKat - one-time setup (safe to run again; it only adds what is missing).
#
#   install.bat            (double-click), or in PowerShell:
#   .\install.ps1 [-Yes] [-SkipModel] [-SkipTests]
#
# What it does:
#   1. Checks Python 3.11+ and Node.js 20.19+ / 22.12+
#   2. Creates the Python virtual environment (venv\) and installs the backend packages
#   3. Installs the Chromium browser used for filling application forms (Playwright)
#   4. Installs the frontend packages and builds the app
#   5. Creates .env from .env.example if you don't have one (never overwrites)
#   6. Checks Ollama and offers to download the qwen2.5:1.5b model (about 1 GB)
#   7. Runs a quick self-test
# Your data in storage\ is never touched.

param(
    [switch]$Yes,        # answer "yes" to questions (download the model)
    [switch]$SkipModel,  # don't check / pull the Ollama model
    [switch]$SkipTests   # skip the quick self-test
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
$model = "qwen2.5:1.5b"
$problems = New-Object System.Collections.Generic.List[string]

function Step($n, $text) { Write-Host ""; Write-Host "[$n/7] $text" -ForegroundColor Cyan }
function Ok($text) { Write-Host "  OK  $text" -ForegroundColor Green }
function Warn($text) { Write-Host "  !!  $text" -ForegroundColor Yellow }
function Fail($text) {
    Write-Host ""
    Write-Host "SETUP STOPPED: $text" -ForegroundColor Red
    Write-Host "Fix the problem above and run install.bat again." -ForegroundColor Red
    exit 1
}
function Ask($question) {
    if ($Yes) { return $true }
    $a = Read-Host "$question [Y/n]"
    return ($a -eq "" -or $a -match "^(y|yes)$")
}

Write-Host "==================================================" -ForegroundColor Yellow
Write-Host "  AGENT KITKAT - SETUP" -ForegroundColor Yellow
Write-Host "==================================================" -ForegroundColor Yellow

# ---------------------------------------------------------------- 1. Python + Node
Step 1 "Checking Python and Node.js"
$py = $null
$candidates = @(@("py", "-3.13"), @("py", "-3.12"), @("py", "-3.11"), @("py", "-3"), @("python"))
foreach ($c in $candidates) {
    try {
        $exe = $c[0]; $pyArgs = @($c | Select-Object -Skip 1)
        $out = & $exe @pyArgs -c "import sys; print('%d.%d' % sys.version_info[:2]); print(int(sys.version_info[:2] >= (3, 11)))" 2>$null
        if ($LASTEXITCODE -eq 0 -and $out -and $out[1] -eq "1") { $py = $c; Ok "Python $($out[0]) ($($c -join ' '))"; break }
    } catch { }
}
if (-not $py) {
    Fail "Python 3.11 or newer not found. Install it from https://www.python.org/downloads/windows/ (tick 'Add python.exe to PATH'), then reopen this window."
}

try { $nodeV = (& node --version) 2>$null } catch { $nodeV = $null }
if (-not $nodeV) { Fail "Node.js not found. Install the LTS version from https://nodejs.org/ and reopen this window." }
$parts = $nodeV.TrimStart("v").Split(".")
$maj = [int]$parts[0]; $min = [int]$parts[1]
if (($maj -eq 20 -and $min -ge 19) -or ($maj -eq 22 -and $min -ge 12) -or $maj -ge 23) { Ok "Node.js $nodeV" }
else { Fail "Node.js $nodeV is too old; the frontend needs 20.19+ or 22.12+. Install the current LTS from https://nodejs.org/" }

# ---------------------------------------------------------------- 2. venv + packages
Step 2 "Python environment and backend packages"
$venvPy = Join-Path $root "venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    $exe = $py[0]; $pyArgs = @($py | Select-Object -Skip 1)
    & $exe @pyArgs -m venv venv
    if ($LASTEXITCODE -ne 0) { Fail "Could not create the virtual environment (venv)." }
    Ok "Created venv\"
} else { Ok "venv\ already exists" }

& $venvPy -m pip install --upgrade pip --quiet --disable-pip-version-check
& $venvPy -m pip install -r backend\requirements.lock.txt --quiet --disable-pip-version-check
if ($LASTEXITCODE -ne 0) {
    Warn "Exact tested versions could not be installed for this Python; installing the newest compatible ones."
    & $venvPy -m pip install -r backend\requirements.txt --quiet --disable-pip-version-check
    if ($LASTEXITCODE -ne 0) { Fail "pip could not install the backend packages (see the error above)." }
    $problems.Add("Packages installed from requirements.txt instead of the tested lock file.")
}
Ok "Backend packages installed"

# ---------------------------------------------------------------- 3. Playwright browser
Step 3 "Browser for filling application forms (Chromium, about 150 MB)"
& $venvPy -m playwright install chromium
if ($LASTEXITCODE -ne 0) {
    Warn "Chromium could not be installed. Everything except form filling works; run: venv\Scripts\python -m playwright install chromium"
    $problems.Add("Playwright Chromium not installed.")
} else { Ok "Chromium ready" }

# ---------------------------------------------------------------- 4. frontend
Step 4 "Frontend packages and build"
Push-Location (Join-Path $root "frontend")
try {
    if (Test-Path "package-lock.json") { npm ci --no-audit --no-fund } else { npm install --no-audit --no-fund }
    if ($LASTEXITCODE -ne 0) { Fail "npm could not install the frontend packages." }
    npm run build
    if ($LASTEXITCODE -ne 0) { Fail "The frontend build failed." }
} finally { Pop-Location }
Ok "Frontend built (frontend\dist)"

# ---------------------------------------------------------------- 5. settings + storage
Step 5 "Settings and storage folders"
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Ok "Created .env from .env.example (edit it to change the timezone, schedule sources, etc.)"
} else { Ok ".env exists (left unchanged)" }
foreach ($d in @("storage", "storage\resumes", "storage\applications", "storage\screenshots", "storage\logs", "storage\backups")) {
    if (-not (Test-Path $d)) { New-Item -ItemType Directory -Path $d | Out-Null }
}
Ok "storage\ ready (your data stays here and is never uploaded)"

# ---------------------------------------------------------------- 6. Ollama
Step 6 "Local AI (Ollama, model $model)"
if ($SkipModel) {
    Warn "Skipped (-SkipModel)."
} elseif (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
    Warn "Ollama is not installed. Agent KitKat still works, but cover letters and answers use simple templates."
    Warn "Install it from https://ollama.com/download/windows, then run: ollama pull $model"
    $problems.Add("Ollama not installed.")
} else {
    $running = $false
    try { Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 3 | Out-Null; $running = $true } catch { }
    if (-not $running) {
        Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Minimized
        Start-Sleep -Seconds 4
        try { Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 3 | Out-Null; $running = $true } catch { }
    }
    if (-not $running) {
        Warn "Ollama is installed but not responding on http://127.0.0.1:11434. Start the Ollama app and run install.bat again."
        $problems.Add("Ollama not running.")
    } else {
        $tags = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 5
        $names = @($tags.models | ForEach-Object { $_.name })
        if ($names -contains $model) { Ok "Ollama running, $model installed" }
        elseif (Ask "Download the $model model now (about 1 GB)?") {
            ollama pull $model
            if ($LASTEXITCODE -eq 0) { Ok "$model downloaded" } else { $problems.Add("ollama pull $model failed.") }
        } else {
            Warn "Model not downloaded. Later run: ollama pull $model"
            $problems.Add("Model $model not downloaded.")
        }
    }
}

# ---------------------------------------------------------------- 7. self-test
Step 7 "Quick self-test (uses a temporary database, not yours)"
if ($SkipTests) {
    Warn "Skipped (-SkipTests)."
} else {
    & $venvPy -m pytest -q -x tests\test_stage2_regressions.py tests\test_stage4_profile_eligibility.py -p no:warnings
    if ($LASTEXITCODE -eq 0) { Ok "Self-test passed" }
    else { Warn "Self-test failed (see above). Run .\test.ps1 for the full suite."; $problems.Add("Self-test failed.") }
}

# ---------------------------------------------------------------- summary
Write-Host ""
Write-Host "==================================================" -ForegroundColor Yellow
if ($problems.Count -eq 0) {
    Write-Host "  Setup complete." -ForegroundColor Green
} else {
    Write-Host "  Setup finished with notes:" -ForegroundColor Yellow
    foreach ($p in $problems) { Write-Host "   - $p" -ForegroundColor Yellow }
}
Write-Host "  Start Agent KitKat:  start.bat   (stop with stop.bat)"
Write-Host "  Then open:           http://localhost:5173"
Write-Host "  Phone:               Settings > Phone access (scan the QR code)"
Write-Host "==================================================" -ForegroundColor Yellow
