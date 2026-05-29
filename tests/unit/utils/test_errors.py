"""Tests for the exception hierarchy."""

from opengame.utils.errors import (
    AssetError,
    ConfigError,
    DebugError,
    LlmError,
    OpenGameError,
    ToolError,
)


class TestOpenGameError:
    """Tests for the base OpenGameError class."""

    def test_construction_basic(self) -> None:
        """Error can be constructed with just a message."""
        e = OpenGameError("something went wrong")
        assert e.message == "something went wrong"
        assert e.context == {}
        assert e.recoverable is False

    def test_construction_with_context(self) -> None:
        """Error can carry structured context."""
        e = OpenGameError("failed", {"path": "/tmp", "code": 42}, recoverable=True)
        assert e.context == {"path": "/tmp", "code": 42}
        assert e.recoverable is True

    def test_str_representation(self) -> None:
        """__str__ includes the error class name and message."""
        e = OpenGameError("test message")
        assert "OpenGameError" in str(e)
        assert "test message" in str(e)

    def test_str_with_context(self) -> None:
        """__str__ includes context when present."""
        e = OpenGameError("failed", {"key": "val"})
        assert "key=val" in str(e)


class TestExceptionHierarchy:
    """Tests for inheritance and isinstance checks."""

    def test_llm_error_is_opengame_error(self) -> None:
        """LlmError inherits from OpenGameError."""
        e = LlmError("api timeout")
        assert isinstance(e, OpenGameError)
        assert isinstance(e, Exception)

    def test_tool_error_is_opengame_error(self) -> None:
        """ToolError inherits from OpenGameError."""
        e = ToolError("tool failed")
        assert isinstance(e, OpenGameError)

    def test_config_error_is_opengame_error(self) -> None:
        """ConfigError inherits from OpenGameError."""
        e = ConfigError("invalid config")
        assert isinstance(e, OpenGameError)

    def test_debug_error_is_opengame_error(self) -> None:
        """DebugError inherits from OpenGameError."""
        e = DebugError("debug loop failed")
        assert isinstance(e, OpenGameError)

    def test_asset_error_is_opengame_error(self) -> None:
        """AssetError inherits from OpenGameError."""
        e = AssetError("generation failed")
        assert isinstance(e, OpenGameError)

    def test_all_errors_carry_context(self) -> None:
        """All error subclasses support the full constructor."""
        for cls in [LlmError, ToolError, ConfigError, DebugError, AssetError]:
            e = cls("msg", {"key": "val"}, recoverable=True)
            assert e.message == "msg"
            assert e.context == {"key": "val"}
            assert e.recoverable is True
