"""Interactive-mode exceptions — used to pause agent execution for user input."""

from __future__ import annotations

from typing import Any


class UserQuestionRequested(Exception):
    """Raised by the ask_user tool to pause execution and prompt the user.

    The interactive shell catches this exception, displays the question
    to the user, collects their response, and sets it on the exception.
    The ToolScheduler then converts the exception into a ToolResult
    with the user's answer as the output.

    Usage:
        raise UserQuestionRequested(
            question="Which color theme do you prefer?",
            header="Theme Selection",
            options=["dark", "light", "colorful"],
        )
        # ... shell catches, displays, gets user input ...
        # exception.response = "dark"
        # ToolScheduler converts to ToolResult(output="dark")
    """

    def __init__(
        self,
        question: str,
        header: str = "",
        options: list[str] | None = None,
    ) -> None:
        self.question = question
        self.header = header
        self.options = options or []
        self.response: str | None = None  # Filled by the shell after user input
        super().__init__(question)
