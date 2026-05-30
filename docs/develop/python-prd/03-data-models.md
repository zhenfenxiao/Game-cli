# 03 — Data Models (Pydantic)

This document defines all data models used across the framework. Every model is a **Pydantic v2 BaseModel** with validation, serialization, and strict typing.

---

## 3.1 Configuration Models

```python
from pydantic import BaseModel, Field, field_validator
from pathlib import Path
from typing import Literal, Any


class LlmConfig(BaseModel):
    """Configuration for LLM API access."""
    provider: Literal["openai", "anthropic", "dashscope", "deepseek", "openrouter"] = "openai"
    api_key: str | None = None
    base_url: str | None = Field(default="https://api.openai.com/v1", description="API base URL")
    model: str = "gpt-4o"
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4096, ge=1)
    timeout: int = Field(default=120, ge=1, description="Request timeout in seconds")

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, v: str | None) -> str | None:
        if v is not None and not v.startswith(("sk-", "gsk_")):
            # Allow any format for custom providers
            pass
        return v


class AssetProviderConfig(BaseModel):
    """Configuration for a single asset modality provider."""
    provider: str = Field(description="Provider name: tongyi, doubao, openai-compat, fal")
    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None


class GameSkillConfig(BaseModel):
    """Paths and settings for Game Skill."""
    templates_dir: Path = Field(default=Path("agent-test/templates"))
    docs_dir: Path = Field(default=Path("agent-test/docs"))
    archetypes_dir: Path = Field(default=Path("agent-test/templates/modules"))
    library_output_dir: Path = Field(default=Path(".opengame/template-library"))
    protocol_output_dir: Path = Field(default=Path(".opengame/debug-protocol"))
    max_debug_iterations: int = Field(default=20, ge=1, le=100)
    evolve_after_debug: bool = True


class OpenGameConfig(BaseModel):
    """Top-level configuration — loaded from CLI flags, env vars, and settings.json."""
    llm: LlmConfig = Field(default_factory=LlmConfig)
    image: AssetProviderConfig | None = None
    audio: AssetProviderConfig | None = None
    video: AssetProviderConfig | None = None
    reasoning: AssetProviderConfig | None = None
    game_skill: GameSkillConfig = Field(default_factory=GameSkillConfig)
    approval_mode: Literal["ask", "auto-edit", "yolo"] = "auto-edit"
    sandbox: bool = False
    verbose: bool = False
    telemetry: bool = True
```

---

## 3.2 Template Skill Models

