param(
    [Parameter(Mandatory = $true)]
    [string]$PromptsFile,

    [switch]$RequireLogin,
    [switch]$SubmitOnly,
    [switch]$WatchAndDownload
)

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

$pyArgs = @("--prompts-file", $PromptsFile)
if ($RequireLogin) {
    $pyArgs += "--require-login"
}
if ($SubmitOnly) {
    $pyArgs += "--submit-only"
} else {
    # 默认：按 prompts.json 段数批量提交 + 监听 + 720p 下载
    $pyArgs += "--watch-and-download"
}

python -m flow.run_batch @pyArgs
