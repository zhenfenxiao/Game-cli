# 15 — Testing Strategy

This document defines the testing approach for the Python port of OpenGame, including test structure, key scenarios, fixtures, and quality targets.

## 15.1 Test Structure

```
tests/
├── conftest.py                    # Shared pytest fixtures and configuration
├── unit/                          # Unit tests (fast, isolated)
│   ├── core/
│   │   ├── test_turn_loop.py
│   │   ├── test_tool_registry.py
│   │   ├── test_llm_client.py
│   │   └── test_prompts.py
│   ├── tools/
│   │   ├── test_file_tools.py
│   │   ├── test_shell_tool.py
│   │   ├── test_edit.py
│   │   └── test_web_tools.py
│   ├── skills/
│   │   ├── test_classifier.py
│   │   ├── test_extractor.py
│   │   ├── test_library_manager.py
│   │   ├── test_protocol_manager.py
│   │   └── test_runner.py
│   └── utils/
│       ├── test_retry.py
│       ├── test_json_utils.py
│       └── test_edit_helper.py
├── integration/                   # Integration tests (slower, multi-module)
│   ├── test_game_generation.py
│   ├── test_debug_skill.py
│   ├── test_template_skill.py
│   └── test_asset_pipeline.py
├── fixtures/                      # Test data and fixtures
│   ├── projects/                  # Sample game projects
│   │   ├── snake/                 # Complete Snake game
│   │   ├── platformer_demo/       # Platformer demo
│   │   └── minimal_ts/            # Minimal TypeScript project
│   ├── templates/                 # Test templates
│   │   └── core/                  # Simplified core template
│   └── protocols/                 # Test debug protocols
│       ├── seed_protocol.json
│       └── populated_protocol.json
├── bench/                         # Benchmark tests
│   └── test_evaluator.py
└── e2e/                           # End-to-end tests (slowest)
    ├── test_cli.py
    └── test_full_pipeline.py
```

## 15.2 pytest Configuration

```ini
# pyproject.toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py", "*_test.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
addopts = "-v --tb=short --strict-markers"
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
    "integration: marks tests as integration tests",
    "e2e: marks tests as end-to-end tests",
    "requires_api: marks tests that require external API calls",
]
```

## 15.3 Shared Fixtures

```python
# tests/conftest.py
import pytest
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def temp_dir():
    """Provide a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


@pytest.fixture
def mock_llm_client():
    """Provide a mock LLM client."""
    client = AsyncMock()
    client.generate = AsyncMock(return_value=MagicMock(
        content="Mock response",
        tool_calls=None,
        usage={"prompt_tokens": 100, "completion_tokens": 50},
    ))
    return client


@pytest.fixture
def mock_tool_registry():
    """Provide a mock tool registry."""
    registry = MagicMock()
    registry.get_tool_definitions = MagicMock(return_value=[])
    registry.execute = AsyncMock(return_value=MagicMock(
        output="Mock tool result",
        error=None,
    ))
    return registry


@pytest.fixture
def sample_project(temp_dir):
    """Create a minimal sample project for testing."""
    project = temp_dir / "sample_game"
    project.mkdir()
    (project / "package.json").write_text(
        '{"name": "test-game", "scripts": {"build": "echo build", "test": "echo test"}}'
    )
    src = project / "src"
    src.mkdir()
    (src / "gameConfig.json").write_text('{"screenSize": {"width": {"value": 1280}}}')
    (src / "main.ts").write_text('console.log("Hello game");')
    return project


@pytest.fixture
def empty_library(temp_dir):
    """Create an empty template library."""
    from opengame.skills.template_skill.types import TemplateLibrary
    return TemplateLibrary(
        version=0,
        created_at="2024-01-01T00:00:00Z",
        updated_at="2024-01-01T00:00:00Z",
        meta_template_path="agent-test/template-skill/meta-template",
        families=[],
        evolution_log=[],
    )


@pytest.fixture
def populated_library(temp_dir):
    """Create a template library with one family."""
    from opengame.skills.template_skill.types import (
        TemplateLibrary, TemplateFamily, PhysicsProfile,
        DirectoryPattern, TemplateFileDef, HookDef
    )
    family = TemplateFamily(
        id="fam-platformer-001",
        archetype="platformer",
        physics_profile=PhysicsProfile(
            has_gravity=True, perspective="side", movement_type="continuous"
        ),
        discovered_at_task=1,
        contributing_projects=["/test/project1"],
        stability=0.5,
        file_structure=DirectoryPattern(
            directories=["src", "assets"],
            files_by_directory={"src": ["main.ts"]}
        ),
        base_classes=[],
        hooks=[HookDef(
            name="onJump", declaring_class="BasePlayer",
            signature="onJump(): void", is_abstract=False, occurrence_count=1
        )],
        config_extensions=[],
        template_files=[TemplateFileDef(
            relative_path="src/main.ts", content="// template", role="base_class"
        )],
        summary="A platformer template",
    )
    return TemplateLibrary(
        version=1,
        created_at="2024-01-01T00:00:00Z",
        updated_at="2024-01-01T00:00:00Z",
        meta_template_path="agent-test/template-skill/meta-template",
        families=[family],
        evolution_log=[],
    )


@pytest.fixture
def empty_protocol(temp_dir):
    """Create an empty debug protocol."""
    from opengame.skills.debug_skill.types import DebugProtocol
    return DebugProtocol(
        version=0,
        created_at="2024-01-01T00:00:00Z",
        updated_at="2024-01-01T00:00:00Z",
        seed_protocol_path="agent-test/debug-skill/seed-protocol",
        entries=[],
        rules=[],
        evolution_log=[],
    )


@pytest.fixture
def sample_snapshot(temp_dir):
    """Create a sample project snapshot."""
    from opengame.skills.template_skill.types import ProjectSnapshot, FileEntry
    return ProjectSnapshot(
        project_path=str(temp_dir),
        files=[
            FileEntry(
                relative_path="src/main.ts",
                content="class Player { jump() {} }",
                extension=".ts"
            ),
            FileEntry(
                relative_path="src/scenes/Level1.ts",
                content="class Level1 extends BaseLevelScene {}",
                extension=".ts"
            ),
        ],
        file_tree=["src/main.ts", "src/scenes/Level1.ts", "package.json"],
        game_config={"title": "Test Game"},
        code_summary="A simple platformer with Player class and Level1 scene.",
    )
```

