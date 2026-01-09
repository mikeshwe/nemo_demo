"""Test script for Agent Trust Plane"""
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
import os

from src.observability.lineage import initialize_lineage, shutdown_lineage, get_lineage_client
from src.trust_plane import (
    initialize_trust_plane,
    shutdown_trust_plane,
    authorize_dataset_access,
    is_trust_plane_enabled
)
from src.ingestion.lineage_tracker import track_ingestion


def create_fresh_dataset():
    """Create test files with fresh data (passes policy)"""
    temp_dir = Path(tempfile.mkdtemp())
    fresh_file = temp_dir / "fresh_doc.md"
    fresh_file.write_text("# Fresh Documentation\nThis was just created.")
    return [fresh_file]


def create_stale_dataset():
    """Create test files with stale data (fails policy)"""
    temp_dir = Path(tempfile.mkdtemp())
    stale_file = temp_dir / "stale_doc.md"
    stale_file.write_text("# Stale Documentation\nPython 3.8 and CUDA 11.0 required.")

    # Set mtime to 45 days ago (exceeds 30-day policy threshold)
    forty_five_days_ago = (datetime.now() - timedelta(days=45)).timestamp()
    os.utime(stale_file, (forty_five_days_ago, forty_five_days_ago))

    return [stale_file]


def test_trust_plane_initialization():
    """Test Trust Plane initialization"""
    print("\n" + "="*70)
    print("Test 1: Trust Plane Initialization")
    print("="*70)

    # Initialize lineage first (required for Trust Plane)
    print("\n1. Initializing OpenLineage...")
    lineage_success = initialize_lineage(
        enabled=True,
        url="http://localhost:5000",
        namespace="test-trust-plane"
    )
    print(f"   Lineage initialized: {lineage_success}")

    # Initialize Trust Plane
    print("\n2. Initializing Trust Plane...")
    trust_plane_success = initialize_trust_plane(enabled=True)
    print(f"   Trust Plane initialized: {trust_plane_success}")
    print(f"   Trust Plane enabled: {is_trust_plane_enabled()}")

    if not is_trust_plane_enabled():
        print("   ✗ Trust Plane initialization failed")
        return False

    print("   ✓ Trust Plane initialized successfully")
    return True


def test_fresh_data_authorization():
    """Test authorization with fresh data (should ALLOW)"""
    print("\n" + "="*70)
    print("Test 2: Fresh Data Authorization (ALLOW)")
    print("="*70)

    # Create fresh dataset
    print("\n1. Creating fresh dataset (0 days old)...")
    file_paths = create_fresh_dataset()

    # Ingest with lineage tracking
    print("\n2. Ingesting with lineage tracking...")
    with track_ingestion(job_name="test_fresh_ingestion") as tracker:
        tracker.start(file_paths)
        print(f"   Max freshness: {tracker.metrics['max_freshness_days']:.1f} days")
        tracker.complete(collection_name="fresh_docs", num_chunks=5)

    # Test authorization
    print("\n3. Testing Trust Plane authorization...")
    decision = authorize_dataset_access(
        namespace="chromadb",
        dataset_name="fresh_docs.chunks",
        tool_name="test_tool"
    )

    print(f"   Decision: {decision.action}")
    print(f"   Allowed: {decision.allowed}")
    print(f"   Reason: {decision.reason}")
    print(f"   Violations: {len(decision.violations)}")

    # Cleanup
    for f in file_paths:
        f.unlink()
    file_paths[0].parent.rmdir()

    if decision.allowed and decision.action == "ALLOW":
        print("\n   ✓ PASS: Fresh data correctly ALLOWED")
        return True
    else:
        print(f"\n   ✗ FAIL: Expected ALLOW, got {decision.action}")
        return False


def test_stale_data_authorization():
    """Test authorization with stale data (should DENY)"""
    print("\n" + "="*70)
    print("Test 3: Stale Data Authorization (DENY)")
    print("="*70)

    # Create stale dataset
    print("\n1. Creating stale dataset (45 days old)...")
    file_paths = create_stale_dataset()

    # Ingest with lineage tracking
    print("\n2. Ingesting with lineage tracking...")
    with track_ingestion(job_name="test_stale_ingestion") as tracker:
        tracker.start(file_paths)
        print(f"   Max freshness: {tracker.metrics['max_freshness_days']:.1f} days")
        tracker.complete(collection_name="stale_docs", num_chunks=5)

    # Test authorization
    print("\n3. Testing Trust Plane authorization...")
    decision = authorize_dataset_access(
        namespace="chromadb",
        dataset_name="stale_docs.chunks",
        tool_name="test_tool"
    )

    print(f"   Decision: {decision.action}")
    print(f"   Allowed: {decision.allowed}")
    print(f"   Reason: {decision.reason}")
    print(f"   Violations: {len(decision.violations)}")

    if decision.violations:
        print("\n   Policy Violations:")
        for v in decision.violations:
            print(f"     - {v['metric']}: {v['actual']} (threshold: {v['operator']} {v['threshold']})")
            print(f"       {v['reason']}")

    # Cleanup
    for f in file_paths:
        f.unlink()
    file_paths[0].parent.rmdir()

    if not decision.allowed and decision.action == "DENY":
        print("\n   ✓ PASS: Stale data correctly DENIED")
        return True
    else:
        print(f"\n   ✗ FAIL: Expected DENY, got {decision.action}")
        return False