```python
from pydantic import BaseModel, Field
from typing import Literal


class PhysicsProfile(BaseModel):
    """Physical properties of a game, used for archetype classification."""
    has_gravity: bool = Field(description="Does the game apply Y-axis gravity?")
    perspective: Literal["side", "top_down", "none"] = Field(
        description="Camera perspective: side-view, top-down, or not applicable"
    )
    movement_type: Literal["continuous", "grid", "path", "ui_only"] = Field(
        description="Movement system: continuous physics, discrete grid, fixed path, or UI-only"
    )


class FileEntry(BaseModel):
    """A single file in a project snapshot."""
    relative_path: str = Field(description="Path relative to project root")
    content: str = Field(description="File contents")
    extension: str = Field(description="File extension, e.g. '.ts', '.json'")


class ProjectSnapshot(BaseModel):
    """Complete snapshot of a project for analysis."""
    project_path: str
    files: list[FileEntry]
    file_tree: list[str] = Field(description="List of all relative paths")
    game_config: dict[str, Any] | None = None
    code_summary: str = Field(description="Human-readable summary of code structure")


class ClassificationResult(BaseModel):
    """Output of the archetype classifier."""
    archetype: str = Field(description="snake_case physics regime label")
    reasoning: str = Field(description="Explanation citing specific code evidence")
    physics_profile: PhysicsProfile
    confidence: float = Field(ge=0.0, le=1.0)
    is_new_family: bool = Field(default=False, description="Whether this archetype is new to the library")


class ClassDef(BaseModel):
    """Extracted class definition from source code."""
    name: str
    parent_class: str | None
    file_path: str
    is_abstract: bool
    methods: list["MethodDef"]


class MethodDef(BaseModel):
    """Extracted method definition."""
    name: str
    visibility: Literal["public", "protected", "private"]
    is_abstract: bool
    is_override: bool
    signature: str = Field(description="Simplified signature string")


class HookDef(BaseModel):
    """A hook method — an override point in the template architecture."""
    name: str
    declaring_class: str = Field(description="Which base class declares this hook")
    signature: str
    is_abstract: bool
    occurrence_count: int = Field(default=0, description="How many projects use this hook")


class ImportEdge(BaseModel):
    """An import dependency between files."""
    from_file: str
    to_file: str
    imported_names: list[str]


class DirectoryPattern(BaseModel):
    """Directory structure pattern extracted from a project."""
    directories: list[str]
    files_by_directory: dict[str, list[str]]


class ConfigField(BaseModel):
    """A configuration field extension beyond the M0 baseline."""
    path: str = Field(description="Dot-notation path, e.g. 'gameplay.player_speed'")
    value: Any
    type: str = Field(description="Type annotation, e.g. 'number', 'string', 'boolean'")
    description: str | None = None


class ExtractedPatterns(BaseModel):
    """All patterns extracted from a completed project."""
    archetype: str
    physics_profile: PhysicsProfile
    project_path: str
    file_structure: DirectoryPattern
    classes: list[ClassDef]
    hooks: list[HookDef]
    config_extensions: list[ConfigField]
    imports: list[ImportEdge]
    code_snippets: dict[str, str] = Field(description="Raw code snippets for key files")


class TemplateFileDef(BaseModel):
    """A single file in an abstracted template family."""
    relative_path: str
    content: str
    role: Literal["base_class", "copy_template", "system", "behavior", "utility"] = Field(
        description="""
        base_class: Engine code that should NOT be modified (KEEP files)
        copy_template: Files meant to be copied and customized (_Template* pattern)
        system: Reusable system managers (BoardManager, WaveManager, etc.)
        behavior: Reusable behavior components (PatrolAI, MeleeAttack, etc.)
        utility: Shared utility functions
        """
    )


class AbstractedTemplates(BaseModel):
    """Output of the abstractor — generalized templates from concrete code."""
    archetype: str
    template_files: list[TemplateFileDef]
    hooks: list[HookDef]
    config_schema: list[ConfigField]
    summary: str = Field(description="Natural-language description of what this family provides")


class TemplateFamily(BaseModel):
    """A template family — accumulated patterns for one archetype."""
    id: str = Field(description="Unique identifier, e.g. 'fam-platformer-001'")
    archetype: str
    physics_profile: PhysicsProfile
    discovered_at_task: int = Field(description="Which task number first discovered this family")
    contributing_projects: list[str]
    stability: float = Field(ge=0.0, le=1.0, description="Higher = more projects reinforced this family")
    file_structure: DirectoryPattern
    base_classes: list[ClassDef]
    hooks: list[HookDef]
    config_extensions: list[ConfigField]
    template_files: list[TemplateFileDef]
    summary: str


class EvolutionEntry(BaseModel):
    """A single entry in the template library evolution log."""
    task_id: str
    timestamp: str
    project_path: str
    archetype: str
    action: Literal["created_family", "merged_to_family"]
    family_id: str
    patterns_extracted: int
    patterns_merged: int


class TemplateLibrary(BaseModel):
    """The complete template library — persisted to disk."""
    version: int = 0
    created_at: str
    updated_at: str
    meta_template_path: str
    families: list[TemplateFamily]
    evolution_log: list[EvolutionEntry]
```

---

## 3.3 Debug Skill Models

