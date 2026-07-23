# 从 skills/*/skill.json 调用：自动定位仓库根（auto_video），与 clone 路径无关。
param(
    [Parameter(Mandatory = $true)]
    [string]$Script,

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Rest
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$scriptPath = Join-Path $RepoRoot "douyin-kepu-flow\$Script"
if (-not (Test-Path $scriptPath)) {
    throw "找不到脚本: $scriptPath"
}

if ($Rest.Count -gt 0) {
    & $scriptPath @Rest
} else {
    & $scriptPath
}