## 15.4 Unit Test Examples

### Tool Registry Tests

```python
# tests/unit/core/test_tool_registry.py
import pytest
from opengame.core.tool_registry import ToolRegistry


class TestToolRegistry:
    def test_register_tool(self):
        registry = ToolRegistry()

        @registry.register(
            name="test_tool",
            description="A test tool",
            schema={
                "type": "object",
                "properties": {"x": {"type": "string"}},
                "required": ["x"],
            },
        )
        async def test_tool(x: str) -> str:
            return f"Result: {x}"

        assert "test_tool" in registry.list_tools()
        definitions = registry.get_tool_definitions()
        assert len(definitions) == 1
        assert definitions[0]["function"]["name"] == "test_tool"

    @pytest.mark.asyncio
    async def test_execute_tool(self):
        registry = ToolRegistry()

        @registry.register(
            name="echo",
            description="Echo input",
            schema={
                "type": "object",
                "properties": {"message": {"type": "string"}},
                "required": ["message"],
            },
        )
        async def echo(message: str) -> str:
            return message

        result = await registry.execute("echo", {"message": "hello"}, "call-1")
        assert result.output == "hello"
        assert result.error is None

    @pytest.mark.asyncio
    async def test_execute_missing_tool(self):
        registry = ToolRegistry()
        result = await registry.execute("nonexistent", {}, "call-1")
        assert "not found" in result.error
```

### Classifier Tests

```python
# tests/unit/skills/test_classifier.py
import pytest
from opengame.skills.template_skill.classifier import Classifier, PHYSICS_SIGNALS


class TestClassifier:
    @pytest.mark.asyncio
    async def test_heuristic_classify_platformer(self, sample_snapshot, populated_library):
        # Inject platformer signals into snapshot
        sample_snapshot.files[0].content = """
            class Player {
                setGravityY(1000);
                jumpPower = 500;
                coyoteTime = 100;
            }
        """
        classifier = Classifier(mock_llm_client=None)
        result = classifier._heuristic_classify(sample_snapshot, populated_library)

        assert result.archetype == "platformer"
        assert result.physics_profile.has_gravity is True
        assert result.physics_profile.perspective == "side"
        assert result.physics_profile.movement_type == "continuous"
        assert result.confidence > 0

    @pytest.mark.asyncio
    async def test_heuristic_classify_new_family(self, sample_snapshot, empty_library):
        sample_snapshot.files[0].content = """
            class Player {
                setGravityY(1000);
                jumpPower = 500;
            }
        """
        classifier = Classifier(mock_llm_client=None)
        result = classifier._heuristic_classify(sample_snapshot, empty_library)

        assert result.archetype == "gravity"
        assert result.is_new_family is False  # Heuristic doesn't set this
        assert result.physics_profile.has_gravity is True

    def test_physics_signals_defined(self):
        assert len(PHYSICS_SIGNALS) == 5
        signal_names = {s["name"] for s in PHYSICS_SIGNALS}
        assert signal_names == {"gravity", "free_movement", "grid_discrete", "path_wave", "ui_state"}
```

