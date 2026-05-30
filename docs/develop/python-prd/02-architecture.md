# 02 — System Architecture

## 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        CLI Layer                            │
│  (Typer entry point, argument parsing, config loading,      │
│   Rich console for styled output and progress panels)       │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                      Agent Runtime                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │  Turn Loop   │  │ Tool Registry│  │  LLM Clients     │   │
│  │ (async loop) │  │ (decorator-  │  │ (OpenAI-compat,  │   │
│  │              │  │  based)      │  │  streaming)      │   │
│  └──────────────┘  └──────────────┘  └──────────────────┘   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │ File System  │  │  Shell Exec  │  │   MCP Support    │   │
│  │   Service    │  │   Service    │  │   (optional)     │   │
│  └──────────────┘  └──────────────┘  └──────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                      Game Skill                               │
│  ┌─────────────────────┐  ┌─────────────────────────────┐   │
│  │   Template Skill    │  │      Debug Skill            │   │
│  │  (classify, extract,│  │  (validate, build, test,    │   │
│  │   abstract, merge,  │  │   diagnose, repair, evolve) │   │
│  │   evolve library)   │  │                             │   │
│  └─────────────────────┘  └─────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    Asset Pipeline                             │
│  (Image / Audio / Video generation via provider HTTP APIs)    │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                    Evaluation (Bench)                         │
│  (Headless browser execution + VLM-based scoring)             │
└─────────────────────────────────────────────────────────────┘
```

## 2.2 Package Layout

```
opengame/                          # Root Python package
├── __init__.py
├── __main__.py                    # python -m opengame
│
├── cli/                           # CLI layer
│   ├── __init__.py
│   ├── main.py                    # Typer root app
│   ├── commands/
│   │   ├── generate.py            # opengame -p "..."
│   │   ├── debug.py               # opengame debug <path>
│   │   ├── evolve.py              # opengame evolve-templates
│   │   └── config.py              # opengame config
│   └── config_loader.py           # Merge CLI → env → project → user → defaults
│
├── core/                          # Agent runtime
│   ├── __init__.py
│   ├── turn_loop.py               # Main conversation loop
│   ├── tool_registry.py           # @tool decorator + dispatch
│   ├── tool_scheduler.py          # Async tool execution scheduling
│   ├── content_generator.py       # Abstraction over LLM content generation
│   ├── llm_client.py              # BaseLlmClient ABC
│   ├── openai_client.py           # OpenAI-compatible client
│   └── prompts.py                 # Prompt assembly with context injection
│
├── tools/                         # Tool implementations
│   ├── __init__.py
│   ├── file_tools.py              # read_file, write_file, edit, glob, grep, ls
│   ├── shell_tool.py              # Shell command execution
│   ├── web_tools.py               # web_fetch, web_search
│   ├── memory_tool.py             # save_memory
│   ├── todo_tool.py               # todo_write
│   ├── task_tool.py               # subagent delegation
│   ├── game_tools.py              # generate_gdd, generate_game_assets
│   │                              # classify_game_type, generate_tilemap
│   └── exit_plan_mode.py          # Exit planning mode
│
├── skills/                        # Game Skill
│   ├── __init__.py
│   ├── game_skill.py              # Main orchestrator
│   ├── template_skill/
│   │   ├── __init__.py
│   │   ├── classifier.py          # Archetype classification
│   │   ├── collector.py           # Project snapshot collection
│   │   ├── extractor.py           # Pattern extraction from source
│   │   ├── abstractor.py          # LLM-driven code generalization
│   │   ├── merger.py              # Template family merging
│   │   ├── library_manager.py     # Library CRUD + persistence
│   │   └── types.py               # Pydantic models
│   └── debug_skill/
│       ├── __init__.py
│       ├── debug_loop.py          # Algorithm 1 REPEAT...UNTIL
│       ├── validator.py           # Pre-execution validation
│       ├── runner.py              # Build/test/dev stage execution
│       ├── diagnoser.py           # Error diagnosis
│       ├── repairer.py            # Fix application
│       ├── recorder.py            # Outcome recording
│       ├── protocol_manager.py    # Protocol load/save/evolve
│       ├── generalizer.py         # Rule generalization
│       └── types.py               # Pydantic models
│
├── services/                      # Support services
│   ├── __init__.py
│   ├── asset_service.py           # Asset generation router
│   ├── asset_image_service.py     # Image generation
│   ├── asset_audio_service.py     # Audio generation
│   ├── asset_video_service.py     # Video generation
│   ├── file_discovery.py          # File discovery and indexing
│   ├── fs_service.py              # File system operations
│   └── shell_service.py           # Shell execution service
│
├── bench/                         # Evaluation
│   ├── __init__.py
│   ├── evaluator.py               # Main orchestrator
│   ├── browser_runner.py          # Headless browser execution
│   ├── vlm_judge.py               # VLM-based scoring
│   └── scoring/
│       ├── build_health.py
│       ├── visual_usability.py
│       └── intent_alignment.py
│
├── config/                        # Configuration
│   ├── __init__.py
│   ├── models.py                  # Pydantic config models
│   ├── constants.py               # Constants
│   └── storage.py                 # Config persistence
│
├── utils/                         # Utilities
│   ├── __init__.py
│   ├── errors.py                  # Custom exceptions
│   ├── retry.py                   # Retry decorators
│   ├── token_counter.py           # Token estimation
│   ├── json_utils.py              # Safe JSON parse/stringify
│   ├── edit_helper.py             # Diff/patch utilities
│   └── browser_launcher.py        # Secure browser launch
│
└── prompts/                       # System prompts
    ├── default.md
    └── custom.md
