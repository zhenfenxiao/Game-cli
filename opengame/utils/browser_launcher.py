"""Secure browser launch utility.

Opens a URL in the system's default web browser. This is a placeholder
that will be replaced with Playwright-based headless browsing in Phase 6.
"""

from __future__ import annotations

import webbrowser
from typing import Any


def launch_browser(url: str) -> dict[str, Any]:
    """Launch the system's default browser to open a URL.

    Args:
        url: The URL to open.

    Returns:
        Dict with success status and optional error message.
    """
    if not url:
        return {"success": False, "error": "No URL provided"}

    try:
        opened = webbrowser.open(url)
        if opened:
            return {"success": True, "url": url}
        return {"success": False, "error": "Failed to open browser", "url": url}
    except Exception as e:
        return {"success": False, "error": str(e), "url": url}
