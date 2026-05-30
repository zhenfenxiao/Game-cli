# 10 — Tool Reference

This document defines all tools available to the agent, including their schemas, behaviors, and implementation notes.

## 10.1 Tool Registration Convention

All tools are registered with the `@tool` decorator:

```python
from opengame.core.tool_registry import tool

@tool(
    name="tool_name",
    description="What this tool does",
    schema={
        "type": "object",
        "properties": {...},
        "required": [...]
    }
)
async def tool_name(param1: str, param2: int = 0) -> str:
    ...
```

## 10.2 File Tools

### read_file

Read the contents of a file.

```python
@tool(
    name="read_file",
    description="Read the contents of a file. Use absolute paths. Supports offset and limit for large files.",
    schema={
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Absolute path to the file to read"
            },
            "offset": {
                "type": "integer",
                "description": "Line number to start reading from (1-indexed)",
                "default": 0
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of lines to read",
                "default": 2000
            }
        },
        "required": ["file_path"]
    }
)
async def read_file(file_path: str, offset: int = 0, limit: int = 2000) -> str:
    """
    Read a file with optional offset and limit.

    Args:
        file_path: Absolute path to the file
        offset: Starting line (0-indexed)
        limit: Maximum lines to read

    Returns:
        File contents as string
    """
    async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
        lines = []
        async for i, line in enumerate(f):
            if i < offset:
                continue
            if len(lines) >= limit:
                break
            lines.append(line)
        return "".join(lines)
```

### read_many_files

Read multiple files in parallel.

```python
@tool(
    name="read_many_files",
    description="Read multiple files at once. More efficient than calling read_file multiple times.",
    schema={
        "type": "object",
        "properties": {
            "file_paths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of absolute file paths to read"
            }
        },
        "required": ["file_paths"]
    }
)
async def read_many_files(file_paths: list[str]) -> dict[str, str]:
    """Read multiple files concurrently. Returns dict mapping path to contents."""
    async def read_one(path: str) -> tuple[str, str]:
        try:
            async with aiofiles.open(path, "r", encoding="utf-8") as f:
                return path, await f.read()
        except Exception as e:
            return path, f"ERROR: {e}"

    results = await asyncio.gather(*[read_one(p) for p in file_paths])
    return {path: content for path, content in results}
```

### write_file

Write or overwrite a file.

```python
@tool(
    name="write_file",
    description="Write content to a file. Creates the file if it doesn't exist, overwrites if it does.",
    schema={
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Absolute path to write to"
            },
            "content": {
                "type": "string",
                "description": "Content to write"
            }
        },
        "required": ["file_path", "content"]
    }
)
async def write_file(file_path: str, content: str) -> str:
    """Write content to a file, creating parent directories as needed."""
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(path, "w", encoding="utf-8") as f:
        await f.write(content)
    return f"Wrote {len(content)} characters to {file_path}"
```

### edit

Search-and-replace edit.

```python
@tool(
    name="edit",
    description="Edit a file by replacing old_string with new_string. The old_string must match exactly.",
    schema={
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Absolute path to the file"
            },
            "old_string": {
                "type": "string",
                "description": "Exact text to replace (must be unique in file)"
            },
            "new_string": {
                "type": "string",
                "description": "Replacement text"
            }
        },
        "required": ["file_path", "old_string", "new_string"]
    }
)
async def edit(file_path: str, old_string: str, new_string: str) -> str:
    """
    Replace old_string with new_string in a file.

    old_string must appear exactly once in the file.
    """
    async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
        content = await f.read()

    if old_string not in content:
        return f"ERROR: old_string not found in {file_path}"

    if content.count(old_string) > 1:
        return f"ERROR: old_string appears multiple times in {file_path}. Be more specific."

    content = content.replace(old_string, new_string, 1)

    async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
        await f.write(content)

    return f"Edited {file_path}: replaced {len(old_string)} chars with {len(new_string)} chars"
```

### smart_edit

AI-assisted edit with context.

