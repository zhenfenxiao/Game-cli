# 快速入门

OpenGame 是一个开源 AI 代理框架，能够根据自然语言描述自动生成完整的网页游戏。

## 环境要求

- Python 3.11 或更高版本
- uv（推荐的包管理器）

## 安装

```bash
# 克隆仓库
git clone https://github.com/leigest519/OpenGame.git
cd OpenGame

# 创建虚拟环境
uv venv
source .venv/bin/activate

# 安装 OpenGame（含开发依赖）
uv pip install -e ".[dev]"
```

## 验证安装

```bash
# 查看版本
python -m opengame --version
# 输出: opengame v0.6.0

# 查看帮助
python -m opengame --help

# 查看当前配置
python -m opengame config show
```

## 配置 API 密钥

OpenGame 需要 LLM API 密钥才能生成游戏。运行以下命令创建配置文件：

```bash
# 创建配置文件模板
python -m opengame config init

# 编辑配置文件，填入你的 API 密钥
# 文件路径: ~/.opengame/settings.json
```

或者通过环境变量配置：

```bash
export OPENAI_API_KEY="sk-your-key-here"
export OPENAI_MODEL="gpt-4o"
```

## 可用命令

| 命令 | 说明 | 状态 |
|------|------|------|
| `config show` | 显示当前配置 | ✅ 可用 |
| `config init` | 创建配置文件模板 | ✅ 可用 |
| `config validate` | 验证配置完整性 | ✅ 可用 |
| `generate` | 生成游戏（根据提示词） | 🚧 Phase 5 |
| `debug` | 调试游戏项目 | 🚧 Phase 3 |
| `evolve` | 进化模板库 | 🚧 Phase 3 |

## 运行测试

```bash
# 运行所有测试
pytest

# 运行特定模块测试
pytest tests/unit/utils/

# 带覆盖率报告
pytest --cov=opengame
```

## 项目状态

当前 Phase 1（基础搭建）已完成，包括：

- 项目脚手架和包结构
- 配置系统（Pydantic 模型 + 5 层合并）
- CLI 接口（Typer + Rich）
- 核心运行时基础（工具注册表、LLM 客户端）
- 基础服务（异步文件 I/O、shell 执行、文件发现）
- 完整的单元测试覆盖（116 个测试）

后续阶段将逐步实现游戏生成、资产管线、评估体系等功能。
