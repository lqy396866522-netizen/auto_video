# 统一风格前缀 + 10 段 Prompt 模板

## 统一风格前缀（每段 visual_prompt_en 前必须拼接）

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

## 10 段叙事结构（60 秒）

| 段号 | 时长 | 叙事功能 | narration_zh 要点 |
|------|------|----------|-------------------|
| 1 | 6s | 反常识钩子 | 打破常见误解，抛出核心问题 |
| 2 | 6s | 机制引入 | 用最简模型说明「它怎么运作」 |
| 3 | 6s | 核心原理 1 | 第一个关键概念 |
| 4 | 6s | 核心原理 2 | 第二个关键概念 |
| 5 | 6s | 转折/深入 | 「但为什么是这样？」 |
| 6 | 6s | 证据/机制细节 | 具体规则、流程或数据逻辑 |
| 7 | 6s | 风险/约束 | 限制条件、边界情况 |
| 8 | 6s | 后果/案例 | 不遵守会怎样 |
| 9 | 6s | 回归主题 | 直接回答开头的问题 |
| 10 | 6s | 行动启示 | 给观众的 takeaway，理性、不煽动 |

## 单段输出格式

每段必须包含：

1. **narration_zh**：中文旁白要点（15–30 字，口语化，适合配音）
2. **visual_prompt_en**：英文画面描述（不含风格前缀；生成 JSON 时与 `style_prefix` 拼接后写入 Flow）

### visual_prompt_en 写作规则

- 只描述**这一 6 秒**内的画面与动作，不要写整片剧情
- 用具体可视元素：人物动作、图标、箭头、图表、标签
- 画面中如需文字，在 visual 描述里注明「简体中文字标签：XXX」；否则用图标代替
- 禁止写实摄影、3D 渲染、电影镜头语言
- 禁止英文可见文字、乱码、假文字
- 每段画面应能独立成 clip，风格与前后段一致

## JSON 落盘格式

选定选题并生成 10 段后，写入：

```
douyin-kepu-flow/prompts/{slug}/prompts.json
```

```json
{
  "topic": "选题中文标题",
  "slug": "kebab-case-slug",
  "style_prefix": "Modern flat vector illustration...",
  "aspect_ratio": "16:9",
  "duration_sec_per_segment": 6,
  "segments": [
    {
      "index": 1,
      "duration_sec": 6,
      "narration_zh": "...",
      "visual_prompt_en": "..."
    }
  ]
}
```

## Flow 实际提交的 prompt 文本

Playwright 脚本会将每段提交为：

```
{style_prefix}

{visual_prompt_en}
```

## 剪辑清单（editing_guide.md）

生成 prompts.json 后，同步在同目录写 `editing_guide.md`，包含：

- 选题标题
- 总时长估算（10 × 6s = 60s）
- 表格：段号 | 时间轴 | narration_zh | 文件名 seg-01.mp4 … seg-10.mp4

时间轴格式：`00:00–00:06`、`00:06–00:12` …

## 整段旁白文案（narration_script）

除分段 `narration_zh` 外，必须生成整段口播文案：

- JSON 字段：`narration_script`（10 段旁白首尾相接，无时间轴）
- 同目录文件：`narration_script.txt`（纯文本，方便复制到剪映/TTS）

示例：

```
几十块钱随便吃的自助餐，老板为什么不亏钱？秘密不在菜好不好吃，而在于整个餐厅的精心布局。第一招：动线设计。……
```
