# CLI 命令参考

OpenGame 提供命令行接口，通过 `opengame` 调用。

## 全局选项

```
opengame [全局选项] <命令> [命令选项]
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
opengame config show

# JSON 格式输出
opengame config show --raw
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
opengame config init
```

#### config validate

检查配置完整性，报告缺失的 API 密钥和其他问题。

```bash
opengame config validate
```

---

### generate — 游戏生成 ✅

从自然语言提示词生成完整网页游戏（6-phase pipeline）。

```bash
opengame generate -p "Build a Snake clone with WASD controls and a dark theme"

# 指定输出目录
opengame generate -p "A platformer game" -o ./my-game

# 指定模型
opengame generate -p "..." -m gpt-4o-mini
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
opengame debug ./my-game

# 自动修复模式
opengame debug ./my-game --auto-fix

# 限制调试迭代次数
opengame debug ./my-game --max-iterations 10
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
opengame evolve ./my-game

# 预览模式（不写入）
opengame evolve ./my-game --dry-run

# 指定模板库路径
opengame evolve ./my-game --library ./my-templates
```

| 选项 | 简写 | 说明 |
|------|------|------|
| `PROJECT_PATH` | — | 项目路径（必填，位置参数） |
| `--library` | `-l` | 模板库路径 |
| `--dry-run` | — | 预览变更，不实际写入 |
| `--verbose` | — | 详细输出 |

> **当前状态（Phase 3）**：✅ 完整的 Collect→Classify→Extract→Abstract→Merge→Save 管道已实现。支持 dry-run 预览。

---

### traces — 轨迹查看 ✅

浏览、查看和导出 agent trace 记录。

每次 `opengame generate` 会自动记录完整的生成过程到 SQLite 数据库（`.opengame/traces/traces.db`）。

**列出最近的 sessions：**

```bash
opengame traces list
opengame traces list -n 50
```

输出示例：
```
          Trace Sessions (last 3)
┏━━━━┳━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━┓
┃ ID ┃ Prompt             ┃ Model          ┃ Status ┃ Start                 ┃
┡━━━━╇━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━┩
│ 3  │ Build a Snake...   │ deepseek-v4-   │ ✓      │ 2026-05-30T14:30:00   │
│ 2  │ A platformer...    │ deepseek-v4-   │ ✗      │ 2026-05-30T13:00:00   │
│ 1  │ Test game          │ deepseek-v4-   │ ✓      │ 2026-05-30T12:00:00   │
└────┴────────────────────┴────────────────┴────────┴───────────────────────┘
```

**查看某次 session 的详细信息：**

```bash
opengame traces show 3
```

输出包括各阶段耗时、LLM 调用、工具执行和错误信息的时间线。

**导出为 JSON（用于模型训练或分析）：**

```bash
# 导出所有 sessions
opengame traces export

# 导出指定 session
opengame traces export -s 3

# 自定义输出目录
opengame traces export -o ./training-data

# 紧凑格式
opengame traces export --compact
```

导出格式：`{ "session": {id, prompt, model, success, ...}, "events": [{seq, phase, event_type, data, timestamp}, ...] }`

> **存储位置**：`.opengame/traces/traces.db`（SQLite）。每次 generate 自动记录，无需额外配置。

---

## 退出码

| 退出码 | 说明 |
|--------|------|
| 0 | 成功 |
| 1 | 一般错误 |
| 2 | 用户中断（Ctrl+C） |
