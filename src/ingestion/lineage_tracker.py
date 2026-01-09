"""Lineage tracking for document ingestion jobs"""
import uuid
from pathlib import Path
from typing import List, Dict, Optional
import logging

from src.observability.lineage import (
    is_lineage_enabled,
    get_lineage_client,
    emit_job_event,
    set_lineage_context,
    clear_lineage_context
)
from src.observability.lineage.metrics import (
    calculate_data_quality_metrics,
    build_data_quality_facet,
    format_metrics_for_cache
)

logger = logging.getLogger(__name__)


class IngestionLineageTracker:
    """Tracks lineage for document ingestion jobs

    This class handles:
    1. Emitting OpenLineage events (START/COMPLETE/FAIL)
    2. Calculating data quality metrics from source files
    3. Caching metrics for Trust Plane queries
    4. Setting lineage context for correlation with OTel traces

    Example:
        >>> tracker = IngestionLineageTracker(
        ...     job_name="document_ingestion",
        ...     source_dir="/path/to/docs"
        ... )
        >>> tracker.start(file_paths)
        >>> # ... do ingestion work ...
        >>> tracker.complete(num_chunks=100)
    """

    def __init__(self, job_name: str = "document_ingestion", source_dir: Optional[str] = None):
        """Initialize ingestion lineage tracker

        Args:
            job_name: Name of the ingestion job
            source_dir: Source directory for input dataset namespace
        """
        self.job_name = job_name
        self.source_dir = source_dir or "filesystem"
        self.run_id = str(uuid.uuid4())
        self.file_paths: List[Path] = []
        self.metrics: Optional[Dict] = None
        self.enabled = is_lineage_enabled()

        if self.enabled:
            # Set lineage context for this ingestion run
            set_lineage_context(self.run_id, self.job_name)
            logger.info(f"Lineage tracking enabled for {job_name} (run: {self.run_id[:8]}...)")
        else:
            logger.debug("Lineage tracking disabled")

    def start(self, file_paths: List[Path]):
        """Emit START event with input datasets

        Args:
            file_paths: List of source file paths being ingested
        """
        if not self.enabled:
            return

        self.file_paths = file_paths

        # Calculate data quality metrics from source files
        self.metrics = calculate_data_quality_metrics(file_paths)

        logger.info(f"Data quality metrics:")
        logger.info(f"  Files: {self.metrics['file_count']}")
        logger.info(f"  Avg freshness: {self.metrics['avg_freshness_days']:.1f} days")
        logger.info(f"  Max freshness: {self.metrics['max_freshness_days']:.1f} days")

        # Build input dataset with source files
        inputs = [{
            "namespace": "filesystem",
            "name": str(Path(self.source_dir).name) if self.source_dir != "filesystem" else "documents",
            "facets": {}
        }]

        # Emit START event
        emit_job_event(
            job_name=self.job_name,
            run_id=self.run_id,
            event_type="START",
            inputs=inputs,
            metadata={
                "file_count": self.metrics["file_count"],
                "total_size_bytes": self.metrics["total_size_bytes"]
            }
        )

    def complete(self, collection_name: str = "internal_docs", num_chunks: int = 0):
        """Emit COMPLETE event with output dataset and data quality facets

        Args:
            collection_name: ChromaDB collection name
            num_chunks: Number of document chunks created
        """
        if not self.enabled or not self.metrics:
            return

        # Build data quality facet for output dataset
        quality_facet = build_data_quality_facet(self.metrics)

        # Build output dataset (ChromaDB collection)
        outputs = [{
            "namespace": "chromadb",
            "name": f"{collection_name}.chunks",
            "facets": {
                "dataQualityMetrics": quality_facet
            }
        }]

        # Emit COMPLETE event
        emit_job_event(
            job_name=self.job_name,
            run_id=self.run_id,
            event_type="COMPLETE",
            outputs=outputs,
            metadata={
                "num_chunks": num_chunks,
                "avg_freshness_days": self.metrics["avg_freshness_days"],
                "max_freshness_days": self.metrics["max_freshness_days"]
            }
        )

        # Cache metrics for Trust Plane (include producer_run_id for bidirectional traceability)
        client = get_lineage_client()
        if client:
            cache_metadata = format_metrics_for_cache(self.metrics)
            # Add producer lineage information
            cache_metadata["producer_run_id"] = self.run_id
            cache_metadata["producer_job"] = self.job_name
            client.cache_dataset_metadata(
                namespace="chromadb",
                name=f"{collection_name}.chunks",
                metadata=cache_metadata
            )

        logger.info(f"✓ Ingestion lineage complete (run: {self.run_id[:8]}...)")

    def fail(self, error: Exception):
        """Emit FAIL event with error details

        Args:
            error: Exception that caused the failure
        """
        if not self.enabled:
            return

        emit_job_event(
            job_name=self.job_name,
            run_id=self.run_id,
            event_type="FAIL",
            metadata={
                "error": str(error),
                "error_type": type(error).__name__
            }
        )

        logger.error(f"✗ Ingestion failed (run: {self.run_id[:8]}...): {error}")

    def cleanup(self):
        """Clear lineage context

        Call this in a finally block to ensure context is cleaned up
        """
        if self.enabled:
            clear_lineage_context()

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with automatic cleanup"""
        if exc_type is not None:
            # Exception occurred
            self.fail(exc_val)
        self.cleanup()
        return False  # Don't suppress exceptions


def track_ingestion(job_name: str = "document_ingestion", source_dir: Optional[str] = None):
    """Context manager for ingestion lineage tracking

    Usage:
        >>> with track_ingestion("my_ingestion_job") as tracker:
        ...     tracker.start(file_paths)
        ...     # ... do ingestion work ...
        ...     tracker.complete(num_chunks=100)

    Args:
        job_name: Name of the ingestion job
        source_dir: Source directory for input dataset

    Returns:
        IngestionLineageTracker instance
    """
    return IngestionLineageTracker(job_name=job_name, source_dir=source_dir)
