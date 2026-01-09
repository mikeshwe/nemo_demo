"""Test script for OpenLineage initialization"""
import uuid
from src.observability.lineage import (
    initialize_lineage,
    shutdown_lineage,
    get_lineage_client,
    is_lineage_enabled,
    emit_job_event,
    set_lineage_context,
    get_current_run_id,
    get_current_job_name,
    clear_lineage_context
)

def test_lineage_initialization():
    """Test basic OpenLineage initialization"""
    print("\n" + "="*60)
    print("Testing OpenLineage Initialization")
    print("="*60)

    # Test 1: Initialize with console transport (no Marquez required)
    print("\n1. Initializing OpenLineage...")
    success = initialize_lineage(
        enabled=True,
        url="http://localhost:5000",  # Will fallback to console if not available
        namespace="test-namespace"
    )
    print(f"   Initialization: {'✓ Success' if success else '✗ Failed'}")

    # Test 2: Check if lineage is enabled
    print("\n2. Checking lineage status...")
    enabled = is_lineage_enabled()
    print(f"   Lineage enabled: {enabled}")

    # Test 3: Get client instance
    print("\n3. Getting lineage client...")
    client = get_lineage_client()
    if client:
        print(f"   Client namespace: {client.namespace}")
        print(f"   Backend available: {client.backend_available}")
        print("   ✓ Client retrieved successfully")
    else:
        print("   ✗ Client is None")

    # Test 4: Set lineage context
    print("\n4. Testing lineage context...")
    run_id = str(uuid.uuid4())
    job_name = "test_job"
    set_lineage_context(run_id, job_name)

    retrieved_run_id = get_current_run_id()
    retrieved_job_name = get_current_job_name()

    print(f"   Set run_id: {run_id[:8]}...")
    print(f"   Retrieved run_id: {retrieved_run_id[:8] if retrieved_run_id else None}...")
    print(f"   Set job_name: {job_name}")
    print(f"   Retrieved job_name: {retrieved_job_name}")
    print(f"   Context match: {'✓' if run_id == retrieved_run_id and job_name == retrieved_job_name else '✗'}")

    # Test 5: Emit a test event
    print("\n5. Emitting test OpenLineage event...")
    try:
        emit_job_event(
            job_name="test_ingestion",
            run_id=run_id,
            event_type="START",
            inputs=[{
                "namespace": "filesystem",
                "name": "test_docs",
                "facets": {}
            }],
            outputs=[{
                "namespace": "chromadb",
                "name": "test_collection",
                "facets": {}
            }],
            metadata={"test": True}
        )
        print("   ✓ START event emitted")

        emit_job_event(
            job_name="test_ingestion",
            run_id=run_id,
            event_type="COMPLETE",
            outputs=[{
                "namespace": "chromadb",
                "name": "test_collection",
                "facets": {}
            }]
        )
        print("   ✓ COMPLETE event emitted")
    except Exception as e:
        print(f"   ✗ Error emitting event: {e}")

    # Test 6: Cache and retrieve metadata
    print("\n6. Testing metadata caching...")
    if client:
        test_metadata = {
            "metrics": {
                "avg_freshness_days": 5.2,
                "max_freshness_days": 10,
                "row_count": 100
            }
        }

        client.cache_dataset_metadata("chromadb", "test_collection", test_metadata)
        print("   ✓ Metadata cached")

        retrieved_metadata = client.get_dataset_metadata("chromadb", "test_collection")
        if retrieved_metadata:
            print(f"   ✓ Metadata retrieved: {retrieved_metadata['metrics']}")
        else:
            print("   ✗ Failed to retrieve metadata")

    # Test 7: Clear context
    print("\n7. Clearing lineage context...")
    clear_lineage_context()
    cleared_run_id = get_current_run_id()
    cleared_job_name = get_current_job_name()
    print(f"   Context cleared: {'✓' if cleared_run_id is None and cleared_job_name is None else '✗'}")

    # Test 8: Shutdown
    print("\n8. Shutting down OpenLineage...")
    shutdown_lineage()
    final_enabled = is_lineage_enabled()
    print(f"   Lineage disabled: {'✓' if not final_enabled else '✗'}")

    print("\n" + "="*60)
    print("OpenLineage Test Complete")
    print("="*60 + "\n")


if __name__ == "__main__":
    test_lineage_initialization()