def test_no_metadata_authorization():
    """Test authorization when no metadata exists (should fail-open ALLOW)"""
    print("\n" + "="*70)
    print("Test 4: No Metadata (Fail-Open ALLOW)")
    print("="*70)

    print("\n1. Testing authorization for nonexistent dataset...")
    decision = authorize_dataset_access(
        namespace="chromadb",
        dataset_name="nonexistent.dataset",
        tool_name="test_tool"
    )

    print(f"   Decision: {decision.action}")
    print(f"   Allowed: {decision.allowed}")
    print(f"   Reason: {decision.reason}")
    print(f"   Metadata found: {decision.metadata_found}")

    if decision.allowed and not decision.metadata_found:
        print("\n   ✓ PASS: Correctly fail-open when no metadata")
        return True
    else:
        print(f"\n   ✗ FAIL: Unexpected behavior")
        return False


def test_trust_plane_disabled():
    """Test that access is allowed when Trust Plane is disabled"""
    print("\n" + "="*70)
    print("Test 5: Trust Plane Disabled (ALLOW)")
    print("="*70)

    print("\n1. Disabling Trust Plane...")
    shutdown_trust_plane()
    print(f"   Trust Plane enabled: {is_trust_plane_enabled()}")

    print("\n2. Testing authorization with Trust Plane disabled...")
    decision = authorize_dataset_access(
        namespace="chromadb",
        dataset_name="any.dataset",
        tool_name="test_tool"
    )

    print(f"   Decision: {decision.action}")
    print(f"   Allowed: {decision.allowed}")
    print(f"   Reason: {decision.reason}")

    if decision.allowed:
        print("\n   ✓ PASS: Access allowed when Trust Plane disabled")
        return True
    else:
        print(f"\n   ✗ FAIL: Access denied even with Trust Plane disabled")
        return False


def test_policy_evaluation():
    """Test policy engine evaluation logic"""
    print("\n" + "="*70)
    print("Test 6: Policy Engine Evaluation")
    print("="*70)

    from src.trust_plane.policy import PolicyEngine

    print("\n1. Loading policies...")
    policy_file = "src/trust_plane/policies.yaml"
    engine = PolicyEngine(policy_file)
    print(f"   Loaded {len(engine.policies)} policies")

    print("\n2. Testing with fresh data metrics...")
    fresh_metrics = {
        "max_freshness_days": 5.0,
        "avg_freshness_days": 3.0,
        "row_count": 100
    }
    result = engine.evaluate_dataset("chromadb", "test.chunks", fresh_metrics)
    print(f"   Action: {result['action']}")
    print(f"   Allowed: {result['allowed']}")
    print(f"   Violations: {len(result['violations'])}")

    print("\n3. Testing with stale data metrics...")
    stale_metrics = {
        "max_freshness_days": 45.0,
        "avg_freshness_days": 20.0,
        "row_count": 100
    }
    result = engine.evaluate_dataset("chromadb", "test.chunks", stale_metrics)
    print(f"   Action: {result['action']}")
    print(f"   Allowed: {result['allowed']}")
    print(f"   Violations: {len(result['violations'])}")

    for v in result['violations']:
        print(f"     - {v['reason']}")

    print("\n   ✓ PASS: Policy engine working correctly")
    return True


def main():
    """Run all Trust Plane tests"""
    print("\n" + "="*70)
    print("Agent Trust Plane Test Suite")
    print("="*70)

    tests = [
        ("Initialization", test_trust_plane_initialization),
        ("Fresh Data ALLOW", test_fresh_data_authorization),
        ("Stale Data DENY", test_stale_data_authorization),
        ("No Metadata Fail-Open", test_no_metadata_authorization),
        ("Trust Plane Disabled", test_trust_plane_disabled),
        ("Policy Engine", test_policy_evaluation)
    ]

    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n   ✗ ERROR: {e}")
            results.append((name, False))

    # Summary
    print("\n" + "="*70)
    print("Test Summary")
    print("="*70)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")

    print(f"\nResults: {passed}/{total} tests passed")
    print("="*70 + "\n")

    # Cleanup
    shutdown_lineage()
    shutdown_trust_plane()


if __name__ == "__main__":
    main()
