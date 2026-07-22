# Auto Douyin · Hermes 路由

本目录供 Hermes Agent 加载。项目代码与脚本在 `e:\Auto_douyin\douyin-kepu-flow\`。

## 凭据与环境

- Flow 浏览器 Profile：`%USERPROFILE%\.hermes\flow-browser`（Google 登录态）
- 无需额外 API Key（选题与 prompt 由 Agent 内置生成）
- Python 虚拟环境：`e:\Auto_douyin\.venv`
- 剪映路径：`%LOCALAPPDATA%\JianyingPro\Apps\JianyingPro.exe`（可在 `.env` 覆盖）

## 路由

| 用户说法 | 加载 skill | 动作 |
|----------|-----------|------|
| `/auto-douyin-kepu-flow` | `auto-douyin-kepu-flow` | 按 SKILL.md 三阶段执行 |
| 给我科普选题 / 本周做什么视频 | 同上 | 阶段 1：列出 5–8 条选题 |
| 选第 N 个 / 做「XXX」这个题目 | 同上 | 阶段 2：生成 prompts.json + editing_guide.md |
| 开始生成 / 提交 Flow / 批量生成视频 | 同上 | 阶段 3：run_batch.ps1 |
| `/auto-douyin-jianying-compose` | `auto-douyin-jianying-compose` | 剪映 UI 自动合成 |
| 剪映合成 / 自动剪辑配音 / 导入剪映 | 同上 | 校验 VideoDir → run_jianying_compose.ps1 |

## 部署

在 `e:\Auto_douyin` 执行：

```powershell
powershell -ExecutionPolicy Bypass -File hermes-skill-bundles\deploy.ps1
```

然后在 Hermes 对话发送：`/reload-skills`

## 斜杠命令

```
/auto-douyin-kepu-flow
/auto-douyin-kepu-flow 给我5个金融科普选题
/auto-douyin-jianying-compose
/auto-douyin-jianying-compose 剪映合成 buffet-profit-secret
```
