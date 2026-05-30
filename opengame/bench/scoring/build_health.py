"""BuildHealthEvaluator — checks compilation, tests, and static errors."""

from __future__ import annotations

import asyncio
from pathlib import Path

from opengame.bench.types import BuildHealthScore


class BuildHealthEvaluator:
    """Evaluate build health: compilation, tests, and error counts.

    Checks:
    1. package.json exists
    2. npm install succeeds
    3. npm run build succeeds (TypeScript compilation)
    4. npm test passes (if test script exists)
    """

    async def evaluate(self, game_dir: Path) -> BuildHealthScore:
        """Evaluate the build health of a game project.

        Args:
            game_dir: Path to the game project directory.

        Returns:
            BuildHealthScore with detailed results.
        """
        compiles = False
        test_passes = False
        error_count = 0
        warnings: list[str] = []

        # Check 1: Does package.json exist?
        if not (game_dir / "package.json").exists():
            warnings.append("No package.json found")
            return BuildHealthScore(
                score=0.0,
                compiles=False,
                test_passes=False,
                error_count=1,
                warnings=warnings,
            )

        # Check 2: npm install
        try:
            proc = await asyncio.create_subprocess_exec(
                "npm", "install",
                cwd=game_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=120,
            )
            if proc.returncode != 0:
                stderr_text = stderr.decode("utf-8", errors="replace")[:200]
                warnings.append(f"npm install failed: {stderr_text}")
        except FileNotFoundError:
            warnings.append("npm not found — is Node.js installed?")
        except asyncio.TimeoutError:
            warnings.append("npm install timed out after 120s")
        except Exception as e:
            warnings.append(f"npm install error: {e}")

        # Check 3: TypeScript compilation
        try:
            proc = await asyncio.create_subprocess_exec(
                "npm", "run", "build",
                cwd=game_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=120,
            )
            compiles = proc.returncode == 0
            if not compiles:
                combined = stdout.decode("utf-8", errors="replace") + stderr.decode("utf-8", errors="replace")
                error_count = combined.count("error TS")
                warnings.append(
                    f"Build failed with {error_count} TypeScript errors"
                )
        except FileNotFoundError:
            warnings.append("npm not found")
        except asyncio.TimeoutError:
            warnings.append("Build timed out after 120s")
            error_count = 1
        except Exception as e:
            warnings.append(f"Build error: {e}")
            error_count = 1

        # Check 4: Tests
        pkg_json = game_dir / "package.json"
        if pkg_json.exists():
            try:
                import json
                pkg = json.loads(pkg_json.read_text("utf-8"))
                if "test" in pkg.get("scripts", {}):
                    proc = await asyncio.create_subprocess_exec(
                        "npm", "run", "test",
                        cwd=game_dir,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    stdout, stderr = await asyncio.wait_for(
                        proc.communicate(), timeout=120,
                    )
                    test_passes = proc.returncode == 0
                    if not test_passes:
                        warnings.append("Tests failed")
            except asyncio.TimeoutError:
                warnings.append("Tests timed out after 120s")
            except Exception as e:
                warnings.append(f"Test error: {e}")

        # Calculate score
        score = 0.0
        if compiles:
            score += 0.5
        if test_passes:
            score += 0.3
        if error_count == 0:
            score += 0.2
        else:
            score += max(0, 0.2 - (error_count * 0.02))

        return BuildHealthScore(
            score=round(min(score, 1.0), 2),
            compiles=compiles,
            test_passes=test_passes,
            error_count=error_count,
            warnings=warnings,
        )
