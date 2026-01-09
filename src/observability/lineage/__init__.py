"""OpenLineage data lineage integration"""
from .client import (
    initialize_lineage,
    shutdown_lineage,
    get_lineage_client,
    is_lineage_enabled,
)
from .emitter import (
    emit_job_event,
    emit_dataset
)
from .context import (
    set_lineage_context,
    get_current_run_id,
    get_current_job_name,
    clear_lineage_context
)

__all__ = [
    'initialize_lineage',
    'shutdown_lineage',
    'get_lineage_client',
    'is_lineage_enabled',
    'emit_job_event',
    'emit_dataset',
    'set_lineage_context',
    'get_current_run_id',
    'get_current_job_name',
    'clear_lineage_context'
]
