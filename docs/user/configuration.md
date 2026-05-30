# 配置指南

OpenGame 使用 **5 层优先级模型** 合并配置，从高到低：

```
CLI 参数 > 环境变量 > 项目设置 > 用户设置 > 内置默认值
```

## 推荐方式：.env 文件

在项目根目录创建 `.env` 文件，CLI 命令自动加载（无需手动 export）：

```bash
# LLM（必需）
OPENAI_API_KEY=sk-your-key-here
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_MODEL=deepseek-v4-pro

# 图片生成（可选，Tongyi 已验证可用）
OPENGAME_IMAGE_PROVIDER=tongyi
OPENGAME_IMAGE_API_KEY=sk-your-key-here

# 音频生成（可选，需要支持 TTS 的 API）
# OPENGAME_AUDIO_PROVIDER=openai-compat
# OPENGAME_AUDIO_API_KEY=sk-your-key-here
```

> `.env` 文件最终通过 `python-dotenv` 加载到 `os.environ`，等价于环境变量层。

## 配置文件

### 用户设置（全局）

路径：`~/.opengame/settings.json`

```bash
python -m opengame config init   # 创建配置文件模板
```

```json
{
  "llm": {
    "provider": "openai",
    "api_key": "sk-your-key-here",
    "base_url": "https://api.openai.com/v1",
    "model": "gpt-4o",
    "temperature": 0.7,
    "max_tokens": 4096,
    "timeout": 120
  },
  "image": {
    "provider": "tongyi",
    "api_key": "your-image-api-key",
    "model": "wan2.5-t2i-preview"
  },
  "audio": {
    "provider": "openai",
    "api_key": "your-audio-api-key",
    "model": "tts-1"
  },
  "game_skill": {
    "templates_dir": "agent-test/templates",
    "docs_dir": "agent-test/docs",
    "max_debug_iterations": 20,
    "evolve_after_debug": true
  },
  "approval_mode": "auto-edit",
  "verbose": false
}
```

### 项目设置（项目级）

路径：`.opengame/settings.json`（当前项目根目录）

与用户设置相同的 JSON 格式。项目设置会覆盖用户设置，适合为不同项目使用不同的 LLM 模型或配置。

---

## 环境变量完整映射

| 环境变量 | 映射配置项 | 类型 | 说明 |
|----------|-----------|------|------|
| `OPENAI_API_KEY` | `llm.api_key` | string | LLM API 密钥 |
| `OPENAI_BASE_URL` | `llm.base_url` | string | LLM API 地址 |
| `OPENAI_MODEL` | `llm.model` | string | LLM 模型名称 |
| `OPENGAME_IMAGE_PROVIDER` | `image.provider` | string | 图片 provider（tongyi/openai-compat/doubao/fal） |
| `OPENGAME_IMAGE_API_KEY` | `image.api_key` | string | 图片 API 密钥 |
| `OPENGAME_IMAGE_BASE_URL` | `image.base_url` | string | 图片 API 地址 |
| `OPENGAME_IMAGE_MODEL` | `image.model` | string | 图片生成模型 |
| `OPENGAME_AUDIO_PROVIDER` | `audio.provider` | string | 音频 provider |
| `OPENGAME_AUDIO_API_KEY` | `audio.api_key` | string | 音频 API 密钥 |
| `OPENGAME_AUDIO_MODEL` | `audio.model` | string | 音频模型 |
| `OPENGAME_VIDEO_PROVIDER` | `video.provider` | string | 视频 provider（🚧 stub） |
| `OPENGAME_VIDEO_API_KEY` | `video.api_key` | string | 视频 API 密钥 |
| `OPENGAME_REASONING_PROVIDER` | `reasoning.provider` | string | 推理 provider |
| `OPENGAME_REASONING_API_KEY` | `reasoning.api_key` | string | 推理 API 密钥 |
| `OPENGAME_REASONING_MODEL` | `reasoning.model` | string | 推理模型 |
| `GAME_TEMPLATES_DIR` | `game_skill.templates_dir` | path | 模板目录 |
| `GAME_DOCS_DIR` | `game_skill.docs_dir` | path | 文档目录 |

---

## 配置项详解

### LLM 配置（config.llm）

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `provider` | string | `"openai"` | openai / anthropic / dashscope / deepseek / openrouter |
| `api_key` | string | null | API 密钥 |
| `base_url` | string | `"https://api.openai.com/v1"` | API 地址 |
| `model` | string | `"gpt-4o"` | 模型名称 |
| `temperature` | float | 0.7 | 采样温度（0.0-2.0） |
| `max_tokens` | int | 4096 | 最大输出 token 数 |
| `timeout` | int | 120 | 请求超时（秒） |

### 资产生成（config.image / config.audio / config.video）

每个独立配置，不配置则代表该功能不启用。

| 字段 | 类型 | 说明 |
|------|------|------|
| `provider` | string | 提供商名称（详见 [API 提供商](./api-providers.md)） |
| `api_key` | string | API 密钥 |
| `base_url` | string | API 地址（可选） |
| `model` | string | 模型名称（可选） |

### Game Skill 配置（config.game_skill）

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `templates_dir` | path | `agent-test/templates` | 模板目录 |
| `docs_dir` | path | `agent-test/docs` | 文档目录 |
| `archetypes_dir` | path | `agent-test/templates/modules` | 原始类型模块 |
| `library_output_dir` | path | `.opengame/template-library` | 模板库输出目录 |
| `protocol_output_dir` | path | `.opengame/debug-protocol` | Debug protocol 输出 |
| `max_debug_iterations` | int | 20 | 最大调试迭代次数（1-100） |
| `evolve_after_debug` | bool | true | 调试后是否进化 protocol |

### 审批模式（config.approval_mode）

| 模式 | 说明 |
|------|------|
| `ask` | 每次操作前询问用户 |
| `auto-edit` | 自动编辑，但重大变更需确认 |
| `yolo` | 全自动，不询问 |

## 查看和验证

```bash
python -m opengame config show              # 格式化输出
python -m opengame config show --raw        # JSON 格式
python -m opengame config validate          # 检查配置完整性
python -m opengame config init              # 创建全局配置文件
```
