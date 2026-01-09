"""Trust Plane enforcer for authorization decisions"""
from typing import Optional
from dataclasses import dataclass
from pathlib import Path
import logging

from src.observability.lineage import get_lineage_client, is_lineage_enabled
from .policy import PolicyEngine

logger = logging.getLogger(__name__)

# Global state
_trust_plane_enabled: bool = False
_policy_engine: Optional[PolicyEngine] = None


@dataclass
class AuthorizationDecision:
    """Authorization decision from Trust Plane

    Attributes:
        allowed: Whether access is allowed
        action: ALLOW, DENY, or WARN
        reason: Human-readable explanation
        dataset: Dataset identifier
        violations: List of policy violations
        metadata_found: Whether metadata was available
    """
    allowed: bool
    action: str
    reason: str
    dataset: str
    violations: list
    metadata_found: bool = True

    def to_dict(self):
        """Convert to dict for logging"""
        return {
            "allowed": self.allowed,
            "action": self.action,
            "reason": self.reason,
            "dataset": self.dataset,
            "violations": self.violations,
            "metadata_found": self.metadata_found
        }


def initialize_trust_plane(
    enabled: bool = True,
    policy_file: Optional[str] = None
) -> bool:
    """Initialize Trust Plane

    Args:
        enabled: Whether to enable Trust Plane
        policy_file: Path to policies YAML file (default: src/trust_plane/policies.yaml)

    Returns:
        True if initialized successfully
    """
    global _trust_plane_enabled, _policy_engine

    if not enabled:
        _trust_plane_enabled = False
        logger.info("Trust Plane disabled")
        return False

    # Check if lineage is enabled (required for Trust Plane)
    if not is_lineage_enabled():
        logger.warning("Trust Plane requires OpenLineage to be enabled")
        _trust_plane_enabled = False
        return False

    # Default policy file
    if not policy_file:
        policy_file = str(Path(__file__).parent / "policies.yaml")

    try:
        _policy_engine = PolicyEngine(policy_file)
        _trust_plane_enabled = True
        logger.info(f"✓ Trust Plane enabled with policies from {policy_file}")
        return True
    except Exception as e:
        logger.error(f"Failed to initialize Trust Plane: {e}")
        _trust_plane_enabled = False
        return False


def shutdown_trust_plane():
    """Shutdown Trust Plane"""
    global _trust_plane_enabled, _policy_engine

    if _trust_plane_enabled:
        logger.info("Trust Plane shutdown")
        _trust_plane_enabled = False
        _policy_engine = None


def is_trust_plane_enabled() -> bool:
    """Check if Trust Plane is enabled

    Returns:
        True if Trust Plane is enabled
    """
    return _trust_plane_enabled and _policy_engine is not None


def authorize_dataset_access(
    namespace: str,
    dataset_name: str,
    tool_name: Optional[str] = None
) -> AuthorizationDecision:
    """Authorize access to a dataset

    This is the main entry point for Trust Plane authorization.
    Call this BEFORE using data to check if it meets quality requirements.

    Args:
        namespace: Dataset namespace (e.g., "chromadb")
        dataset_name: Dataset name (e.g., "internal_docs.chunks")
        tool_name: Optional tool name for logging

    Returns:
        AuthorizationDecision with allowed/denied status

    Example:
        >>> decision = authorize_dataset_access("chromadb", "internal_docs.chunks")
        >>> if not decision.allowed:
        >>>     return {"error": decision.reason}
    """
    dataset_id = f"{namespace}/{dataset_name}"

    # If Trust Plane is disabled, allow all access
    if not is_trust_plane_enabled():
        logger.debug(f"Trust Plane disabled, allowing access to {dataset_id}")
        return AuthorizationDecision(
            allowed=True,
            action="ALLOW",
            reason="Trust Plane disabled",
            dataset=dataset_id,
            violations=[],
            metadata_found=False
        )

    # Get lineage client
    lineage_client = get_lineage_client()
    if not lineage_client:
        logger.warning("Lineage client not available, allowing access")
        return AuthorizationDecision(
            allowed=True,
            action="ALLOW",
            reason="Lineage client unavailable",
            dataset=dataset_id,
            violations=[],
            metadata_found=False
        )

    # Query dataset metadata (with Marquez API fallback)
    logger.debug(f"Trust Plane: Checking authorization for {dataset_id}")
    metadata = lineage_client.get_dataset_metadata(namespace, dataset_name)

    if not metadata:
        logger.warning(
            f"Trust Plane: No metadata found for {dataset_id}, "
            f"allowing access (fail-open)"
        )
        return AuthorizationDecision(
            allowed=True,
            action="ALLOW",
            reason="No metadata available (fail-open policy)",
            dataset=dataset_id,
            violations=[],
            metadata_found=False
        )

    # Extract metrics
    metrics = metadata.get("metrics", {})
    if not metrics:
        logger.warning(f"Trust Plane: No metrics in metadata for {dataset_id}")
        return AuthorizationDecision(
            allowed=True,
            action="ALLOW",
            reason="No metrics available",
            dataset=dataset_id,
            violations=[],
            metadata_found=True
        )

    # Evaluate policies
    logger.debug(f"Trust Plane: Evaluating policies for {dataset_id}")
    logger.debug(f"  Metrics: {metrics}")

    evaluation = _policy_engine.evaluate_dataset(namespace, dataset_name, metrics)

    # Log decision
    if evaluation["allowed"]:
        if evaluation["action"] == "WARN":
            logger.warning(
                f"Trust Plane: WARN for {dataset_id} "
                f"(tool: {tool_name}): {evaluation['reason']}"
            )
        else:
            logger.info(
                f"Trust Plane: ALLOW {dataset_id} "
                f"(tool: {tool_name})"
            )
    else:
        logger.error(
            f"Trust Plane: DENY {dataset_id} "
            f"(tool: {tool_name}): {evaluation['reason']}"
        )
        logger.debug(f"  Violations: {evaluation['violations']}")

    return AuthorizationDecision(
        allowed=evaluation["allowed"],
        action=evaluation["action"],
        reason=evaluation["reason"],
        dataset=dataset_id,
        violations=evaluation["violations"],
        metadata_found=True
    )
