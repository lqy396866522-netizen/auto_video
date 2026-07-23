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
    # 部署时把文档占位路径替换为当前机器上的仓库根目录（clone 在哪都行）
    $escaped = [regex]::Escape($RepoRoot)
    $text = $Content -replace '__REPO_ROOT__', $RepoRoot
    $text = $text -replace '(?i)([eEgG]):\\Auto_douyin\\auto_video', $RepoRoot
    $text = $text -replace '(?i)([eEgG]):\\Auto_douyin(?![/\\]auto_video)', $RepoRoot
    return $text
}

function Update-ExternalDirs {
    param([string]$ConfigPath, [string]$ExternalDir)
    if (-not (Test-Path $ConfigPath)) {
        Write-Host "[WARN] Config not found: $ConfigPath — add external_dirs manually"
        return
    }
    $config = Get-Content $ConfigPath -Raw -Encoding UTF8
    $externalDirAlt = $ExternalDir -replace '/', '\\'

    # 移除任意位置的旧 Auto_douyin skills 路径（含误追加到文件末尾的条目）
    $config = $config -replace '(?m)^\s*-\s*[eEgG]:[/\\]Auto_douyin(?:[/\\]auto_video)?[/\\]skills\s*\r?\n', ''

    $alreadyPresent = ($config -match [regex]::Escape($ExternalDir)) -or ($config -match [regex]::Escape($externalDirAlt))
    if ($alreadyPresent) {
        $presentPattern = '(?ms)(skills:\s*\r?\n\s*external_dirs:\s*\r?\n(?:\s*-\s*.+\r?\n)*?\s*-\s*' + [regex]::Escape($ExternalDir) + '\s*\r?\n\s*template_vars:)'
        if ($config -match $presentPattern) {
            Write-Host "[OK] external_dirs already contains skills path"
            [System.IO.File]::WriteAllText($ConfigPath, $config, [System.Text.UTF8Encoding]::new($false))
            return
        }
    }
    if ($config -match '(?ms)(skills:\s*\r?\n\s*external_dirs:\s*)\[\]') {
        $config = $config -replace '(?ms)(skills:\s*\r?\n\s*external_dirs:\s*)\[\]', "`${1}`n  - $ExternalDir"
        Write-Host "[OK] Added external_dirs: $ExternalDir"
    }
    elseif ($config -match '(?ms)(skills:\s*\r?\n\s*external_dirs:\s*\r?\n(?:\s*-\s*.+\r?\n)*?)(\s*template_vars:)') {
        $config = $config -replace '(?ms)(skills:\s*\r?\n\s*external_dirs:\s*\r?\n(?:\s*-\s*.+\r?\n)*?)(\s*template_vars:)', "`$1  - $ExternalDir`n`$2"
        Write-Host "[OK] Added external_dirs: $ExternalDir"
    }
    else {
        Write-Host "[WARN] Manually add to $ConfigPath under skills.external_dirs: $ExternalDir"
    }
    [System.IO.File]::WriteAllText($ConfigPath, $config, [System.Text.UTF8Encoding]::new($false))
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

$ExternalDir = ($SkillsSrc -replace '\\', '/')

# 2. 仅使用 external_dirs 加载 skills（避免与 ~/.hermes/skills/ 副本重名冲突）
#    若存在旧版本地副本，删除以免 skill_view 报 collision
foreach ($SkillName in $SkillNames) {
    $LocalCopy = Join-Path $HermesHome "skills\$SkillName"
    if (Test-Path $LocalCopy) {
        Remove-Item -Recurse -Force $LocalCopy
        Write-Host "[OK] Removed duplicate local skill (use external_dirs): $LocalCopy"
    }
}
Write-Host "[OK] Skills source -> $ExternalDir (external_dirs only, no local copy)"
Update-ExternalDirs -ConfigPath $ConfigPath -ExternalDir $ExternalDir

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
