"""
Triad Agents Module - Backward-Compatible Exports.

This module re-exports all classes from the extracted triad module:
- TriadAgent: Base class for all Triad agents
- StewardAgent: Coordinator and governance agent
- AlphaAgent: Primary decision maker and analyst
- BetaAgent: Secondary analyst and validator
- CharlieAgent: Tertiary perspective and challenger

Author: Heretek Swarm Collective
Date: 2026-04-17
Version: 1.0.0
"""

from heretek_swarm.actors.triad.agent import (
    AlphaAgent,
    BetaAgent,
    CharlieAgent,
    StewardAgent,
    TriadAgent,
)

__all__ = [
    "AlphaAgent",
    "BetaAgent",
    "CharlieAgent",
    "StewardAgent",
    "TriadAgent",
]
