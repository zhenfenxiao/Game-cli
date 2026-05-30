"""Tests for StageRunner."""

import pytest

from opengame.skills.debug_skill.runner import StageRunner


class TestStageRunner:
    @pytest.fixture
    def runner(self) -> StageRunner:
        return StageRunner()

    def test_parse_ts_errors(self, runner: StageRunner) -> None:
        output = """
src/Game.ts(10,5): error TS2322: Type 'string' is not assignable to type 'number'.
src/Player.ts(25,3): error TS2339: Property 'jump' does not exist on type 'Player'.
"""
        errors = runner._parse_errors(output)
        assert len(errors) >= 2
        codes = {e.code for e in errors}
        assert "TS2322" in codes
        assert "TS2339" in codes

    def test_parse_module_not_found(self, runner: StageRunner) -> None:
        output = """
Cannot find module './scenes/MissingScene' from 'src/main.ts'
"""
        errors = runner._parse_errors(output)
        assert len(errors) >= 1
        assert any(e.code == "MODULE_NOT_FOUND" for e in errors)

    def test_parse_no_errors(self, runner: StageRunner) -> None:
        output = """
> build
> vite build

vite v5.0.0 building for production...
✓ 10 modules transformed.
dist/index.html  0.5 kB
"""
        errors = runner._parse_errors(output)
        assert len(errors) == 0

    @pytest.mark.asyncio
    async def test_run_unknown_stage(self, runner: StageRunner, tmp_path) -> None:
        result = await runner.run(tmp_path, "deploy")
        assert result.success is False
        assert "Unknown stage" in result.stderr
