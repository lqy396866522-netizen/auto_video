param(
    [Parameter(Mandatory = $true)]
    [string]$PromptsFile,

    [Parameter(Mandatory = $true)]
    [string]$VideoDir,

    [switch]$DryRun,
    [switch]$ImportOneByOne
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Test-Path ".venv")) {
    python -m venv .venv
}
& .\.venv\Scripts\Activate.ps1
pip install -q -r requirements.txt

$env:PYTHONPATH = Join-Path $Root "douyin-kepu-flow"

$pyArgs = @(
    "-m", "jianying.run_compose",
    "--prompts-file", $PromptsFile,
    "--video-dir", $VideoDir
)
if ($DryRun) {
    $pyArgs += "--dry-run"
}
if ($ImportOneByOne) {
    $pyArgs += "--import-one-by-one"
}

python @pyArgs