```python
@tool(
    name="smart_edit",
    description="Make an intelligent edit to a file. The LLM will determine the exact change based on your description.",
    schema={
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Absolute path to the file"
            },
            "instruction": {
                "type": "string",
                "description": "Natural language description of the desired change"
            }
        },
        "required": ["file_path", "instruction"]
    }
)
async def smart_edit(file_path: str, instruction: str, llm_client: BaseLlmClient) -> str:
    """
    Use LLM to make an intelligent edit based on a description.

    1. Read the file
    2. Ask LLM to apply the instruction
    3. Apply the resulting edit
    """
    async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
        content = await f.read()

    prompt = f"""You are editing a file. Make the following change:

Instruction: {instruction}

File content:
```
{content}
```

Output ONLY the edit as:
OLD:
<exact text to replace>
NEW:
<replacement text>

If no change is needed, output "NO_CHANGE"."""

    response = await llm_client.generate(
        messages=[{"role": "user", "content": prompt}],
        stream=False,
        max_tokens=4000,
    )

    if not response.content or "NO_CHANGE" in response.content:
        return "No change needed"

    # Parse OLD/NEW
    parts = response.content.split("NEW:")
    if len(parts) != 2:
        return "ERROR: Could not parse edit"

    old_str = parts[0].replace("OLD:", "").strip()
    new_str = parts[1].strip()

    if old_str not in content:
        return f"ERROR: Generated old_string not found in file"

    content = content.replace(old_str, new_str, 1)

    async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
        await f.write(content)

    return f"Smart-edited {file_path}"
```

### glob

Find files matching a glob pattern.

```python
@tool(
    name="glob",
    description="Find files matching a glob pattern. Returns list of absolute paths.",
    schema={
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Glob pattern, e.g. '**/*.ts', 'src/**/*.test.ts'"
            },
            "directory": {
                "type": "string",
                "description": "Directory to search in (default: project root)",
                "default": "."
            }
        },
        "required": ["pattern"]
    }
)
async def glob(pattern: str, directory: str = ".") -> list[str]:
    """Find files matching a glob pattern."""
    from pathlib import Path
    import fnmatch

    base = Path(directory).resolve()
    matches = []

    for path in base.rglob("*"):
        rel = str(path.relative_to(base))
        if fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(path.name, pattern):
            matches.append(str(path))

    return sorted(matches)
```

### grep

Search for text in files.

```python
@tool(
    name="grep",
    description="Search for text in files. Returns matching lines with file paths and line numbers.",
    schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Text or regex pattern to search for"
            },
            "path": {
                "type": "string",
                "description": "Directory or file to search in"
            },
            "is_regex": {
                "type": "boolean",
                "description": "Whether query is a regex pattern",
                "default": False
            }
        },
        "required": ["query", "path"]
    }
)
async def grep(query: str, path: str, is_regex: bool = False) -> list[dict]:
    """Search for text in files."""
    import re
    pattern = re.compile(query) if is_regex else re.compile(re.escape(query))

    target = Path(path)
    results = []

    files_to_search = [target] if target.is_file() else list(target.rglob("*"))

    for file_path in files_to_search:
        if not file_path.is_file():
            continue
        try:
            async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
                async for i, line in enumerate(f, 1):
                    if pattern.search(line):
                        results.append({
                            "file": str(file_path),
                            "line": i,
                            "text": line.rstrip("\n"),
                        })
        except (UnicodeDecodeError, PermissionError):
            continue

    return results
```

### ls

List directory contents.

```python
@tool(
    name="ls",
    description="List the contents of a directory with file sizes and types.",
    schema={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute path to the directory"
            }
        },
        "required": ["path"]
    }
)
async def ls(path: str) -> list[dict]:
    """List directory contents."""
    target = Path(path)
    if not target.exists():
        return [{"error": f"Path does not exist: {path}"}]
    if not target.is_dir():
        return [{"error": f"Not a directory: {path}"}]

    results = []
    for item in sorted(target.iterdir()):
        stat = item.stat()
        results.append({
            "name": item.name,
            "type": "directory" if item.is_dir() else "file",
            "size": stat.st_size if item.is_file() else None,
        })
    return results
```

## 10.3 Shell Tool

