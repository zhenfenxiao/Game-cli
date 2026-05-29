"""Task management tools: todo_write, task_create, task_update.

todo_write requires access to the TurnLoop's AgentContext for state mutation,
which is injected via closure at registration time.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from opengame.core.tool_registry import ToolParameter, ToolRegistry


def register_task_tools(
    registry: ToolRegistry,
    turn_loop: Any | None = None,
) -> None:
    """Register task management tools.

    Args:
        registry: ToolRegistry to register tools with.
        turn_loop: Optional TurnLoop instance for todo_write context injection.
    """

    # --- todo_write ---
    if turn_loop:

        async def todo_write(todos: str) -> str:
            """Replace the current todo list with a new one.

            Accepts a JSON string of todo items, each with id, content, status, and priority.
            """
            try:
                todo_items = json.loads(todos) if isinstance(todos, str) else todos
                if not isinstance(todo_items, list):
                    return "Error: todos must be a JSON array of todo items"
            except json.JSONDecodeError as e:
                return f"Error parsing todos JSON: {e}"

            if turn_loop.context:
                turn_loop.context.todo_list = todo_items

            return f"Updated todo list with {len(todo_items)} items"

        registry.register(
            name="todo_write",
            func=todo_write,
            description="Write a todo list to track your progress on complex tasks. "
            "Replaces the current list. Each item should have: id, content, status "
            "(pending/in_progress/completed), and priority (high/medium/low).",
            parameters=[
                ToolParameter(
                    name="todos",
                    type="string",
                    description="JSON string of todo items array. Each item: "
                    "{id, content, status, priority}",
                    required=True,
                ),
            ],
        )

    # --- task_create ---
    @registry.tool(
        name="task_create",
        description="Create a tracked task for the current session. Returns a task ID "
        "that can be used with task_update.",
        parameters=[
            ToolParameter(name="subject", type="string", description="Brief task title", required=True),
            ToolParameter(name="description", type="string", description="What needs to be done", required=True),
        ],
    )
    async def task_create(subject: str, description: str) -> str:
        task_id = str(uuid.uuid4())[:8]
        task = {
            "id": task_id,
            "subject": subject,
            "description": description,
            "status": "pending",
        }
        return json.dumps(task, ensure_ascii=False, indent=2)

    # --- task_update ---
    @registry.tool(
        name="task_update",
        description="Update the status of a tracked task.",
        parameters=[
            ToolParameter(name="task_id", type="string", description="The task ID from task_create", required=True),
            ToolParameter(
                name="status",
                type="string",
                description="New status",
                enum=["pending", "in_progress", "completed", "deleted"],
                required=True,
            ),
        ],
    )
    async def task_update(task_id: str, status: str) -> str:
        valid_statuses = {"pending", "in_progress", "completed", "deleted"}
        if status not in valid_statuses:
            return f"Error: invalid status '{status}'. Must be one of: {', '.join(sorted(valid_statuses))}"
        return json.dumps({"task_id": task_id, "status": status, "updated": True}, ensure_ascii=False)
