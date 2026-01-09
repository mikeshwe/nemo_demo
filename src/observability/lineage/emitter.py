"""OpenLineage event emitter helpers"""
from datetime import datetime
from typing import List, Dict, Optional
import logging

from .client import get_lineage_client, is_lineage_enabled

logger = logging.getLogger(__name__)


def emit_job_event(
    job_name: str,
    run_id: str,
    event_type: str,  # START, RUNNING, COMPLETE, FAIL, ABORT
    inputs: Optional[List[Dict]] = None,
    outputs: Optional[List[Dict]] = None,
    metadata: Optional[Dict] = None
):
    """Emit OpenLineage job event

    Args:
        job_name: Job name (e.g., "document_ingestion", "agent_query")
        run_id: Unique run ID (UUID string)
        event_type: Event type - START, RUNNING, COMPLETE, FAIL, ABORT
        inputs: List of input dataset dicts with namespace, name, facets
        outputs: List of output dataset dicts with namespace, name, facets
        metadata: Additional job metadata
    """
    if not is_lineage_enabled():
        logger.debug(f"Lineage not enabled, skipping event: {job_name} ({event_type})")
        return

    client = get_lineage_client()
    if not client:
        return

    try:
        from openlineage.client.run import RunEvent, RunState, Run, Job, Dataset

        # Convert event type string to RunState enum
        run_state_map = {
            "START": RunState.START,
            "RUNNING": RunState.RUNNING,
            "COMPLETE": RunState.COMPLETE,
            "FAIL": RunState.FAIL,
            "ABORT": RunState.ABORT
        }

        run_state = run_state_map.get(event_type.upper())
        if not run_state:
            logger.error(f"Invalid event type: {event_type}")
            return

        # Build input datasets
        input_datasets = []
        if inputs:
            for inp in inputs:
                dataset = Dataset(
                    namespace=inp.get("namespace", client.namespace),
                    name=inp["name"],
                    facets=inp.get("facets", {})
                )
                input_datasets.append(dataset)

        # Build output datasets
        output_datasets = []
        if outputs:
            for out in outputs:
                dataset = Dataset(
                    namespace=out.get("namespace", client.namespace),
                    name=out["name"],
                    facets=out.get("facets", {})
                )
                output_datasets.append(dataset)

        # Create event
        event = RunEvent(
            eventType=run_state,
            eventTime=datetime.now().isoformat(),
            run=Run(runId=run_id, facets={}),
            job=Job(
                namespace=client.namespace,
                name=job_name,
                facets={}
            ),
            inputs=input_datasets,
            outputs=output_datasets,
            producer="genaiops-agent/1.0"
        )

        # Emit event
        client.emit_event(event)

        logger.info(f"✓ Emitted {event_type} event for {job_name} (run: {run_id[:8]}...)")

    except Exception as e:
        logger.error(f"Failed to emit lineage event: {e}", exc_info=True)


def emit_dataset(
    namespace: str,
    name: str,
    event_type: str,
    run_id: Optional[str] = None,
    facets: Optional[Dict] = None
):
    """Emit dataset-level event (READ, WRITE)

    This is a convenience function for logging dataset access
    without a full job context.

    Args:
        namespace: Dataset namespace
        name: Dataset name
        event_type: READ or WRITE
        run_id: Associated run ID (optional)
        facets: Dataset facets (optional)
    """
    if not is_lineage_enabled():
        return

    logger.debug(f"Dataset {event_type}: {namespace}/{name}")

    # Note: In OpenLineage, dataset events are typically part of job events
    # This function logs for observability but doesn't emit a standalone event
    # Full events should use emit_job_event with inputs/outputs
