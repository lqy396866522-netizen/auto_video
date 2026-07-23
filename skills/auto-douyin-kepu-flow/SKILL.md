---
name: auto-douyin-kepu-flow
description: >
  抖音一分钟科普自动化：列出选题、生成 10 段 Google Flow 视频 prompt、Playwright 批量提交。
  当用户提到「科普选题」「一分钟抖音」「Flow 视频」「批量生成视频」「抖音科普」时立即加载本 skill。
  斜杠命令：/auto-douyin-kepu-flow
  项目根目录：__REPO_ROOT__（clone 到任意盘符均可，运行 deploy.ps1 后 Hermes 自动写入本机路径）
---

# 抖音一分钟科普 · Google Flow（Hermes Skill）

## 触发方式

- 斜杠命令：`/auto-douyin-kepu-flow`
- 自然语言：「给我科普选题」「做一条一分钟科普」「生成 Flow prompt」「开始批量生成视频」

## 项目路径（固定）

| 用途 | 路径 |
|------|------|
| 仓库根 | `__REPO_ROOT__`（即含 `douyin-kepu-flow` 的目录，clone 路径任意） |
| 选题/模板 | `__REPO_ROOT__/douyin-kepu-flow/references/` |
| Prompt 落盘 | `__REPO_ROOT__/douyin-kepu-flow/prompts/{slug}/` |
| Flow 批处理 | `__REPO_ROOT__/douyin-kepu-flow/run_batch.ps1` |
| Flow 登录 | `__REPO_ROOT__/douyin-kepu-flow/run_login.ps1` |
| 干跑测试（不提交） | `python -m flow.test_fill_download` |

**禁止**说「没有现成脚本」——本仓库已包含完整自动化。

## 三阶段对话流程

### 阶段 1 — 列出选题

用户尚未选定题目时：

1. 阅读 `e:\Auto_douyin\auto_video\douyin-kepu-flow\references\topic-rules.md`
2. 输出 **5–8 条**选题，格式：

```
1. 【标题】钩子一句话（难度：入门/进阶）
```

3. 请用户回复序号或标题，**不要**直接进入阶段 2

### 阶段 2 — 生成 N 段 Prompt 并落盘

用户选定选题后：

1. 阅读 `e:\Auto_douyin\auto_video\douyin-kepu-flow\references\prompt-template.md`
2. 生成 `prompts.json`（**N 段 × 6 秒**，常见 8–12 段，含 `style_prefix` + `narration_zh` + `visual_prompt_en`，画幅 **16:9**）
3. **写入文件**：
   - `e:\Auto_douyin\auto_video\douyin-kepu-flow\prompts\{slug}\prompts.json`（含 `narration_script` 整段旁白字段）
   - `e:\Auto_douyin\auto_video\douyin-kepu-flow\prompts\{slug}\editing_guide.md`（旁白时间轴）
   - `e:\Auto_douyin\auto_video\douyin-kepu-flow\prompts\{slug}\narration_script.txt`（纯旁白文案，无时间，方便复制配音）
4. 校验（可选）：

```powershell
cd __REPO_ROOT__
.\.venv\Scripts\python.exe douyin-kepu-flow\content\generate_prompts.py validate --file douyin-kepu-flow\prompts\{slug}\prompts.json
.\.venv\Scripts\python.exe douyin-kepu-flow\content\generate_prompts.py render-guide --file douyin-kepu-flow\prompts\{slug}\prompts.json
```

`narration_script` 规则：将 N 段 `narration_zh` 首尾相接成一段连续口播文案（无时间轴），写入 JSON 的 `narration_script` 字段，并同步生成 `narration_script.txt`。

5. 向用户展示 N 段摘要，询问：「是否开始提交到 Google Flow？」

### 阶段 3 — 批量提交 + 监听百分比 + 720p 下载

用户确认后执行（**默认行为**，直到全部下载完才结束）：

```powershell
cd __REPO_ROOT__
powershell -ExecutionPolicy Bypass -File douyin-kepu-flow\run_batch.ps1 -PromptsFile "douyin-kepu-flow\prompts\{slug}\prompts.json"
```

**监听逻辑（已实现，勿改）：**

1. 按 `prompts.json` 连续提交 N 段（Flow 并行排队，不等单段完成）
2. 每段绑定一个 `data-tile-id` tile
3. 轮询（默认 3s）读取 tile 状态：
   - 页面上仍显示 `\d+%` → **生成中**，继续等
   - 百分比消失且 `video` 有有效 `src` → **完成**，触发 720p 下载
   - 显示「失败」→ 标记失败，跳过
