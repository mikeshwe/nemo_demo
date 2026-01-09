"""Test script for Marquez API integration

This test demonstrates:
1. Emitting OpenLineage events to Marquez (if running)
2. Querying dataset metadata via Marquez API
3. Fallback behavior when Marquez is unavailable
"""
import uuid
from pathlib import Path
from datetime import datetime, timedelta
import tempfile
import os

from src.observability.lineage import (
    initialize_lineage,
    shutdown_lineage,
    get_lineage_client
)
from src.ingestion.lineage_tracker import track_ingestion


def create_test_dataset():
    """Create test files with stale data"""
    temp_dir = Path(tempfile.mkdtemp())
    print(f"Creating test dataset in: {temp_dir}")

    # Create a stale file (45 days old)
    stale_file = temp_dir / "stale_doc.md"
    stale_file.write_text("# Stale Documentation\nPython 3.8 and CUDA 11.0 required.")

    # Set mtime to 45 days ago
    forty_five_days_ago = (datetime.now() - timedelta(days=45)).timestamp()
    os.utime(stale_file, (forty_five_days_ago, forty_five_days_ago))

    print(f"  ✓ Created {stale_file.name} (45 days old)")
    return [stale_file]


def test_marquez_api_flow():
    """Test complete flow: emit events → query Marquez API → get metadata"""
    print("\n" + "="*70)
    print("Marquez API Integration Test")
    print("="*70)

    # Initialize OpenLineage
    print("\n1. Initializing OpenLineage...")
    success = initialize_lineage(
        enabled=True,
        url="http://localhost:5000",
        namespace="test-marquez-api"
    )

    if not success:
        print("   ✗ Initialization failed")
        return

    client = get_lineage_client()
    if not client:
        print("   ✗ Client not available")
        return

    print(f"   ✓ Client initialized")
    print(f"   Backend available: {client.backend_available}")

    # Create test dataset
    print("\n2. Creating test dataset...")
    file_paths = create_test_dataset()

    # Simulate ingestion with lineage tracking
    print("\n3. Running ingestion with lineage tracking...")
    dataset_name = "stale_docs.chunks"

    with track_ingestion(job_name="test_ingestion") as tracker:
        # START event with metrics calculation
        tracker.start(file_paths)
        print(f"   ✓ Emitted START event")
        print(f"   Metrics calculated:")
        print(f"     - Avg freshness: {tracker.metrics['avg_freshness_days']:.1f} days")
        print(f"     - Max freshness: {tracker.metrics['max_freshness_days']:.1f} days")

        # Simulate ingestion work (normally would chunk and embed here)
        num_chunks = len(file_paths) * 5  # Simulate 5 chunks per file

        # COMPLETE event with data quality facet
        tracker.complete(collection_name="stale_docs", num_chunks=num_chunks)
        print(f"   ✓ Emitted COMPLETE event with data quality facet")
        print(f"   ✓ Metadata cached for Trust Plane")

    if client.backend_available:
        print(f"   ℹ Events sent to Marquez at {client.url}")
        print(f"   ℹ View in UI: {client.url.replace(':5000', ':3000')}")
    else:
        print(f"   ℹ Events logged to console (Marquez not running)")

    # Test metadata retrieval
    print("\n4. Testing metadata retrieval...")

    # Test cache (should be populated from emit)
    print("\n   a) Local cache lookup:")
    cached_metadata = client.get_dataset_metadata("chromadb", dataset_name)
    if cached_metadata:
        print(f"      ✓ Found in cache")
        print(f"      Source: {cached_metadata.get('source', 'local_cache')}")
        print(f"      Metrics: {cached_metadata['metrics']}")
    else:
        print(f"      ✗ Not in cache")

    # Clear cache to force Marquez API query
    print("\n   b) Marquez API query (cache cleared):")
    client._metadata_cache.clear()

    api_metadata = client.get_dataset_metadata("chromadb", dataset_name)
    if api_metadata:
        print(f"      ✓ Retrieved from Marquez API")
        print(f"      Source: {api_metadata.get('source', 'unknown')}")
        print(f"      Metrics: {api_metadata['metrics']}")
    else:
        if client.backend_available:
            print(f"      ℹ Dataset not found in Marquez")
            print(f"      This is expected if Marquez was just started")
        else:
            print(f"      ℹ Marquez not available, using fallback")

    # Test Trust Plane policy evaluation
    print("\n5. Trust Plane Policy Evaluation:")
    print("   (Simulating Trust Plane query during agent runtime)")

    # In real scenario, this happens in separate process after ingestion
    # For demo without Marquez: manually cache metadata like ingestion would
    if not client.backend_available and not client._metadata_cache:
        from src.observability.lineage.metrics import (
            calculate_data_quality_metrics,
            format_metrics_for_cache
        )
        metrics = calculate_data_quality_metrics(file_paths)
        cache_data = format_metrics_for_cache(metrics)
        client.cache_dataset_metadata("chromadb", dataset_name, cache_data)
        print("   (Metadata re-cached for demo purposes)")

    metadata = client.get_dataset_metadata("chromadb", dataset_name)

    if metadata:
        policy_threshold = 30.0
        max_freshness = metadata['metrics']['max_freshness_days']

        print(f"   Policy: max_freshness_days <= {policy_threshold}")
        print(f"   Actual: {max_freshness:.1f} days")

        if max_freshness > policy_threshold:
            print(f"   ✗ DENY: Data exceeds freshness threshold")
            print(f"   Reason: Stale by {max_freshness - policy_threshold:.1f} days")
        else:
            print(f"   ✓ ALLOW: Data meets quality requirements")
    else:
        print(f"   ℹ No metadata available for policy evaluation")

    # Cleanup
    for file_path in file_paths:
        file_path.unlink()
    file_paths[0].parent.rmdir()

    shutdown_lineage()

    print("\n" + "="*70)
    print("Test Complete")
    print("="*70)

    if client.backend_available:
        print(f"\n📊 View lineage graph in Marquez UI:")
        print(f"   {client.url.replace(':5000', ':3000')}/datasets/chromadb/{dataset_name}")
    else:
        print(f"\n💡 To test with Marquez, start it with:")
        print(f"   docker run -p 3000:3000 -p 5000:5000 marquezproject/marquez")

    print()


def test_fallback_behavior():
    """Test fallback chain: cache → Marquez API → None"""
    print("\n" + "="*70)
    print("Fallback Chain Test")
    print("="*70)

    initialize_lineage(
        enabled=True,
        url="http://localhost:5000",
        namespace="test-fallback"
    )

    client = get_lineage_client()
    if not client:
        print("Client not available")
        return

    dataset_name = "nonexistent.dataset"

    print(f"\n1. Query nonexistent dataset: {dataset_name}")
    print(f"   Cache: empty")
    print(f"   Marquez: {'available' if client.backend_available else 'unavailable'}")

    metadata = client.get_dataset_metadata("chromadb", dataset_name)

    if metadata:
        print(f"   Result: Found (unexpected)")
    else:
        print(f"   Result: None (expected)")
        print(f"   ✓ Fallback chain working correctly")

    shutdown_lineage()

    print("\n" + "="*70)


if __name__ == "__main__":
    test_marquez_api_flow()
    test_fallback_behavior()
