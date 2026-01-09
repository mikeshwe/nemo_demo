"""Test script for data quality metrics calculation"""
import tempfile
import time
from pathlib import Path
from datetime import datetime, timedelta

from src.observability.lineage.metrics import (
    calculate_freshness_days,
    calculate_data_quality_metrics,
    build_data_quality_facet,
    format_metrics_for_cache,
    extract_metrics_from_facet
)


def create_test_files():
    """Create temporary test files with different ages

    Returns:
        List of file paths
    """
    temp_dir = Path(tempfile.mkdtemp())
    print(f"Creating test files in: {temp_dir}\n")

    files = []

    # File 1: Fresh (just created)
    file1 = temp_dir / "fresh_doc.md"
    file1.write_text("# Fresh Documentation\nThis was just created.")
    files.append(file1)
    print(f"✓ Created {file1.name} (fresh)")

    # File 2: 2 days old
    file2 = temp_dir / "recent_doc.md"
    file2.write_text("# Recent Documentation\nThis is a few days old.")
    # Set mtime to 2 days ago
    two_days_ago = (datetime.now() - timedelta(days=2)).timestamp()
    file2.touch()
    import os
    os.utime(file2, (two_days_ago, two_days_ago))
    files.append(file2)
    print(f"✓ Created {file2.name} (2 days old)")

    # File 3: 45 days old (stale)
    file3 = temp_dir / "stale_doc.md"
    file3.write_text("# Stale Documentation\nThis is very old.")
    forty_five_days_ago = (datetime.now() - timedelta(days=45)).timestamp()
    file3.touch()
    os.utime(file3, (forty_five_days_ago, forty_five_days_ago))
    files.append(file3)
    print(f"✓ Created {file3.name} (45 days old)")

    return files


def test_freshness_calculation():
    """Test freshness calculation for individual files"""
    print("\n" + "="*60)
    print("Test 1: Freshness Calculation")
    print("="*60)

    files = create_test_files()

    for file_path in files:
        freshness = calculate_freshness_days(file_path)
        print(f"\n{file_path.name}:")
        print(f"  Freshness: {freshness:.2f} days")

    return files


def test_metrics_calculation(files):
    """Test data quality metrics calculation"""
    print("\n" + "="*60)
    print("Test 2: Data Quality Metrics Calculation")
    print("="*60)

    metrics = calculate_data_quality_metrics(files)

    print("\nCalculated Metrics:")
    print(f"  File count: {metrics['file_count']}")
    print(f"  Row count: {metrics['row_count']}")
    print(f"  Total size: {metrics['total_size_bytes']} bytes")
    print(f"  Avg freshness: {metrics['avg_freshness_days']:.2f} days")
    print(f"  Min freshness: {metrics['min_freshness_days']:.2f} days")
    print(f"  Max freshness: {metrics['max_freshness_days']:.2f} days")

    print("\nPer-file details:")
    for file_detail in metrics['files']:
        print(f"  {Path(file_detail['path']).name}:")
        print(f"    Freshness: {file_detail['freshness_days']:.2f} days")
        print(f"    Size: {file_detail['size_bytes']} bytes")

    # Validate calculations
    expected_avg = (0 + 2 + 45) / 3  # Approximately
    print(f"\n✓ Average freshness validation: {abs(metrics['avg_freshness_days'] - expected_avg) < 1}")
    print(f"✓ Max freshness is stale file: {metrics['max_freshness_days'] > 40}")

    return metrics


