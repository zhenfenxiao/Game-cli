# OpenGame

Open-source agentic framework for end-to-end web game creation. Takes a natural-language prompt and produces a complete **Phaser 3 + TypeScript + Vite** web game through an AI agent-driven pipeline.

This is the **Python port** of the OpenGame TypeScript reference implementation (v0.6.0).

## Quick Start

```bash
# Clone and install
git clone https://github.com/leigest519/OpenGame.git
cd OpenGame
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"

# Verify installation
python -m opengame --version
python -m opengame --help
python -m opengame config show

# Run tests
pytest
```

## Project Structure

```
opengame/
├── cli/          # Typer CLI (config, generate, debug, evolve)
├── core/         # Agent runtime (tool registry, LLM clients)
├── config/       # Pydantic config models and loader
├── services/     # Async file I/O, shell execution, file discovery
└── utils/        # Errors, retry, JSON, token counter, diff/patch

tests/
├── unit/         # Unit tests for all modules
│   ├── utils/    # errors, json, retry, token, edit helper
│   ├── config/   # config models and loader
│   ├── cli/      # CLI commands
│   ├── core/     # tool registry, LLM client, prompts
│   └── services/ # FS service, shell service
└── conftest.py   # Shared fixtures
```

## Development Status

| Phase | Status |
|-------|--------|
| Phase 1: Foundation | ✅ Complete |
| Phase 2: Agent Runtime | 🚧 Planned |
| Phase 3: Game Skill | 📋 Planned |
| Phase 4: Asset Pipeline | 📋 Planned |
| Phase 5: Integration | 📋 Planned |
| Phase 6: Bench + Polish | 📋 Planned |

## Tech Stack

- **CLI:** Typer + Rich
- **Config:** Pydantic v2
- **Async:** asyncio + httpx + aiofiles
- **LLM:** OpenAI-compatible SDK
- **Testing:** pytest + pytest-asyncio
- **Lint/Type:** ruff + mypy

## License

Apache-2.0
