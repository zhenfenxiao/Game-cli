# API 提供商配置

OpenGame 使用多个独立的 API 提供商来驱动不同的功能模块。每个模块独立配置，可以混用不同厂商。

## 配置方式

OpenGame 的 API 配置支持 3 种方式，优先级从高到低：

1. **`.env` 文件**（推荐，命令行自动加载）
2. **`~/.opengame/settings.json`**（全局配置）
3. **`.opengame/settings.json`**（项目级配置）

### .env 文件配置（推荐）

在项目根目录创建或编辑 `.env` 文件：

```bash
# LLM — 驱动 agent 主循环
OPENAI_API_KEY=sk-xxxxxx
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_MODEL=deepseek-v4-pro

# 图片生成 — 游戏精灵和背景
OPENGAME_IMAGE_PROVIDER=tongyi
OPENGAME_IMAGE_API_KEY=sk-xxxxxx

# 音频生成 — BGM 和音效
OPENGAME_AUDIO_PROVIDER=openai-compat
OPENGAME_AUDIO_API_KEY=sk-xxxxxx
```

### 验证配置

```bash
opengame config show
```

---

## LLM 提供商

LLM 是**必需**的，驱动整个 agent 的游戏生成能力。

| Provider | 说明 | 兼容 API | 测试状态 |
|----------|------|----------|----------|
| `deepseek` | DeepSeek | OpenAI-compat | ✅ `deepseek-v4-pro` 可用 |
| `openai` | OpenAI 官方 | OpenAI 原生 | 待验证 |
| `openrouter` | OpenRouter | OpenAI-compat | 待验证 |
| `anthropic` | Anthropic Claude | 独立 API | 待验证 |
| `dashscope` | 阿里 DashScope（千问）| OpenAI-compat | 待验证 |

```bash
# DeepSeek（.env 示例）
OPENAI_API_KEY=sk-xxxxxx
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_MODEL=deepseek-v4-pro

# OpenAI 官方
OPENAI_API_KEY=sk-xxxxxx
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o
```

> **注意**：`deepseek-v4-pro` 是推理模型，reasoning tokens 计入 `max_tokens` 预算，需要至少 4096 max_tokens（代码已自动处理）。如果手动测试时 `max_tokens` 太小（如 10），回复会为空。该模型也可能不支持同时设置 `temperature`（代码检测到推理模型时自动省略 temperature）。

---

## 图片生成（可选）

用于生成游戏精灵、背景、图标、tileset 等。

| Provider | 说明 | 格式 | 状态 |
|----------|------|------|------|
| `tongyi` | 阿里 Tongyi Wanx（DashScope） | 自定义 API | ✅ 已验证 |
| `openai-compat` | OpenAI DALL-E 兼容 | `/v1/images/generations` | 待验证 |
| `doubao` | 字节豆包（Seedream） | 自定义 API | 🚧 stub |
| `fal` | fal.ai | 自定义 API | 🚧 stub |

### Tongyi 配置

```bash
OPENGAME_IMAGE_PROVIDER=tongyi
OPENGAME_IMAGE_API_KEY=sk-xxxxxx
# 可选：自定义 model（默认 wan2.5-t2i-preview）
# OPENGAME_IMAGE_MODEL=wan2.5-t2i-preview
```

**Tongyi 参数限制**：
- 最小尺寸：768×768（589,824 pixels）
- 尺寸格式：`1024*1024`（用 `*` 不用 `x`）
- 只支持异步模式（需 `X-DashScope-Async: enable` header，代码已自动处理）

### OpenAI 兼容配置

```bash
OPENGAME_IMAGE_PROVIDER=openai-compat
OPENGAME_IMAGE_API_KEY=sk-xxxxxx
OPENGAME_IMAGE_BASE_URL=https://api.openai.com/v1   # 或兼容 endpoint
OPENGAME_IMAGE_MODEL=dall-e-3
```

---

## 音频生成（可选）

用于生成 BGM（背景音乐）和 SFX（音效）。

| Provider | 说明 | Endpoint | 状态 |
|----------|------|----------|------|
| `openai-compat` | OpenAI TTS 兼容 | `/v1/audio/speech` | 需真实 OpenAI key |
| `tongyi` | 阿里 Tongyi | 自定义 API | 🚧 stub |
| `doubao` | 字节豆包 | 自定义 API | 🚧 stub |

```bash
# 需要真实的 OpenAI TTS endpoint
OPENGAME_AUDIO_PROVIDER=openai-compat
OPENGAME_AUDIO_API_KEY=sk-xxxxxx
OPENGAME_AUDIO_MODEL=tts-1   # 或 tts-1-hd
```

> **注意**：DeepSeek 不支持 `/v1/audio/speech` endpoint（404），即使 `base_url` 指向 DeepSeek 也无法使用音频功能。需要提供真正的 OpenAI API key 或其他支持 TTS 的 API。

---

## 视频生成（可选，🚧 stub）

| Provider | 状态 |
|----------|------|
| 所有 | 🚧 stub（Sora/Wan Video/Seedance API 尚不稳定，等待后续版本） |

---

## Reasoning 模型（可选）

用于 GDD 生成和 classify-game-type 等推理密集型任务：

```bash
OPENGAME_REASONING_PROVIDER=openai-compat
OPENGAME_REASONING_API_KEY=sk-xxxxxx
OPENGAME_REASONING_BASE_URL=https://api.deepseek.com
OPENGAME_REASONING_MODEL=deepseek-v4-pro
```

---

## 快速排错

### LLM 返回空内容（HTTP 200）

model name 不对。尝试：
```bash
OPENAI_MODEL=deepseek-v4-pro   # DeepSeek
OPENAI_MODEL=gpt-4o          # OpenAI
```

### 图片生成 HTTP 403

Tongyi **同步** API 返回 403，必须用异步模式。代码已自动处理（`X-DashScope-Async: enable`）。

### 音频 404

当前 provider 不支持 TTS endpoint。DeepSeek 无音频能力。需换成真实的 OpenAI API 或其他支持 `/v1/audio/speech` 的服务。
