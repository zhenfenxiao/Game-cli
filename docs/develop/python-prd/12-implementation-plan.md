# 12 — Implementation Plan

## 12.1 Timeline Overview

| Phase | Duration | Focus | Deliverable |
|-------|----------|-------|-------------|
| Phase 1 | Weeks 1-2 | Foundation | Project scaffolding, utilities, config |
| Phase 2 | Weeks 3-4 | Agent Runtime | Turn loop, tools, LLM clients |
| Phase 3 | Weeks 5-7 | Game Skill | Template + Debug skills |
| Phase 4 | Week 8 | Asset Pipeline | Image/audio/video generation |
| Phase 5 | Week 9 | Integration | End-to-end pipeline |
| Phase 6 | Week 10 | Bench + Polish | Evaluation, tests, docs, packaging |

## 12.2 Phase 1: Foundation (Weeks 1-2)

### Week 1: Project Structure

| Task | Detail | Effort |
|------|--------|--------|
| Set up project scaffolding | `pyproject.toml`, package structure, `.gitignore` | 1 day |
| Implement config system | Pydantic models, config loader, env var parsing | 2 days |
| Implement core utilities | JSON, retry, token counter, edit helpers, errors | 2 days |
| Set up testing infrastructure | pytest, pytest-asyncio, fixtures, CI config | 1 day |

### Week 2: Basic CLI and Services

| Task | Detail | Effort |
|------|--------|--------|
| Implement Typer CLI | Root command, `--help`, `--version`, subcommands | 1 day |
| Implement file system service | Async file I/O, path utilities | 1 day |
| Implement shell service | Async subprocess, read-only checker | 1 day |
| Implement file discovery | File indexing, ignore patterns, glob | 1 day |
| Write unit tests for utilities | 80%+ coverage on utils | 1 day |

**Phase 1 Deliverables:**
- `opengame --help` works
- Config loading from all sources
- All utility modules with tests

## 12.3 Phase 2: Agent Runtime (Weeks 3-4)

### Week 3: Core Runtime

| Task | Detail | Effort |
|------|--------|--------|
| Implement tool registry | `@tool` decorator, dispatch, async execution | 1 day |
| Implement turn loop | Conversation loop, streaming, tool call parsing | 2 days |
| Implement OpenAI client | Streaming, tool calls, retry logic | 1 day |
| Implement prompt assembler | System prompt loading, context injection | 1 day |

### Week 4: Tools

| Task | Detail | Effort |
|------|--------|--------|
| Implement file tools | read_file, write_file, edit, glob, grep, ls | 2 days |
| Implement shell tool | Command execution, read-only checker | 0.5 day |
| Implement web tools | web_fetch, web_search | 1 day |
| Implement game tools | classify_game_type, generate_gdd, generate_tilemap | 1 day |
| Implement task tools | todo_write, task_create, task_update | 0.5 day |

**Phase 2 Deliverables:**
- Agent can hold a conversation with tool calls
- All 20+ tools implemented and tested
- Streaming LLM responses work

## 12.4 Phase 3: Game Skill (Weeks 5-7)

### Week 5: Template Skill

| Task | Detail | Effort |
|------|--------|--------|
| Implement Collector | Project snapshot collection | 1 day |
| Implement Classifier | LLM + heuristic archetype detection | 1 day |
| Implement Extractor | Pattern extraction from source | 1 day |
| Implement Abstractor | LLM-driven code generalization | 1 day |
| Implement Merger | Template family merging | 0.5 day |
| Implement Library Manager | CRUD, persistence, querying | 0.5 day |

### Week 6: Debug Skill Core

| Task | Detail | Effort |
|------|--------|--------|
| Implement Protocol Manager | Load/save/initialize protocol | 0.5 day |
| Implement Validator | Pre-execution validation checks | 1 day |
| Implement Runner | Build/test/dev stage execution | 0.5 day |
| Implement Diagnoser | Error signature matching + LLM fallback | 1 day |
| Implement Repairer | Fix application (edit/shell/config) | 1 day |
| Implement Recorder | Outcome recording to protocol | 0.5 day |

### Week 7: Debug Skill Loop + Generalizer

| Task | Detail | Effort |
|------|--------|--------|
| Implement Debug Loop | Algorithm 1 REPEAT...UNTIL | 1 day |
| Implement Generalizer | Rule generalization from repeated entries | 1 day |
| Integrate Template + Debug | GameSkill orchestrator | 1 day |
| Write skill tests | Unit tests for all skill components | 2 days |

**Phase 3 Deliverables:**
- Template Skill can classify, extract, abstract, and evolve
- Debug Skill can diagnose and repair build errors
- Algorithm 1 converges on test projects

## 12.5 Phase 4: Asset Pipeline (Week 8)

