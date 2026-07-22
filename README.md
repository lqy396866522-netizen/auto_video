# 抖音一分钟科普 · Google Flow 自动化

Hermes Agent 对话生成科普选题与 **10 段** 6 秒视频 prompt（**16:9** 横屏），Playwright 自动操作 [Google Flow](https://labs.google/fx/zh/tools/flow) 批量生成并下载到桌面。

## 功能

| 阶段 | 说明 |
|------|------|
| 选题 | Hermes Skill 输出 5–8 条科普选题 |
| Prompt | 生成 10 段 JSON（16:9）+ 剪映剪辑清单 |
| 生成 | Playwright 持久化浏览器批处理 Flow |
| 剪辑 | 剪映 UI 自动合成（见 `run_jianying_compose.ps1`）或手动 `editing_guide.md` |

## 快速开始

### 1. 安装依赖

```powershell
cd e:\Auto_douyin
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium
```

### 2. 配置（可选）

```powershell
copy .env.example .env
```

默认下载目录：`%USERPROFILE%\Desktop\douyin-videos\{slug}\`

### 3. 打开 Flow 项目页

脚本默认打开固定项目（已登录即可直接跑）：

`https://labs.google/fx/zh/tools/flow/project/147a46cc-6217-4b1f-a162-e5bcfcd96b9b`

如需首次在自动化浏览器登录 Google：

```powershell
powershell -ExecutionPolicy Bypass -File douyin-kepu-flow\run_login.ps1
```

### 4. Hermes Skill 部署（对话触发）

```powershell
cd e:\Auto_douyin
powershell -ExecutionPolicy Bypass -File hermes-skill-bundles\deploy.ps1
```

在 Hermes 对话发送：

```
/reload-skills
/auto-douyin-kepu-flow
```

**自然语言示例：**

- 「给我 5 个科普选题」
- 「选第 2 个，生成 prompt」
- 「开始批量提交 Flow」

Skill 文件位置：

- [`skills/auto-douyin-kepu-flow/SKILL.md`](skills/auto-douyin-kepu-flow/SKILL.md) — Hermes 主 skill
- [`hermes-skill-bundles/auto-douyin-kepu-flow.yaml`](hermes-skill-bundles/auto-douyin-kepu-flow.yaml) — 斜杠 bundle

### 5. 批量生成（示例）

**仅提交 10 段 prompt（写入 → 点创建 → 清空，不等待下载）：**

```powershell
powershell -ExecutionPolicy Bypass -File douyin-kepu-flow\run_batch.ps1 `
  -PromptsFile "douyin-kepu-flow\prompts\example-bank-lending\prompts.json" `
  -SubmitOnly
```

**完整模式（等待每段生成并下载）：**

```powershell
powershell -ExecutionPolicy Bypass -File douyin-kepu-flow\run_batch.ps1 `
  -PromptsFile "douyin-kepu-flow\prompts\example-bank-lending\prompts.json"
```

### 6. 剪映自动合成

手动下载 10 段 mp4 到 `Desktop\douyin-videos\{slug}\` 后：

**校验片段（不操作剪映）：**

```powershell
powershell -ExecutionPolicy Bypass -File douyin-kepu-flow\run_jianying_compose.ps1 `
  -PromptsFile "douyin-kepu-flow\prompts\buffet-profit-secret\prompts.json" `
  -VideoDir "buffet-profit-secret" `
  -DryRun
```

**全自动导入 + 字幕 + 配音：**

```powershell
powershell -ExecutionPolicy Bypass -File douyin-kepu-flow\run_jianying_compose.ps1 `
  -PromptsFile "douyin-kepu-flow\prompts\buffet-profit-secret\prompts.json" `
  -VideoDir "$env:USERPROFILE\Desktop\douyin-videos\buffet-profit-secret"
```

Hermes 斜杠：`/auto-douyin-jianying-compose`

Skill：[`skills/auto-douyin-jianying-compose/SKILL.md`](skills/auto-douyin-jianying-compose/SKILL.md)

## Hermes 对话流程

1. 「给我 5 个科普选题」→ Agent 列出选题
2. 「选第 1 个」→ Agent 生成 `prompts/{slug}/prompts.json` 与 `editing_guide.md`
3. 「开始生成视频」→ Agent 执行 `run_batch.ps1`

## 目录结构

```
Auto_douyin/
├── douyin-kepu-flow/
│   ├── SKILL.md              # Hermes 技能说明
│   ├── flow/                 # Playwright 自动化
│   ├── jianying/             # 剪映 UI 自动化
│   ├── content/              # JSON 校验与剪辑清单
│   ├── prompts/              # 每次选题落盘
│   └── references/           # 模板、选题规则、选择器
├── skills/
│   ├── auto-douyin-kepu-flow/
│   └── auto-douyin-jianying-compose/
├── hermes-skill-bundles/
└── requirements.txt
```

## 输出文件

批处理完成后，在下载目录可找到：

- `seg-01.mp4` … `seg-10.mp4`
- `batch_report.json` — 成功/失败段记录
- `editing_guide.md` — 旁白时间轴（剪映用）
- `jianying_compose_report.json` — 剪映合成各步报告（跑 `run_jianying_compose.ps1` 后）

## 校验 Prompt JSON

```powershell
python douyin-kepu-flow\content\generate_prompts.py validate `
  --file douyin-kepu-flow\prompts\example-bank-lending\prompts.json

python douyin-kepu-flow\content\generate_prompts.py render-guide `
  --file douyin-kepu-flow\prompts\example-bank-lending\prompts.json
```

## 选择器维护

Flow 页面更新后，若自动化找不到按钮，请：

1. 保存当前页面 HTML
2. 更新 [douyin-kepu-flow/references/selectors.md](douyin-kepu-flow/references/selectors.md)
3. 必要时调整 `flow/navigate.py` 中的文案正则

## 环境变量

| 变量 | 默认 | 说明 |
|------|------|------|
| `FLOW_URL` | 固定 Flow 项目页 URL | Flow 入口 |
| `FLOW_CDP_PORT` | 9335 | Chromium CDP 端口 |
| `FLOW_BROWSER_PROFILE` | ~/.hermes/flow-browser | 登录态 |
| `FLOW_GENERATION_TIMEOUT_SEC` | 300 | 单段生成超时 |
| `FLOW_GENERATION_RETRIES` | 2 | 失败重试次数 |
| `FLOW_DOWNLOAD_DIR` | Desktop/douyin-videos/{topic} | 下载目录 |
| `JIANYING_EXE` | %LOCALAPPDATA%\JianyingPro\Apps\JianyingPro.exe | 剪映路径 |
| `JIANYING_SPLIT_SENTENCE_TIMEOUT_SEC` | 300 | 自动拆句等待超时 |

## 常见问题

**Q: 提示未找到「新建项目」或「生成」按钮？**  
A: Google Flow UI 可能已改版。提供页面 HTML 更新 selectors。

**Q: 生成超时？**  
A: 在 `.env` 增大 `FLOW_GENERATION_TIMEOUT_SEC`（Flow 免费档排队可能较久）。

**Q: 剪映能自动剪辑吗？**  
A: 可以。手动下载 10 段 mp4 后运行 `run_jianying_compose.ps1`（或 Hermes `/auto-douyin-jianying-compose`）。导出成片仍建议手动确认。

## 示例

完整示例见 [douyin-kepu-flow/prompts/example-bank-lending/](douyin-kepu-flow/prompts/example-bank-lending/)（选题：银行为什么愿意借钱给你）。