```python
from pydantic import BaseModel, Field
from typing import Literal


class FailureSignature(BaseModel):
    """Normalized fingerprint for matching errors against the protocol."""
    stage: Literal["build", "test", "runtime"] = Field(description="Verification stage that produced this error")
    error_code: str = Field(description="Error class/code, e.g. 'TS2339', 'MODULE_NOT_FOUND'")
    message_pattern: str = Field(
        description="""
        Normalized regex pattern matching the error message.
        Concrete names replaced with capture groups, e.g.:
        "Property '(.+)' does not exist on type '(.+)'"
        """
    )
    file_context: str | None = Field(
        default=None,
        description="Glob pattern narrowing the error context, e.g. 'src/scenes/*.ts'"
    )


class DebugEntry(BaseModel):
    """Atomic unit of the debug protocol — one (signature, cause, fix) tuple."""
    id: str = Field(description="Unique ID, e.g. 'entry-TS2339-abc12345'")
    kind: Literal["reactive", "proactive"] = Field(
        description="reactive = diagnose after failure; proactive = validate before execution"
    )
    signature: FailureSignature
    root_cause: str = Field(description="Human-readable root-cause explanation")
    tags: list[str] = Field(default_factory=list, description="Categorized tags, e.g. ['import', 'type-mismatch']")
    fix: dict[str, Any] = Field(description="""
        The verified fix. Structure:
        {
            'type': 'edit' | 'shell' | 'config' | 'delete' | 'create',
            'description': str,           # Natural-language description
            'patch': str                  # Machine-applicable patch
        }
        For 'edit': unified diff or search/replace pair
        For 'shell': shell command string
        For 'config': JSON-patch-like operation
    """)
    occurrences: int = 0
    contributing_projects: list[str] = Field(default_factory=list)
    created_at: str
    last_matched_at: str
    generalized_from: list[str] | None = None


class ValidationCheck(BaseModel):
    """A single validation check within a ProtocolRule."""
    target: Literal["file", "config", "imports", "scene_registration", "assets"]
    file_pattern: str | None = Field(default=None, description="Glob or path pattern")
    query: str = Field(description="Regex or structured query to run against target")
    violation_message: str = Field(description="Description of what a violation looks like")


class ProtocolRule(BaseModel):
    """Generalized rule derived from repeated DebugEntries."""
    id: str
    name: str = Field(description="Human-readable name, e.g. 'Asset key consistency check'")
    description: str
    preconditions: list[str] = Field(default_factory=list, description="Conditions for rule activation")
    action: Literal["flag", "fix", "block"] = Field(description="Action when rule fires")
    checks: list[ValidationCheck]
    derived_from: list[str] = Field(description="DebugEntry IDs this rule was derived from")
    prevention_count: int = 0
    created_at: str
    updated_at: str


class DebugProtocol(BaseModel):
    """The living debugging protocol P — persisted to disk."""
    version: int = 0
    created_at: str
    updated_at: str
    seed_protocol_path: str = Field(description="Path to the seed protocol (P0) this was initialized from")
    entries: list[DebugEntry]
    rules: list[ProtocolRule]
    evolution_log: list["DebugEvolutionEntry"]


class DebugEvolutionEntry(BaseModel):
    """Entry in the debug protocol evolution log."""
    task_id: str
    timestamp: str
    project_path: str
    action: Literal["new_entry", "matched_existing", "generalized_rule"]
    entry_id: str | None = None
    rule_id: str | None = None
    details: str


class ParsedError(BaseModel):
    """A single error extracted from build/test/runtime output."""
    code: str = Field(description="Normalized error code, e.g. 'TS2339', 'ReferenceError'")
    message: str = Field(description="Original error message")
    file: str | None = None
    line: int | None = None
    column: int | None = None


class RunResult(BaseModel):
    """Result of running a single verification stage."""
    stage: Literal["build", "test", "dev"]
    success: bool
    exit_code: int
    stdout: str
    stderr: str
    errors: list[ParsedError] = Field(default_factory=list)
    duration_ms: int


class ValidationResult(BaseModel):
    """Result of a single pre-execution validation check."""
    rule_id: str
    passed: bool
    violations: list[str] = Field(default_factory=list)


class DebugIteration(BaseModel):
    """One iteration of the verify-diagnose-repair loop."""
    iteration: int
    timestamp: str
    stage: Literal["build", "test", "runtime"]
    passed: bool
    raw_error: str | None = None
    matched_entry_id: str | None = None
    new_entry_id: str | None = None
    repair_action: str | None = None
    duration_ms: int


class DebugTrace(BaseModel):
    """Complete log of one debug session on one project."""
    project_path: str
    started_at: str
    completed_at: str
    success: bool
    total_iterations: int
    max_iterations: int
    validation_results: list[ValidationResult]
    iterations: list[DebugIteration]
    new_entries: list[str]
    matched_entries: list[str]
    total_duration_ms: int


class DebugLoopResult(BaseModel):
    """Final result of the debug loop."""
    success: bool
    trace: DebugTrace
    protocol: DebugProtocol


class RepairResult(BaseModel):
    """Result of applying a repair."""
    applied: bool
    description: str
    patch: str
    verify_stage: Literal["build", "test", "dev"]
```