### Debug Loop Tests

```python
# tests/unit/skills/test_debug_loop.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from opengame.skills.debug_skill.debug_loop import DebugSkill
from opengame.skills.debug_skill.types import (
    DebugProtocol, ParsedError, RunResult, DebugLoopResult
)


class TestDebugLoop:
    @pytest.fixture
    def debug_skill(self, mock_llm_client):
        protocol_manager = AsyncMock()
        protocol_manager.load_or_init = AsyncMock(return_value=DebugProtocol(
            version=0,
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
            seed_protocol_path="seed",
            entries=[],
            rules=[],
            evolution_log=[],
        ))
        protocol_manager.save = AsyncMock()

        return DebugSkill(
            llm_client=mock_llm_client,
            protocol_manager=protocol_manager,
            max_iterations=5,
        )

    @pytest.mark.asyncio
    async def test_debug_loop_success(self, debug_skill, sample_project):
        # Mock runner to always succeed
        debug_skill.runner.run = AsyncMock(return_value=RunResult(
            stage="build", success=True, exit_code=0,
            stdout="", stderr="", errors=[], duration_ms=1000,
        ))

        result = await debug_skill.debug(sample_project, run_dev=False, evolve_after=False)

        assert isinstance(result, DebugLoopResult)
        assert result.success is True
        assert result.trace.total_iterations == 1

    @pytest.mark.asyncio
    async def test_debug_loop_with_failure_and_repair(self, debug_skill, sample_project):
        # First build fails, second succeeds
        debug_skill.runner.run = AsyncMock(side_effect=[
            RunResult(
                stage="build", success=False, exit_code=1,
                stdout="", stderr="error TS2339: Property 'x' does not exist",
                errors=[ParsedError(code="TS2339", message="Property 'x' does not exist")],
                duration_ms=1000,
            ),
            RunResult(
                stage="build", success=True, exit_code=0,
                stdout="", stderr="", errors=[], duration_ms=1000,
            ),
        ])

        # Mock diagnoser and repairer
        debug_skill.diagnoser.diagnose = AsyncMock(return_value=[MagicMock(
            matched=False, candidate_entry=None, root_cause="Missing property",
        )])
        debug_skill.repairer.repair = AsyncMock(return_value=MagicMock(
            applied=True, description="Added property", patch="",
        ))
        debug_skill.recorder.record = MagicMock(return_value=MagicMock(
            entry_id="entry-1",
        ))

        result = await debug_skill.debug(sample_project, run_dev=False, evolve_after=False)

        assert result.success is True
        assert result.trace.total_iterations == 2

    @pytest.mark.asyncio
    async def test_debug_loop_max_iterations(self, debug_skill, sample_project):
        # Build always fails
        debug_skill.runner.run = AsyncMock(return_value=RunResult(
            stage="build", success=False, exit_code=1,
            stdout="", stderr="error", errors=[ParsedError(code="ERR", message="fail")],
            duration_ms=1000,
        ))

        result = await debug_skill.debug(sample_project, run_dev=False, evolve_after=False)

        assert result.success is False
        assert result.trace.total_iterations == 5  # max_iterations
```

### File Tools Tests

