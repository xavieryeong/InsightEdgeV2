# run_eval.ps1 — end-to-end eval runner (Windows PowerShell)
#
# Usage:
#   cd <repo-root>
#   .\eval\run_eval.ps1
#
# Required env vars before running:
#   $env:ANTHROPIC_API_KEY = "sk-ant-..."
#   $env:OPENAI_API_KEY    = "sk-..."

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent

Write-Host "`n[1/4] Regenerating frozen contexts from existing result JSONs..."
python "$Root\eval\freeze_contexts.py"

Write-Host "`n[2/4] Generating Promptfoo test cases..."
python "$Root\eval\generate_promptfoo_tests.py"

Write-Host "`n[3/4] Running Promptfoo benchmark (3 repeats per test)..."
$PFOut = "$Root\eval\promptfoo_output.json"
npx promptfoo eval `
    --config "$Root\eval\promptfoo_call2.yaml" `
    --repeat 3 `
    --output $PFOut

if (-not (Test-Path $PFOut)) {
    Write-Error "Promptfoo did not produce output file. Aborting."
    exit 1
}

Write-Host "`nDone. Results in eval/promptfoo_output.json"
Write-Host "Note: RAGAS (run_ragas.py) requires Python 3.10+ and is run separately if needed."
Write-Host "View Promptfoo report: npx promptfoo view"
