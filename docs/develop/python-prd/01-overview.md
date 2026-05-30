# 01 — Project Overview

## 1.1 What is OpenGame?

OpenGame is an open-source agentic framework for end-to-end web game creation from a natural language prompt. Given a description like "Build a Snake clone with WASD controls and a dark theme", the agent autonomously:

1. Classifies the game type by physics regime
2. Scaffolds a project from reusable templates
3. Generates a Game Design Document (GDD)
4. Generates game assets (images, audio, video)
5. Implements game code following the GDD
6. Debugs until the game compiles, tests pass, and the game is playable

The output is a complete, playable web game built with Phaser 3 + TypeScript + Vite.

## 1.2 Why a Python Port?

The TypeScript reference implementation works but has limitations:

- **Python ecosystem**: Many ML/AI developers prefer Python. A Python CLI integrates better with existing Python workflows.
- **Tooling**: Python's async ecosystem (asyncio, httpx, aiofiles) provides cleaner abstractions for I/O-bound agent work.
- **Package management**: `pip install opengame` vs `npm install -g @opengame/opengame` — broader reach in data science communities.
- **Extensibility**: Python's decorator-based tool registration and Pydantic validation make the framework more approachable for customization.

## 1.3 Scope

### In Scope

| Feature | Description |
|---------|-------------|
| Complete CLI toolchain | `opengame` command with headless mode, debug, evolve, config |
| Agent runtime | Tool loop, LLM clients (OpenAI-compatible), file I/O, shell execution |
| Game Skill — Template | Classify → Extract → Abstract → Merge → Evolve template library |
| Game Skill — Debug | Algorithm 1 (validate → build → test → diagnose → repair → evolve) |
| Asset pipeline | Image, audio, video generation via provider APIs |
| OpenGame-Bench | Build Health + Visual Usability + Intent Alignment scoring |
| Settings system | `settings.json` + environment variables + CLI flags |
| All 5 game archetypes | platformer, top_down, grid_logic, tower_defense, ui_heavy |

### Out of Scope (v1)

| Feature | Rationale |
|---------|-----------|
| IDE extensions (VS Code, JetBrains) | Requires IDE-specific APIs, can be added later |
| Web docs site | Next.js site is separate from core framework |
| Docker sandbox variants | macOS sandbox profiles are platform-specific |
| GameCoder-27B model training | Model training is independent of the framework port |
| Multiplayer / networked games | Single-player games are the current focus |
| Interactive TUI mode | Ink.js (React TUI) has no direct Python equivalent; Rich panels are the substitute |
| Telemetry / clearcut logging | Can be added post-v1 |

## 1.4 Output Format Preservation

**The Python version continues to output web-based games** (HTML5 / Phaser 3 / TypeScript / Vite). The port rewrites the *agent framework* in Python, not the game runtime engine.

This is a deliberate architectural decision: OpenGame's core value is the agent's ability to scaffold stable architectures and systematically repair integration errors. The generated games are web games because that's what the template ecosystem supports.

## 1.5 Success Criteria

| # | Criterion | Measurement |
|---|-----------|-------------|
| 1 | CLI parity | `opengame -p "Build a Snake clone" --yolo` produces output equivalent to TS version |
| 2 | Archetype coverage | All 5 archetypes produce playable games |
| 3 | Template accumulation | Template Skill accumulates and reuses templates across sessions |
| 4 | Debug convergence | Debug Skill repairs build/test/runtime errors within 20 iterations |
| 5 | Bench parity | OpenGame-Bench scores within 5% of TS version on identical prompts |
| 6 | Build success | `pytest` passes, `mypy` type-checks clean |

## 1.6 Key Concepts

| Concept | Definition |
|---------|------------|
| **Agent** | An AI system that uses tools (read_file, write_file, shell, etc.) to accomplish tasks autonomously |
| **Game Skill** | Reusable game development capability composed of Template Skill + Debug Skill |
| **Template Skill** | Learns and maintains a library of project skeletons from accumulated experience |
| **Debug Skill** | Maintains a living protocol of verified fixes for integration errors |
| **Archetype** | Physics-based game category (e.g., "side_gravity", "free_top_down") — not a genre |
| **Protocol (P)** | Living debugging protocol containing error signatures, root causes, and verified fixes |
| **GDD** | Game Design Document — structured specification of game mechanics, assets, and code |
| **M0** | Meta-template — the baseline core template shared across all game types |
| **Hook** | An override method in a base class that customizes behavior without rewriting lifecycle logic |
