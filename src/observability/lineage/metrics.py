"""Data quality metrics calculation for OpenLineage facets"""
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


def calculate_freshness_days(file_path: Path) -> float:
    """Calculate file freshness in days since last modification

    Args:
        file_path: Path to file

    Returns:
        Age in days (float)
    """
    try:
        mtime = os.path.getmtime(file_path)
        file_date = datetime.fromtimestamp(mtime)
        age = (datetime.now() - file_date).total_seconds() / 86400  # Convert to days
        return round(age, 2)
    except Exception as e:
        logger.error(f"Error calculating freshness for {file_path}: {e}")
        return 0.0


def calculate_data_quality_metrics(file_paths: List[Path]) -> Dict:
    """Calculate data quality metrics for a set of files

    This computes metrics used by the Trust Plane to determine
    whether data is safe to use based on policy thresholds.

    Args:
        file_paths: List of file paths that were ingested

    Returns:
        Dict with data quality metrics:
        {
            "avg_freshness_days": float,
            "max_freshness_days": float,
            "min_freshness_days": float,
            "row_count": int,
            "file_count": int,
            "total_size_bytes": int,
            "files": [
                {
                    "path": str,
                    "freshness_days": float,
                    "size_bytes": int
                }
            ]
        }
    """
    if not file_paths:
        return {
            "avg_freshness_days": 0.0,
            "max_freshness_days": 0.0,
            "min_freshness_days": 0.0,
            "row_count": 0,
            "file_count": 0,
            "total_size_bytes": 0,
            "files": []
        }

    freshness_values = []
    file_details = []
    total_size = 0

    for file_path in file_paths:
        if not file_path.exists():
            logger.warning(f"File not found: {file_path}")
            continue

        freshness = calculate_freshness_days(file_path)
        size = file_path.stat().st_size

        freshness_values.append(freshness)
        total_size += size

        file_details.append({
            "path": str(file_path),
            "freshness_days": freshness,
            "size_bytes": size
        })

    if not freshness_values:
        return {
            "avg_freshness_days": 0.0,
            "max_freshness_days": 0.0,
            "min_freshness_days": 0.0,
            "row_count": 0,
            "file_count": 0,
            "total_size_bytes": 0,
            "files": []
        }

    return {
        "avg_freshness_days": round(sum(freshness_values) / len(freshness_values), 2),
        "max_freshness_days": round(max(freshness_values), 2),
        "min_freshness_days": round(min(freshness_values), 2),
        "row_count": len(file_paths),  # In document ingestion, each file = 1 row
        "file_count": len(file_paths),
        "total_size_bytes": total_size,
        "files": file_details
    }


def build_data_quality_facet(metrics: Dict) -> Dict:
    """Build OpenLineage dataQualityMetrics facet

    This creates the facet structure that will be attached to
    output datasets in OpenLineage events.

    Args:
        metrics: Metrics dict from calculate_data_quality_metrics()

    Returns:
        OpenLineage facet dict in the correct format
    """
    return {
        "_producer": "genaiops-agent/1.0",
        "_schemaURL": "https://openlineage.io/spec/facets/1-0-0/DataQualityMetricsInputDatasetFacet.json",
        "rowCount": metrics["row_count"],
        "bytes": metrics["total_size_bytes"],
        "columnMetrics": {
            "freshness": {
                "_producer": "genaiops-agent/1.0",
                "_schemaURL": "https://openlineage.io/spec/facets/1-0-0/ColumnMetric.json",
                "count": metrics["file_count"],
                "sum": metrics["avg_freshness_days"] * metrics["file_count"],
                "min": metrics["min_freshness_days"],
                "max": metrics["max_freshness_days"],
                "quantiles": {
                    "0.5": metrics["avg_freshness_days"]  # median approximation
                }
            }
        }
    }


def format_metrics_for_cache(metrics: Dict) -> Dict:
    """Format metrics for Trust Plane metadata cache

    The cache stores a simplified version that's easy to query.

    Args:
        metrics: Metrics dict from calculate_data_quality_metrics()

    Returns:
        Simplified metrics dict for caching
    """
    return {
        "metrics": {
            "avg_freshness_days": metrics["avg_freshness_days"],
            "max_freshness_days": metrics["max_freshness_days"],
            "row_count": metrics["row_count"],
            "file_count": metrics["file_count"],
            "files": metrics.get("files", [])  # Include file details for VV mode
        },
        "computed_at": datetime.now().isoformat()
    }


def extract_metrics_from_facet(facet: Dict) -> Optional[Dict]:
    """Extract metrics from OpenLineage dataQualityMetrics facet

    This is used when retrieving facets from Marquez API.

    Args:
        facet: OpenLineage dataQualityMetrics facet

    Returns:
        Simplified metrics dict or None if invalid
    """
    try:
        freshness_metric = facet.get("columnMetrics", {}).get("freshness", {})

        return {
            "avg_freshness_days": round(freshness_metric.get("quantiles", {}).get("0.5", 0.0), 2),
            "max_freshness_days": round(freshness_metric.get("max", 0.0), 2),
            "min_freshness_days": round(freshness_metric.get("min", 0.0), 2),
            "row_count": facet.get("rowCount", 0),
            "file_count": freshness_metric.get("count", 0)
        }
    except Exception as e:
        logger.error(f"Error extracting metrics from facet: {e}")
        return None
