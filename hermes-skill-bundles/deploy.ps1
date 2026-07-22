param(
    [string]$HermesHome = "$env:LOCALAPPDATA\hermes"
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$SkillsSrc = Join-Path $RepoRoot "skills"
$BundleSrc = $PSScriptRoot
$ConfigPath = Join-Path $HermesHome "config.yaml"

$SkillNames = @(
    "auto-douyin-kepu-flow",
    "auto-douyin-jianying-compose"
)

function Convert-RepoPaths {
    param([string]$Content)
    # 部署时把文档里的占位盘符统一替换为当前仓库根目录
    return ($Content -replace '(?i)e:\\Auto_douyin', $RepoRoot)
}

function Write-RepoFile {
    param(
        [string]$SourcePath,
        [string]$DestPath
    )
    $raw = Get-Content $SourcePath -Raw -Encoding UTF8
    $text = Convert-RepoPaths $raw
    $dir = Split-Path -Parent $DestPath
    if ($dir -and -not (Test-Path $dir)) {
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
    }
    [System.IO.File]::WriteAllText($DestPath, $text, [System.Text.UTF8Encoding]::new($false))
}

# 0. 项目根 AGENTS.md（Hermes 从 cwd 加载项目上下文）
$AgentsSrc = Join-Path $SkillsSrc "AGENTS.md"
$AgentsDest = Join-Path $RepoRoot "AGENTS.md"
if (Test-Path $AgentsSrc) {
    Write-RepoFile $AgentsSrc $AgentsDest
    Write-Host "[OK] AGENTS.md -> $AgentsDest"
}

# 1. Deploy skill bundles
$BundleDest = Join-Path $HermesHome "skill-bundles"
New-Item -ItemType Directory -Force -Path $BundleDest | Out-Null
Get-ChildItem (Join-Path $BundleSrc "*.yaml") | ForEach-Object {
    Write-RepoFile $_.FullName (Join-Path $BundleDest $_.Name)
}
Write-Host "[OK] Bundles -> $BundleDest"

# 2. Copy skills to ~/.hermes/skills/
foreach ($SkillName in $SkillNames) {
    $SkillDest = Join-Path $HermesHome "skills\$SkillName"
    New-Item -ItemType Directory -Force -Path $SkillDest | Out-Null
    Write-RepoFile (Join-Path $SkillsSrc "$SkillName\SKILL.md") (Join-Path $SkillDest "SKILL.md")
    Write-RepoFile (Join-Path $SkillsSrc "$SkillName\skill.json") (Join-Path $SkillDest "skill.json")
    Write-Host "[OK] Skill -> $SkillDest"
}

# 3. Register external_dirs（优先从仓库直接加载，便于就地修改）
$ExternalDir = ($SkillsSrc -replace '\\', '/')
if (Test-Path $ConfigPath) {
    $config = Get-Content $ConfigPath -Raw -Encoding UTF8
    if ($config -match [regex]::Escape($ExternalDir)) {
        Write-Host "[OK] external_dirs already contains $ExternalDir"
    }
    elseif ($config -match '(?ms)(skills:\s*\r?\n\s*external_dirs:\s*)\[\]') {
        $config = $config -replace '(?ms)(skills:\s*\r?\n\s*external_dirs:\s*)\[\]', "`${1}`n  - $ExternalDir"
        [System.IO.File]::WriteAllText($ConfigPath, $config, [System.Text.UTF8Encoding]::new($false))
        Write-Host "[OK] Added external_dirs: $ExternalDir"
    }
    elseif ($config -match '(?ms)(skills:\s*\r?\n\s*external_dirs:\s*\r?\n)((?:\s*-\s*.+\r?\n)+)') {
        $config = $config -replace '(?ms)(skills:\s*\r?\n\s*external_dirs:\s*\r?\n(?:\s*-\s*.+\r?\n)+)', "`$1  - $ExternalDir`n"
        [System.IO.File]::WriteAllText($ConfigPath, $config, [System.Text.UTF8Encoding]::new($false))
        Write-Host "[OK] Added external_dirs: $ExternalDir"
    }
    else {
        Write-Host "[WARN] Manually add to $ConfigPath under skills.external_dirs: $ExternalDir"
    }
}
else {
    Write-Host "[WARN] Config not found: $ConfigPath — add external_dirs manually"
}

# 4. Reload bundles
if (Get-Command hermes -ErrorAction SilentlyContinue) {
    hermes bundles reload 2>$null
    Write-Host ""
    hermes bundles list 2>$null
}

Write-Host ""
Write-Host "Done. Repo root: $RepoRoot"
Write-Host "In Hermes chat send:"
Write-Host "  /reload-skills"
Write-Host "  /auto-douyin-kepu-flow"
Write-Host "  /auto-douyin-jianying-compose"
