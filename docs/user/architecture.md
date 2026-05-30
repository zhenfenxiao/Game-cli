# 系统架构

OpenGame 的分层架构，从 CLI 到底层服务。

---

## 总体架构

```
┌─────────────────────────────────────────────────────────────┐
│                     CLI Layer (Typer + Rich)                │
│  generate -p "..."  │  debug <path>  │  evolve <path>       │
│  config show        │  config init   │  config validate     │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                   Game Skill Layer                          │
│  ┌─────────────────────┐  ┌─────────────────────────────┐   │
│  │   Template Skill    │  │      Debug Skill            │   │
│  │  (Collect→Classify→  │  │  (REPEAT: build→test→     │   │
│  │   Extract→Abstract→  │  │   diagnose→repair→         │   │
│  │   Merge→Save)       │  │   verify→record)           │   │
│  └─────────────────────┘  └─────────────────────────────┘   │
│                              │                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              GameSkill Orchestrator                  │   │
│  │  Phase 1: Scaffold  →  Phase 2: GDD                 │   │
│  │  Phase 3: Assets    →  Phase 4: Config              │   │
│  │  Phase 5: Code      →  Phase 6: Debug               │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    Agent Runtime                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │  TurnLoop    │  │ ToolRegistry │  │  LLM Clients     │   │
│  │ (async REPL) │  │ (@tool 装饰器)│  │ (OpenAI-compat)  │   │
│  └──────────────┘  └──────────────┘  └──────────────────┘   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │ Compression  │  │  21 Tools    │  │  Content Gen    │   │
│  │ (4 strategies)│  │ (file/shell/ │  │  (LLM wrapper)  │   │
│  │              │  │  web/game/   │  │                  │   │
│  └──────────────┘  │  task/memory)│  └──────────────────┘   │
│                     └──────────────┘                        │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    Services Layer                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │  File System │  │    Shell     │  │  Asset Pipeline  │   │
│  │  (async I/O) │  │  (subprocess)│  │  (Image/Audio/   │   │
│  │              │  │              │  │   Video + Tiler) │   │
│  └──────────────┘  └──────────────┘  └──────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    Utils Layer                              │
│  errors │ retry │ json_utils │ token_counter │ edit_helper │
└─────────────────────────────────────────────────────────────┘
```

---

## 关键设计决策

### 1. 依赖注入：闭包模式

`smart_edit` 需要 LLM 客户端，`todo_write` 需要 TurnLoop，`subagent` 需要 TurnLoop — 这些依赖不能来自 LLM 的 JSON 参数。

```python
# factory.py — 在注册时注入依赖项
register_file_tools(registry, llm_client=llm_client)     # smart_edit 捕获 llm_client
register_task_tools(registry, turn_loop=turn_loop)       # todo_write 捕获 turn_loop
register_subagent_tool(registry, turn_loop=turn_loop)    # subagent 捕获 turn_loop
```

### 2. LLM 优先 + 回落确定性

Classifier、Abstractor、Diagnoser、Repairer 都遵循 "LLM 优先，失败时回落确定性算法" 模式：

```
try:
    result = await llm.generate(...)  # LLM 分析
except:
    result = deterministic_fallback()  # 关键词/正则/规则 回落
```

### 3. 5 层配置合并

```
CLI flags > Env vars > Project settings > User settings > Defaults
```

`.env` 文件通过 `python-dotenv` 加载到环境变量层，所有 CLI 命令默认开启。

### 4. 异步全栈

整个框架构建在 `asyncio` 之上：
- LLM API 调用（httpx）
- 文件系统操作（aiofiles）
- Shell 命令执行（asyncio subprocess）
- 资产生成（HTTP + 异步轮询）
- 工具调度（asyncio.gather 并行执行）

### 5. 21 个 Agent 工具

| 类别 | 工具 | 数量 |
|------|------|------|
| 文件 | read_file, read_many_files, write_file, edit, smart_edit, glob, grep, ls | 8 |
| Shell | shell | 1 |
| Web | web_fetch, web_search | 2 |
| 任务 | todo_write, task_create, task_update | 3 |
| 记忆 | save_memory | 1 |
| 控制 | exit_plan_mode | 1 |
| 游戏 | classify_game_type, generate_gdd, generate_game_assets, generate_tilemap | 4 |
| 子代理 | subagent | 1 |

---

## 模块依赖

```
cli/ → skills/ → core/ → tools/
  ↓       ↓        ↓       ↓
config/ → services/ → utils/
```

---

## 数据流：一次游戏生成

```
User Prompt
    → CLI generate.py
        → ConfigLoader.load(load_dotenv=True)  # .env → env vars → config
        → OpenAiClient(config.llm)             # OpenAI-compatible 客户端
        → AssetService(config)                 # 图片/音频/视频 provider
        → GameSkill.generate_game(prompt, output_dir)
            → Phase 1: classify → copy templates
            → Phase 2: LLM generates GDD.md
            → Phase 3: AssetService generates sprites/audio
            → Phase 4: edit gameConfig.json, main.ts
            → Phase 5: TurnLoop.run(system_prompt, prompt)
                → Agent uses 21 tools to implement code
                → Compression keeps context within limits
            → Phase 6: DebugSkill.debug(project_dir)
                → REPEAT: build → test → diagnose → repair → verify
        → GameResult (success, GDD, assets, debug trace)
```
