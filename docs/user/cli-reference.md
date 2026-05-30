# CLI 命令参考

OpenGame 提供命令行接口，通过 `python -m opengame` 调用。

## 全局选项

```
python -m opengame [全局选项] <命令> [命令选项]
```

| 选项 | 简写 | 默认值 | 说明 |
|------|------|--------|------|
| `--version` | `-v` | — | 显示版本号并退出 |
| `--model` | `-m` | `gpt-4o` | 指定 LLM 模型 |
| `--approval-mode` | — | `auto-edit` | 审批模式：ask / auto-edit / yolo |
| `--verbose` | — | false | 显示详细输出 |
| `--output-dir` | `-o` | 当前目录 | 输出目录 |
| `--help` | — | — | 显示帮助信息 |

## 命令详解

### config — 配置管理

管理 OpenGame 的全局和项目配置。

#### config show

显示当前生效的完整配置（合并所有来源）。

```bash
python -m opengame config show

# JSON 格式输出
python -m opengame config show --raw
```

输出示例：

```
OpenGame Configuration

  LLM Provider: openai
  LLM Model: gpt-4o
  LLM Base URL: https://api.openai.com/v1
  Approval Mode: auto-edit

           Asset Providers
┏━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━┓
┃ Modality  ┃ Provider       ┃ Model ┃
┡━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━┩
│ Image     │ not configured │       │
│ Audio     │ not configured │       │
│ Video     │ not configured │       │
│ Reasoning │ not configured │       │
└───────────┴────────────────┴───────┘

Game Skill:
  Templates: agent-test/templates
  Docs: agent-test/docs
  Max Debug Iterations: 20
```

#### config init

创建用户配置文件模板（`~/.opengame/settings.json`）。

```bash
python -m opengame config init
```

#### config validate

检查配置完整性，报告缺失的 API 密钥和其他问题。

```bash
python -m opengame config validate
```

---

### generate — 游戏生成 ✅

从自然语言提示词生成完整网页游戏（6-phase pipeline）。

```bash
python -m opengame generate -p "Build a Snake clone with WASD controls and a dark theme"

# 指定输出目录
python -m opengame generate -p "A platformer game" -o ./my-game

# 指定模型
python -m opengame generate -p "..." -m gpt-4o-mini
```

| 选项 | 简写 | 说明 |
|------|------|------|
| `--prompt` | `-p` | 自然语言游戏描述（必填） |
| `--output-dir` | `-o` | 输出目录 |
| `--approval` | — | 审批模式 |
| `--model` | `-m` | LLM 模型 |
| `--verbose` | — | 详细输出 |

> **当前状态（Phase 4）**：✅ 完整 6-phase pipeline + 资产生成（Tongyi 图片已验证可用）

---

### debug — 游戏调试 ✅

诊断和修复游戏项目中的构建和运行错误（Algorithm 1 REPEAT...UNTIL）。

```bash
python -m opengame debug ./my-game

# 自动修复模式
python -m opengame debug ./my-game --auto-fix

# 限制调试迭代次数
python -m opengame debug ./my-game --max-iterations 10
```

| 选项 | 简写 | 说明 |
|------|------|------|
| `PROJECT_PATH` | — | 项目路径（必填，位置参数） |
| `--max-iterations` | `-n` | 最大调试迭代次数（默认 20） |
| `--auto-fix` | `-y` | 自动应用修复 |
| `--verbose` | — | 详细输出 |

> **当前状态（Phase 3）**：✅ Algorithm 1 REPEAT...UNTIL 循环已实现。支持自动诊断和修复构建/测试错误。

---

### evolve — 模板进化 ✅

从已有游戏项目学习并进化模板库。（Phase 3 实现）

```bash
python -m opengame evolve ./my-game

# 预览模式（不写入）
python -m opengame evolve ./my-game --dry-run

# 指定模板库路径
python -m opengame evolve ./my-game --library ./my-templates
```

| 选项 | 简写 | 说明 |
|------|------|------|
| `PROJECT_PATH` | — | 项目路径（必填，位置参数） |
| `--library` | `-l` | 模板库路径 |
| `--dry-run` | — | 预览变更，不实际写入 |
| `--verbose` | — | 详细输出 |

> **当前状态（Phase 3）**：✅ 完整的 Collect→Classify→Extract→Abstract→Merge→Save 管道已实现。支持 dry-run 预览。

---

## 退出码

| 退出码 | 说明 |
|--------|------|
| 0 | 成功 |
| 1 | 一般错误 |
| 2 | 用户中断（Ctrl+C） |