def test_facet_building(metrics):
    """Test OpenLineage facet building"""
    print("\n" + "="*60)
    print("Test 3: OpenLineage Facet Building")
    print("="*60)

    facet = build_data_quality_facet(metrics)

    print("\nGenerated Facet Structure:")
    print(f"  Producer: {facet['_producer']}")
    print(f"  Schema URL: {facet['_schemaURL']}")
    print(f"  Row count: {facet['rowCount']}")
    print(f"  Bytes: {facet['bytes']}")

    print("\n  Column Metrics (freshness):")
    freshness_metric = facet['columnMetrics']['freshness']
    print(f"    Count: {freshness_metric['count']}")
    print(f"    Min: {freshness_metric['min']:.2f} days")
    print(f"    Max: {freshness_metric['max']:.2f} days")
    print(f"    Median: {freshness_metric['quantiles']['0.5']:.2f} days")

    print(f"\n✓ Facet has required fields: {all(k in facet for k in ['_producer', 'rowCount', 'columnMetrics'])}")

    return facet


def test_cache_formatting(metrics):
    """Test cache metadata formatting"""
    print("\n" + "="*60)
    print("Test 4: Cache Metadata Formatting")
    print("="*60)

    cache_metadata = format_metrics_for_cache(metrics)

    print("\nCache Metadata:")
    print(f"  Avg freshness: {cache_metadata['metrics']['avg_freshness_days']:.2f} days")
    print(f"  Max freshness: {cache_metadata['metrics']['max_freshness_days']:.2f} days")
    print(f"  Row count: {cache_metadata['metrics']['row_count']}")
    print(f"  File count: {cache_metadata['metrics']['file_count']}")
    print(f"  Computed at: {cache_metadata['computed_at']}")

    print(f"\n✓ Cache has required fields: {all(k in cache_metadata for k in ['metrics', 'computed_at'])}")


def test_facet_extraction(facet):
    """Test extracting metrics from facet"""
    print("\n" + "="*60)
    print("Test 5: Metrics Extraction from Facet")
    print("="*60)

    extracted_metrics = extract_metrics_from_facet(facet)

    if extracted_metrics:
        print("\nExtracted Metrics:")
        print(f"  Avg freshness: {extracted_metrics['avg_freshness_days']:.2f} days")
        print(f"  Max freshness: {extracted_metrics['max_freshness_days']:.2f} days")
        print(f"  Min freshness: {extracted_metrics['min_freshness_days']:.2f} days")
        print(f"  Row count: {extracted_metrics['row_count']}")
        print(f"  File count: {extracted_metrics['file_count']}")

        print(f"\n✓ Extraction successful")
    else:
        print("✗ Extraction failed")


def test_stale_data_detection(metrics):
    """Test Trust Plane policy evaluation"""
    print("\n" + "="*60)
    print("Test 6: Trust Plane Policy Evaluation (Simulation)")
    print("="*60)

    # Simulate Trust Plane policy: max_freshness_days <= 30
    policy_threshold = 30.0

    print(f"\nPolicy: max_freshness_days <= {policy_threshold} days")
    print(f"Current max_freshness_days: {metrics['max_freshness_days']:.2f} days")

    if metrics['max_freshness_days'] > policy_threshold:
        print(f"\n✗ DENY: Data exceeds freshness threshold")
        print(f"  Stale by: {metrics['max_freshness_days'] - policy_threshold:.2f} days")
        print(f"  Recommendation: Re-ingest source documents")
    else:
        print(f"\n✓ ALLOW: Data meets freshness requirements")

    # Show which files are stale
    print(f"\nStale files (> {policy_threshold} days):")
    for file_detail in metrics['files']:
        if file_detail['freshness_days'] > policy_threshold:
            print(f"  ✗ {Path(file_detail['path']).name}: {file_detail['freshness_days']:.2f} days old")


def main():
    print("\n" + "="*60)
    print("Data Quality Metrics Test Suite")
    print("="*60)

    # Run all tests
    files = test_freshness_calculation()
    metrics = test_metrics_calculation(files)
    facet = test_facet_building(metrics)
    test_cache_formatting(metrics)
    test_facet_extraction(facet)
    test_stale_data_detection(metrics)

    # Cleanup
    for file_path in files:
        file_path.unlink()
    files[0].parent.rmdir()

    print("\n" + "="*60)
    print("All Tests Complete")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
