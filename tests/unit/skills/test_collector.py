"""Tests for ProjectCollector."""

import pytest

from opengame.skills.template_skill.collector import ProjectCollector


class TestProjectCollector:
    @pytest.fixture
    def collector(self) -> ProjectCollector:
        return ProjectCollector()

    @pytest.mark.asyncio
    async def test_collect_empty_directory(self, collector: ProjectCollector, tmp_path) -> None:
        snapshot = await collector.collect(tmp_path)
        assert snapshot.project_path == str(tmp_path)
        assert len(snapshot.files) == 0

    @pytest.mark.asyncio
    async def test_collect_with_files(self, collector: ProjectCollector, tmp_path) -> None:
        (tmp_path / "main.ts").write_text("console.log('hello');")
        (tmp_path / "package.json").write_text('{"name": "test"}')
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "Game.ts").write_text("class Game {}")

        snapshot = await collector.collect(tmp_path)
        assert len(snapshot.files) >= 3
        assert any(f.relative_path == "main.ts" for f in snapshot.files)
        assert any(f.relative_path == "package.json" for f in snapshot.files)

    @pytest.mark.asyncio
    async def test_ignores_node_modules(self, collector: ProjectCollector, tmp_path) -> None:
        (tmp_path / "main.ts").write_text("test")
        nm = tmp_path / "node_modules"
        nm.mkdir()
        (nm / "dep.ts").write_text("ignored")

        snapshot = await collector.collect(tmp_path)
        paths = [f.relative_path for f in snapshot.files]
        assert "main.ts" in paths
        assert not any("node_modules" in p for p in paths)

    @pytest.mark.asyncio
    async def test_ignores_dist_build(self, collector: ProjectCollector, tmp_path) -> None:
        (tmp_path / "main.ts").write_text("test")
        (tmp_path / "dist").mkdir()
        (tmp_path / "dist" / "bundle.js").write_text("built")

        snapshot = await collector.collect(tmp_path)
        paths = [f.relative_path for f in snapshot.files]
        assert not any("dist" in p for p in paths)

    @pytest.mark.asyncio
    async def test_creates_code_summary(self, collector: ProjectCollector, tmp_path) -> None:
        (tmp_path / "main.ts").write_text("class Game {}\nclass Player {}")
        (tmp_path / "package.json").write_text("{}")

        snapshot = await collector.collect(tmp_path)
        assert len(snapshot.code_summary) > 0
        assert "Game" in snapshot.code_summary or "Player" in snapshot.code_summary

    @pytest.mark.asyncio
    async def test_collects_game_config(self, collector: ProjectCollector, tmp_path) -> None:
        import json
        (tmp_path / "gameConfig.json").write_text(json.dumps({"gameTitle": "Test"}))

        snapshot = await collector.collect(tmp_path)
        assert snapshot.game_config is not None
        assert snapshot.game_config["gameTitle"] == "Test"
