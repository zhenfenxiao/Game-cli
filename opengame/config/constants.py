"""Configuration constants for OpenGame.

Default paths, model names, and environment variable mappings.
"""

from pathlib import Path

# Config file paths
USER_SETTINGS_DIR = Path.home() / ".opengame"
PROJECT_SETTINGS_DIR = Path(".opengame")
USER_SETTINGS_FILE = USER_SETTINGS_DIR / "settings.json"
PROJECT_SETTINGS_FILE = PROJECT_SETTINGS_DIR / "settings.json"

# Default model names
DEFAULT_LLM_MODEL = "gpt-4o"
DEFAULT_LLM_PROVIDER = "openai"
DEFAULT_LLM_BASE_URL = "https://api.openai.com/v1"
DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_TOKENS = 4096
DEFAULT_TIMEOUT = 120

# Approval modes
APPROVAL_MODE_ASK = "ask"
APPROVAL_MODE_AUTO_EDIT = "auto-edit"
APPROVAL_MODE_YOLO = "yolo"

# Asset provider names
IMAGE_PROVIDER_TONGYI = "tongyi"
IMAGE_PROVIDER_DOUBAO = "doubao"
IMAGE_PROVIDER_OPENAI = "openai-compat"
IMAGE_PROVIDER_FAL = "fal"

# LLM provider names
LLM_PROVIDER_OPENAI = "openai"
LLM_PROVIDER_ANTHROPIC = "anthropic"
LLM_PROVIDER_DASHSCOPE = "dashscope"
LLM_PROVIDER_DEEPSEEK = "deepseek"
LLM_PROVIDER_OPENROUTER = "openrouter"

# Environment variable mappings
ENV_MAPPINGS: dict[str, tuple[str, str]] = {
    "OPENAI_API_KEY": ("llm", "api_key"),
    "OPENAI_BASE_URL": ("llm", "base_url"),
    "OPENAI_MODEL": ("llm", "model"),
    "OPENGAME_IMAGE_PROVIDER": ("image", "provider"),
    "OPENGAME_IMAGE_API_KEY": ("image", "api_key"),
    "OPENGAME_IMAGE_BASE_URL": ("image", "base_url"),
    "OPENGAME_IMAGE_MODEL": ("image", "model"),
    "OPENGAME_AUDIO_PROVIDER": ("audio", "provider"),
    "OPENGAME_AUDIO_API_KEY": ("audio", "api_key"),
    "OPENGAME_AUDIO_BASE_URL": ("audio", "base_url"),
    "OPENGAME_AUDIO_MODEL": ("audio", "model"),
    "OPENGAME_VIDEO_PROVIDER": ("video", "provider"),
    "OPENGAME_VIDEO_API_KEY": ("video", "api_key"),
    "OPENGAME_VIDEO_BASE_URL": ("video", "base_url"),
    "OPENGAME_VIDEO_MODEL": ("video", "model"),
    "OPENGAME_REASONING_PROVIDER": ("reasoning", "provider"),
    "OPENGAME_REASONING_API_KEY": ("reasoning", "api_key"),
    "OPENGAME_REASONING_BASE_URL": ("reasoning", "base_url"),
    "OPENGAME_REASONING_MODEL": ("reasoning", "model"),
    "GAME_TEMPLATES_DIR": ("game_skill", "templates_dir"),
    "GAME_DOCS_DIR": ("game_skill", "docs_dir"),
}

# Max debug iterations
MAX_DEBUG_ITERATIONS = 20
EVOLVE_AFTER_DEBUG = True
