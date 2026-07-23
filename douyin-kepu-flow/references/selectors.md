# Google Flow 页面选择器（基于用户提供的 html.txt）

## URL

| 页面 | URL |
|------|-----|
| 固定项目页 | `https://labs.google/fx/zh/tools/flow/project/147a46cc-6217-4b1f-a162-e5bcfcd96b9b` |

默认打开此 URL，**不再点击「新建项目」**。默认假定已登录。

## Prompt 输入框

| 属性 | 值 |
|------|-----|
| 定位锚点 | placeholder 文案：`您希望创作什么内容？` |
| 编辑器 | `div[role="textbox"][contenteditable="true"][data-slate-editor="true"]` |
| 类型 | Slate 富文本（不可用 `.fill()`，需 keyboard） |

**操作**：

1. 通过 `get_by_text("您希望创作什么内容？")` 向上找 `role=textbox` 祖先
2. `Ctrl+A` → `Backspace` 清空
3. `keyboard.insert_text(prompt)` 写入

## 提交按钮「创建」

| 属性 | 值 |
|------|-----|
| 图标 | `i.google-symbols` 文案 `arrow_forward` |
| 无障碍文案 | span 内隐藏文本 `创建` |
| 空输入时 | `aria-disabled="true"` |
| 有 prompt 后 | `aria-disabled` 移除或变为 false |

**注意**：页面上有两个「创建」按钮；带 `add_2` 图标的是菜单，**不要点**。只点 `arrow_forward` 那个。

```python
page.locator("button").filter(has=page.locator("i.google-symbols", has_text="arrow_forward")).last
```

## 生成参数

使用页面默认值（HTML 中可见 `视频 · 6s`、画幅 **16:9**），脚本**不修改**模型；若需切换画幅可在 `.env` 设置 `FLOW_ASPECT_RATIO=16:9`。

## 批处理循环

N = `len(prompts.json.segments)`。每段 prompt：

1. 写入 prompt
2. 等待「创建」按钮可点击（默认最长 120s，`.env` 可配 `FLOW_CREATE_BUTTON_TIMEOUT_SEC`）
3. 点击「创建」
4. 清空输入框 → 立即提交下一段（**不等单段生成完成**，Flow 支持并行排队）
5. 全部 N 段提交后，轮询 tile 网格 → 720p 下载

（`--submit-only`）仅执行步骤 1–4，不监听/下载。

## 登录

默认 `--require-login` 未传时跳过登录检测。若打开 Google 账号页，可传 `--require-login` 等待人工登录。

## 项目页视频网格（tile）

| 状态 | 定位 |
|------|------|
| 任意 tile | `[data-tile-id="fe_id_..."]` |
| **生成中** | 卡片内 `.sc-40f16b33-7` 含 `\d+%`；或模糊层 `sc-784d6f75-0 cFXNwK` 且无 `video[src]` |
| **已完成** | 卡片内 `sc-e731e35e-0` + `video[src*="getMediaUrlRedirect"]` |
| **失败** | `.sc-101009f9-1` 文案 **失败** |

DOM 顺序：**最新提交的 tile 在最前**。提交前 snapshot baseline，只跟踪新增的 N 个 tile。

## 下载菜单（720p）

已完成 tile 需先 **hover** 卡片，再点 `more_vert` 三点按钮（悬停时才渲染）。

| 步骤 | 定位 |
|------|------|
| 三点菜单 | tile 内 `button` + `i.google-symbols` 文案 `more_vert` |
| 下载 | `[role="menuitem"]` 含 **下载** / `download` 图标 |
| 720p | hover「下载」后，`[role="menuitem"]` 匹配 `/720\s*p/i`（如 **720p (原始尺寸)**） |

## `--watch-and-download` 模式

1. `N = len(prompts.json.segments)`
2. baseline snapshot → 快速 submit N 段 → 每段捕获新 `data-tile-id`
3. 轮询直到 N 段终态（完成/失败）
4. 已完成段：hover → 三点 → 下载 → 720p → 保存 `D:\douyin-videos\{中文topic}\{index:02d}.mp4`
5. 写 `batch_report.json` 后结束
