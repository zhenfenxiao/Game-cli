# 快速入门

OpenGame 是一个开源 AI 代理框架，能够根据自然语言描述自动生成完整的 Phaser 3 + TypeScript + Vite 网页游戏。

## 环境要求

- Python 3.11 或更高版本
- uv（推荐包管理器）
- Node.js 18+（用于构建和测试生成的游戏）

## 安装

```bash
git clone https://github.com/leigest519/OpenGame.git
cd OpenGame

uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

## 最快开始：使用 .env 配置

项目根目录下已有 `.env` 文件（包含示例配置），CLI 命令会自动加载它。

**只需 2 步：**

```bash
# 1. 编辑 .env，填入你的 API 密钥
#    （LLM 必需，Image/Audio 可选）

# 2. 验证配置
python -m opengame config show
```

### .env 文件关键配置

```bash
# LLM（必需）— 驱动整个 agent
OPENAI_API_KEY=sk-your-key-here
OPENAI_BASE_URL=https://api.deepseek.com    # 或其他 OpenAI 兼容 API
OPENAI_MODEL=deepseek-v4-pro

# 图片生成（可选）— 生成游戏精灵和背景
OPENGAME_IMAGE_PROVIDER=tongyi
OPENGAME_IMAGE_API_KEY=sk-your-key-here
# OPENGAME_IMAGE_MODEL=wan2.5-t2i-preview

# 音频生成（可选）— 生成 BGM 和音效
# 注意：DeepSeek 不支持 TTS，需配置真实 OpenAI 或其他支持 /v1/audio/speech 的 provider
# OPENGAME_AUDIO_PROVIDER=openai-compat
# OPENGAME_AUDIO_API_KEY=sk-your-key-here
```

> 详见 [API 提供商配置](./api-providers.md) 了解完整的 provider 选项。

## 验证安装

```bash
python -m opengame --version     # opengame v0.6.0
python -m opengame --help        # 查看所有命令
python -m opengame config show   # 查看当前生效的配置
python -m opengame config validate  # 检查配置完整性
```

## 可用命令

| 命令 | 说明 | 状态 |
|------|------|------|
| `config show` | 显示当前配置（含 .env 加载） | ✅ |
| `config init` | 创建全局配置文件模板 | ✅ |
| `config validate` | 验证配置完整性 | ✅ |
| `generate -p "..."` | 6 阶段游戏生成 | ✅ |
| `debug <path>` | Algorithm 1 调试循环 | ✅ |
| `evolve <path>` | 模板库进化（从成品学习） | ✅ |

## 生成第一个游戏

```bash
# 需要有模板目录和 LLM API key
python -m opengame generate -p "Build a simple Snake clone with WASD controls"
```

## 运行测试

```bash
pytest                          # 203 个测试
pytest tests/unit/core/         # 特定模块
pytest --cov=opengame           # 覆盖率报告
```

## 项目架构

```
opengame/
├── cli/          # Typer CLI（config/generate/debug/evolve）
├── core/         # Agent 运行时（TurnLoop、ToolRegistry、LLM 客户端、压缩系统）
├── tools/        # 21 个 Agent 工具（文件、shell、web、game、task）
├── skills/       # 游戏技能（Template Skill、Debug Skill、GameSkill 编排器）
├── services/     # 异步服务（文件 I/O、shell 执行、资产管线）
├── config/       # Pydantic v2 配置模型
└── utils/        # 工具（异常、重试、JSON、token 计数）
```

## 项目状态

| Phase | 内容 | 测试数 | 状态 |
|-------|------|--------|------|
| Phase 1 | Foundation | 116 | ✅ |
| Phase 2 | Agent Runtime | 168 | ✅ |
| Phase 3 | Game Skill | 203 | ✅ |
| Phase 4 | Asset Pipeline | 203 | ✅ |
| Phase 5 | Integration | — | 📋 |
| Phase 6 | Bench + Polish | — | 📋 |

## 下一步

- [API 提供商配置](./api-providers.md) — 配置 LLM、图片、音频 provider
- [配置指南](./configuration.md) — 完整的 5 层配置系统说明
- [CLI 命令参考](./cli-reference.md) — 所有命令的详细参数
- [架构概述](./architecture.md) — 系统架构和设计决策
- [技能使用指南](./skills.md) — Template Skill、Debug Skill、GameSkill
