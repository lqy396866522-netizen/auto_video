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

每段 prompt：

1. 写入 prompt
2. 等待「创建」按钮可点击
3. 点击「创建」
4. （`--submit-only`）清空输入框 → 下一段
5. （默认 full 模式）等待生成完成 → 下载 → 清空输入框 → 下一段

## 登录

默认 `--require-login` 未传时跳过登录检测。若打开 Google 账号页，可传 `--require-login` 等待人工登录。
