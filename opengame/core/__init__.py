"""Core agent runtime package.

Provides the tool registry, LLM clients, prompt assembly, tool scheduling,
agent context, content generation, and token limit checking.
"""

from opengame.core.agent_context import AgentContext, TurnLoopResult
from opengame.core.chat_compression_service import ChatCompressionService, CompressionResult, CompressionStatus
from opengame.core.content_generator import ContentGenerator
from opengame.core.llm_client import BaseLlmClient, LlmResponse
from opengame.core.openai_client import OpenAiClient
from opengame.core.prompts import PromptAssembler
from opengame.core.token_limit_checker import TokenLimitChecker, get_model_output_limit
from opengame.core.tool_output_summarizer import ToolOutputSummarizer
from opengame.core.tool_output_truncator import ToolOutputTruncator
from opengame.core.tool_registry import ToolRegistry
from opengame.core.tool_scheduler import execute_all
from opengame.core.turn_loop import TurnLoop

__all__ = [
    "AgentContext",
    "TurnLoopResult",
    "ToolRegistry",
    "BaseLlmClient",
    "LlmResponse",
    "OpenAiClient",
    "PromptAssembler",
    "ContentGenerator",
    "TokenLimitChecker",
    "get_model_output_limit",
    "ChatCompressionService",
    "CompressionResult",
    "CompressionStatus",
    "ToolOutputSummarizer",
    "ToolOutputTruncator",
    "TurnLoop",
    "execute_all",
]
