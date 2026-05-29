"""Tests for the async file system service."""

from __future__ import annotations

from pathlib import Path

import pytest

from opengame.services.fs_service import (
    delete_file,
    edit_file,
    list_directory,
    read_file,
    write_file,
)
from opengame.utils.errors import ToolError


class TestReadFile:
    """Tests for read_file."""

    @pytest.mark.asyncio
    async def test_read_existing_file(self, temp_dir: Path) -> None:
        """Can read an existing file."""
        file_path = temp_dir / "test.txt"
        file_path.write_text("line1\nline2\nline3\n")

        content = await read_file(str(file_path))
        assert "line1" in content
        assert "line2" in content

    @pytest.mark.asyncio
    async def test_read_nonexistent_file_raises(self, temp_dir: Path) -> None:
        """Reading a nonexistent file raises ToolError."""
        with pytest.raises(ToolError, match="not found"):
            await read_file(str(temp_dir / "does-not-exist.txt"))

    @pytest.mark.asyncio
    async def test_read_directory_raises(self, temp_dir: Path) -> None:
        """Reading a directory raises ToolError."""
        with pytest.raises(ToolError, match="directory"):
            await read_file(str(temp_dir))

    @pytest.mark.asyncio
    async def test_read_with_offset_and_limit(self, temp_dir: Path) -> None:
        """Offset and limit work for partial reads."""
        file_path = temp_dir / "lines.txt"
        lines = [f"line{i}\n" for i in range(10)]
        file_path.write_text("".join(lines))

        content = await read_file(str(file_path), offset=2, limit=3)
        # Should include line numbers for partial reads
        assert len(content.split("\n")) >= 3


class TestWriteFile:
    """Tests for write_file."""

    @pytest.mark.asyncio
    async def test_write_new_file(self, temp_dir: Path) -> None:
        """Can write a new file."""
        file_path = temp_dir / "new.txt"
        result = await write_file(str(file_path), "hello world")
        assert "Wrote" in result
        assert file_path.read_text() == "hello world"

    @pytest.mark.asyncio
    async def test_write_creates_parent_directories(self, temp_dir: Path) -> None:
        """Parent directories are created automatically."""
        file_path = temp_dir / "deeply" / "nested" / "dir" / "file.txt"
        result = await write_file(str(file_path), "content")
        assert file_path.exists()

    @pytest.mark.asyncio
    async def test_write_overwrites_existing(self, temp_dir: Path) -> None:
        """Writing overwrites existing file."""
        file_path = temp_dir / "existing.txt"
        file_path.write_text("old")
        await write_file(str(file_path), "new")
        assert file_path.read_text() == "new"


class TestEditFile:
    """Tests for edit_file."""

    @pytest.mark.asyncio
    async def test_edit_file_success(self, temp_dir: Path) -> None:
        """Single occurrence replacement works."""
        file_path = temp_dir / "edit.txt"
        file_path.write_text("Hello world")

        result = await edit_file(str(file_path), "world", "there")
        assert "Edited" in result
        assert file_path.read_text() == "Hello there"

    @pytest.mark.asyncio
    async def test_edit_multiple_occurrences_raises(self, temp_dir: Path) -> None:
        """Multiple occurrences raises error."""
        file_path = temp_dir / "dup.txt"
        file_path.write_text("hello hello")

        with pytest.raises(ToolError, match="2 times"):
            await edit_file(str(file_path), "hello", "hi")

    @pytest.mark.asyncio
    async def test_edit_not_found_raises(self, temp_dir: Path) -> None:
        """No match raises error."""
        file_path = temp_dir / "edit.txt"
        file_path.write_text("hello")

        with pytest.raises(ToolError, match="not found"):
            await edit_file(str(file_path), "world", "hi")


class TestListDirectory:
    """Tests for list_directory."""

    @pytest.mark.asyncio
    async def test_list_directory(self, temp_dir: Path) -> None:
        """Lists directory contents."""
        (temp_dir / "file1.txt").write_text("a")
        (temp_dir / "file2.txt").write_text("b")
        (temp_dir / "subdir").mkdir()

        entries = await list_directory(str(temp_dir))
        assert len(entries) == 3
        names = {e["name"] for e in entries}
        assert names == {"file1.txt", "file2.txt", "subdir"}
