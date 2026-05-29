# 配置指南

OpenGame 使用 **5 层优先级模型** 合并配置，从高到低依次为：

```
CLI 参数 > 环境变量 > 项目设置 > 用户设置 > 内置默认值
```

## 配置文件

### 用户设置（全局）

路径：`~/.opengame/settings.json`

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
    "model": "wanx-v1"
  },
  "audio": {
    "provider": "openai",
    "api_key": "sk-your-key-here",
    "model": "tts-1"
  },
  "video": {
    "provider": "doubao",
    "api_key": "sk-your-key-here"
  },
  "reasoning": {
    "provider": "openai",
    "api_key": "sk-your-key-here",
    "model": "o3-mini"
  },
  "game_skill": {
    "templates_dir": "agent-test/templates",
    "docs_dir": "agent-test/docs",
    "max_debug_iterations": 20,
    "evolve_after_debug": true
  },
  "approval_mode": "auto-edit",
  "verbose": false,
  "telemetry": true
}
```

创建配置文件模板：

```bash
python -m opengame config init
```

### 项目设置（项目级）

路径：`.opengame/settings.json`（项目根目录）

与用户设置相同的 JSON 格式。项目设置会覆盖用户设置，适合为不同项目使用不同的 LLM 模型或配置。

## 环境变量

| 环境变量 | 映射配置项 | 说明 |
|----------|-----------|------|
| `OPENAI_API_KEY` | `llm.api_key` | LLM API 密钥 |
| `OPENAI_BASE_URL` | `llm.base_url` | LLM API 地址 |
| `OPENAI_MODEL` | `llm.model` | 默认模型 |
| `OPENGAME_IMAGE_PROVIDER` | `image.provider` | 图片生成提供商 |
| `OPENGAME_IMAGE_API_KEY` | `image.api_key` | 图片 API 密钥 |
| `OPENGAME_AUDIO_PROVIDER` | `audio.provider` | 音频生成提供商 |
| `OPENGAME_AUDIO_API_KEY` | `audio.api_key` | 音频 API 密钥 |
| `OPENGAME_VIDEO_PROVIDER` | `video.provider` | 视频生成提供商 |
| `OPENGAME_VIDEO_API_KEY` | `video.api_key` | 视频 API 密钥 |
| `GAME_TEMPLATES_DIR` | `game_skill.templates_dir` | 模板目录 |
| `GAME_DOCS_DIR` | `game_skill.docs_dir` | 文档目录 |

## 配置项详解

### LLM 配置（llm）

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `provider` | string | `"openai"` | 提供商：openai, anthropic, dashscope, deepseek, openrouter |
| `api_key` | string | null | API 密钥 |
| `base_url` | string | `"https://api.openai.com/v1"` | API 地址 |
| `model` | string | `"gpt-4o"` | 模型名称 |
| `temperature` | float | 0.7 | 采样温度（0.0-2.0） |
| `max_tokens` | int | 4096 | 最大输出 token 数 |
| `timeout` | int | 120 | 请求超时（秒） |

### 审批模式（approval_mode）

| 模式 | 说明 |
|------|------|
| `ask` | 每次操作前询问用户 |
| `auto-edit` | 自动编辑，但重大变更需确认 |
| `yolo` | 全自动，不询问 |

## 查看和验证配置

```bash
# 查看当前生效配置
python -m opengame config show

# 输出 JSON 格式（适合脚本处理）
python -m opengame config show --raw

# 验证配置完整性
python -m opengame config validate
```