```python
@tool(
    name="shell",
    description="Execute a shell command. Use with caution. Prefer file tools for file operations.",
    schema={
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "Shell command to execute"
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in seconds",
                "default": 120
            }
        },
        "required": ["command"]
    }
)
async def shell(command: str, timeout: int = 120) -> dict:
    """
    Execute a shell command.

    WARNING: Shell commands can modify the system. Read-only commands are preferred.
    """
    # Check if command is read-only
    checker = ShellReadOnlyChecker()
    if not checker.is_read_only(command):
        # In non-yolo mode, would ask for approval
        pass

    proc = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return {
            "exit_code": proc.returncode,
            "stdout": stdout.decode("utf-8", errors="replace"),
            "stderr": stderr.decode("utf-8", errors="replace"),
        }
    except asyncio.TimeoutError:
        proc.kill()
        return {
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Command timed out after {timeout}s",
        }
```

### ShellReadOnlyChecker

```python
class ShellReadOnlyChecker:
    """Check if a shell command is read-only (safe to run without approval)."""

    READ_ONLY_PATTERNS = [
        r"^ls\b",
        r"^cat\b",
        r"^head\b",
        r"^tail\b",
        r"^grep\b",
        r"^find\b",
        r"^pwd\b",
        r"^echo\b",
        r"^git\s+(status|log|diff|show|branch)\b",
        r"^npm\s+run\s+(build|test|dev)\b",
        r"^node\s+--version\b",
        r"^python\s+--version\b",
    ]

    DANGEROUS_PATTERNS = [
        r"rm\s+-rf\b",
        r">\s*/dev",
        r"dd\s+if=",
        r"mkfs",
        r"chmod\s+777",
    ]

    def is_read_only(self, command: str) -> bool:
        """Check if a command is read-only."""
        import re
        cmd = command.strip()

        # Check dangerous patterns first
        for pattern in self.DANGEROUS_PATTERNS:
            if re.search(pattern, cmd, re.I):
                return False

        # Check read-only patterns
        for pattern in self.READ_ONLY_PATTERNS:
            if re.search(pattern, cmd, re.I):
                return True

        return False
```

## 10.4 Web Tools

### web_fetch

```python
@tool(
    name="web_fetch",
    description="Fetch and parse content from a URL. Returns markdown-formatted content.",
    schema={
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "URL to fetch"
            }
        },
        "required": ["url"]
    }
)
async def web_fetch(url: str) -> str:
    """Fetch content from a URL and convert to markdown."""
    async with httpx.AsyncClient() as client:
        response = await client.get(url, timeout=30)
        response.raise_for_status()

        content_type = response.headers.get("content-type", "")

        if "text/html" in content_type:
            # Simple HTML to text conversion
            import re
            text = re.sub(r"<script[^>]*>.*?</script>", "", response.text, flags=re.DOTALL)
            text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
            text = re.sub(r"<[^>]+>", "", text)
            text = re.sub(r"\n\s*\n", "\n\n", text)
            return text.strip()
        else:
            return response.text
```

### web_search

```python
@tool(
    name="web_search",
    description="Search the web and return relevant results.",
    schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query"
            },
            "num_results": {
                "type": "integer",
                "description": "Number of results to return",
                "default": 5
            }
        },
        "required": ["query"]
    }
)
async def web_search(query: str, num_results: int = 5) -> list[dict]:
    """Search the web using configured provider."""
    # Implementation depends on search provider (Google, Tavily, DashScope, etc.)
    # Returns list of {title, url, snippet} dicts
    raise NotImplementedError("Web search requires a configured provider")
```

## 10.5 Memory Tool

```python
@tool(
    name="save_memory",
    description="Save a fact or preference to persistent memory for future sessions.",
    schema={
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "Content to remember"
            },
            "category": {
                "type": "string",
                "description": "Category: user, project, feedback, reference",
                "enum": ["user", "project", "feedback", "reference"]
            }
        },
        "required": ["content", "category"]
    }
)
async def save_memory(content: str, category: str) -> str:
    """Save content to persistent memory."""
    memory_dir = Path.home() / ".opengame" / "memory"
    memory_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.utcnow().isoformat()
    filename = f"{category}_{timestamp.replace(':', '-')}.md"

    memory_file = memory_dir / filename
    async with aiofiles.open(memory_file, "w") as f:
        await f.write(f"---\ncategory: {category}\ntimestamp: {timestamp}\n---\n\n{content}\n")

    return f"Memory saved to {memory_file}"
```

## 10.6 Task Management Tools

### todo_write