4. 下载走 Playwright 720p 菜单；fallback 用 `page.request`（带 cookie），拒绝 <1KB 空文件

- 段数 **N = prompts.json 的 segments 长度**（不写死 10）
- 下载目录：`D:\douyin-videos\{中文 topic}\`（topic 来自 prompts.json，非法字符自动清理）
- 文件名：`01.mp4` … `{N:02d}.mp4`
- 失败段跳过并在 `batch_report.json` 标注，其余继续
- 整批超时：`FLOW_BATCH_WATCH_TIMEOUT_SEC`（默认 `max(3600, N×300)` 秒）

**仅提交（调试，不监听/下载）：**

```powershell
powershell -ExecutionPolicy Bypass -File douyin-kepu-flow\run_batch.ps1 -PromptsFile "douyin-kepu-flow\prompts\{slug}\prompts.json" -SubmitOnly
```

**干跑测试（不点「创建」，不消耗额度）：** 仅验证 Slate 填入/清空 + 下载已有 tile

```powershell
cd __REPO_ROOT__
$env:PYTHONPATH="douyin-kepu-flow"
.\.venv\Scripts\python.exe -m flow.test_fill_download --prompts-file "douyin-kepu-flow\prompts\{slug}\prompts.json"
```

完成后读取 `batch_report.json` 汇报成功/失败段数。

## Google Flow 固定配置

- **项目 URL（写死）**：`https://labs.google/fx/zh/tools/flow/project/147a46cc-6217-4b1f-a162-e5bcfcd96b9b`
- **默认已登录**，无需登录检测
- **输入框**：placeholder「您希望创作什么内容？」
- **提交**：`arrow_forward` 图标的「创建」按钮
- **模型/时长**：使用页面默认（视频 · 6s），脚本不修改
- **画幅**：**16:9**（横屏，JSON 中 `aspect_ratio: "16:9"`）

若 Flow 页面改版失败，请用户提供 HTML 更新 `references/selectors.md`。

## 统一风格前缀（每段 visual 拼接用，必须完整复制）

```
Modern flat vector illustration,
corporate explainer animation style,
educational motion graphics.

Storyset style,
ManyPixels style,
Google Material illustration style.

2D flat design,
clean vector artwork,
bold black outlines,
consistent line thickness.

Friendly professional characters,
simple geometric shapes.

Low saturation pastel colors.

Smooth motion graphics animation,
gentle easing,
subtle character movement.

Minimal modern environment.

---

Chinese language requirement:

All visible text in the video must use simplified Chinese characters.

Use Chinese only for:
labels,
charts,
documents,
blackboards,
UI interfaces,
educational annotations.

Do not generate English text.
Do not generate random symbols.
Do not create fake unreadable text.

Chinese text must be clear and correctly written.

If text generation is unreliable,
keep the area blank or replace with simple icons.

---

No:
3D rendering,
anime,
Pixar style,
realistic characters,
cinematic lighting,
complex shadows,
random text,
English words.
```

Flow 实际提交文本：`{style_prefix}\n\n{visual_prompt_en}`（**不要**提交中文旁白）

## 首次环境（仅一次）

```powershell
cd __REPO_ROOT__
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium
powershell -ExecutionPolicy Bypass -File douyin-kepu-flow\run_login.ps1
```

浏览器 Profile：当前用户 `~/.hermes/flow-browser`（`Path.home()` 自动判断，勿写死 `C:\Users\xxx`）

## 示例

`e:\Auto_douyin\auto_video\douyin-kepu-flow\prompts\example-bank-lending\prompts.json`

## 剪映

Flow 生成片段后，用独立 Skill **`auto-douyin-jianying-compose`** 自动导入剪映、粘贴 `narration_script`、选「活力科普」配音。

```powershell
powershell -ExecutionPolicy Bypass -File douyin-kepu-flow\run_jianying_compose.ps1 `
  -PromptsFile "douyin-kepu-flow\prompts\{slug}\prompts.json" `
  -VideoDir "D:\douyin-videos\{中文topic}"
```

（在 `e:\Auto_douyin\auto_video` 目录下执行）

斜杠：`/auto-douyin-jianying-compose`。导出成片仍建议手动确认。
