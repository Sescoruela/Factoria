"""Shared catalog locks; multi-resource callers always acquire skill, agent, workflow."""

from threading import RLock

SKILL_LOCK = RLock()
AGENT_LOCK = RLock()
WORKFLOW_LOCK = RLock()
