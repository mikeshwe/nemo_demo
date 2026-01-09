"""Agent Trust Plane - Proactive data quality authorization

The Trust Plane enforces data quality policies BEFORE the agent uses data,
preventing errors from happening in the first place.

Components:
- Policy Engine: Loads and evaluates YAML policies
- Enforcer: Makes ALLOW/DENY decisions based on lineage metadata
- Integration: Intercepts tool calls to check authorization

Usage:
    from src.trust_plane import initialize_trust_plane, authorize_dataset_access

    initialize_trust_plane(enabled=True)

    # Before using data
    decision = authorize_dataset_access("chromadb", "internal_docs.chunks")
    if decision.allowed:
        # Use data
    else:
        # Block access, return error
"""
from .enforcer import (
    initialize_trust_plane,
    shutdown_trust_plane,
    is_trust_plane_enabled,
    authorize_dataset_access,
    AuthorizationDecision
)

__all__ = [
    'initialize_trust_plane',
    'shutdown_trust_plane',
    'is_trust_plane_enabled',
    'authorize_dataset_access',
    'AuthorizationDecision'
]