```

## 2.3 Tech Stack

| Concern | TS Reference | Python Choice | Justification |
|---------|-------------|---------------|---------------|
| CLI framework | Ink.js (React TUI) | Typer + Rich | Typer for declarative CLI, Rich for styled output and progress panels |
| Config / validation | Hand-rolled JSON | Pydantic v2 | Type-safe config with validation, serialization, and env var parsing |
| HTTP client | Node fetch | httpx | Native async support, connection pooling, excellent ergonomics |
| Async file I/O | fs/promises | aiofiles | Drop-in async wrapper around standard file operations |
| Async subprocess | child_process | asyncio.create_subprocess_exec | Native asyncio integration |
| Testing | Vitest | pytest + pytest-asyncio | De facto Python standard, excellent async support |
| Browser automation | Playwright (TS) | Playwright (Python) | Same engine, official Python bindings |
| LLM SDK | Custom fetch | openai (Python SDK) | Official SDK with streaming, tool calling, structured outputs |
| Type checking | TypeScript | mypy + pyright | Static analysis for Python |
| Packaging | npm | uv / hatch | Modern Python packaging with lock files and fast resolution |
| AST parsing | TypeScript compiler API | tree-sitter / libcst | Python source analysis for pattern extraction |
| Diff / patch | diff library | difflib | Standard library, no external dependency |

## 2.4 Module Dependencies

```
cli/ → core/ → tools/
  ↓      ↓       ↓
services/ ←──┘    ↓
  ↓            skills/
  ↓               ↓
config/ ←───────┘
  ↓
utils/
```

- `cli` depends on `core`, `config`, `skills`
- `core` depends on `tools`, `services`, `config`, `utils`
- `tools` depend on `services`, `config`
- `skills` depend on `core`, `services`, `config`
- `services` depend on `config`, `utils`
- `bench` depends on `services`, `config`
- `config` depends on `utils`

## 2.5 Async Design

The entire framework is built on **asyncio**. Every I/O-bound operation is async:

- LLM API calls (streaming)
- File system operations (aiofiles)
- Shell command execution (asyncio subprocess)
- Asset generation (HTTP requests)
- Browser automation (Playwright async API)

Synchronous operations are wrapped with `asyncio.to_thread` where necessary (e.g., CPU-intensive diff computation).

## 2.6 Error Handling Strategy

```python
# utils/errors.py
class OpenGameError(Exception):
    """Base exception for all OpenGame errors."""
    pass

class LlmError(OpenGameError):
    """LLM API errors (rate limit, timeout, invalid response)."""
    pass

class ToolError(OpenGameError):
    """Tool execution errors."""
    pass

class ConfigError(OpenGameError):
    """Configuration errors."""
    pass

class DebugError(OpenGameError):
    """Debug loop failures."""
    pass

class AssetError(OpenGameError):
    """Asset generation failures."""
    pass
```

All errors carry:
- `message`: Human-readable description
- `context`: Structured context dict for debugging
- `recoverable`: Whether the operation can be retried