```python
@tool(
    name="todo_write",
    description="Write a todo list. Replaces the current list. Use frequently to track progress.",
    schema={
        "type": "object",
        "properties": {
            "todos": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "content": {"type": "string"},
                        "status": {"type": "string", "enum": ["pending", "in_progress", "completed"]},
                        "priority": {"type": "integer", "default": 1}
                    }
                }
            }
        },
        "required": ["todos"]
    }
)
async def todo_write(todos: list[dict]) -> str:
    """Write the current todo list."""
    # Store in agent context
    return f"Updated todo list with {len(todos)} items"
```

### task_create

```python
@tool(
    name="task_create",
    description="Create a tracked task for complex multi-step work.",
    schema={
        "type": "object",
        "properties": {
            "subject": {
                "type": "string",
                "description": "Brief task title"
            },
            "description": {
                "type": "string",
                "description": "Detailed description"
            }
        },
        "required": ["subject", "description"]
    }
)
async def task_create(subject: str, description: str) -> str:
    """Create a tracked task."""
    task_id = f"task-{uuid.uuid4().hex[:8]}"
    return f"Created task {task_id}: {subject}"
```

### task_update

```python
@tool(
    name="task_update",
    description="Update a task's status.",
    schema={
        "type": "object",
        "properties": {
            "task_id": {"type": "string"},
            "status": {"type": "string", "enum": ["pending", "in_progress", "completed"]}
        },
        "required": ["task_id", "status"]
    }
)
async def task_update(task_id: str, status: str) -> str:
    """Update a task's status."""
    return f"Updated task {task_id} to {status}"
```

## 10.7 Game-Specific Tools

### classify_game_type

```python
@tool(
    name="classify_game_type",
    description="Classify a game idea into an archetype based on physics regime.",
    schema={
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "User's game description"
            }
        },
        "required": ["prompt"]
    }
)
async def classify_game_type(prompt: str) -> dict:
    """Classify game type from prompt."""
    # Uses keyword heuristics + optional LLM
    prompt_lower = prompt.lower()

    keywords = {
        "platformer": ["platform", "jump", "gravity", "side-scrolling"],
        "top_down": ["top-down", "overhead", "shooter"],
        "grid_logic": ["grid", "puzzle", "match", "board"],
        "tower_defense": ["tower defense", "wave", "turret"],
        "ui_heavy": ["card game", "visual novel", "quiz"],
    }

    scores = {arch: sum(1 for kw in kws if kw in prompt_lower) for arch, kws in keywords.items()}
    best = max(scores, key=scores.get)

    return {
        "archetype": best,
        "confidence": scores[best] / max(len(keywords[best]), 1),
        "physics_profile": {
            "has_gravity": best == "platformer",
            "perspective": "side" if best == "platformer" else "top_down" if best in ("top_down", "grid_logic", "tower_defense") else "none",
            "movement_type": "continuous" if best in ("platformer", "top_down") else "grid" if best == "grid_logic" else "path" if best == "tower_defense" else "ui_only",
        }
    }
```

### generate_gdd

```python
@tool(
    name="generate_gdd",
    description="Generate a Game Design Document from a game description and archetype.",
    schema={
        "type": "object",
        "properties": {
            "raw_user_requirement": {
                "type": "string",
                "description": "User's game description"
            },
            "archetype": {
                "type": "string",
                "description": "Game archetype"
            }
        },
        "required": ["raw_user_requirement", "archetype"]
    }
)
async def generate_gdd(raw_user_requirement: str, archetype: str) -> str:
    """Generate a GDD. Returns the markdown content."""
    # This would use the LLM to generate the GDD
    # Implementation is in GameSkillOrchestrator
    return "GDD generated"
```

### generate_game_assets

```python
@tool(
    name="generate_game_assets",
    description="Generate game assets (images, audio) from an asset registry.",
    schema={
        "type": "object",
        "properties": {
            "assets": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "key": {"type": "string"},
                        "type": {"type": "string", "enum": ["image", "audio", "video"]},
                        "description": {"type": "string"},
                        "output_path": {"type": "string"}
                    }
                }
            }
        },
        "required": ["assets"]
    }
)
async def generate_game_assets(assets: list[dict]) -> list[dict]:
    """Generate game assets. Returns list of generation results."""
    # Routes to AssetService
    results = []
    for asset in assets:
        # Generate each asset
        results.append({"key": asset["key"], "status": "generated", "path": asset["output_path"]})
    return results
```

### generate_tilemap

