"""Lineage context management for tracking run IDs across agent execution"""
import contextvars
from typing import Optional

# Thread-local context variables for lineage tracking
_current_run_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    'lineage_run_id',
    default=None
)
_current_job_name: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    'lineage_job_name',
    default=None
)


def set_lineage_context(run_id: str, job_name: str):
    """Set lineage context for current execution

    This should be called at the start of an agent run or data ingestion job
    to establish lineage context that will be propagated to all child operations.

    Args:
        run_id: Unique run identifier (UUID string)
        job_name: Job name (e.g., "agent_query", "document_ingestion")

    Example:
        >>> import uuid
        >>> run_id = str(uuid.uuid4())
        >>> set_lineage_context(run_id, "agent_query")
    """
    _current_run_id.set(run_id)
    _current_job_name.set(job_name)


def get_current_run_id() -> Optional[str]:
    """Get current lineage run ID from context

    Returns:
        Current run ID string, or None if not set

    Example:
        >>> run_id = get_current_run_id()
        >>> if run_id:
        >>>     # Include in OTel span attributes for correlation
        >>>     span.set_attribute("lineage.run_id", run_id)
    """
    return _current_run_id.get()


def get_current_job_name() -> Optional[str]:
    """Get current lineage job name from context

    Returns:
        Current job name string, or None if not set

    Example:
        >>> job_name = get_current_job_name()
        >>> if job_name:
        >>>     span.set_attribute("lineage.job_name", job_name)
    """
    return _current_job_name.get()


def clear_lineage_context():
    """Clear lineage context

    This should be called at the end of an agent run or job execution
    to clean up thread-local context.

    Example:
        >>> try:
        >>>     set_lineage_context(run_id, job_name)
        >>>     # ... do work ...
        >>> finally:
        >>>     clear_lineage_context()
    """
    _current_run_id.set(None)
    _current_job_name.set(None)
