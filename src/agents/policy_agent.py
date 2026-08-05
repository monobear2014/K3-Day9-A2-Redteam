"""Compatibility entry point for the P4 deliverable.

The project historically imports ``src.agents.policy``; keeping this thin alias
avoids breaking that pipeline while providing the requested policy_agent module.
"""

from .policy import run

__all__ = ["run"]

