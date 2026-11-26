# Kept for old shortcuts: runs .\test.ps1 (add -Live for the Ollama / job-site checks).
& (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "test.ps1") @args
exit $LASTEXITCODE