```python
# tests/unit/tools/test_file_tools.py
import pytest
from pathlib import Path
from opengame.tools.file_tools import read_file, write_file, edit


class TestFileTools:
    @pytest.mark.asyncio
    async def test_read_file(self, temp_dir):
        test_file = temp_dir / "test.txt"
        test_file.write_text("line1\nline2\nline3\n")

        result = await read_file(str(test_file), offset=0, limit=10)
        assert result == "line1\nline2\nline3\n"

    @pytest.mark.asyncio
    async def test_read_file_with_offset(self, temp_dir):
        test_file = temp_dir / "test.txt"
        test_file.write_text("line1\nline2\nline3\n")

        result = await read_file(str(test_file), offset=1, limit=10)
        assert result == "line2\nline3\n"

    @pytest.mark.asyncio
    async def test_write_file(self, temp_dir):
        test_file = temp_dir / "subdir" / "output.txt"
        result = await write_file(str(test_file), "hello world")

        assert test_file.exists()
        assert test_file.read_text() == "hello world"
        assert "Wrote" in result

    @pytest.mark.asyncio
    async def test_edit_success(self, temp_dir):
        test_file = temp_dir / "code.ts"
        test_file.write_text("const x = 1;\nconst y = 2;")

        result = await edit(
            str(test_file),
            old_string="const x = 1;",
            new_string="const x = 42;",
        )

        assert "Edited" in result
        assert test_file.read_text() == "const x = 42;\nconst y = 2;"

    @pytest.mark.asyncio
    async def test_edit_not_found(self, temp_dir):
        test_file = temp_dir / "code.ts"
        test_file.write_text("const x = 1;")

        result = await edit(
            str(test_file),
            old_string="const z = 99;",
            new_string="const z = 0;",
        )

        assert "ERROR" in result
        assert "not found" in result

    @pytest.mark.asyncio
    async def test_edit_not_unique(self, temp_dir):
        test_file = temp_dir / "code.ts"
        test_file.write_text("const x = 1;\nconst x = 2;")

        result = await edit(
            str(test_file),
            old_string="const x = 1;",
            new_string="const x = 0;",
        )

        # Should fail because old_string appears twice
        assert "multiple times" in result
```

## 15.5 Integration Tests

### Full Pipeline Test

```python
# tests/integration/test_game_generation.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestGameGeneration:
    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_generate_snake_game(self, temp_dir, mock_llm_client):
        """Test end-to-end game generation for a simple Snake game."""
        from opengame.skills.game_skill import GameSkill

        # Configure mock LLM to return appropriate responses
        mock_llm_client.generate = AsyncMock(side_effect=[
            # Classification response
            MagicMock(content='{"archetype": "grid_logic", "confidence": 0.9}'),
            # GDD generation
            MagicMock(content="# Snake Game\n\n## Section 0: Architecture..."),
            # Other LLM calls...
        ])

        game_skill = GameSkill(
            llm_client=mock_llm_client,
            template_skill=MagicMock(),
            debug_skill=MagicMock(),
            asset_service=MagicMock(),
            tool_registry=MagicMock(),
            config=MagicMock(),
        )

        output_dir = temp_dir / "snake_game"
        result = await game_skill.generate_game(
            prompt="Build a Snake clone with WASD controls and a dark theme",
            output_dir=output_dir,
        )

        assert result.project_dir == output_dir
        assert result.duration_ms > 0

    @pytest.mark.asyncio
    async def test_debug_skill_integration(self, temp_dir):
        """Test debug skill on a project with known errors."""
        from opengame.skills.debug_skill.debug_loop import DebugSkill

        # Create a project with a TypeScript error
        project = temp_dir / "broken_game"
        project.mkdir()
        src = project / "src"
        src.mkdir()
        (src / "main.ts").write_text(
            'const x: number = "string";  // Type error\n'
        )
        (project / "package.json").write_text(
            '{"scripts": {"build": "tsc --noEmit"}}'
        )

        # Test would require actual TypeScript compiler
        # This is a structural test
        assert (src / "main.ts").exists()
```

## 15.6 E2E Tests

### CLI Tests

```python
# tests/e2e/test_cli.py
import pytest
from typer.testing import CliRunner
from opengame.cli.main import app


runner = CliRunner()


class TestCLI:
    def test_help(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "OpenGame" in result.output

    def test_version(self):
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "0.6.0" in result.output

    def test_config_show(self):
        result = runner.invoke(app, ["config", "show"])
        assert result.exit_code == 0
        assert "Configuration" in result.output

    @pytest.mark.slow
    @pytest.mark.requires_api
    def test_generate_headless(self, tmp_path):
        """Test headless generation (requires API key)."""
        result = runner.invoke(app, [
            "-p", "Build a simple clicker game",
            "--output-dir", str(tmp_path / "clicker"),
        ])
        # May fail without API key, but should not crash
        assert result.exit_code in [0, 1]
```

