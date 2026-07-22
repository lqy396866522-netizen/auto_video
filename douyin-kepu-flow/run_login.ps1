$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Test-Path ".venv")) {
    python -m venv .venv
}
& .\.venv\Scripts\Activate.ps1
pip install -q -r requirements.txt
python -m playwright install chromium 2>$null

$env:PYTHONPATH = Join-Path $Root "douyin-kepu-flow"
python -m flow.run_login @args
