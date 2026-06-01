"""Interactive tools: ask_user, propose_design.

Tools that require user interaction — the ask_user tool raises
UserQuestionRequested to pause agent execution until the user responds.
"""

from __future__ import annotations

from opengame.core.exceptions import UserQuestionRequested
from opengame.core.tool_registry import ToolParameter, ToolRegistry


def register_interactive_tools(registry: ToolRegistry) -> None:
    """Register interactive tools (ask_user, propose_design).

    These tools enable the agent to interact with the user during
    an interactive shell session.

    Args:
        registry: ToolRegistry to register tools with.
    """

    @registry.tool(
        name="ask_user",
        description="Ask the user a question when you need clarification. "
        "Use this when you're unsure about requirements, design choices, "
        "or need the user to choose between options. "
        "The user's response will be provided as the tool output.",
        parameters=[
            ToolParameter(
                name="question",
                type="string",
                description="The question to ask the user. Be specific and clear.",
                required=True,
            ),
            ToolParameter(
                name="header",
                type="string",
                description="Short label for the question (max 12 chars), e.g. 'Color', 'Difficulty'",
                required=False,
            ),
            ToolParameter(
                name="options",
                type="string",
                description="Optional JSON array of choices, e.g. '[\"easy\", \"medium\", \"hard\"]'. "
                "If provided, the user should pick from these options.",
                required=False,
            ),
        ],
    )
    async def ask_user(question: str, header: str = "", options: str = "") -> str:
        """Ask the user a question and wait for their response.

        This tool pauses agent execution. The interactive shell displays
        the question to the user and injects their response as the tool output.
        """
        import json

        option_list = None
        if options:
            try:
                option_list = json.loads(options) if isinstance(options, str) else options
            except json.JSONDecodeError:
                option_list = [options]

        raise UserQuestionRequested(
            question=question,
            header=header or "Question",
            options=option_list,
        )

    @registry.tool(
        name="propose_design",
        description="Propose an implementation design for the user to review. "
        "Output a detailed plan with approach, files to modify, and trade-offs. "
        "The user will approve, reject, or modify the plan before implementation.",
        parameters=[
            ToolParameter(
                name="title",
                type="string",
                description="Short title for the design proposal",
                required=True,
            ),
            ToolParameter(
                name="plan",
                type="string",
                description="Detailed implementation plan with approach, files, and trade-offs. "
                "Use markdown format.",
                required=True,
            ),
        ],
    )
    async def propose_design(title: str, plan: str) -> str:
        """Propose an implementation design for user review.

        This tool pauses agent execution to present a design proposal.
        The user can approve, reject, or modify the plan.
        """
        raise UserQuestionRequested(
            question=f"## {title}\n\n{plan}\n\nDo you approve this design? (yes / no / changes needed)",
            header="Design Review",
            options=["approve", "reject", "request changes"],
        )
