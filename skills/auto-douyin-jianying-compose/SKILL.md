---
name: auto-douyin-jianying-compose
description: >
  剪映 UI 自动合成：扫描 01-10 段 mp4 → 导入拼接 → 粘贴 narration_script → 活力科普配音 → 等自动拆句。
  当用户提到「剪映合成」「自动剪辑配音」「导入剪映」「Jianying compose」时立即加载本 skill。
  斜杠命令：/auto-douyin-jianying-compose
  项目根目录：e:\Auto_douyin
---

# 抖音一分钟科普 · 剪映自动合成（Hermes Skill）

## 触发方式

- 斜杠命令：`/auto-douyin-jianying-compose`
- 自然语言：「剪映合成 buffet-profit-secret」「自动剪辑配音」「导入剪映并配音」

## 前置条件（必须检查）

1. **10 个 mp4** 已在指定目录，文件名含 **01–10** 序号（如 `seg-01.mp4`）
2. **prompts.json** 含 `narration_script` 字段（阶段 2 已生成）
3. 剪映在**首页**空闲，运行期间勿操作鼠标键盘
4. 剪映路径默认：`%LOCALAPPDATA%\JianyingPro\Apps\JianyingPro.exe`

## 项目路径

| 用途 | 路径 |
|------|------|
| 仓库根 | `e:\Auto_douyin` |
| 剪映脚本 | `e:\Auto_douyin\douyin-kepu-flow\run_jianying_compose.ps1` |
| UI 模块 | `e:\Auto_douyin\douyin-kepu-flow\jianying\` |
| 选择器文档 | `e:\Auto_douyin\douyin-kepu-flow\references\jianying-selectors.md` |

## 执行流程

### 1. 校验片段（推荐先跑）

```powershell
cd e:\Auto_douyin
powershell -ExecutionPolicy Bypass -File douyin-kepu-flow\run_jianying_compose.ps1 `
  -PromptsFile "douyin-kepu-flow\prompts\{slug}\prompts.json" `
  -VideoDir "{slug}" `
  -DryRun
```

`-VideoDir` 支持：

- 绝对路径：`D:\videos\buffet-profit-secret`
- 文件夹名：自动查找 `Desktop\douyin-videos\{name}`

### 2. 全自动合成

```powershell
cd e:\Auto_douyin
powershell -ExecutionPolicy Bypass -File douyin-kepu-flow\run_jianying_compose.ps1 `
  -PromptsFile "douyin-kepu-flow\prompts\{slug}\prompts.json" `
  -VideoDir "$env:USERPROFILE\Desktop\douyin-videos\{slug}"
```

完成后读取 `{VideoDir}\jianying_compose_report.json` 汇报各步耗时与成败。

### 3. 人工导出

脚本**不**自动导出成片。合成成功后提示用户在剪映内点击「导出」。

## 固定参数

| 项 | 值 |
|----|-----|
| 旁白来源 | `prompts.json` → `narration_script` |
| 配音 Tab | 收藏 |
| 配音音色 | 活力科普 |
| 字幕模式 | 手动写字幕 → 智能分割 |

## 与 Flow Skill 的关系

- **独立 Skill**，不与 `auto-douyin-kepu-flow` 合并
- 现阶段：**手动触发**（Flow 多用 `-SubmitOnly`，片段需手动下载）
- 后续：Flow 全量下载且 `batch_report.json` 10/10 成功后可串联

## 故障排查

- 找不到按钮 → 更新 `references/jianying-selectors.md`
- 导入失败 → 试 `-ImportOneByOne`（目录有多余 mp4 时）
- 拆句超时 → `.env` 增大 `JIANYING_SPLIT_SENTENCE_TIMEOUT_SEC`

## 示例

```powershell
powershell -ExecutionPolicy Bypass -File douyin-kepu-flow\run_jianying_compose.ps1 `
  -PromptsFile "douyin-kepu-flow\prompts\buffet-profit-secret\prompts.json" `
  -VideoDir "buffet-profit-secret"
```
