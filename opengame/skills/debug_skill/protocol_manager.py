"""ProtocolManager — load/save/initialize the debug protocol.

Manages the JSON persistence of DebugProtocol on disk.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import aiofiles

from opengame.skills.debug_skill.types import DebugProtocol


class ProtocolManager:
    """Manage debug protocol persistence.

    Stores the protocol as protocol.json in the output directory.
    """

    def __init__(self, output_dir: str | Path) -> None:
        self.output_dir = Path(output_dir)
        self.protocol_path = self.output_dir / "protocol.json"
        self.seed_protocol_path = self.output_dir / "seed-protocol" / "protocol.json"

    async def initialize(self) -> DebugProtocol:
        """Create a new empty debug protocol.

        Returns:
            Fresh DebugProtocol with version 0.
        """
        now = datetime.now(timezone.utc).isoformat()
        return DebugProtocol(
            version=0,
            created_at=now,
            updated_at=now,
        )

    async def load(self) -> DebugProtocol | None:
        """Load the protocol from disk.

        Returns:
            DebugProtocol if the file exists and is valid, None otherwise.
        """
        if not self.protocol_path.exists():
            return None

        try:
            async with aiofiles.open(self.protocol_path, "r", encoding="utf-8") as f:
                data = await f.read()
            return DebugProtocol.model_validate(json.loads(data))
        except (json.JSONDecodeError, OSError, ValueError):
            return None

    async def load_or_init(self) -> DebugProtocol:
        """Load protocol or create a new one.

        If a seed protocol exists, it will be loaded as the starting point.

        Returns:
            Existing, seeded, or new DebugProtocol.
        """
        protocol = await self.load()
        if protocol is not None:
            return protocol

        # Try seed protocol
        if self.seed_protocol_path.exists():
            try:
                async with aiofiles.open(self.seed_protocol_path, "r", encoding="utf-8") as f:
                    data = await f.read()
                protocol = DebugProtocol.model_validate(json.loads(data))
                protocol.seed_protocol_path = str(self.seed_protocol_path)
                return protocol
            except (json.JSONDecodeError, OSError, ValueError):
                pass

        return await self.initialize()

    async def save(self, protocol: DebugProtocol) -> None:
        """Save the protocol to disk.

        Args:
            protocol: The debug protocol to persist.
        """
        self.output_dir.mkdir(parents=True, exist_ok=True)

        data = protocol.model_dump()
        async with aiofiles.open(self.protocol_path, "w", encoding="utf-8") as f:
            await f.write(json.dumps(data, ensure_ascii=False, indent=2))

    async def bump_version(self, protocol: DebugProtocol) -> None:
        """Increment protocol version and save.

        Args:
            protocol: The protocol to bump and save.
        """
        protocol.version += 1
        protocol.updated_at = datetime.now(timezone.utc).isoformat()
        await self.save(protocol)
