"""Debug Skill — diagnose and repair build/test errors in generated games.

Implements Algorithm 1: REPEAT...UNTIL loop with validation, build,
test, diagnosis, repair, and protocol evolution.
"""

from opengame.skills.debug_skill.debug_loop import DebugSkill
from opengame.skills.debug_skill.protocol_manager import ProtocolManager
from opengame.skills.debug_skill.types import DebugProtocol

__all__ = ["DebugSkill", "ProtocolManager", "DebugProtocol"]
