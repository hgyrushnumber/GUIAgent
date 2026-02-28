"""
Intra-Agent Multi-Role Reasoning Module

This module implements role-based reasoning within a single agent instance.
Roles communicate through direct method calls instead of message passing.
"""

from pcguiagent.roles.base_role import BaseRole
from pcguiagent.roles.planner_role import PlannerRole
from pcguiagent.roles.memory_role import MemoryRole
from pcguiagent.roles.reflector_role import ReflectorRole

__all__ = [
    "BaseRole",
    "PlannerRole",
    "MemoryRole",
    "ReflectorRole",
]

