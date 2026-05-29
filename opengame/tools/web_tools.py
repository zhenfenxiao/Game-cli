"""Web tools: web_fetch and web_search.

web_fetch uses httpx to retrieve web content.
web_search is a stub that requires a search provider integration.
"""

from __future__ import annotations

import re

import httpx

from opengame.core.tool_registry import ToolParameter, ToolRegistry


def register_web_tools(registry: ToolRegistry) -> None:
    """Register web interaction tools.

    Args:
        registry: ToolRegistry to register tools with.
    """

    @registry.tool(
        name="web_fetch",
        description="Fetch content from a URL. Returns plain text content with "
        "HTML tags stripped for readability. Use for reading documentation, "
        "API references, and web pages.",
        parameters=[
            ToolParameter(
                name="url",
                type="string",
                description="The URL to fetch (must start with http:// or https://)",
                required=True,
            ),
        ],
    )
    async def web_fetch(url: str) -> str:
        if not url.startswith(("http://", "https://")):
            return "Error: URL must start with http:// or https://"

        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(url, headers={
                    "User-Agent": "OpenGame/0.6.0",
                    "Accept": "text/html,text/plain,*/*",
                })
                response.raise_for_status()

                content_type = response.headers.get("content-type", "")
                text = response.text

                if "text/html" in content_type:
                    # Strip HTML tags for LLM consumption
                    text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
                    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
                    text = re.sub(r"<[^>]+>", " ", text)
                    text = re.sub(r"\s+", " ", text)
                    text = text.strip()

                # Truncate to reasonable size
                if len(text) > 10_000:
                    text = text[:10_000] + "\n\n[... Content truncated at 10000 characters ...]"

                return text

        except httpx.HTTPStatusError as e:
            return f"HTTP error {e.response.status_code}: {e.response.reason_phrase}"
        except httpx.RequestError as e:
            return f"Request error: {e}"
        except Exception as e:
            return f"Error fetching URL: {e}"

    @registry.tool(
        name="web_search",
        description="Search the web for information. Returns titles, URLs, and snippets "
        "of relevant pages. Requires a search provider to be configured.",
        parameters=[
            ToolParameter(
                name="query",
                type="string",
                description="The search query",
                required=True,
            ),
            ToolParameter(
                name="num_results",
                type="integer",
                description="Number of results to return (default 5)",
                required=False,
                default=5,
            ),
        ],
    )
    async def web_search(query: str, num_results: int = 5) -> str:
        return (
            "Web search is not yet configured. To enable web search, configure a "
            "search provider (Google, Tavily, DashScope) in your OpenGame settings.\n\n"
            "In the meantime, use web_fetch to retrieve content from known URLs."
        )