## 15.7 Mock Strategies

### LLM Client Mocking

```python
# Create a configurable mock LLM client
def create_mock_llm(responses: list[str]) -> AsyncMock:
    """Create a mock LLM client that returns responses in sequence."""
    client = AsyncMock()
    call_count = 0

    async def mock_generate(*args, **kwargs):
        nonlocal call_count
        response = responses[call_count % len(responses)]
        call_count += 1
        return MagicMock(content=response, tool_calls=None)

    client.generate = mock_generate
    return client
```

### HTTP Mocking

```python
# tests/unit/tools/test_web_tools.py
import pytest
import respx
from httpx import Response


class TestWebTools:
    @respx.mock
    @pytest.mark.asyncio
    async def test_web_fetch(self):
        route = respx.get("https://example.com").mock(return_value=Response(200, text="<html><body>Hello</body></html>"))

        from opengame.tools.web_tools import web_fetch
        result = await web_fetch("https://example.com")

        assert route.called
        assert "Hello" in result

    @respx.mock
    @pytest.mark.asyncio
    async def test_web_fetch_error(self):
        route = respx.get("https://example.com").mock(return_value=Response(404))

        from opengame.tools.web_tools import web_fetch
        with pytest.raises(Exception):
            await web_fetch("https://example.com")
```

## 15.8 Coverage Targets

| Module | Target Coverage | Priority |
|--------|-----------------|----------|
| `core/` | 85%+ | Critical |
| `tools/` | 80%+ | High |
| `skills/` | 75%+ | High |
| `services/` | 70%+ | Medium |
| `bench/` | 70%+ | Medium |
| `cli/` | 60%+ | Medium |
| `utils/` | 80%+ | High |

## 15.9 Test Commands

```bash
# Run all tests
pytest

# Run only unit tests (fast)
pytest tests/unit -m "not slow"

# Run with coverage
pytest --cov=opengame --cov-report=html --cov-report=term-missing

# Run integration tests
pytest tests/integration -m integration

# Run e2e tests
pytest tests/e2e -m e2e

# Run tests requiring API (expensive)
pytest -m requires_api

# Run specific test file
pytest tests/unit/skills/test_classifier.py -v

# Run with debugger on failure
pytest --pdb

# Parallel execution
pytest -n auto
```

## 15.10 Continuous Integration

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12", "3.13"]

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: |
          pip install uv
          uv pip install -e ".[dev,bench]"

      - name: Run linting
        run: |
          ruff check opengame
          ruff format --check opengame

      - name: Run type checking
        run: mypy opengame

      - name: Run unit tests
        run: pytest tests/unit -m "not slow" --cov=opengame --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage.xml
```

## 15.11 Test Data

### Sample Game Project

```typescript
// tests/fixtures/projects/snake/src/main.ts
import { Game } from 'phaser';
import { Preloader } from './scenes/Preloader';
import { TitleScreen } from './scenes/TitleScreen';
import { Level1 } from './scenes/Level1';

const config = {
  type: Phaser.AUTO,
  width: 800,
  height: 600,
  scene: [Preloader, TitleScreen, Level1],
  physics: {
    default: 'arcade',
    arcade: { gravity: { x: 0, y: 0 } }
  }
};

export default new Game(config);
```

### Sample Seed Protocol

```json
{
  "version": 0,
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z",
  "seed_protocol_path": "",
  "entries": [
    {
      "id": "entry-TS2339-seed001",
      "kind": "reactive",
      "signature": {
        "stage": "build",
        "error_code": "TS2339",
        "message_pattern": "Property '(.+)' does not exist on type '(.+)'",
        "file_context": "src/scenes/*.ts"
      },
      "root_cause": "Missing property declaration in class",
      "tags": ["typescript", "property-missing"],
      "fix": {
        "type": "edit",
        "description": "Add missing property to class",
        "patch": "OLD:\nclass {className} {\nNEW:\nclass {className} {\n  {propertyName}: {type};"
      },
      "occurrences": 0,
      "contributing_projects": [],
      "created_at": "2024-01-01T00:00:00Z",
      "last_matched_at": "2024-01-01T00:00:00Z"
    }
  ],
  "rules": [],
  "evolution_log": []
}
```