---

## 3.4 Game Generation Models

```python
from pydantic import BaseModel, Field
from pathlib import Path


class GameArchetypeInfo(BaseModel):
    """Metadata for a known game archetype."""
    name: str
    physics_profile: PhysicsProfile
    description: str
    example_games: list[str]


class GddSection(BaseModel):
    """A single section of the Game Design Document."""
    section_number: int
    title: str
    content: str


class GameDesignDocument(BaseModel):
    """Complete GDD for a game."""
    title: str
    archetype: str
    sections: list[GddSection]
    asset_registry: list[dict] = Field(default_factory=list)
    config_schema: list[ConfigField] = Field(default_factory=list)
    scene_registry: list[dict] = Field(default_factory=list)
    level_maps: list[dict] = Field(default_factory=list)
    implementation_roadmap: list[dict] = Field(default_factory=list)


class AssetSpec(BaseModel):
    """Specification for a single game asset."""
    key: str = Field(description="Asset key used in code, e.g. 'player_sprite'")
    type: Literal["image", "audio", "video", "tileset", "spritesheet"]
    description: str = Field(description="Generation prompt or description")
    size: str | None = None
    format: str | None = None
    output_path: str


class GeneratedAsset(BaseModel):
    """A generated asset with metadata."""
    spec: AssetSpec
    output_path: Path
    generation_time_ms: int
    provider: str


class GameResult(BaseModel):
    """Final result of game generation."""
    success: bool
    project_dir: Path
    gdd: GameDesignDocument
    assets: list[GeneratedAsset]
    debug_trace: DebugTrace | None = None
    duration_ms: int
    error: str | None = None
```

---

## 3.5 Evaluation (Bench) Models

```python
from pydantic import BaseModel, Field


class BuildHealthScore(BaseModel):
    """Build health dimension score."""
    score: float = Field(ge=0.0, le=1.0)
    compiles: bool
    test_passes: bool
    error_count: int
    warnings: list[str] = Field(default_factory=list)


class VisualUsabilityScore(BaseModel):
    """Visual usability dimension score."""
    score: float = Field(ge=0.0, le=1.0)
    renders: bool
    responds_to_input: bool
    frame_rate_stable: bool
    screenshot_path: str | None = None
    issues: list[str] = Field(default_factory=list)


class IntentAlignmentScore(BaseModel):
    """Intent alignment dimension score."""
    score: float = Field(ge=0.0, le=1.0)
    prompt: str
    vlm_reasoning: str
    criteria_met: list[str] = Field(default_factory=list)
    criteria_missed: list[str] = Field(default_factory=list)


class EvaluationResult(BaseModel):
    """Complete evaluation result for one game."""
    build_health: BuildHealthScore
    visual_usability: VisualUsabilityScore
    intent_alignment: IntentAlignmentScore
    overall: float = Field(ge=0.0, le=1.0)
    duration_ms: int
    game_dir: str
    evaluated_at: str
```

---

## 3.6 Tool System Models

```python
from pydantic import BaseModel, Field
from typing import Callable, Any
from dataclasses import dataclass


class ToolParameter(BaseModel):
    """JSON Schema for a single tool parameter."""
    name: str
    type: str
    description: str
    required: bool = True
    default: Any | None = None
    enum: list[str] | None = None


class ToolDefinition(BaseModel):
    """Complete definition of a tool for LLM consumption."""
    name: str
    description: str
    parameters: list[ToolParameter]
    returns_description: str = ""
    is_async: bool = True

    def to_json_schema(self) -> dict[str, Any]:
        """Convert to OpenAI-compatible function schema."""
        properties = {}
        required = []
        for p in self.parameters:
            prop = {"type": p.type, "description": p.description}
            if p.enum:
                prop["enum"] = p.enum
            properties[p.name] = prop
            if p.required:
                required.append(p.name)
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }


@dataclass
class ToolCall:
    """A parsed tool call from the LLM response."""
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ToolResult:
    """Result of executing a tool call."""
    call_id: str
    name: str
    output: str
    error: str | None = None
    duration_ms: int = 0


class TurnResult(BaseModel):
    """Result of one turn in the conversation loop."""
    text: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    tool_results: list[ToolResult] = Field(default_factory=list)
    finished: bool = False
    token_usage: dict[str, int] = Field(default_factory=dict)
```