| Task | Detail | Effort |
|------|--------|--------|
| Implement AssetService router | Modality routing | 0.5 day |
| Implement ImageService | OpenAI, Tongyi, Doubao providers | 1.5 days |
| Implement AudioService | Audio generation | 1 day |
| Implement VideoService | Video generation (stubs) | 0.5 day |
| Implement AutoTiler | Tileset generation | 0.5 day |
| Implement TilesetProcessor | Phaser tileset metadata | 0.5 day |
| Asset pipeline tests | Mock provider tests | 0.5 day |

**Phase 4 Deliverables:**
- Image generation works with at least one provider
- Asset pack JSON is built correctly
- Tilemaps can be generated from ASCII

## 12.6 Phase 5: Integration (Week 9)

| Task | Detail | Effort |
|------|--------|--------|
| Implement headless mode | `opengame -p "..."` command | 1 day |
| Implement 6-phase orchestrator | Complete pipeline | 2 days |
| Implement debug/evolve commands | `opengame debug`, `opengame evolve` | 1 day |
| End-to-end testing | Run full pipeline on 3 test prompts | 1 day |

**Phase 5 Deliverables:**
- `opengame -p "Build a Snake clone" --yolo` produces a playable game
- Debug and evolve commands work
- At least 3 archetypes produce working games

## 12.7 Phase 6: Bench + Polish (Week 10)

| Task | Detail | Effort |
|------|--------|--------|
| Implement BuildHealth evaluator | Compilation + test scoring | 0.5 day |
| Implement VisualUsability evaluator | Browser automation scoring | 1 day |
| Implement IntentAlignment evaluator | VLM judge scoring | 1 day |
| Write integration tests | E2E tests for full pipeline | 1 day |
| Write documentation | README, API docs, examples | 1 day |
| Package for PyPI | `pyproject.toml`, versioning, publish | 0.5 day |

**Phase 6 Deliverables:**
- OpenGame-Bench evaluates games across 3 dimensions
- All tests pass
- Package published to PyPI

## 12.8 Milestones

### Milestone 1: "Hello Runtime" (End of Phase 2)
- Agent can chat with user using tools
- File operations work
- LLM streaming works

### Milestone 2: "Hello Game" (End of Phase 3)
- Template Skill classifies and scaffolds
- Debug Skill repairs errors
- Agent implements simple games

### Milestone 3: "Hello World" (End of Phase 5)
- Full pipeline: prompt → playable game
- All 5 archetypes work
- Debug loop converges

### Milestone 4: "Ship It" (End of Phase 6)
- Bench scores within 5% of TS version
- PyPI package published
- Documentation complete

## 12.9 Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| LLM streaming tool call parsing is complex | High | High | Start early, test thoroughly, fallback to blocking |
| Phaser/TS game templates need porting | Medium | Medium | Keep templates as-is (they're on-disk files) |
| Browser automation flaky in CI | Medium | Medium | Use Playwright's built-in waits, retry logic |
| Asset provider APIs change | Low | Medium | Abstract provider interface, easy to add new ones |
| Token limit compression logic | Medium | Medium | Implement summarization, test with large projects |
| Async subprocess hangs on Windows | Medium | Medium | Use timeouts, test on all target platforms |

## 12.10 Development Setup

```bash
# Clone repository
git clone https://github.com/leigest519/OpenGame.git
cd OpenGame

# Create virtual environment
uv venv
source .venv/bin/activate

# Install in development mode
uv pip install -e ".[dev]"

# Run tests
pytest

# Run type checker
mypy opengame

# Run linter
ruff check opengame

# Run formatter
ruff format opengame

# Test CLI
python -m opengame --help
```

## 12.11 Testing Strategy Summary

| Level | Tool | Coverage Target |
|-------|------|-----------------|
| Unit | pytest | 80%+ on core modules |
| Integration | pytest | Full pipeline on 3 archetypes |
| E2E | pytest + Playwright | Game generation + playability |
| Bench | pytest | Score comparison with TS version |

## 12.12 Dependencies

```toml
# pyproject.toml
[project]
name = "opengame"
version = "0.6.0"
description = "Open-source agentic framework for end-to-end web game creation"
readme = "README.md"
license = {text = "Apache-2.0"}
requires-python = ">=3.11"
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: Apache Software License",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
]
dependencies = [
    "typer>=0.12.0",
    "rich>=13.0.0",
    "pydantic>=2.0.0",
    "httpx>=0.27.0",
    "aiofiles>=23.0.0",
    "openai>=1.0.0",
]

[project.optional-dependencies]
bench = [
    "playwright>=1.40.0",
]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=4.0.0",
    "mypy>=1.8.0",
    "ruff>=0.2.0",
    "respx>=0.21.0",
]

[project.scripts]
opengame = "opengame.cli.main:app"

[project.urls]
Homepage = "https://github.com/leigest519/OpenGame"
Documentation = "https://www.opengame-project-page.com/"
```