```python
@tool(
    name="generate_tilemap",
    description="Generate a tilemap from an ASCII layout.",
    schema={
        "type": "object",
        "properties": {
            "ascii_map": {
                "type": "string",
                "description": "ASCII representation of the map"
            },
            "tile_mapping": {
                "type": "object",
                "description": "Map of ASCII chars to tile IDs"
            },
            "output_path": {
                "type": "string",
                "description": "Where to save the tilemap JSON"
            }
        },
        "required": ["ascii_map", "tile_mapping", "output_path"]
    }
)
async def generate_tilemap(ascii_map: str, tile_mapping: dict, output_path: str) -> str:
    """Generate a Phaser-compatible tilemap from ASCII."""
    lines = ascii_map.strip().split("\n")
    height = len(lines)
    width = max(len(line) for line in lines) if lines else 0

    # Build tile data
    data = []
    for line in lines:
        row = []
        for char in line:
            tile_id = tile_mapping.get(char, 0)
            row.append(tile_id)
        # Pad to width
        while len(row) < width:
            row.append(0)
        data.append(row)

    tilemap = {
        "width": width,
        "height": height,
        "tileWidth": 32,
        "tileHeight": 32,
        "layers": [{
            "name": "ground",
            "data": data,
        }]
    }

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(path, "w") as f:
        await f.write(json.dumps(tilemap, indent=2))

    return f"Tilemap saved to {output_path}"
```

## 10.8 Subagent Tool

```python
@tool(
    name="subagent",
    description="Delegate a task to a specialized subagent. Useful for parallel work or specialized expertise.",
    schema={
        "type": "object",
        "properties": {
            "description": {
                "type": "string",
                "description": "Brief description of the subagent's task"
            },
            "prompt": {
                "type": "string",
                "description": "Full prompt/instructions for the subagent"
            },
            "tools": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of tool names the subagent can use"
            }
        },
        "required": ["description", "prompt"]
    }
)
async def subagent(description: str, prompt: str, tools: list[str] | None = None) -> str:
    """
    Spawn a subagent to handle a task.

    The subagent gets its own context and runs independently.
    """
    # Create a new agent context
    sub_context = AgentContext()

    # Filter tools if specified
    available_tools = tool_registry.get_tool_definitions()
    if tools:
        available_tools = [t for t in available_tools if t["function"]["name"] in tools]

    # Run subagent
    result = await turn_loop.run(
        system_prompt="You are a specialized subagent. " + description,
        user_message=prompt,
        context=sub_context,
    )

    return result.text or "Subagent completed"
```

## 10.9 Exit Plan Mode

```python
@tool(
    name="exit_plan_mode",
    description="Exit planning mode and begin implementation. Use after the plan is finalized.",
    schema={
        "type": "object",
        "properties": {},
        "required": []
    }
)
async def exit_plan_mode() -> str:
    """Exit planning mode."""
    return "Exited planning mode. Beginning implementation."
```

## 10.10 Complete Tool Catalog

| Tool | Async | Category | Description |
|------|-------|----------|-------------|
| `read_file` | Yes | File | Read file with offset/limit |
| `read_many_files` | Yes | File | Read multiple files in parallel |
| `write_file` | Yes | File | Write/overwrite file |
| `edit` | Yes | File | Search-and-replace edit |
| `smart_edit` | Yes | File | AI-assisted edit |
| `glob` | Yes | File | Find files by glob pattern |
| `grep` | Yes | File | Search file contents |
| `ls` | Yes | File | List directory |
| `shell` | Yes | System | Execute shell command |
| `web_fetch` | Yes | Web | Fetch URL content |
| `web_search` | Yes | Web | Search the web |
| `save_memory` | Yes | Memory | Save to persistent memory |
| `todo_write` | Yes | Task | Manage todo list |
| `task_create` | Yes | Task | Create tracked task |
| `task_update` | Yes | Task | Update task status |
| `classify_game_type` | Yes | Game | Classify game archetype |
| `generate_gdd` | Yes | Game | Generate game design doc |
| `generate_game_assets` | Yes | Game | Generate game assets |
| `generate_tilemap` | Yes | Game | Generate tilemap from ASCII |
| `subagent` | Yes | Agent | Delegate to subagent |
| `exit_plan_mode` | Yes | Control | Exit planning mode |
