"""Tests for file tools."""

import pytest

from opengame.core.tool_registry import ToolRegistry
from opengame.tools.file_tools import register_file_tools


@pytest.fixture
def registry() -> ToolRegistry:
    reg = ToolRegistry()
    register_file_tools(reg)
    return reg


class TestFileTools:
    @pytest.mark.asyncio
    async def test_read_file_success(self, registry: ToolRegistry, tmp_path) -> None:
        f = tmp_path / "test.txt"
        f.write_text("hello world")
        result = await registry.execute("read_file", {"file_path": str(f)})
        assert result.success
        assert "hello world" in result.output

    @pytest.mark.asyncio
    async def test_read_file_not_found(self, registry: ToolRegistry) -> None:
        result = await registry.execute("read_file", {"file_path": "/nonexistent.txt"})
        # Tool returns error message as output (not as error) for graceful handling
        assert "Error reading file" in result.output

    @pytest.mark.asyncio
    async def test_write_file(self, registry: ToolRegistry, tmp_path) -> None:
        f = tmp_path / "new.txt"
        result = await registry.execute("write_file", {"file_path": str(f), "content": "test content"})
        assert result.success
        assert f.read_text() == "test content"

    @pytest.mark.asyncio
    async def test_edit_file(self, registry: ToolRegistry, tmp_path) -> None:
        f = tmp_path / "edit.txt"
        f.write_text("hello world")
        result = await registry.execute("edit", {"file_path": str(f), "old_string": "world", "new_string": "there"})
        assert result.success
        assert f.read_text() == "hello there"

    @pytest.mark.asyncio
    async def test_glob(self, registry: ToolRegistry, tmp_path) -> None:
        (tmp_path / "a.ts").write_text("")
        (tmp_path / "b.ts").write_text("")
        (tmp_path / "c.py").write_text("")
        result = await registry.execute("glob", {"pattern": "*.ts", "directory": str(tmp_path)})
        assert result.success
        assert "a.ts" in result.output
        assert "b.ts" in result.output
        assert "c.py" not in result.output

    @pytest.mark.asyncio
    async def test_ls(self, registry: ToolRegistry, tmp_path) -> None:
        (tmp_path / "file.txt").write_text("x")
        (tmp_path / "subdir").mkdir()
        result = await registry.execute("ls", {"path": str(tmp_path)})
        assert result.success
        assert "file.txt" in result.output
        assert "subdir" in result.output
